#!/usr/bin/env python3
"""Compress the baked web GLBs for the /sect page (runs on this PC; needs Node and Pillow).

Two profiles. Both run every file through the glTF Transform 4.5.1 CLI (the npx cache copy is run with node
directly, which saves npx's 13 s start-up per call):

    weld -> [card files: fill the card sprites' transparent texels] -> unlit -> [any texture > 4096 px: resize]
         -> webp (lossy, --quality) -> meshopt (high; positions 16 bit, UVs 14 bit) -> [full profile: post step]
         -> [cards: MASK] -> gzip -9

Post step (full profile, POST_JS, one Node process per file): drops the triangles whose quantised corners coincide
or line up (they can never cover a pixel) and then the vertices nothing uses any more; rounds float UVs (water:
metres, outside 0..1, so meshopt leaves them float) to a power-of-two grid of 2^-UV_BITS of their extent; writes the
vertex streams with meshopt codec version 1 under the name KHR_meshopt_compression (--codec 0: version 0 and
EXT_meshopt_compression, as before); then decodes the file again and checks every accessor is what was meant.
Water primitives keep every triangle (the page splits sheets into pieces by connectivity) and vertex-coloured ones
only lose triangles whose corners all have a colour, keeping every vertex (the page fills black corners from their
neighbours and the mesh median), so the page's repairs come out the same.

The page fetches the .glb.gz and inflates it with DecompressionStream (static hosts such as Vercel do not
compress .glb). Files with textures also get a phone / low-tier copy with every texture at most 2048 px
(low/<name>.glb.gz; 4x less GPU memory), same geometry and nodes. Card materials (name 'trees.cards*') get
alphaMode MASK / cutoff 0.5 and are double-sided; their transparent texels get the colour of the nearest leaves
(push-pull fill), so mipmapping no longer blends near-black into the leaf edges. Needle cards (material name
'trees.needle*') stay OPAQUE in the file: their card texture is the occlusionTexture on TEXCOORD_1, which the page
alpha-tests. extras {cardAlpha: 'needle'}: a greyscale alpha (made greyscale from its R channel, then WebP like every
texture). extras {cardAlpha: 'twig'}: an RGB twig card texture (G coverage, R luminance detail with 0.5 neutral,
bake_trees.py / prep_textures.mjs): R and G are kept apart (B zeroed), box-filtered down to at most TWIG_PACK_PX,
named TWIG_IMAGE and WebP-encoded near-lossless (level TWIG_WEBP_Q) in a pass of its own before the lossy pass (lossy
WebP's 4:2:0 chroma would blur R and G into each other); the checks decode it again (twig_check). Extras
(hotspot, label, glow, glowTint, proxyOf, chunk, water, instances, detail, cardAlpha), TEXCOORD_1 and
EXT_mesh_gpu_instancing pass through untouched.

--profile full  (the whole flight, manifest version 2)

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/sect_pack.py --profile full [--quality 88]
        [--only gate,gate_trees,backdrop] [--workers 4] [--keep-tmp] [--no-install] [--codec 1]
        [--src DIR] [--work DIR]

    Reads out/web/full/raw/: per area <area>.glb (bake_web.py), <area>_trees.glb (bake_trees.py) and
    <area>_water.glb (bake_web.py water; steles and formation have none), plus the always-loaded backdrop.glb,
    backdrop_trees.glb and backdrop_water.glb. Packs them into a staging folder (out/web/full/bake/packtmp/site),
    then CHECKS every packed file with Node (gltf-transform + the Khronos gltf-validator):
      - validator: 0 errors, on the file as shipped and on its decoded geometry written out plain (the validator
        cannot read meshopt streams itself);
      - decoded (meshopt, either codec version) triangle count equals the raw file's less the zero-area triangles
        the post step dropped, instances included; the post step's own decode check passed;
      - every raw node is there with the same extras, and its world-space box (instances included) is within
        quantisation error of the raw one; material extras and occlusion texCoord unchanged; every primitive has
        the UV sets its material's textures read; needle materials OPAQUE with their alpha (occlusion) texture;
      - textures at most 4096 px (low copies 2048 px);
      - every hotspot id in meta.json that names a node exists as a node with extras.hotspot, in its own area's
        chunk; backdrop proxies (extras.proxyOf) for all 11 areas;
      - twig card textures still RGB with R and G apart, G coverage present, R neutral where nothing is covered;
    and reports the budgets (per chunk ~10 MB / 1.5M triangles, global ~7 MB, global + gate ~15 MB, total
    ~125 MB). Only when every check passes are the files installed into client/public/sect/full/:
      <name>.glb.gz, low/<name>.glb.gz, camera.json, meta.json (+ a 'bake' note), clouds.json, flyer.glb,
      flyer.json, sky.webp (copied from out/web/full/site/, the export agent's data files), detail.webp (the
      tiling detail texture from tools/prep_textures.mjs, when present) and manifest.json:
        {"version": 2, "baked": true, "camera", "meta", "clouds", "flyer", "flyerPath", "detail", "water": null,
         "global": ["backdrop.glb.gz", "backdrop_trees.glb.gz", "backdrop_water.glb.gz"], "globalLow": [...],
         "globalBytes", "globalBytesLow", "globalTris", "globalTexBytes", "globalTexBytesLow",
         "chunks": [{"id", "files": [<area>.glb.gz, <area>_trees.glb.gz, <area>_water.glb.gz], "filesLow",
                     "need": [first, last], "bytes", "bytesLow", "tris", "texBytes", "texBytesLow", "core",
                     "need250", "hold"}, ...],
         "fileTexBytes": {<file as listed, low/ copies too>: bytes}}
      need / core / need250 come from out/web/full/chunks.json (export_web.py plan), hold from camera.json.
      texBytes: GPU memory of the file's textures as the page holds them, RGBA8 plus the mip chain (w * h * 4 * 4/3
      per texture, one per image and sampler as GLTFLoader caches them; streaming.ts textureBytes counts the same),
      summed per chunk (texBytesLow: filesLow; null when there is no low list) and per file (fileTexBytes).
    Packed files that are no longer listed (the unbaked stand-ins) are removed. Per-file stats and the check
    results: out/web/full/bake/pack_stats.json. --only re-packs some files and keeps the others' stats.
    --src DIR reads raw/, site/ and chunks.json from DIR instead of out/web/full; --work DIR stages, keeps the work
    files and writes pack_stats.json in DIR instead of out/web/full/bake(/packtmp) (trial packs beside a real one).

--profile proto  (the first test, the default; unchanged)

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/sect_pack.py [--quality 88] [--only gate,trees]

    Reads out/web/raw/{gate,mirror,backdrop,trees,water}.glb and writes client/public/sect/proto/<name>.glb.gz.
    Also merges out/web/water_meta.json (waterfall corners, beams) into meta.json, re-encodes sky.png as a
    1024x512 sky.webp, removes the stand-in GLBs and updates the version 1 manifest ("scene", "sceneLow",
    "sceneDeferred", "water"). Report: out/web/bake/pack_stats.json; copies to out/web/proto/.
"""
import argparse
import concurrent.futures as cf
import glob
import gzip
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time

import numpy as np
from PIL import Image

ROOT = "E:/Github/PortfolioV5/blender/xianxia-sect"
RAW = os.path.join(ROOT, "out", "web", "raw")
PROTO_MIRROR = os.path.join(ROOT, "out", "web", "proto")
CLIENT = "E:/Github/PortfolioV5/client/public/sect/proto"
ORDER = ["gate", "backdrop", "trees", "mirror"]          # load order: the opening view first
DEFERRED = ["mirror"]                                    # may load after the page opens (first needed ~frame 150)
LOW_PX = 2048
MAX_PX = 4096
CLI_VERSION = "4.5.1"

# full profile
FULL = os.path.join(ROOT, "out", "web", "full")
FULL_RAW = os.path.join(FULL, "raw")
FULL_SITE = os.path.join(FULL, "site")                   # the export agent's data files (camera, meta, ...)
FULL_BAKE = os.path.join(FULL, "bake")
FULL_TMP = os.path.join(FULL_BAKE, "packtmp")
FULL_CLIENT = "E:/Github/PortfolioV5/client/public/sect/full"
GLOBAL_NAMES = ["backdrop", "backdrop_trees", "backdrop_water"]
DATA_FILES = ["camera.json", "meta.json", "clouds.json", "flyer.glb", "flyer.json", "sky.webp",
              "detail.webp"]                     # detail.webp: optional (tools/prep_textures.mjs)
# budgets (the brief; raised for the AAA tree pass: chunk 8 -> 10 MB and 1.2M -> 1.5M triangles, global 6 -> 7 MB,
# total 100 -> 125 MB; the opening target unchanged): per chunk, the always-loaded set, the opening download, everything
BUDGET = dict(chunk_bytes=10e6, chunk_tris=1.5e6, global_bytes=7e6, initial_bytes=15e6, total_bytes=125e6,
              max_px=MAX_PX)
# twig card textures (cardAlpha 'twig'): at most this size, near-lossless WebP at this level (0-100, lower = smaller;
# 40 changes a channel by at most 4 levels; 1024 px would be ~3x the bytes for detail only seen within ~5 m)
TWIG_PACK_PX = 512
TWIG_WEBP_Q = 40
TWIG_IMAGE = "twig_card"
# post step: float UVs (water) onto a grid of 2^-UV_BITS of their extent (18: 0.1 mm across a 25 m sheet, 2 mm along
# the 544 m backdrop stream; 4x finer than the 16-bit position grid); meshopt vertex codec (1: KHR_meshopt_compression,
# about 5% smaller after gzip; 0: EXT_meshopt_compression as gltf-transform writes it)
UV_BITS = 18
CODEC = 1


def _find_node_modules():
    """node_modules of a cached npx install of @gltf-transform/cli@CLI_VERSION, or None."""
    bases = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm-cache", "_npx"),
             os.path.join(os.path.expanduser("~"), ".npm", "_npx")]
    for base in bases:
        for pj in sorted(glob.glob(os.path.join(base, "*", "node_modules", "@gltf-transform", "cli", "package.json"))):
            try:
                with open(pj, encoding="utf-8") as fh:
                    if json.load(fh).get("version") == CLI_VERSION:
                        return os.path.dirname(os.path.dirname(os.path.dirname(pj)))
            except (OSError, ValueError):
                continue
    return None


NODE_MODULES = _find_node_modules()
if NODE_MODULES is None and shutil.which("npx"):
    # first use on this PC: let npx install it into its cache once, then run it with node
    subprocess.run("npx --yes @gltf-transform/cli@%s --version" % CLI_VERSION, shell=True, capture_output=True)
    NODE_MODULES = _find_node_modules()
if NODE_MODULES:
    CLI = ["node", os.path.join(NODE_MODULES, "@gltf-transform", "cli", "bin", "cli.js")]
else:
    CLI = ["npx", "--yes", "@gltf-transform/cli@%s" % CLI_VERSION]


def run(args):
    cmd = CLI + args
    if cmd[0] == "npx":
        r = subprocess.run(" ".join('"%s"' % a if " " in a else a for a in cmd), shell=True, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("failed: %s" % " ".join(args[:2]))


def read_glb(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return parse_glb(data)


def parse_glb(data):
    n = struct.unpack("<I", data[12:16])[0]
    j = json.loads(data[20:20 + n])
    rest = data[20 + n:]
    return j, rest


def write_glb(path, j, rest):
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    head = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + len(rest))
    with open(path, "wb") as fh:
        fh.write(head + struct.pack("<II", len(js), 0x4E4F534A) + js + rest)


def patch(path):
    j, rest = read_glb(path)
    changed = 0
    for m in j.get("materials", []):
        if m.get("name", "").startswith("trees.cards"):
            m["alphaMode"] = "MASK"
            m["alphaCutoff"] = 0.5
            m["doubleSided"] = True
            changed += 1
    if changed:
        write_glb(path, j, rest)
    return changed


def json_tris(j):
    """Triangles drawn (instances counted) from a glTF JSON's accessor counts."""
    tris = 0
    for nd in j.get("nodes", []):
        if "mesh" not in nd:
            continue
        cnt = 1
        ext = nd.get("extensions", {}).get("EXT_mesh_gpu_instancing")
        if ext:
            cnt = j["accessors"][ext["attributes"]["TRANSLATION"]]["count"]
        for p in j["meshes"][nd["mesh"]]["primitives"]:
            acc = p.get("indices", p["attributes"]["POSITION"])
            tris += j["accessors"][acc]["count"] // 3 * cnt
    return tris


def stats(path):
    j, rest = read_glb(path)
    tris = prims = inst_nodes = mesh_nodes = instances = 0
    for nd in j.get("nodes", []):
        if "mesh" not in nd:
            continue
        mesh_nodes += 1
        cnt = 1
        ext = nd.get("extensions", {}).get("EXT_mesh_gpu_instancing")
        if ext:
            cnt = j["accessors"][ext["attributes"]["TRANSLATION"]]["count"]
            inst_nodes += 1
            instances += cnt
        for p in j["meshes"][nd["mesh"]]["primitives"]:
            prims += 1
            acc = p.get("indices", p["attributes"]["POSITION"])
            tris += j["accessors"][acc]["count"] // 3 * cnt
    imgs = []
    for im in j.get("images", []):
        bv = j["bufferViews"][im["bufferView"]]
        imgs.append(dict(name=im.get("name"), mime=im.get("mimeType"), bytes=bv["byteLength"],
                         size=image_size(rest, bv)))
    return dict(bytes=os.path.getsize(path), triangles=tris, draw_calls=prims, mesh_nodes=mesh_nodes,
                instanced_nodes=inst_nodes, instances=instances, materials=len(j.get("materials", [])),
                images=imgs, tex_bytes=tex_bytes(j, imgs), extensions=j.get("extensionsUsed", []))


def tex_bytes(j, imgs):
    """GPU memory of a GLB's textures as the page holds them: RGBA8 plus the mip chain (w * h * 4 * 4/3), one texture
    per (image, sampler) pair (GLTFLoader caches them so; the page's streaming.ts textureBytes counts the same way).
    An image whose size cannot be read counts as 4096 x 4096 (as the page does)."""
    seen = set()
    n = 0.0
    for ti, t in enumerate(j.get("textures", [])):
        ii = _texture_source(j, ti)
        if ii is None or (ii, t.get("sampler")) in seen:
            continue
        seen.add((ii, t.get("sampler")))
        size = imgs[ii]["size"] if ii < len(imgs) else None
        n += (size[0] * size[1] if size else 4096 * 4096) * 4 * 4 / 3
    return int(round(n))


def image_size(rest, bv):
    """(w, h) of a WebP/PNG image inside the BIN chunk."""
    off = 8 + bv.get("byteOffset", 0)        # BIN chunk header is 8 bytes
    b = rest[off:off + 64]
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        if b[12:16] == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return [w & 0x3FFF, h & 0x3FFF]
        if b[12:16] == b"VP8L":
            v = struct.unpack("<I", b[21:25])[0]
            return [(v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1]
        if b[12:16] == b"VP8X":
            return [1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return list(struct.unpack(">II", b[16:24]))
    return None


def validate(path):
    """Khronos glTF validator through the CLI: (errors, warnings)."""
    cmd = CLI + ["validate", path]
    r = subprocess.run(" ".join(cmd) if cmd[0] == "npx" else cmd, shell=cmd[0] == "npx", capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    txt = (r.stdout or "") + (r.stderr or "")
    return r.returncode, txt


def write_meta_note(a):
    """Add a 'bake' block to meta.json: how the baked assets are meant to be drawn."""
    mp = os.path.join(CLIENT, "meta.json")
    if not os.path.isfile(mp):
        return
    with open(mp, encoding="utf-8") as fh:
        meta = json.load(fh)
    post = {}
    pp = os.path.join(ROOT, "out", "web", "bake", "post_stats.json")
    if os.path.isfile(pp):
        with open(pp, encoding="utf-8") as fh:
            post = json.load(fh)
    meta["bake"] = dict(
        colour="Baked atlases, tree textures, card sprites and vertex colours are display-referred sRGB "
               "(Blender AgX / AgX - Punchy, exposure %s, look.py CDL grade, saturation %s already applied). "
               "All materials are KHR_materials_unlit: draw with no tone mapping (Canvas flat / NoToneMapping) so "
               "the pixels round-trip exactly." % (post.get("exposure"), post.get("sat")),
        glow="Emissive surfaces are separate primitives, one material per source-material class (mirror face, cyan "
             "and gold runes, jade inlays, lantern panes, flames); material and node extras carry {\"glow\": "
             "strength, \"glowTint\": \"#rrggbb\"} (bake_web.py GLOW_CLASSES). Multiply the colour by the strength "
             "(toward the tint) so only they exceed 1.0 and bloom, and their hue survives.",
        chunks="Plain atlas and backdrop faces are split into spatially compact chunks (extras {\"chunk\": 1}) so "
               "the browser can cull what is off screen: do not merge them back.",
        hotspots="Nodes named 'hotspot.<id>' carry extras {hotspot, label}; click boxes are meta.hotspots.",
        trees="trees.glb: near trees are EXT_mesh_gpu_instancing groups (one InstancedMesh per prototype and "
              "lighting variant) plus small groups merged into 'trees.near.<zone>'; far trees, shrubs and bamboo are "
              "crossed cards merged per zone ('trees.cards.<zone>', alphaMode MASK 0.5, double-sided).",
        notBaked="Haze/fog (meta.fog), the cloud sea and cloud banks (meta.cloudSea, clouds.json), the moon, the "
                 "sky (sky.webp) and the light beams (meta.beams) are not in the scene GLBs: draw them on the web "
                 "side. Waterfall sheets and streams are in water.glb.gz (manifest.water; materials 'water.*', UV u "
                 "across / v along the flow, COLOR_0 = seed, flow); meta.waterfalls also carry their corners.",
        lighting="Cycles bake of the scene's golden-hour sun and sky, sky fill x1.4 warmed plus a soft warm fill sun "
                 "(stand-in for the film's golden haze in-scatter); diffuse + emission only, metals baked as their "
                 "base colour.")
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, ensure_ascii=False)
    if os.path.isdir(PROTO_MIRROR):
        shutil.copy2(mp, os.path.join(PROTO_MIRROR, "meta.json"))


# ---- texture fill for alpha-tested sprites ----------------------------------------------------------

def push_pull_fill(rgba):
    """RGB of the transparent texels from the nearest opaque ones (push-pull: average down a pyramid with
    alpha weights, then fill the holes from the coarser levels). Alpha is unchanged."""
    a = rgba[..., 3:4].astype(np.float64) / 255.0
    w = (a > 0.02).astype(np.float64)
    c = rgba[..., :3].astype(np.float64) * w
    levels = [(c, w)]
    while min(levels[-1][1].shape[:2]) > 1:
        c0, w0 = levels[-1]
        h, wd = c0.shape[:2]
        h2, w2 = (h + 1) // 2, (wd + 1) // 2
        cp = np.zeros((h2 * 2, w2 * 2, 3))
        wp = np.zeros((h2 * 2, w2 * 2, 1))
        cp[:h, :wd] = c0
        wp[:h, :wd] = w0
        levels.append((cp.reshape(h2, 2, w2, 2, 3).sum((1, 3)), wp.reshape(h2, 2, w2, 2, 1).sum((1, 3))))
    col = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)
    for c0, w0 in reversed(levels[:-1]):
        h, wd = c0.shape[:2]
        up = np.repeat(np.repeat(col, 2, 0), 2, 1)[:h, :wd]
        col = np.where(w0 > 0, c0 / np.maximum(w0, 1e-9), up)
    out = rgba.copy()
    hole = rgba[..., 3] < 250
    fill = np.clip(np.round(col), 0, 255).astype(np.uint8)
    out[..., :3] = np.where(hole[..., None], fill, rgba[..., :3])
    return out


def rebuild_glb(j, rest, replace):
    """(json, BIN chunk) with some bufferViews' bytes replaced ({view index: bytes}); views re-laid out."""
    bin_len = struct.unpack("<I", rest[:4])[0]
    data = rest[8:8 + bin_len]
    out = bytearray()
    for k, bv in enumerate(j["bufferViews"]):
        b = replace.get(k)
        if b is None:
            off = bv.get("byteOffset", 0)
            b = data[off:off + bv["byteLength"]]
        while len(out) % 4:
            out += b"\0"
        bv["byteOffset"] = len(out)
        bv["byteLength"] = len(b)
        out += b
    while len(out) % 4:
        out += b"\0"
    j["buffers"][0]["byteLength"] = len(out)
    return j, struct.pack("<II", len(out), 0x004E4942) + bytes(out)


def _texture_source(j, ti):
    """Image index of texture ti (core source, else an EXT/KHR texture extension's)."""
    t = j["textures"][ti]
    if t.get("source") is not None:
        return t["source"]
    for e in (t.get("extensions") or {}).values():
        if isinstance(e, dict) and e.get("source") is not None:
            return e["source"]
    return None


def twig_images(j):
    """Image indices of the twig card textures (occlusionTexture of materials with extras cardAlpha 'twig')."""
    out = set()
    for m in j.get("materials", []):
        t = m.get("occlusionTexture")
        if (m.get("extras") or {}).get("cardAlpha") == "twig" and isinstance(t, dict) and "index" in t:
            ii = _texture_source(j, t["index"])
            if ii is not None:
                out.add(ii)
    return out


def _image_bytes(j, rest, ii):
    bv = j["bufferViews"][j["images"][ii]["bufferView"]]
    off = 8 + bv.get("byteOffset", 0)
    return rest[off:off + bv["byteLength"]]


def twig_check(path, label):
    """Stats and problems of the twig card textures of a packed GLB (decoded with Pillow): RGB(A) with R and G apart,
    G coverage present, R neutral (0.5) where nothing is covered, at most TWIG_PACK_PX. (stats list, problems list)"""
    j, rest = read_glb(path)
    stats_, probs = [], []
    for ii in sorted(twig_images(j)):
        im = j["images"][ii]
        try:
            img = Image.open(io.BytesIO(_image_bytes(j, rest, ii)))
            img.load()
        except Exception as e:                       # noqa: BLE001 (any decoder failure is a problem to report)
            probs.append("%s: twig texture %s does not decode: %s" % (label, im.get("name"), e))
            continue
        a = np.asarray(img.convert("RGB")).astype(np.float64)
        g = a[..., 1]
        empty = g < 1
        s = dict(name=im.get("name"), mime=im.get("mimeType"), mode=img.mode, size=list(img.size),
                 bytes=len(_image_bytes(j, rest, ii)), coverage=round(float((g > 102).mean()), 3),
                 rg_diff=round(float(np.abs(a[..., 0] - g).mean()), 1),
                 r_empty=round(float(a[..., 0][empty].mean()), 1) if empty.any() else None)
        stats_.append(s)
        bad = []
        if img.mode not in ("RGB", "RGBA"):
            bad.append("mode %s" % img.mode)
        if max(img.size) > TWIG_PACK_PX:
            bad.append("%s px" % max(img.size))
        if not 0.02 < s["coverage"] < 0.8:
            bad.append("coverage %s" % s["coverage"])
        if s["rg_diff"] < 10:
            bad.append("R and G alike (mean |R - G| %s)" % s["rg_diff"])
        if s["r_empty"] is not None and abs(s["r_empty"] - 128) > 12:
            bad.append("R %s where nothing is covered (neutral 128)" % s["r_empty"])
        if bad:
            probs.append("%s: twig texture %s: %s" % (label, im.get("name"), ", ".join(bad)))
    return stats_, probs


def _twig_png(img):
    """Twig card texture -> PNG bytes: R and G kept, B zeroed, box-filtered down (powers of two) to <= TWIG_PACK_PX."""
    arr = np.asarray(img.convert("RGB")).astype(np.float64)
    while max(arr.shape[:2]) > TWIG_PACK_PX and arr.shape[0] % 2 == 0 and arr.shape[1] % 2 == 0:
        h, w = arr.shape[:2]
        arr = arr.reshape(h // 2, 2, w // 2, 2, 3).mean((1, 3))
    out = np.clip(np.round(arr), 0, 255).astype(np.uint8)
    out[..., 2] = 0
    im = Image.fromarray(out, "RGB")
    if max(im.size) > TWIG_PACK_PX:                 # odd sizes: a plain box resize
        f = TWIG_PACK_PX / float(max(im.size))
        im = im.resize((max(1, round(im.size[0] * f)), max(1, round(im.size[1] * f))), Image.BOX)
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=6)
    return buf.getvalue(), im.size


def fill_card_textures(src, dst, log=print):
    """Push-pull fill on the RGB of every image used by a 'trees.cards*' material. Needle alpha images (the
    occlusionTexture of 'trees.needle*' materials with extras cardAlpha 'needle', used by nothing else) become
    greyscale copies of their R channel (the glTF occlusion channel), so the page reads the same alpha from any
    channel. Twig card textures (cardAlpha 'twig') keep R and G (never greyscale): _twig_png, named TWIG_IMAGE."""
    j, rest = read_glb(src)
    tex_imgs = set()
    alpha_imgs, other_imgs = set(), set()
    twig = twig_images(j)
    for m in j.get("materials", []):
        if m.get("name", "").startswith("trees.cards"):
            t = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if t is not None:
                tex_imgs.add(j["textures"][t["index"]]["source"])
        needle = m.get("name", "").startswith("trees.needle")
        for slot, t in [(k, m.get(k)) for k in ("occlusionTexture", "normalTexture", "emissiveTexture")] + list(
                m.get("pbrMetallicRoughness", {}).items()):
            if isinstance(t, dict) and "index" in t:
                ii = j["textures"][t["index"]].get("source")
                (alpha_imgs if needle and slot == "occlusionTexture" else other_imgs).add(ii)
    bin_len = struct.unpack("<I", rest[:4])[0]
    data = rest[8:8 + bin_len]
    repl = {}
    for ii in sorted(i for i in twig - other_imgs if i is not None):
        im = j["images"][ii]
        bv = j["bufferViews"][im["bufferView"]]
        off = bv.get("byteOffset", 0)
        img = Image.open(io.BytesIO(data[off:off + bv["byteLength"]]))
        size0, mode0 = img.size, img.mode
        if mode0 not in ("RGB", "RGBA"):
            log("  WARN twig card texture %s is %s: its R and G are gone (re-run bake_trees.py with "
                "assets/web/twig_card.png)" % (im.get("name"), mode0))
        repl[im["bufferView"]], size = _twig_png(img)
        im["mimeType"] = "image/png"
        im["name"] = TWIG_IMAGE
        log("  twig card texture %s %s (%s) -> %s: R and G kept, B zeroed" % (TWIG_IMAGE, size0, mode0, size))
    for ii in sorted(i for i in alpha_imgs - other_imgs - twig if i is not None):
        im = j["images"][ii]
        bv = j["bufferViews"][im["bufferView"]]
        off = bv.get("byteOffset", 0)
        img = Image.open(io.BytesIO(data[off:off + bv["byteLength"]]))
        if img.mode == "L":
            continue
        rgb = np.asarray(img.convert("RGB")).astype(np.int16)
        spread = int(np.abs(rgb[..., 1:] - rgb[..., :1]).max())
        buf = io.BytesIO()
        Image.fromarray(rgb[..., 0].astype(np.uint8), "L").save(buf, "PNG", compress_level=6)
        repl[im["bufferView"]] = buf.getvalue()
        im["mimeType"] = "image/png"
        log("  needle alpha %s %s (%s): R channel kept as greyscale (G/B differed from R by up to %d)"
            % (im.get("name"), img.size, img.mode, spread))
    for ii in sorted(tex_imgs):
        im = j["images"][ii]
        bv = j["bufferViews"][im["bufferView"]]
        off = bv.get("byteOffset", 0)
        img = Image.open(io.BytesIO(data[off:off + bv["byteLength"]])).convert("RGBA")
        arr = np.asarray(img).copy()
        tr = arr[..., 3] < 128
        before = arr[tr][:, :3].mean(0).round(1).tolist() if tr.any() else None
        arr = push_pull_fill(arr)
        after = arr[tr][:, :3].mean(0).round(1).tolist() if tr.any() else None
        buf = io.BytesIO()
        Image.fromarray(arr, "RGBA").save(buf, "PNG", compress_level=6)
        repl[im["bufferView"]] = buf.getvalue()
        im["mimeType"] = "image/png"
        log("  filled card texture %s %s transparent texels' mean RGB %s -> %s" % (im.get("name"), img.size, before,
                                                                                  after))
    if repl:
        j, rest = rebuild_glb(j, rest, repl)
    write_glb(dst, j, rest)
    return len(repl)


def has_images(path):
    j, _ = read_glb(path)
    return len(j.get("images", [])) > 0


def max_image_px(path):
    j, rest = read_glb(path)
    px = 0
    for im in j.get("images", []):
        s = image_size(rest, j["bufferViews"][im["bufferView"]])
        if s:
            px = max(px, s[0], s[1])
    return px


def gz(src, dst):
    with open(src, "rb") as fh:
        raw = fh.read()
    with open(dst, "wb") as fh:
        fh.write(gzip.compress(raw, compresslevel=9, mtime=0))
    return os.path.getsize(dst)


def gunzip_bytes(path):
    with open(path, "rb") as fh:
        b = fh.read()
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


def merge_water_meta(meta):
    """meta.waterfalls get corners / lip / foot / local size from out/web/water_meta.json; meta.beams = beams."""
    wp = os.path.join(ROOT, "out", "web", "water_meta.json")
    if not os.path.isfile(wp):
        return 0
    with open(wp, encoding="utf-8") as fh:
        wm = json.load(fh)
    by = {f["name"]: f for f in wm.get("falls", [])}
    n = 0
    for w in meta.get("waterfalls", []):
        f = by.get(w.get("name"))
        if f is None:
            continue
        w["corners"] = f["corners"]
        w["lip"] = f["lip"]
        w["foot"] = f["foot"]
        w["flow"] = f.get("flow", 1.0)
        if "worldSize" not in w:
            w["worldSize"] = w.get("size")
        w["size"] = f["sizeLocal"]
        n += 1
    meta["beams"] = wm.get("beams", [])
    return n


def sky_webp(meta):
    """sky.png (2048x1024 lossless RGBA) -> sky.webp (1024x512, q85): the shader shows it at a quarter
    strength under haze, so the lossless copy only cost 2 MB of download."""
    png = os.path.join(CLIENT, "sky.png")
    src = png if os.path.isfile(png) else os.path.join(PROTO_MIRROR, "sky.png")
    if not os.path.isfile(src):
        return None
    out = os.path.join(CLIENT, "sky.webp")
    Image.open(src).convert("RGB").resize((1024, 512), Image.LANCZOS).save(out, "WEBP", quality=85, method=6)
    meta.setdefault("sky", {})["texture"] = "sky.webp"
    if os.path.isfile(png):
        os.remove(png)
    return os.path.getsize(out)


def is_card_file(n):
    return n == "trees" or n.endswith("_trees")


def pack_one(n, src, tmp, quality, low):
    """raw GLB -> packed GLB (uncompressed, for stats) + its .glb.gz in the client folder. low: textures <= LOW_PX."""
    tag = n + (".low" if low else "")
    t0, t1, t2, t3, t4 = (os.path.join(tmp, "%s.%d.glb" % (tag, k)) for k in range(5))
    run(["weld", src, t1])
    if is_card_file(n):
        fill_card_textures(t1, t0)
        t1 = t0
    run(["unlit", t1, t2])
    if low:
        run(["resize", t2, t4, "--width", str(LOW_PX), "--height", str(LOW_PX)])
        t2 = t4
    run(["webp", t2, t3, "--quality", str(quality)])
    out = os.path.join(tmp, tag + ".packed.glb")
    run(["meshopt", t3, out, "--level", "high", "--quantize-position", "16", "--quantize-texcoord", "14"])
    patch(out)
    rel = ("low/" if low else "") + n + ".glb.gz"
    dst = os.path.join(CLIENT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    gz_bytes = gz(out, dst)
    return out, rel, gz_bytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="proto", choices=["proto", "full"],
                    help="proto: the first test (out/web/raw -> public/sect/proto, manifest v1); full: all 11 areas "
                         "(out/web/full/raw -> public/sect/full, manifest v2)")
    ap.add_argument("--quality", type=int, default=None, help="WebP quality (proto 88, full 82)")
    ap.add_argument("--simplify-px", type=float, default=0.5,
                    help="full: area files are simplified up to this many pixels of error (0 = off)")
    ap.add_argument("--simplify-ref", type=int, default=1080, help="full: ... at this many lines of screen height")
    ap.add_argument("--simplify-min", type=int, default=1000, help="full: primitives under this many triangles stay")
    ap.add_argument("--only", default="")
    ap.add_argument("--keep-tmp", action="store_true")
    ap.add_argument("--out", default="", help="output folder (default: the client's public/sect/proto or full)")
    ap.add_argument("--no-manifest", action="store_true", help="proto: do not touch manifest.json (trial runs)")
    ap.add_argument("--workers", type=int, default=4, help="full: files packed at once")
    ap.add_argument("--no-install", action="store_true",
                    help="full: pack and check into the staging folder only; leave the client folder alone")
    ap.add_argument("--check-only", action="store_true",
                    help="full: re-run the checks and the manifest on the staged files (no packing)")
    ap.add_argument("--codec", type=int, default=CODEC, choices=[0, 1],
                    help="full: meshopt vertex codec (1: KHR_meshopt_compression; 0: EXT_meshopt_compression, version 0)")
    ap.add_argument("--src", default="", help="full: read raw/, site/ and chunks.json from this folder "
                                              "(default out/web/full)")
    ap.add_argument("--work", default="", help="full: staging and work folder, and pack_stats.json, here "
                                               "(default out/web/full/bake/packtmp; for trial packs beside a real one)")
    a = ap.parse_args()
    if a.quality is None:
        a.quality = 82 if a.profile == "full" else 88
    if a.profile == "full":
        return main_full(a)
    return main_proto(a)


def main_proto(a):
    global CLIENT
    CLIENT = a.out or CLIENT
    names = [n for n in ORDER + ["water"] if os.path.isfile(os.path.join(RAW, n + ".glb"))]
    if a.only:
        names = [n for n in names if n in a.only.split(",")]
    tmp = os.path.join(ROOT, "out", "web", "packtmp")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(CLIENT, exist_ok=True)
    report = {}
    for n in names:
        src = os.path.join(RAW, n + ".glb")
        out, rel, gzb = pack_one(n, src, tmp, a.quality, low=False)
        rc, vtxt = validate(out)
        vsum = [l.strip() for l in vtxt.splitlines() if any(k in l.lower() for k in ("error", "warning"))][:6]
        r = report[n] = dict(file=rel, raw_bytes=os.path.getsize(src), **stats(out), gz_bytes=gzb,
                             validator=dict(exit=rc, summary=vsum))
        low_rel = rel
        if has_images(out):
            lout, low_rel, lgz = pack_one(n, src, tmp, a.quality, low=True)
            ls = stats(lout)
            r["low"] = dict(file=low_rel, gz_bytes=lgz, images=ls["images"])
        r["low_file"] = low_rel
        print("  validate", n, "exit", rc, vsum[:4])
        print("%-10s %6.2f MB gz (%6.2f MB packed, raw %6.1f MB)  %8d tris  %3d draws  images %s%s"
              % (n, gzb / 1e6, r["bytes"] / 1e6, r["raw_bytes"] / 1e6, r["triangles"], r["draw_calls"],
                 ", ".join("%s %s %.2fMB" % (i["name"], i["size"], i["bytes"] / 1e6) for i in r["images"]),
                 ("  | low %.2f MB gz" % (r["low"]["gz_bytes"] / 1e6)) if "low" in r else ""))
        # the plain .glb is no longer served
        for stale in (os.path.join(CLIENT, n + ".glb"),):
            if os.path.isfile(stale):
                os.remove(stale)
    if not a.keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    if a.no_manifest:
        return
    # stand-in GLBs are not served by the baked page (they stay in out/web/proto)
    for f in ("scene_unbaked.glb", "backdrop_unbaked.glb"):
        p = os.path.join(CLIENT, f)
        if os.path.isfile(p):
            os.remove(p)
    # manifest
    mp = os.path.join(CLIENT, "manifest.json")
    man = {}
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8") as fh:
            man = json.load(fh)
    present = [n for n in ORDER if os.path.isfile(os.path.join(CLIENT, n + ".glb.gz"))]
    man["scene"] = [n + ".glb.gz" for n in present]
    low = []
    for n in present:
        lp = "low/%s.glb.gz" % n
        low.append(lp if os.path.isfile(os.path.join(CLIENT, lp)) else n + ".glb.gz")
    man["sceneLow"] = low
    man["sceneDeferred"] = [n + ".glb.gz" for n in DEFERRED if n in present]
    if os.path.isfile(os.path.join(CLIENT, "water.glb.gz")):
        man["water"] = "water.glb.gz"
    man.setdefault("camera", "camera.json")
    man.setdefault("meta", "meta.json")
    man.setdefault("flyer", "flyer.glb")
    man.setdefault("flyerPath", "flyer.json")
    man["baked"] = True
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    write_meta_note(a)
    # meta: waterfall corners and beams, sky.webp
    metap = os.path.join(CLIENT, "meta.json")
    with open(metap, encoding="utf-8") as fh:
        meta = json.load(fh)
    nfalls = merge_water_meta(meta)
    sky_bytes = sky_webp(meta)
    with open(metap, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, ensure_ascii=False)
    print("meta: %d waterfalls with corners, %d beams, sky.webp %s bytes" % (nfalls, len(meta.get("beams", [])),
                                                                           sky_bytes))
    # mirror into out/web/proto
    if os.path.isdir(PROTO_MIRROR):
        for f in ["manifest.json", "meta.json", "sky.webp"] + man["scene"] + man["sceneLow"] + (
                [man["water"]] if man.get("water") else []):
            s_ = os.path.join(CLIENT, f)
            if os.path.isfile(s_):
                d_ = os.path.join(PROTO_MIRROR, f)
                os.makedirs(os.path.dirname(d_), exist_ok=True)
                shutil.copy2(s_, d_)
    tot = dict(gz_bytes=0, triangles=0, draw_calls=0)
    for n in present:
        r = report.get(n)
        if r is None:
            continue
        tot["gz_bytes"] += r["gz_bytes"]
        tot["triangles"] += r["triangles"]
        tot["draw_calls"] += r["draw_calls"]
    extra = 0
    for f in ("camera.json", "meta.json", "manifest.json", "sky.webp", "clouds.json", "water.glb.gz"):
        p = os.path.join(CLIENT, f)
        if os.path.isfile(p):
            extra += os.path.getsize(p)
    tot["bytes_with_data_files"] = tot["gz_bytes"] + extra
    print("TOTAL scene %.2f MB gz (+data, sky, water %.2f MB), %d triangles, %d draw calls"
          % (tot["gz_bytes"] / 1e6, extra / 1e6, tot["triangles"], tot["draw_calls"]))
    with open(os.path.join(ROOT, "out", "web", "bake", "pack_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(files=report, total=tot, manifest=man, quality=a.quality), fh, indent=1)


# ==== full profile: the whole flight, manifest v2 =====================================================

def _log(*a):
    print(*a, flush=True)


def full_plan():
    """(areas in flight order with need/core/need250, holds by id) from chunks.json and camera.json."""
    with open(os.path.join(FULL, "chunks.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    with open(os.path.join(FULL_SITE, "camera.json"), encoding="utf-8") as fh:
        cam = json.load(fh)
    holds = {h["id"]: h["frame"] for h in cam.get("holds", [])}
    areas = []
    for c in plan["chunks"]:
        areas.append(dict(id=c["id"], need=list(c["need"]), core=list(c.get("core") or c["need"]),
                          need250=list(c.get("need250") or c["need"]), hold=holds.get(c["id"], c.get("hold"))))
    return areas


def full_names(areas):
    """Every raw file name (no extension) the page uses, globals first, then per area: area, trees, water."""
    names = [n for n in GLOBAL_NAMES if os.path.isfile(os.path.join(FULL_RAW, n + ".glb"))]
    for ar in areas:
        for suf in ("", "_trees", "_water"):
            n = ar["id"] + suf
            if os.path.isfile(os.path.join(FULL_RAW, n + ".glb")):
                names.append(n)
    return names


def round_vertex_colors(src, dst):
    """Float COLOR_0 rounded to the 8-bit levels meshopt stores anyway (k / 255), so the weld can merge corners
    whose colours only differed below 8 bits (the backdrop's per-corner baked colours: 1.24M -> 0.90M vertices).
    The packed colours are bit-identical to an unrounded pack. Returns the number of vertices rounded (0: dst not
    written)."""
    j, rest = read_glb(src)
    bin_len = struct.unpack("<I", rest[:4])[0]
    data = bytearray(rest[8:8 + bin_len])
    done, n = set(), 0
    for m in j.get("meshes", []):
        for p in m["primitives"]:
            ai = p["attributes"].get("COLOR_0")
            if ai is None or ai in done:
                continue
            done.add(ai)
            acc = j["accessors"][ai]
            if acc["componentType"] != 5126 or "bufferView" not in acc:
                continue
            k = {"VEC3": 3, "VEC4": 4}[acc["type"]]
            bv = j["bufferViews"][acc["bufferView"]]
            if bv.get("byteStride", 4 * k) != 4 * k:
                continue
            off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            arr = np.frombuffer(bytes(data[off:off + acc["count"] * k * 4]), dtype=np.float32)
            q = (np.round(np.clip(arr, 0.0, 1.0) * 255.0) / 255.0).astype(np.float32)
            data[off:off + q.nbytes] = q.tobytes()
            n += acc["count"]
    if n:
        write_glb(dst, j, rest[:8] + bytes(data) + rest[8 + bin_len:])
    return n


# Sub-pixel simplification of the area files: every mesh primitive (>= --simplify-min triangles) is simplified
# with meshoptimizer (borders locked, UV seams kept) only as far as its nearest approach to the camera path
# allows: the error stays under --simplify-px pixels at --simplify-ref lines, using each frame's own fovY.
# Content items (hotspots 'kind:n', 'resume'), glowing pieces (runes, glyph text) and instanced meshes are left
# exactly as baked. Writes <out> and a JSON summary.
SIMPLIFY_JS = r"""
'use strict';
const path = require('path'); const fs = require('fs'); const { pathToFileURL } = require('url');
const [NM, CAM, PX, REFH, MINT, IN, OUT, SUM] = process.argv.slice(2);
const req = require('module').createRequire(path.join(NM, '_.js'));
const core = req('@gltf-transform/core'); const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const fn = req('@gltf-transform/functions');
function hotspotOf(node) {
  for (let n = node; n; n = n.getParentNode()) { const x = n.getExtras(); if (x && x.hotspot) return x.hotspot; }
  return null;
}
(async () => {
  const mo = await import(pathToFileURL(req.resolve('meshoptimizer')).href);
  await mo.MeshoptSimplifier.ready;
  const cam = JSON.parse(fs.readFileSync(CAM, 'utf8'));
  const F = cam.frames.map((f) => [f.p, 2 * Math.tan((f.fovY * Math.PI / 180) / 2) / Number(REFH)]);
  const io = new core.NodeIO().registerExtensions(ALL_EXTENSIONS);
  const doc = await io.read(IN);
  const buffer = doc.getRoot().listBuffers()[0];
  const s = { before: 0, after: 0, simplified: 0, keptItem: 0, keptGlow: 0, keptSmall: 0, keptNear: 0, maxErrorM: 0 };
  const seen = new Set();
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh(); if (!mesh) continue;
    if (node.getExtension('EXT_mesh_gpu_instancing')) continue;
    const W = node.getWorldMatrix();
    const hs = hotspotOf(node);
    const item = !!hs && (hs.includes(':') || hs === 'resume');
    const sc = Math.max(Math.hypot(W[0], W[1], W[2]), Math.hypot(W[4], W[5], W[6]), Math.hypot(W[8], W[9], W[10]));
    for (const prim of mesh.listPrimitives()) {
      if (seen.has(prim)) continue; seen.add(prim);
      const idx = prim.getIndices(); const pos = prim.getAttribute('POSITION');
      if (!idx || !pos || prim.getMode() !== 4) continue;
      const t0 = idx.getCount() / 3; s.before += t0;
      const mat = prim.getMaterial();
      const glow = !!(mat && mat.getExtras() && mat.getExtras().glow);
      if (item) { s.keptItem += t0; s.after += t0; continue; }
      if (glow) { s.keptGlow += t0; s.after += t0; continue; }
      if (t0 < Number(MINT) || !(pos.getArray() instanceof Float32Array) || pos.getNormalized()) { s.keptSmall += t0; s.after += t0; continue; }
      const lo = pos.getMinNormalized([0, 0, 0]), hi = pos.getMaxNormalized([0, 0, 0]);
      const wl = [Infinity, Infinity, Infinity], wh = [-Infinity, -Infinity, -Infinity];
      for (let i = 0; i < 8; i++) {
        const p = [i & 1 ? hi[0] : lo[0], i & 2 ? hi[1] : lo[1], i & 4 ? hi[2] : lo[2]];
        for (let r = 0; r < 3; r++) {
          const v = W[r] * p[0] + W[4 + r] * p[1] + W[8 + r] * p[2] + W[12 + r];
          wl[r] = Math.min(wl[r], v); wh[r] = Math.max(wh[r], v);
        }
      }
      let eAbs = Infinity;
      for (const [p, mpp] of F) {
        const dx = Math.max(wl[0] - p[0], 0, p[0] - wh[0]), dy = Math.max(wl[1] - p[1], 0, p[1] - wh[1]), dz = Math.max(wl[2] - p[2], 0, p[2] - wh[2]);
        const e = Number(PX) * Math.max(Math.hypot(dx, dy, dz), 0.5) * mpp;
        if (e < eAbs) eAbs = e;
      }
      const ext = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) * sc;
      if (eAbs < 2e-4 * ext) { s.keptNear += t0; s.after += t0; continue; }
      const [dst] = mo.MeshoptSimplifier.simplify(Uint32Array.from(idx.getArray()), pos.getArray(), 3, 0, eAbs / sc, ['LockBorder', 'ErrorAbsolute']);
      if (dst.length < 3 || dst.length >= idx.getCount()) { s.after += t0; continue; }
      prim.setIndices(doc.createAccessor().setType('SCALAR').setArray(dst).setBuffer(buffer));
      if (!idx.listParents().some((x) => x.propertyType === 'Primitive')) idx.dispose();
      fn.compactPrimitive(prim);
      s.after += dst.length / 3; s.simplified++; s.maxErrorM = Math.max(s.maxErrorM, eAbs);
    }
  }
  await doc.transform(fn.prune({ propertyTypes: ['Accessor'], keepAttributes: true, keepIndices: true, keepLeaves: true, keepExtras: true }));
  await io.write(OUT, doc);
  fs.writeFileSync(SUM, JSON.stringify(s));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def simplify_file(src, dst, px, ref_h, min_tris, tmp):
    """Runs SIMPLIFY_JS on one GLB; returns its summary."""
    js = os.path.join(tmp, "sect_pack_simplify.cjs")
    if not os.path.isfile(js) or open(js, encoding="utf-8").read() != SIMPLIFY_JS:
        with open(js + ".%d" % os.getpid(), "w", encoding="utf-8") as fh:
            fh.write(SIMPLIFY_JS)
        os.replace(js + ".%d" % os.getpid(), js)
    sp = dst + ".json"
    r = subprocess.run(["node", "--max-old-space-size=8192", js, NODE_MODULES, os.path.join(FULL_SITE, "camera.json"),
                        str(px), str(ref_h), str(min_tris), src, dst, sp], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("simplify failed: %s" % src)
    with open(sp, encoding="utf-8") as fh:
        s = json.load(fh)
    os.remove(sp)
    return s


# Post step on one meshopt-packed GLB (quantised, EXT_meshopt_compression codec 0, as the CLI writes it): drops
# zero-area triangles and the vertices left unused, rounds float UVs, writes the vertex streams with codec CODEC
# (1: renamed KHR_meshopt_compression), decodes the result and checks every accessor (see the module docstring).
# Writes <out> and a JSON summary; exits 2 when the decode check fails.
POST_JS = r"""
'use strict';
const path = require('path'); const fs = require('fs'); const { pathToFileURL } = require('url');
const [NM, IN, OUT, SUM, OPTS] = process.argv.slice(2);
const req = require('module').createRequire(path.join(NM, '_.js'));
const core = req('@gltf-transform/core'); const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const EXT = 'EXT_meshopt_compression', KHR = 'KHR_meshopt_compression';
const opt = Object.assign({ codec: 1, uvBits: 18 }, JSON.parse(OPTS));
// the extension renamed in the JSON chunk (the two names are the same JSON); the binary chunk is untouched
function renameMeshopt(bytes, from, to) {
  const b = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const jlen = b.readUInt32LE(12);
  const json = JSON.parse(b.subarray(20, 20 + jlen).toString('utf8'));
  const ren = (list) => (list ? list.map((x) => (x === from ? to : x)) : list);
  json.extensionsUsed = ren(json.extensionsUsed);
  if (json.extensionsRequired) json.extensionsRequired = ren(json.extensionsRequired);
  for (const o of [...(json.bufferViews || []), ...(json.buffers || [])]) {
    if (o.extensions && o.extensions[from]) { o.extensions[to] = o.extensions[from]; delete o.extensions[from]; }
  }
  let js = Buffer.from(JSON.stringify(json), 'utf8');
  if (js.length % 4) js = Buffer.concat([js, Buffer.alloc(4 - (js.length % 4), 0x20)]);
  const rest = b.subarray(20 + jlen);
  const head = Buffer.alloc(20);
  head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(20 + js.length + rest.length, 8);
  head.writeUInt32LE(js.length, 12); head.writeUInt32LE(0x4e4f534a, 16);
  return Buffer.concat([head, js, rest]);
}
function drawnTris(doc) {
  let t = 0;
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh(); if (!mesh) continue;
    const inst = node.getExtension('EXT_mesh_gpu_instancing');
    const a = inst && inst.listAttributes()[0];
    const cnt = a ? a.getCount() : 1;
    for (const p of mesh.listPrimitives()) {
      if (p.getMode() !== 4) continue;
      const i = p.getIndices(); t += Math.floor((i ? i.getCount() : p.getAttribute('POSITION').getCount()) / 3) * cnt;
    }
  }
  return t;
}
const prims = (doc) => doc.getRoot().listMeshes().flatMap((m) => m.listPrimitives());
const isWater = (p) => { const m = p.getMaterial(); return !!m && /^water/i.test(m.getName() || ''); };
// corners whose colour the page treats as unset (lib/sect/vertex-colors.ts: every channel <= 1.5/255)
function missingColors(col) {
  const n = col.getCount(); const out = new Uint8Array(n); const e = [0, 0, 0, 0];
  for (let v = 0; v < n; v++) {
    col.getElement(v, e);
    if (e[0] <= 1.5 / 255 && e[1] <= 1.5 / 255 && e[2] <= 1.5 / 255) out[v] = 1;
  }
  return out;
}
function dropDegenerate(doc, s) {
  const byIdx = new Map();
  for (const p of prims(doc)) {
    const idx = p.getIndices(); if (!idx) continue;
    if (!byIdx.has(idx)) byIdx.set(idx, []);
    byIdx.get(idx).push(p);
  }
  for (const [idx, ps] of byIdx) {
    if (ps.some((p) => p.getMode() !== 4 || !p.getAttribute('POSITION') || p.listTargets().length)) continue;
    const a = idx.getArray(); const nt = Math.floor(a.length / 3);
    // a triangle goes only when it is degenerate in every primitive that shares these indices
    const keep = new Uint8Array(nt);
    for (const p of ps) {
      const pos = p.getAttribute('POSITION'); const P = pos.getArray(); const es = pos.getElementSize();
      const col = p.getAttribute('COLOR_0'); const miss = col ? missingColors(col) : null;
      for (let t = 0; t < nt; t++) {
        if (keep[t]) continue;
        const i0 = a[t * 3], i1 = a[t * 3 + 1], i2 = a[t * 3 + 2];
        let degen = i0 === i1 || i1 === i2 || i0 === i2;
        if (!degen) {
          const o0 = i0 * es, o1 = i1 * es, o2 = i2 * es;
          const ux = P[o1] - P[o0], uy = P[o1 + 1] - P[o0 + 1], uz = P[o1 + 2] - P[o0 + 2];
          const vx = P[o2] - P[o0], vy = P[o2 + 1] - P[o0 + 1], vz = P[o2 + 2] - P[o0 + 2];
          // exact on the stored 16-bit integers (products < 2^33); float positions: exact zeros only
          degen = uy * vz - uz * vy === 0 && uz * vx - ux * vz === 0 && ux * vy - uy * vx === 0;
        }
        if (degen && miss && (miss[i0] || miss[i1] || miss[i2])) { degen = false; s.vcKept++; }
        if (!degen) keep[t] = 1;
      }
    }
    let kept = 0;
    for (let t = 0; t < nt; t++) kept += keep[t];
    const cls = ps.some(isWater) ? 'water' : ps.some((p) => p.getAttribute('COLOR_0')) ? 'vc' : 'plain';
    s.degenerate[cls] = (s.degenerate[cls] || 0) + nt - kept;
    if (kept === nt || cls === 'water') continue;
    if (kept === 0) { keep[0] = 1; kept = 1; s.keptLast++; }         // an accessor may not be empty
    const out = new a.constructor(kept * 3);
    for (let t = 0, k = 0; t < nt; t++) if (keep[t]) { out[k++] = a[t * 3]; out[k++] = a[t * 3 + 1]; out[k++] = a[t * 3 + 2]; }
    idx.setArray(out);
    s.trisDropped += nt - kept;
  }
}
// vertices no index references any more leave every accessor that shares them (order kept); not on water or
// vertex-coloured primitives
function compact(doc, s) {
  const parent = new Map();
  const find = (x) => { while (parent.get(x) !== x) { parent.set(x, parent.get(parent.get(x))); x = parent.get(x); } return x; };
  const union = (x, y) => { for (const z of [x, y]) if (!parent.has(z)) parent.set(z, z); const a = find(x), b = find(y); if (a !== b) parent.set(a, b); };
  for (const p of prims(doc)) {
    const accs = [p.getIndices(), ...p.listAttributes()].filter(Boolean);
    for (const t of p.listTargets()) accs.push(...t.listAttributes());
    for (const x of accs) union(accs[0], x);
  }
  const groups = new Map();
  for (const p of prims(doc)) {
    const first = p.getIndices() || p.listAttributes()[0]; if (!first) continue;
    const r = find(first);
    if (!groups.has(r)) groups.set(r, { ps: [], idx: new Set(), attrs: new Set() });
    const g = groups.get(r);
    g.ps.push(p);
    if (p.getIndices()) g.idx.add(p.getIndices());
    for (const x of p.listAttributes()) g.attrs.add(x);
  }
  for (const g of groups.values()) {
    if (g.ps.some((p) => !p.getIndices() || p.listTargets().length || isWater(p) || p.getAttribute('COLOR_0'))) continue;
    const counts = new Set([...g.attrs].map((x) => x.getCount()));
    if (counts.size !== 1) continue;
    const n = [...counts][0];
    const used = new Uint8Array(n);
    for (const idx of g.idx) { const a = idx.getArray(); for (let i = 0; i < a.length; i++) used[a[i]] = 1; }
    let k = 0; const remap = new Int32Array(n);
    for (let v = 0; v < n; v++) remap[v] = used[v] ? k++ : -1;
    if (k === n) continue;
    for (const x of g.attrs) {
      const src = x.getArray(); const es = x.getElementSize(); const dst = new src.constructor(k * es);
      for (let v = 0; v < n; v++) if (used[v]) dst.set(src.subarray(v * es, v * es + es), remap[v] * es);
      x.setArray(dst);
    }
    for (const idx of g.idx) { const a = idx.getArray(); for (let i = 0; i < a.length; i++) a[i] = remap[a[i]]; idx.setArray(a); }
    s.vertsDropped += n - k;
  }
}
// float UVs onto a power-of-two grid of their extent / 2^bits, per component
function roundUVs(doc, s, bits) {
  const seen = new Set();
  for (const p of prims(doc)) for (const sem of p.listSemantics()) {
    const x = p.getAttribute(sem);
    if (!/^TEXCOORD_/.test(sem) || seen.has(x) || x.getComponentType() !== 5126 || x.getNormalized()) continue;
    seen.add(x);
    const a = x.getArray(); const es = x.getElementSize(); const n = x.getCount();
    for (let c = 0; c < es; c++) {
      let lo = Infinity, hi = -Infinity;
      for (let v = 0; v < n; v++) { const q = a[v * es + c]; if (q < lo) lo = q; if (q > hi) hi = q; }
      if (!(hi >= lo)) continue;
      const step = Math.pow(2, Math.ceil(Math.log2(Math.max(hi - lo, 1e-6) / Math.pow(2, bits))));
      for (let v = 0; v < n; v++) {
        const q0 = a[v * es + c];
        a[v * es + c] = Math.round(q0 / step) * step;
        s.uvMaxErr = Math.max(s.uvMaxErr, Math.abs(a[v * es + c] - q0));
      }
    }
    x.setArray(a);
    s.uvAccessors++;
  }
}
(async () => {
  const mo = await import(pathToFileURL(req.resolve('meshoptimizer')).href);
  const D = mo.MeshoptDecoder, E = mo.MeshoptEncoder;
  await D.ready; await E.ready;
  // gltf-transform's writer calls encodeGltfBuffer(source, count, stride, mode) only: vertex streams get opt.codec
  const enc = Object.assign({}, E, { encodeGltfBuffer: (src, count, stride, mode) =>
    E.encodeGltfBuffer(src, count, stride, mode, mode === 'ATTRIBUTES' ? opt.codec : undefined) });
  const io = new core.NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': D, 'meshopt.encoder': enc });
  const doc = await io.read(IN);
  const s = { trisBefore: drawnTris(doc), trisAfter: 0, trisDropped: 0, degenerate: {}, vcKept: 0, keptLast: 0,
              vertsDropped: 0, uvAccessors: 0, uvMaxErr: 0, codec: opt.codec, rotated: 0, check: null };
  dropDegenerate(doc, s);
  compact(doc, s);
  if (opt.uvBits > 0) roundUVs(doc, s, opt.uvBits);
  s.trisAfter = drawnTris(doc);
  let bytes = Buffer.from(await io.writeBinary(doc));
  if (opt.codec === 1) bytes = renameMeshopt(bytes, EXT, KHR);
  fs.writeFileSync(OUT, bytes);
  // decode what was written and compare every accessor with what was meant. The triangle codec may start a
  // triangle at another corner (same winding, same triangle order): index accessors match when every triangle is a
  // rotation of the one meant.
  const back = await io.readBinary(new Uint8Array(opt.codec === 1 ? renameMeshopt(bytes, KHR, EXT) : bytes));
  const A = doc.getRoot().listAccessors(), B = back.getRoot().listAccessors();
  const indexAcc = new Set(prims(doc).filter((p) => p.getMode() === 4).map((p) => p.getIndices()).filter(Boolean));
  const bad = [];
  if (A.length !== B.length) bad.push(`${A.length} accessors written, ${B.length} read back`);
  for (let i = 0; !bad.length && i < A.length; i++) {
    const x = A[i].getArray(), y = B[i].getArray();
    let same = x.length === y.length && x.constructor === y.constructor;
    if (same && Buffer.compare(Buffer.from(x.buffer, x.byteOffset, x.byteLength), Buffer.from(y.buffer, y.byteOffset, y.byteLength)) !== 0) {
      same = indexAcc.has(A[i]) && x.length % 3 === 0;
      for (let t = 0; same && t < x.length; t += 3) {
        if (x[t] === y[t] && x[t + 1] === y[t + 1] && x[t + 2] === y[t + 2]) continue;
        if ((x[t] === y[t + 1] && x[t + 1] === y[t + 2] && x[t + 2] === y[t]) || (x[t] === y[t + 2] && x[t + 1] === y[t] && x[t + 2] === y[t + 1])) s.rotated++;
        else same = false;
      }
    }
    if (!same) bad.push(`accessor ${i} (${x.constructor.name} x${x.length}) reads back as ${y.constructor.name} x${y.length}, different`);
  }
  if (drawnTris(back) !== s.trisAfter) bad.push(`${drawnTris(back)} triangles read back, ${s.trisAfter} written`);
  s.check = bad.length ? bad.slice(0, 3).join('; ') : 'ok';
  fs.writeFileSync(SUM, JSON.stringify(s));
  if (bad.length) process.exit(2);
})().catch((e) => { console.error(e); process.exit(1); });
"""


def post_file(src, dst, codec, uv_bits, tmp):
    """Runs POST_JS on one meshopt-packed GLB; returns its summary (raises when its decode check fails)."""
    if not NODE_MODULES:
        raise SystemExit("the post step needs the cached @gltf-transform/cli@%s install (npx)" % CLI_VERSION)
    js = os.path.join(tmp, "sect_pack_post.cjs")
    if not os.path.isfile(js) or open(js, encoding="utf-8").read() != POST_JS:
        part = js + ".%d.%d" % (os.getpid(), threading.get_ident())      # packing threads share the process
        with open(part, "w", encoding="utf-8") as fh:
            fh.write(POST_JS)
        os.replace(part, js)
    sp = dst + ".json"
    r = subprocess.run(["node", "--max-old-space-size=8192", js, NODE_MODULES, src, dst, sp,
                        json.dumps(dict(codec=codec, uvBits=uv_bits))], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    s = None
    if os.path.isfile(sp):
        with open(sp, encoding="utf-8") as fh:
            s = json.load(fh)
        os.remove(sp)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("post step failed: %s: %s" % (src, s and s.get("check")))
    return s


def pack_full_file(n, quality, stage, tmp, simp=None, codec=CODEC):
    """One raw file -> stage/<n>.glb.gz (+ stage/low/<n>.glb.gz when it has textures). Keeps the uncompressed
    packed GLBs in tmp for the checks (and the simplified GLB, the reference for the triangle check). simp:
    (px, ref_h, min_tris) to simplify this file, or None. codec: the meshopt vertex codec of the post step.
    Returns its record."""
    t_start = time.time()
    msgs = []
    src = os.path.join(FULL_RAW, n + ".glb")
    p = lambda k: os.path.join(tmp, "%s.%s.glb" % (n, k))
    rec = dict(name=n, raw=src, raw_bytes=os.path.getsize(src), ref=None)
    cur = src
    nc = round_vertex_colors(cur, p("c8"))
    if nc:
        cur = p("c8")
        msgs.append("  %s: rounded %d vertex colours to 8 bits before the weld" % (n, nc))
    run(["weld", cur, p("weld")])
    cur = p("weld")
    if simp:
        rec["simplify"] = simplify_file(cur, p("simp"), simp[0], simp[1], simp[2], tmp)
        cur = rec["ref"] = p("simp")
        s = rec["simplify"]
        msgs.append("  %s: simplified %d primitives, %d -> %d triangles (%.1f%% fewer; max error %.1f cm); kept "
                    "exact: items %d, glow %d, small %d, near %d" % (
                        n, s["simplified"], s["before"], s["after"], 100.0 * (1 - s["after"] / max(1, s["before"])),
                        s["maxErrorM"] * 100, s["keptItem"], s["keptGlow"], s["keptSmall"], s["keptNear"]))
    twig = False
    if is_card_file(n):
        fill_card_textures(cur, p("fill"), log=msgs.append)
        cur = p("fill")
        twig = bool(twig_images(read_glb(cur)[0]))
    run(["unlit", cur, p("unlit")])
    cur = p("unlit")
    if max_image_px(cur) > MAX_PX:
        run(["resize", cur, p("cap"), "--width", str(MAX_PX), "--height", str(MAX_PX)])
        cur = p("cap")
        msgs.append("  textures capped at %d px" % MAX_PX)
    tiers = [("full", cur)]
    if max_image_px(cur) > LOW_PX:          # files with textures <= 2048 px serve the low tier as they are
        run(["resize", cur, p("lowsize"), "--width", str(LOW_PX), "--height", str(LOW_PX)])
        tiers.append(("low", p("lowsize")))
    rec["problems"] = []
    for tier, base in tiers:
        k = "" if tier == "full" else ".low"
        if twig:
            # the twig card texture first, near-lossless (R and G must stay apart), then every other (PNG) texture
            # lossy as usual; the second pass skips the twig texture, already WebP
            run(["webp", base, p("twig" + k), "--pattern", TWIG_IMAGE, "--near-lossless", "true",
                 "--quality", str(TWIG_WEBP_Q)])
            run(["webp", p("twig" + k), p("webp" + k), "--formats", "png", "--quality", str(quality)])
        else:
            run(["webp", base, p("webp" + k), "--quality", str(quality)])
        packed = p("packed" + k)
        run(["meshopt", p("webp" + k), p("mo" + k), "--level", "high", "--quantize-position", "16",
             "--quantize-texcoord", "14"])
        post = post_file(p("mo" + k), packed, codec, UV_BITS, tmp)
        patch(packed)
        rel = ("low/" if tier == "low" else "") + n + ".glb.gz"
        dst = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        s = stats(packed)
        rec[tier] = dict(file=rel, packed=packed, gz_bytes=gz(packed, dst), post=post, **s)
        if tier == "full" and (post["trisDropped"] or post["uvAccessors"]):
            msgs.append("  %s: dropped %d zero-area triangles and %d unused vertices (kept %d on vertex-coloured "
                        "corners left black); %d float UV sets rounded (max %.2g)" % (
                            n, post["trisDropped"], post["vertsDropped"], post["vcKept"], post["uvAccessors"],
                            post["uvMaxErr"]))
        if twig:
            rec[tier]["twig"], probs = twig_check(packed, n + k)
            rec["problems"] += probs
            msgs += ["  %s%s twig texture %s" % (n, k, t) for t in rec[tier]["twig"]]
    rec["low_file"] = rec["low"]["file"] if "low" in rec else rec["full"]["file"]
    rec["seconds"] = round(time.time() - t_start, 1)
    rec["log"] = msgs
    for k in ("c8", "weld", "fill", "unlit", "cap", "lowsize", "webp", "webp.low", "twig", "twig.low", "mo", "mo.low"):
        if os.path.isfile(p(k)):
            os.remove(p(k))
    return rec


# Node check: decodes each packed file (meshopt, either codec; gltf-transform 4.5.1 knows only the name
# EXT_meshopt_compression, so a KHR_meshopt_compression file is read under that name, the same JSON) with glTF
# Transform, runs the Khronos validator on it as shipped and on its decoded geometry written out plain (the validator
# cannot read meshopt streams), counts the vertex streams per codec version, and summarises raw and packed alike
# (triangles with instances, world boxes per node, extras, textures).
CHECK_JS = r"""
'use strict';
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');
const [NM, JOBS, OUT] = process.argv.slice(2);
const req = require('module').createRequire(path.join(NM, '_.js'));
const core = req('@gltf-transform/core');
const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const validator = req('gltf-validator');

function mul(a, b) {            // column-major 4x4
  const o = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
    let s = 0;
    for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
    o[c * 4 + r] = s;
  }
  return o;
}
function trs(t, q, s) {
  const [x, y, z, w] = q;
  const x2 = x + x, y2 = y + y, z2 = z + z;
  const xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2;
  const wx = w * x2, wy = w * y2, wz = w * z2;
  return [(1 - (yy + zz)) * s[0], (xy + wz) * s[0], (xz - wy) * s[0], 0,
          (xy - wz) * s[1], (1 - (xx + zz)) * s[1], (yz + wx) * s[1], 0,
          (xz + wy) * s[2], (yz - wx) * s[2], (1 - (xx + yy)) * s[2], 0,
          t[0], t[1], t[2], 1];
}
function boxOf(m, lo, hi, acc) {
  for (let i = 0; i < 8; i++) {
    const p = [i & 1 ? hi[0] : lo[0], i & 2 ? hi[1] : lo[1], i & 4 ? hi[2] : lo[2]];
    for (let r = 0; r < 3; r++) {
      const v = m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r];
      if (v < acc[0][r]) acc[0][r] = v;
      if (v > acc[1][r]) acc[1][r] = v;
    }
  }
}
function summarize(doc) {
  const root = doc.getRoot();
  const nodes = {};
  let tris = 0, instanced = 0, instances = 0, badIndex = 0, nanPos = 0;
  for (const node of root.listNodes()) {
    const e = { extras: node.getExtras() };
    const mesh = node.getMesh();
    if (mesh) {
      const W = node.getWorldMatrix();
      let mats = [W];
      const batch = node.getExtension('EXT_mesh_gpu_instancing');
      if (batch) {
        const T = batch.getAttribute('TRANSLATION'), R = batch.getAttribute('ROTATION'), S = batch.getAttribute('SCALE');
        const n = (T || R || S).getCount();
        mats = [];
        for (let i = 0; i < n; i++) {
          const t = T ? T.getElement(i, [0, 0, 0]) : [0, 0, 0];
          const q = R ? R.getElement(i, [0, 0, 0, 1]) : [0, 0, 0, 1];
          const s = S ? S.getElement(i, [1, 1, 1]) : [1, 1, 1];
          const ql = Math.hypot(...q) || 1;
          mats.push(mul(W, trs(t, q.map((v) => v / ql), s)));
        }
        instanced++; instances += n; e.instances = n;
      }
      const acc = [[Infinity, Infinity, Infinity], [-Infinity, -Infinity, -Infinity]];
      let t = 0;
      for (const prim of mesh.listPrimitives()) {
        const pos = prim.getAttribute('POSITION');
        const idx = prim.getIndices();
        const vc = pos.getCount();
        const n = idx ? idx.getCount() : vc;
        if (prim.getMode() === 4) t += Math.floor(n / 3);
        if (idx) { const a = idx.getArray(); for (let i = 0; i < a.length; i++) if (a[i] >= vc) { badIndex++; break; } }
        const lo = pos.getMinNormalized([0, 0, 0]), hi = pos.getMaxNormalized([0, 0, 0]);
        if (![...lo, ...hi].every(Number.isFinite)) nanPos++;
        for (const m of mats) boxOf(m, lo, hi, acc);
      }
      e.tris = t * mats.length;
      e.box = acc;
      tris += e.tris;
    }
    let name = node.getName(), k = 1;
    while (nodes[name]) name = node.getName() + '#' + (++k);
    nodes[name] = e;
  }
  // primitives per material that lack a UV set its base colour or occlusion texture reads
  const uvMissing = new Map();
  for (const mesh of root.listMeshes()) for (const prim of mesh.listPrimitives()) {
    const m = prim.getMaterial();
    if (!m) continue;
    const sets = [];
    if (m.getBaseColorTexture()) sets.push(m.getBaseColorTextureInfo().getTexCoord());
    if (m.getOcclusionTexture()) sets.push(m.getOcclusionTextureInfo().getTexCoord());
    if (sets.some((k) => !prim.getAttribute(`TEXCOORD_${k}`))) uvMissing.set(m, (uvMissing.get(m) || 0) + 1);
  }
  const materials = {};
  for (const m of root.listMaterials()) materials[m.getName()] = { extras: m.getExtras(), alphaMode: m.getAlphaMode(),
    unlit: !!m.getExtension('KHR_materials_unlit'),
    occlusion: m.getOcclusionTexture() ? m.getOcclusionTextureInfo().getTexCoord() : null,
    uvMissing: uvMissing.get(m) || 0 };
  const images = root.listTextures().map((tx) => ({ name: tx.getName(), mime: tx.getMimeType(),
    size: core.ImageUtils.getSize(tx.getImage(), tx.getMimeType()), bytes: tx.getImage().byteLength }));
  return { tris, nodes, materials, images, instanced, instances, badIndex, nanPos,
           extensions: root.listExtensionsUsed().map((x) => x.extensionName) };
}
// bytes gltf-transform can read: KHR_meshopt_compression renamed EXT_meshopt_compression in the JSON chunk (the
// names are the same length; latin1 keeps every other byte as it is)
function readable(file) {
  const b = fs.readFileSync(file);
  const jlen = b.readUInt32LE(12);
  const js = b.subarray(20, 20 + jlen).toString('latin1');
  if (!js.includes('KHR_meshopt_compression')) return new Uint8Array(b);
  const out = Buffer.from(b);
  out.write(js.split('KHR_meshopt_compression').join('EXT_meshopt_compression'), 20, 'latin1');
  return new Uint8Array(out);
}
// vertex streams per extension name and codec version (the stream's header byte: 0xa0 version 0, 0xa1 version 1)
function codecs(file) {
  const b = fs.readFileSync(file);
  const jlen = b.readUInt32LE(12);
  const json = JSON.parse(b.subarray(20, 20 + jlen).toString('utf8'));
  const bin = b.subarray(20 + jlen + 8);
  const n = {};
  for (const bv of json.bufferViews || []) {
    const x = bv.extensions || {};
    const e = x.KHR_meshopt_compression || x.EXT_meshopt_compression;
    if (!e || e.mode !== 'ATTRIBUTES') continue;
    const k = (x.KHR_meshopt_compression ? 'KHR' : 'EXT') + ' v' + (bin[e.byteOffset || 0] & 0x0f);
    n[k] = (n[k] || 0) + 1;
  }
  return n;
}
async function validate(bytes) {
  const rep = await validator.validateBytes(new Uint8Array(bytes), { maxIssues: 200, writeTimestamp: false });
  const msgs = rep.issues.messages.filter((m) => m.severity <= 1).slice(0, 12).map((m) => `${m.code}: ${m.message} ${m.pointer || ''}`);
  // index accessors with triangles that repeat a corner (the validator does not look for collinear ones)
  const degen = rep.issues.messages.filter((m) => m.code === 'ACCESSOR_INDEX_TRIANGLE_DEGENERATE').length;
  return { errors: rep.issues.numErrors, warnings: rep.issues.numWarnings, infos: rep.issues.numInfos,
           hints: rep.issues.numHints, degenerateAccessors: degen, messages: msgs };
}
(async () => {
  const mo = await import(pathToFileURL(req.resolve('meshoptimizer')).href);
  await mo.MeshoptDecoder.ready;
  const io = new core.NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': mo.MeshoptDecoder });
  const jobs = JSON.parse(fs.readFileSync(JOBS, 'utf8'));
  const res = {};
  for (const j of jobs) {
    const r = (res[j.key] = {});
    try {
      r.validator = await validate(fs.readFileSync(j.packed));
      r.codecs = codecs(j.packed);
      const doc = await io.readBinary(readable(j.packed));
      r.packed = summarize(doc);
      // the decoded geometry written out plain, for the validator (indices in range, accessor bounds, degenerates)
      for (const x of doc.getRoot().listExtensionsUsed()) if (x.extensionName === 'EXT_meshopt_compression') x.dispose();
      r.decoded = await validate(await io.writeBinary(doc));
      if (j.raw) r.raw = summarize(await io.read(j.raw));
      if (j.ref) r.ref = summarize(await io.read(j.ref));
    } catch (e) { r.error = String(e && e.stack || e); }
    process.stdout.write(`checked ${j.key}\n`);
  }
  fs.writeFileSync(OUT, JSON.stringify(res));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def run_checks(recs, tmp, workers):
    """Runs CHECK_JS over every packed file (full and low tiers) in a few node processes. {key: result}."""
    if not NODE_MODULES:
        raise SystemExit("the checks need the cached @gltf-transform/cli@%s install (npx)" % CLI_VERSION)
    js = os.path.join(tmp, "sect_pack_check.cjs")
    with open(js, "w", encoding="utf-8") as fh:
        fh.write(CHECK_JS)
    jobs = []
    for r in recs:
        jobs.append(dict(key=r["name"], packed=r["full"]["packed"], raw=r["raw"], ref=r.get("ref")))
        if "low" in r:
            jobs.append(dict(key=r["name"] + ".low", packed=r["low"]["packed"], raw=None))
    # big files first, spread over the workers
    jobs.sort(key=lambda j: -os.path.getsize(j["packed"]))
    nproc = max(1, min(workers, len(jobs)))
    parts = [jobs[k::nproc] for k in range(nproc)]
    procs = []
    for k, part in enumerate(parts):
        jp = os.path.join(tmp, "check_jobs_%d.json" % k)
        op = os.path.join(tmp, "check_out_%d.json" % k)
        with open(jp, "w", encoding="utf-8") as fh:
            json.dump(part, fh)
        procs.append((subprocess.Popen(["node", "--max-old-space-size=8192", js, NODE_MODULES, jp, op],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       encoding="utf-8", errors="replace"), op))
    out = {}
    for pr, op in procs:
        so, se = pr.communicate()
        if pr.returncode != 0:
            sys.stderr.write(so + se)
            raise SystemExit("check failed")
        with open(op, encoding="utf-8") as fh:
            out.update(json.load(fh))
    return out


def _box_diff(a, b):
    """Largest corner difference between two world boxes, and the tolerance for them (quantisation)."""
    d = max(abs(a[i][k] - b[i][k]) for i in range(2) for k in range(3))
    ext = max(a[1][k] - a[0][k] for k in range(3))
    return d, max(0.02, 2e-3 * ext)


def compare_file(name, res, tier, post=None, codec=None):
    """Problems (list of str) of one packed file against its raw file. post: the post step's summary for this file
    (the zero-area triangles it dropped; None for records packed before it existed), codec: the meshopt vertex codec
    it was asked to write."""
    probs = []
    if "error" in res:
        return ["%s: check crashed: %s" % (name, res["error"][:300])]
    v = res["validator"]
    if v["errors"]:
        probs.append("%s: validator %d errors: %s" % (name, v["errors"], "; ".join(v["messages"][:4])))
    d = res.get("decoded")
    if d and d["errors"]:
        probs.append("%s: validator on the decoded geometry %d errors: %s" % (name, d["errors"],
                                                                             "; ".join(d["messages"][:4])))
    if post is not None:
        if post.get("check") != "ok":
            probs.append("%s: post step decode check: %s" % (name, post.get("check")))
        want_codec = "KHR v1" if codec == 1 else "EXT v0"
        if any(k != want_codec for k in res.get("codecs") or {}):
            probs.append("%s: vertex streams %s, expected only %s" % (name, res.get("codecs"), want_codec))
    pk = res["packed"]
    if pk["badIndex"] or pk["nanPos"]:
        probs.append("%s: decoded data broken (bad indices %d, NaN positions %d)" % (name, pk["badIndex"], pk["nanPos"]))
    limit = LOW_PX if tier == "low" else MAX_PX
    for im in pk["images"]:
        if not im["size"] or max(im["size"]) > limit:
            probs.append("%s: texture %s is %s (limit %d)" % (name, im["name"], im["size"], limit))
    for mn, q in pk["materials"].items():
        if q.get("uvMissing"):
            probs.append("%s: material %s: %d primitives lack the UV set of its textures" % (name, mn, q["uvMissing"]))
        # needle cards: opaque in the file (the page alpha-tests them with the occlusion image on TEXCOORD_1)
        if mn.startswith("trees.needle") and (q["alphaMode"] != "OPAQUE" or q.get("occlusion") is None):
            probs.append("%s: needle material %s is %s, needle alpha (occlusion) texCoord %s" % (
                name, mn, q["alphaMode"], q.get("occlusion")))
    rw = res.get("raw")
    if rw is None:
        return probs
    ref = res.get("ref")          # the simplified GLB (when the file was simplified): the triangle reference
    want = (ref or rw)["tris"]
    dropped = 0
    if post is not None:
        # zero-area triangles the post step dropped (instances counted); what it was given must be the reference
        dropped = post["trisBefore"] - post["trisAfter"]
        if post["trisBefore"] != want:
            probs.append("%s: %d triangles reached the post step, %s has %d" % (
                name, post["trisBefore"], "simplified" if ref else "raw", want))
    if want - dropped != pk["tris"]:
        probs.append("%s: %d triangles decoded, %s has %d less %d zero-area ones dropped" % (
            name, pk["tris"], "simplified" if ref else "raw", want, dropped))
    for nn, e in rw["nodes"].items():
        q = pk["nodes"].get(nn)
        if q is None:
            probs.append("%s: node %s missing" % (name, nn))
            continue
        if json.dumps(e["extras"], sort_keys=True) != json.dumps(q["extras"], sort_keys=True):
            probs.append("%s: node %s extras %s -> %s" % (name, nn, e["extras"], q["extras"]))
        if "box" in e:
            if "box" not in q:
                probs.append("%s: node %s lost its mesh" % (name, nn))
                continue
            if e.get("instances") != q.get("instances"):
                probs.append("%s: node %s instances %s -> %s" % (name, nn, e.get("instances"), q.get("instances")))
            rb = ref["nodes"].get(nn, {}).get("box") if ref else None
            d, tol = _box_diff(rb or e["box"], q["box"])
            if d > tol:
                # dropping zero-area triangles (the post step) can pull a box in at an edge; only growth is wrong
                b0 = rb or e["box"]
                grow = max(max(b0[0][k] - q["box"][0][k], q["box"][1][k] - b0[1][k]) for k in range(3))
                if not (dropped > 0 and grow <= tol):
                    probs.append("%s: node %s moved %.3f m (tolerance %.3f)" % (name, nn, d, tol))
            if rb:
                # against the raw file: simplification may pull a box in by its (sub-pixel) error, never more
                d2 = _box_diff(e["box"], q["box"])[0]
                ext = max(e["box"][1][k] - e["box"][0][k] for k in range(3))
                if d2 > max(0.15, 0.01 * ext):
                    probs.append("%s: node %s is %.3f m off the raw file" % (name, nn, d2))
    for mn, m in rw["materials"].items():
        q = pk["materials"].get(mn)
        if q is None:
            probs.append("%s: material %s missing" % (name, mn))
        elif json.dumps(m["extras"], sort_keys=True) != json.dumps(q["extras"], sort_keys=True):
            probs.append("%s: material %s extras changed" % (name, mn))
        elif mn.startswith("trees.cards") and q["alphaMode"] != "MASK":
            probs.append("%s: card material %s is %s" % (name, mn, q["alphaMode"]))
        elif m.get("occlusion") != q.get("occlusion"):
            probs.append("%s: material %s occlusion texture texCoord %s -> %s" % (name, mn, m.get("occlusion"),
                                                                                 q.get("occlusion")))
    if rw["instanced"] != pk["instanced"]:
        probs.append("%s: instanced nodes %d -> %d" % (name, rw["instanced"], pk["instanced"]))
    return probs


def node_box_err(res):
    """Largest box difference over the nodes (m), for the report."""
    rw, pk = res.get("raw"), res.get("packed")
    if not rw or not pk:
        return None
    worst = 0.0
    for nn, e in rw["nodes"].items():
        q = pk["nodes"].get(nn)
        if q and "box" in e and "box" in q:
            worst = max(worst, _box_diff(e["box"], q["box"])[0])
    return round(worst, 4)


def build_manifest(areas, recs_by_name):
    """manifest.json v2 from the packed records (sizes are the .glb.gz files)."""
    def files_of(names, tier):
        return [(recs_by_name[n][tier]["file"] if tier in recs_by_name[n] else recs_by_name[n]["full"]["file"])
                for n in names]

    def bytes_of(names, tier, key="gz_bytes"):
        return sum((recs_by_name[n][tier] if tier in recs_by_name[n] else recs_by_name[n]["full"])[key]
                   for n in names)

    gl = [n for n in GLOBAL_NAMES if n in recs_by_name]
    has_low = lambda names: any("low" in recs_by_name[n] for n in names)
    man = dict(version=2, baked=True, camera="camera.json", meta="meta.json",
               clouds="clouds.json" if os.path.isfile(os.path.join(FULL_SITE, "clouds.json")) else None,
               flyer="flyer.glb" if os.path.isfile(os.path.join(FULL_SITE, "flyer.glb")) else None,
               flyerPath="flyer.json" if os.path.isfile(os.path.join(FULL_SITE, "flyer.json")) else None,
               detail="detail.webp" if os.path.isfile(os.path.join(FULL_SITE, "detail.webp")) else None,
               water=None,
               **{"global": files_of(gl, "full")},
               globalLow=files_of(gl, "low") if has_low(gl) else None,
               globalBytes=bytes_of(gl, "full"), globalBytesLow=bytes_of(gl, "low") if has_low(gl) else None,
               globalTris=sum(recs_by_name[n]["full"]["triangles"] for n in gl),
               globalTexBytes=bytes_of(gl, "full", "tex_bytes"),
               globalTexBytesLow=bytes_of(gl, "low", "tex_bytes") if has_low(gl) else None,
               chunks=[], fileTexBytes={})
    for ar in areas:
        names = [ar["id"] + s for s in ("", "_trees", "_water") if ar["id"] + s in recs_by_name]
        if ar["id"] not in recs_by_name:
            raise SystemExit("no packed %s.glb: cannot write the manifest" % ar["id"])
        low = has_low(names)
        man["chunks"].append(dict(
            id=ar["id"], files=files_of(names, "full"), filesLow=files_of(names, "low") if low else None,
            need=ar["need"], bytes=bytes_of(names, "full"), bytesLow=bytes_of(names, "low") if low else None,
            tris=sum(recs_by_name[n]["full"]["triangles"] for n in names),
            texBytes=bytes_of(names, "full", "tex_bytes"),
            texBytesLow=bytes_of(names, "low", "tex_bytes") if low else None,
            core=ar["core"], need250=ar["need250"], hold=ar["hold"]))
    # every listed file (low copies too) by the name the page fetches it under
    for n in gl + [ar["id"] + s for ar in areas for s in ("", "_trees", "_water")]:
        for tier in ("full", "low"):
            r = recs_by_name.get(n, {}).get(tier)
            if r:
                man["fileTexBytes"][r["file"]] = r["tex_bytes"]
    return man


def full_meta_note(meta, a):
    post = {}
    pp = os.path.join(FULL_BAKE, "post", "gate.json")
    if os.path.isfile(pp):
        with open(pp, encoding="utf-8") as fh:
            post = json.load(fh)
    meta["bake"] = dict(
        colour="Baked atlases, tree textures, card sprites and vertex colours are display-referred sRGB "
               "(Blender AgX / AgX - Punchy, exposure %s, look.py CDL grade, saturation %s already applied). "
               "All materials are KHR_materials_unlit: draw with no tone mapping so the pixels round-trip."
               % (post.get("exposure", 1.2), post.get("sat", 1.15)),
        glow="Emissive surfaces are separate primitives; material and node extras carry {\"glow\": strength, "
             "\"glowTint\": \"#rrggbb\"}. Multiply the colour by the strength (toward the tint) so only they bloom.",
        chunks="manifest.json v2: 'global' (backdrop, backdrop_trees, backdrop_water) always loaded; per area "
               "<area>.glb.gz (baked atlases, hotspot nodes), <area>_trees.glb.gz (instanced near trees, cards; plant "
               "hotspots 'trees.hs.<id>'), <area>_water.glb.gz (waterfall sheets, streams). Backdrop nodes with "
               "extras {\"proxyOf\": area} stand in for an area while its chunk is not drawn. Faces split into "
               "compact pieces (extras {\"chunk\": 1}) for culling: do not merge them back.",
        hotspots="Nodes with extras {hotspot, label} (named 'hotspot.<id>' or 'trees.hs.<id>'); meta.hotspots "
                 "carry the click boxes, area and chunk. 'moon' is meta-only (meta.moon).",
        notBaked="Haze/fog, cloud sea and banks (clouds.json), the moon, the sky (sky.webp), light beams "
                 "(meta.beams), the formation dome and pillar are drawn by the page, not in the GLBs.",
        packed="tools/sect_pack.py --profile full: weld, area files simplified below %s px of error at %d lines "
               "(content items and glow pieces exact), unlit, WebP q%d, meshopt (positions 16 bit, UVs 14 bit; "
               "zero-area triangles dropped; float water UVs on a 2^-%d grid of their extent; vertex codec %d, %s), "
               "gzip; low/ copies with textures <= 2048 px." % (
                   a.simplify_px, a.simplify_ref, a.quality, UV_BITS, a.codec,
                   "KHR_meshopt_compression" if a.codec == 1 else "EXT_meshopt_compression"))
    return meta


def install_full(stage, man, a):
    """Copies the staged set and the data files into the client folder; removes packed files no longer listed."""
    os.makedirs(FULL_CLIENT, exist_ok=True)
    listed = set(man["global"]) | set(man["globalLow"] or [])
    for c in man["chunks"]:
        listed |= set(c["files"]) | set(c["filesLow"] or [])
    for rel in sorted(listed):
        s_ = os.path.join(stage, rel)
        d_ = os.path.join(FULL_CLIENT, rel)
        os.makedirs(os.path.dirname(d_), exist_ok=True)
        shutil.copyfile(s_, d_ + ".part")
        os.replace(d_ + ".part", d_)
    for f in DATA_FILES:
        s_ = os.path.join(FULL_SITE, f)
        if not os.path.isfile(s_):
            continue
        d_ = os.path.join(FULL_CLIENT, f)
        if f == "meta.json":
            with open(s_, encoding="utf-8") as fh:
                meta = full_meta_note(json.load(fh), a)
            with open(d_ + ".part", "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=1, ensure_ascii=False)
        else:
            shutil.copyfile(s_, d_ + ".part")
        os.replace(d_ + ".part", d_)
    with open(os.path.join(FULL_CLIENT, "manifest.json.part"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    os.replace(os.path.join(FULL_CLIENT, "manifest.json.part"), os.path.join(FULL_CLIENT, "manifest.json"))
    removed = []
    for dirpath, _dirs, files in os.walk(FULL_CLIENT):
        for fn in files:
            rel = os.path.relpath(os.path.join(dirpath, fn), FULL_CLIENT).replace("\\", "/")
            if (fn.endswith(".glb.gz") or fn.endswith(".glb")) and rel not in listed and rel not in DATA_FILES:
                os.remove(os.path.join(dirpath, fn))
                removed.append(rel)
    return removed


def main_full(a):
    global FULL, FULL_RAW, FULL_SITE, FULL_TMP
    t_all = time.time()
    if a.src:
        FULL, FULL_RAW, FULL_SITE = a.src, os.path.join(a.src, "raw"), os.path.join(a.src, "site")
    if a.work:
        FULL_TMP = a.work
    areas = full_plan()
    names = full_names(areas)
    stage = os.path.join(FULL_TMP, "site")
    work = os.path.join(FULL_TMP, "work")
    stats_path = os.path.join(a.work, "pack_stats.json") if a.work else os.path.join(FULL_BAKE, "pack_stats.json")
    os.makedirs(stage, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    old = {}
    if os.path.isfile(stats_path):
        with open(stats_path, encoding="utf-8") as fh:
            old = json.load(fh).get("files", {})
    todo = [] if a.check_only else ([n for n in names if n in a.only.split(",")] if a.only else list(names))
    _log("pack (full): %d raw files from %s, packing %d with %d workers (CLI: %s); meshopt codec %d" % (
        len(names), FULL_RAW, len(todo), a.workers, " ".join(CLI[:2]), a.codec))
    recs = {}
    # biggest first so the long ones start early
    todo.sort(key=lambda n: -os.path.getsize(os.path.join(FULL_RAW, n + ".glb")))
    area_ids = {ar["id"] for ar in areas}
    simp = (a.simplify_px, a.simplify_ref, a.simplify_min) if a.simplify_px > 0 else None
    with cf.ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = {ex.submit(pack_full_file, n, a.quality, stage, work, simp if n in area_ids else None, a.codec): n
                for n in todo}
        for fu in cf.as_completed(futs):
            r = fu.result()
            recs[r["name"]] = r
            for m in r["log"]:
                _log(m)
            _log("  packed %-16s %6.2f MB gz (raw %5.1f MB) %8d tris%s  %5.1f s"
                 % (r["name"], r["full"]["gz_bytes"] / 1e6, r["raw_bytes"] / 1e6, r["full"]["triangles"],
                    ("  low %.2f MB" % (r["low"]["gz_bytes"] / 1e6)) if "low" in r else "", r["seconds"]))
    # files not re-packed this time: their previous records (packed GLBs must still be in the work folder)
    for n in names:
        if n not in recs:
            r = old.get(n)
            if r is not None and os.path.isfile(r["full"]["packed"]) and os.path.isfile(
                    os.path.join(stage, r["full"]["file"])):
                for tier in ("full", "low"):
                    if tier in r and "tex_bytes" not in r[tier]:      # packed before the manifest carried texBytes
                        r[tier]["tex_bytes"] = stats(r[tier]["packed"])["tex_bytes"]
                recs[n] = r
    partial = [n for n in names if n not in recs]
    if partial:
        # a trial: check what was packed, no manifest, no install
        _log("partial run (never packed: %s): checking the packed files only" % ", ".join(partial))
        names = [n for n in names if n in recs]
        a.no_install = True
    _log("checking %d files (validator, decoded triangles, node boxes, extras, textures) ..." % len(recs))
    t0 = time.time()
    check = run_checks([recs[n] for n in names], work, a.workers)
    problems = []
    for n in names:
        r = recs[n]
        res = check[n]
        problems += compare_file(n, res, "full", r["full"].get("post"), a.codec)
        problems += r.get("problems") or []          # found while packing (twig card textures)
        r["full"]["validator"] = res.get("validator")
        r["full"]["validator_decoded"] = res.get("decoded")
        r["full"]["codecs"] = res.get("codecs")
        r["full"]["decoded_tris"] = res.get("packed", {}).get("tris")
        r["full"]["raw_tris"] = res.get("raw", {}).get("tris")
        r["full"]["box_err_m"] = node_box_err(res)
        r["full"]["image_px"] = [im["size"] for im in res.get("packed", {}).get("images", [])]
        r["hotspots"] = sorted({e["extras"].get("hotspot") for e in res.get("packed", {}).get("nodes", {}).values()
                                if isinstance(e.get("extras"), dict) and e["extras"].get("hotspot")})
        r["proxyOf"] = sorted({e["extras"].get("proxyOf") for e in res.get("packed", {}).get("nodes", {}).values()
                               if isinstance(e.get("extras"), dict) and e["extras"].get("proxyOf")})
        if "low" in r:
            lres = check[n + ".low"]
            problems += compare_file(n + ".low", lres, "low", r["low"].get("post"), a.codec)
            lp = lres.get("packed", {})
            if lp.get("tris") != res.get("packed", {}).get("tris"):
                problems.append("%s.low: %s triangles, full tier has %s" % (n, lp.get("tris"),
                                                                            res.get("packed", {}).get("tris")))
            r["low"]["validator"] = lres.get("validator")
            r["low"]["validator_decoded"] = lres.get("decoded")
            r["low"]["codecs"] = lres.get("codecs")
            r["low"]["image_px"] = [im["size"] for im in lp.get("images", [])]
    _log("  checks done in %.0f s" % (time.time() - t0))
    # hotspots: every meta hotspot that names a node exists, in its own area's chunk
    with open(os.path.join(FULL_SITE, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    where = {}
    for n in names:
        for h in recs[n]["hotspots"]:
            where.setdefault(h, []).append(n)
    hs_missing, hs_wrong, meta_only = [], [], []
    for h in meta.get("hotspots", []):
        if not h.get("node"):
            meta_only.append(h["id"])
            continue
        files = where.get(h["id"])
        if not files:
            hs_missing.append(h["id"])
        elif not any(f.split("_")[0] == (h.get("chunk") or h.get("area")) for f in files):
            hs_wrong.append("%s in %s (meta chunk %s)" % (h["id"], files, h.get("chunk")))
    meta_ids = {h["id"] for h in meta.get("hotspots", [])}
    hs_extra = sorted(h for h in where if h not in meta_ids)
    problems += ["hotspot %s: no node in any packed file" % h for h in hs_missing]
    problems += ["hotspot %s" % s for s in hs_wrong]
    for g in ("backdrop", "backdrop_trees"):
        if g in recs:
            miss = sorted({ar["id"] for ar in areas} - set(recs[g]["proxyOf"]))
            if miss:
                problems.append("%s: no proxyOf node for %s" % (g, miss))
    if partial:
        hs_missing = [h for h in hs_missing if (next((x for x in meta["hotspots"] if x["id"] == h), {}).get("chunk")
                                                in {n.split("_")[0] for n in names})]
        problems = [p for p in problems if not p.startswith("hotspot") or any(h in p for h in hs_missing + hs_wrong)]
        for n in names:
            r = recs[n]
            _log("%-18s %6.2f MB gz  %8d tris  decoded %s raw %s  box err %s m  validator %s  textures %s" % (
                n, r["full"]["gz_bytes"] / 1e6, r["full"]["triangles"], r["full"]["decoded_tris"],
                r["full"]["raw_tris"], r["full"]["box_err_m"],
                {k: r["full"]["validator"][k] for k in ("errors", "warnings", "infos")}, r["full"]["image_px"]))
        _log("PROBLEMS: %d%s" % (len(problems), "".join("\n  - " + p for p in problems[:60])))
        with open(stats_path, "w", encoding="utf-8") as fh:
            json.dump(dict(files=recs, manifest=None, summary=dict(partial=partial, problems=problems)), fh, indent=1)
        return 1 if problems else 0
    man = build_manifest(areas, recs)
    # budgets
    data_bytes = sum(os.path.getsize(os.path.join(FULL_SITE, f)) for f in DATA_FILES
                     if os.path.isfile(os.path.join(FULL_SITE, f)))
    total = sum(recs[n]["full"]["gz_bytes"] for n in names) + data_bytes
    total_low = sum((recs[n]["low"] if "low" in recs[n] else recs[n]["full"])["gz_bytes"] for n in names) + data_bytes
    gate = next(c for c in man["chunks"] if c["id"] == "gate")
    # the opening download: the data the page always fetches (not the flyer files: only with ?flyer=1), the
    # global set and the gate chunk
    opening_data = sum(os.path.getsize(os.path.join(FULL_SITE, f)) for f in ("camera.json", "meta.json",
                                                                            "clouds.json", "sky.webp",
                                                                            "detail.webp")
                       if os.path.isfile(os.path.join(FULL_SITE, f)))
    initial = man["globalBytes"] + gate["bytes"] + opening_data
    over = []
    for c in man["chunks"]:
        if c["bytes"] > BUDGET["chunk_bytes"]:
            over.append("chunk %s %.2f MB > %.0f MB" % (c["id"], c["bytes"] / 1e6, BUDGET["chunk_bytes"] / 1e6))
        if c["tris"] > BUDGET["chunk_tris"]:
            over.append("chunk %s %.2fM triangles > %.1fM" % (c["id"], c["tris"] / 1e6, BUDGET["chunk_tris"] / 1e6))
    if man["globalBytes"] > BUDGET["global_bytes"]:
        over.append("global %.2f MB > %.0f MB" % (man["globalBytes"] / 1e6, BUDGET["global_bytes"] / 1e6))
    if initial > BUDGET["initial_bytes"]:
        over.append("opening (global + gate + data) %.2f MB > %.0f MB" % (initial / 1e6, BUDGET["initial_bytes"] / 1e6))
    if total > BUDGET["total_bytes"]:
        over.append("total %.2f MB > %.0f MB" % (total / 1e6, BUDGET["total_bytes"] / 1e6))
    # report
    _log("\n%-18s %9s %9s %10s %10s %9s  %s" % ("file", "MB gz", "low MB", "raw tris", "packed", "box err m",
                                                "textures (px)"))
    for n in names:
        r = recs[n]
        _log("%-18s %9.2f %9s %10d %10d %9s  %s" % (n, r["full"]["gz_bytes"] / 1e6,
                                                  ("%.2f" % (r["low"]["gz_bytes"] / 1e6)) if "low" in r else "-",
                                                  r["full"].get("raw_tris") or 0, r["full"]["triangles"],
                                                  r["full"].get("box_err_m"),
                                                  " ".join("%dx%d" % tuple(s) for s in r["full"].get("image_px") or [])))
    _log("\n%-10s %8s %8s %8s %9s %9s  %s" % ("chunk", "MB", "low MB", "M tris", "tex MB", "low tex", "need"))
    for c in man["chunks"]:
        _log("%-10s %8.2f %8.2f %8.3f %9.1f %9.1f  %s" % (
            c["id"], c["bytes"] / 1e6, (c["bytesLow"] or c["bytes"]) / 1e6, c["tris"] / 1e6, c["texBytes"] / 1e6,
            (c["texBytesLow"] if c["texBytesLow"] is not None else c["texBytes"]) / 1e6, c["need"]))
    _log("global %.2f MB (low %.2f), %.3fM tris; data files %.2f MB; opening (global + gate + data) %.2f MB; "
         "total %.2f MB (low tier %.2f MB)" % (man["globalBytes"] / 1e6, (man["globalBytesLow"] or man["globalBytes"]) / 1e6,
                                               man["globalTris"] / 1e6, data_bytes / 1e6, initial / 1e6,
                                               total / 1e6, total_low / 1e6))
    posts = [recs[n]["full"]["post"] for n in names if recs[n]["full"].get("post")]
    _log("post step: %d zero-area triangles and %d unused vertices dropped, %d kept on black vertex-colour corners; "
         "%d float UV sets rounded (max %.2g); vertex streams %s" % (
             sum(s["trisDropped"] for s in posts), sum(s["vertsDropped"] for s in posts),
             sum(s["vcKept"] for s in posts), sum(s["uvAccessors"] for s in posts),
             max([s["uvMaxErr"] for s in posts] or [0]),
             {k: sum((recs[n]["full"].get("codecs") or {}).get(k, 0) for n in names)
              for k in sorted({k for n in names for k in (recs[n]["full"].get("codecs") or {})})}))
    _log("hotspots: %d with nodes found, meta-only %s, in files but not in meta %s" % (
        len([h for h in meta.get("hotspots", []) if h.get("node")]) - len(hs_missing), meta_only, hs_extra))
    _log("over budget: %s" % (over or "none"))
    _log("PROBLEMS: %d%s" % (len(problems), "".join("\n  - " + p for p in problems[:60])))
    removed = []
    installed = False
    if not problems and not a.no_install:
        removed = install_full(stage, man, a)
        installed = True
        _log("installed into %s; removed %s" % (FULL_CLIENT, removed or "nothing"))
    elif problems:
        _log("NOT installed: fix the problems first")
    else:
        _log("NOT installed (--no-install): the page still serves the files already in %s" % FULL_CLIENT)
    summary = dict(total_bytes=total, total_bytes_low=total_low, data_bytes=data_bytes, initial_bytes=initial,
                   global_bytes=man["globalBytes"], global_tris=man["globalTris"],
                   chunk_tris=sum(c["tris"] for c in man["chunks"]), over_budget=over, problems=problems,
                   hotspots_missing=hs_missing, hotspots_wrong_chunk=hs_wrong, hotspots_meta_only=meta_only,
                   hotspots_not_in_meta=hs_extra, installed=installed, removed=removed, budget=BUDGET,
                   quality=a.quality, codec=a.codec, uv_bits=UV_BITS,
                   tris_dropped=sum(s["trisDropped"] for s in posts), seconds=round(time.time() - t_all, 1))
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(dict(files=recs, manifest=man, summary=summary), fh, indent=1)
    _log("work files (packed GLBs before gzip) kept in %s for --only / --check-only re-runs" % FULL_TMP)
    _log("done in %.0f s" % (time.time() - t_all))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
