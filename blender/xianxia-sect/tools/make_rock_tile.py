"""Round 60: a seamless cliff-rock tile cut from Poly Haven's mountainside model skin (CC0), for the rock photo
layer (materials.ROCK_SCANS). PC only, with PIL, numpy and scipy. It never runs Blender. Run from anywhere:

    python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/make_rock_tile.py
    python .../make_rock_tile.py --gain 1.35 --name mtn_cliff_hc

The skin is a UV atlas, so it does not tile as it ships. From one clean square of it (CROP: 704 px, about 2.7 m of
rock, one UV island) the tool:
 1. puts the mesh's normals and real up into the crop's pixels (raster_mesh);
 2. divides out the light baked into the photo, fitted on those normals (delight);
 3. integrates the GL normal map to a height (height_from_normals), after checking its green sign (green_sign);
 4. turns colour and height by the 90 degree step that brings real up closest to image up (measure_up, turn);
 5. wraps both onto themselves along one min-cut seam, across then down (wrap_mincut);
 6. flattens what is larger than tile/5, takes out the green specks and scales the log contrast (flatten,
    despeckle_green, log_gain);
 7. enlarges to 4096 px with wrap-around Lanczos and writes the 4k sources to <assets>/derived/<name>/, then the
    2048 px box copies to assets/web by prep_textures.mjs's rules (upscale_wrap, write_box_copy).
It writes a JSON report and sheets (2x2, 3x3, a 60 m wall through an emulation of materials._photo_mix) to
out/tmp/r60/tile, and exits 1 when a gate fails: seams, repeat score, half-tile gaps, light fit, green share or
file sizes. When only the repeat score fails, it retries once with a harder flatten (tile/8, strength 1.0).

The height does not depend on --gain or the flatten, so every run writes the same <disp-name>_disp files (left as
they are when the bytes match). assets/web and assets/derived are git-ignored: the tile is rebuilt from CROP.
"""
import argparse
import hashlib
import io
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # blender/xianxia-sect of this checkout
ASSETS = "E:/Github/PortfolioV5/blender/xianxia-sect/assets"           # the downloaded sources (main checkout)
WEB_OUT = os.path.join(ROOT, "assets", "web")                          # what rblender.py uploads (git-ignored)
OUT_DIR = os.path.join(ROOT, "out", "tmp", "r60", "tile")

SRC_DIFF = "polyhaven/mountainside/textures/mountainside_diff_4k.jpg"
SRC_NOR = "polyhaven/mountainside/textures/mountainside_nor_gl_4k.jpg"
SRC_GLTF = "polyhaven/mountainside/mountainside_4k.gltf"
SRC_PX = 4096                         # the skin's size: glTF UV (0, 0) is its top-left pixel
CROP = (2432, 1648, 3136, 2352)       # left, top, right, bottom in SRC_PX pixels: 704 px inside one island
MARBLE = "polyhaven/marble_cliff_06/marble_cliff_06_diff_4k.jpg"   # today's rock photo, the reference

TILE_M = 8.14                         # the scene tile the sheets and the relief assume (materials.ROCK_SCANS)
OUT_PX = 4096                         # the derived 4k source
LUMA = np.array([0.2126, 0.7152, 0.0722])
LOG_EPS = 0.004                       # log2(Y + eps), as prep_textures.mjs: keeps black crevices finite
FLATTEN = (5.0, 0.85)                 # blur sigma = tile / [0], strength [1]
FLATTEN_HARD = (8.0, 1.0)             # the one retry when the repeat score fails
NZ_MIN = 0.2                          # normal z floor when slopes are read from the normal map

# box copies: prep_textures.mjs JPG_PX, JPG_QUALITY, JPG_MAX_BYTES and PAD_OUT (lines 82-84, 121)
BOX_PX = 2048
JPG_QUALITY = 90
JPG_MIN_QUALITY = 70
JPG_MAX_BYTES = 5e6                   # rblender.py uploads files under 5 MB only
PAD_OUT = 16                          # wrap padding in output pixels
SRC_QUALITY = 95                      # the 4k sources

# gates
SEAM_MAX = 1.2                        # wrap seam over the mean step inside (about 1 when seamless)
GAP_MAX = 0.17                        # half-tile log brightness gap, stops (marble_cliff_06's left-right gap)
R2_MAX = 0.02                         # share of log brightness the mesh normals still explain
GREEN_MAX = 0.001                     # share of green pixels

# materials._photo_mix as the bake uses it on rock (ROCK_SCAN_MIX, ROCK_SCAN_HUE) on palette rock_light
SIM_MIX = 0.6
SIM_HUE = 0.55
SIM_ROCK = "#8a8172"


def log(*a):
    print("TILE", *a, flush=True)


def _below_normal():
    """The owner uses this PC while it runs: below-normal priority on Windows (nothing elsewhere)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        pass


# ============================================================ colour helpers

def lin(a):
    """sRGB 0-255 -> linear 0-1."""
    a = np.asarray(a, np.float64) / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def srgb(x):
    """Linear 0-1 -> sRGB 0-255 as floats (not rounded)."""
    x = np.clip(np.asarray(x, np.float64), 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055) * 255.0


def u8(x):
    return np.clip(np.round(x), 0, 255).astype(np.uint8)


def lum(T):
    return np.asarray(T, np.float64) @ LUMA


def log_lum(T):
    return np.log2(lum(T) + LOG_EPS)


def green_mask(T):
    """Green pixels of a linear RGB image (the design's test: G 5 % over R and 20 % over B)."""
    return (T[..., 1] > T[..., 0] * 1.05) & (T[..., 1] > T[..., 2] * 1.2)


# ============================================================ (a) the mesh in the crop

def _gltf_mesh(path):
    """POSITION, NORMAL, TEXCOORD_0 and triangle indices of the glTF's one mesh, checked to sit untransformed
    in the world (glTF +Y is up)."""
    with open(path, encoding="utf-8") as fh:
        g = json.load(fh)
    if len(g["meshes"]) != 1 or len(g["meshes"][0]["primitives"]) != 1:
        raise SystemExit("TILE FAIL %s: expected one mesh with one primitive" % path)
    for n in g.get("nodes", []):
        if "mesh" in n and any(k in n for k in ("matrix", "rotation", "scale")):
            raise SystemExit("TILE FAIL %s: the mesh node is rotated or scaled; world up is not glTF +Y" % path)
    with open(os.path.join(os.path.dirname(path), g["buffers"][0]["uri"]), "rb") as fh:
        buf = fh.read()

    def acc(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[a["type"]]
        dt = np.dtype({5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a["componentType"]])
        if bv.get("byteStride", n * dt.itemsize) != n * dt.itemsize:
            raise SystemExit("TILE FAIL %s: interleaved buffers are not read here" % path)
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        x = np.frombuffer(buf, dt, a["count"] * n, off)
        return x.reshape(a["count"], n) if n > 1 else x

    prim = g["meshes"][0]["primitives"][0]
    at = prim["attributes"]
    return (acc(at["POSITION"]).astype(np.float64), acc(at["NORMAL"]).astype(np.float64),
            acc(at["TEXCOORD_0"]).astype(np.float64), acc(prim["indices"]).reshape(-1, 3))


def raster_mesh(gltf_path, box, size=SRC_PX):
    """The mesh's world normals and its world metres per image pixel along x and y, rasterised into the crop
    ``box`` of the size x size skin. -> dict(nrm, dpdx, dpdy (H, W, 3), cov (H, W) bool, triangles)."""
    P, N, UV, I = _gltf_mesh(gltf_path)
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    px = UV * size
    tu = px[I]
    mn, mx = tu.min(1), tu.max(1)
    sel = (mx[:, 0] >= x0) & (mn[:, 0] <= x1) & (mx[:, 1] >= y0) & (mn[:, 1] <= y1)
    nrm = np.zeros((H, W, 3))
    dpdx = np.zeros((H, W, 3))
    dpdy = np.zeros((H, W, 3))
    cov = np.zeros((H, W), bool)
    for t in I[sel]:
        a, b, c = px[t]
        e1, e2 = b - a, c - a
        det = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(det) < 1e-9:
            continue
        q1, q2 = P[t[1]] - P[t[0]], P[t[2]] - P[t[0]]
        inv = np.array([[e2[1], -e2[0]], [-e1[1], e1[0]]]) / det
        gx = inv[0, 0] * q1 + inv[1, 0] * q2      # world metres per pixel along image x
        gy = inv[0, 1] * q1 + inv[1, 1] * q2      # and along image y (rows, going down)
        xs = np.arange(max(int(np.floor(min(a[0], b[0], c[0]))), x0), min(int(np.ceil(max(a[0], b[0], c[0]))), x1))
        ys = np.arange(max(int(np.floor(min(a[1], b[1], c[1]))), y0), min(int(np.ceil(max(a[1], b[1], c[1]))), y1))
        if not len(xs) or not len(ys):
            continue
        cx, cy = np.meshgrid(xs + 0.5, ys + 0.5)
        rx, ry = cx - a[0], cy - a[1]
        l1 = (rx * e2[1] - ry * e2[0]) / det
        l2 = (e1[0] * ry - e1[1] * rx) / det
        l0 = 1.0 - l1 - l2
        inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not inside.any():
            continue
        nn = l0[..., None] * N[t[0]] + l1[..., None] * N[t[1]] + l2[..., None] * N[t[2]]
        yy, xx = np.nonzero(inside)
        Yi, Xi = ys[yy] - y0, xs[xx] - x0
        nrm[Yi, Xi] = nn[yy, xx]
        dpdx[Yi, Xi] = gx
        dpdy[Yi, Xi] = gy
        cov[Yi, Xi] = True
    nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-9)
    return dict(nrm=nrm, dpdx=dpdx, dpdy=dpdy, cov=cov, triangles=int(sel.sum()))


# ============================================================ (b) baked light

def light_fit(col, nrm, cov):
    """log2(Y + eps) ~ c0 + c . n over the covered pixels -> (fit over the whole image, coef, R2)."""
    L = log_lum(col)
    m = cov & (np.linalg.norm(nrm, axis=-1) > 0.5)
    X = np.c_[np.ones(int(m.sum())), nrm[m]]
    coef, *_ = np.linalg.lstsq(X, L[m], rcond=None)
    pred = X @ coef
    r2 = 1.0 - ((L[m] - pred) ** 2).sum() / max(((L[m] - L[m].mean()) ** 2).sum(), 1e-12)
    fit = np.full(L.shape, pred.mean())
    fit[m] = pred
    return fit, coef, float(r2)


def delight(col, nrm, cov):
    """Divide the light the mesh's own facets explain out of linear colour ``col``: col / 2^(fit - mean(fit)).
    -> (colour, info with R2 before and after and the half-tile gaps before and after, in stops)."""
    fit, coef, r2 = light_fit(col, nrm, cov)
    out = col * (2.0 ** -(fit - fit.mean()))[..., None]
    _, _, r2_after = light_fit(out, nrm, cov)
    d = coef[1:] / max(float(np.linalg.norm(coef[1:])), 1e-12)
    gb, ga = half_gaps(log_lum(col)), half_gaps(log_lum(out))
    return out, dict(r2_before=round(r2, 4), r2_after=round(r2_after, 4),
                     stops_per_unit_normal=round(float(np.linalg.norm(coef[1:])), 3),
                     light_dir_gltf=[round(float(v), 3) for v in d],
                     light_elevation_deg=round(float(np.degrees(np.arcsin(np.clip(d[1], -1, 1)))), 1),
                     gaps_before=gb, gaps_after=ga)


# ============================================================ (c) height from the normal map

def normals_from_rgb(rgb):
    """A normal map's 0-255 pixels -> vectors -1..1."""
    return np.asarray(rgb, np.float64) / 255.0 * 2.0 - 1.0


def slopes(nor, sign=1.0):
    """dz/dx and dz/d(row) of normal vectors ``nor``, in height pixels per pixel. Rows go down and GL green points
    up the image, so q = +ny / nz for a GL map (sign 1) and -ny / nz for a DX map."""
    nz = np.clip(nor[..., 2], NZ_MIN, 1.0)
    return -nor[..., 0] / nz, sign * nor[..., 1] / nz


def curl_residual(nor, sign):
    """How far the slopes read with green ``sign`` are from being a gradient: rms curl over rms slope change."""
    p, q = slopes(nor, sign)
    dpy, dqx = np.gradient(p, axis=0), np.gradient(q, axis=1)
    return float((dpy - dqx).std() / max(float(np.hypot(dpy, dqx).std()), 1e-12))


def green_sign(nor):
    """-> (sign with the lower curl residual, residual for GL, residual for DX)."""
    gl, dx = curl_residual(nor, 1.0), curl_residual(nor, -1.0)
    return (1.0 if gl <= dx else -1.0), gl, dx


def _fc(p, q):
    """Frankot-Chellappa: the periodic height whose gradient is closest to (p, q)."""
    H, W = p.shape
    WX, WY = np.meshgrid(np.fft.fftfreq(W) * 2 * np.pi, np.fft.fftfreq(H) * 2 * np.pi)
    den = WX ** 2 + WY ** 2
    den[0, 0] = 1.0
    Z = (-1j * WX * np.fft.fft2(p) - 1j * WY * np.fft.fft2(q)) / den
    Z[0, 0] = 0.0
    return np.real(np.fft.ifft2(Z))


def height_from_normals(nor, sign=1.0, highpass=None, clamp=(1.0, 99.0), mirror=True):
    """Height (in pixels) integrated from normal vectors ``nor`` with Frankot-Chellappa. ``mirror``: integrate the
    image mirrored into a 2 x 2 block, so a crop that does not tile gets no edge ripple. ``highpass``: drop what
    is larger than this blur sigma (px). ``clamp``: percentiles that cut the integration's spikes."""
    p, q = slopes(nor, sign)
    H, W = p.shape
    if mirror:
        pe = np.block([[p, -p[:, ::-1]], [p[::-1, :], -p[::-1, ::-1]]])
        qe = np.block([[q, q[:, ::-1]], [-q[::-1, :], -q[::-1, ::-1]]])
        z = _fc(pe, qe)[:H, :W]
    else:
        z = _fc(p, q)
    if highpass:
        z = z - gaussian_filter(z, highpass, mode="reflect")
    if clamp:
        lo, hi = np.percentile(z, clamp)
        z = np.clip(z, lo, hi)
    return z - z.mean()


# ============================================================ (d) which way is up

def wrap180(a):
    return (np.asarray(a, np.float64) + 180.0) % 360.0 - 180.0


def measure_up(r):
    """Real up (world +Y) as the image sees it: degrees clockwise from image up, median over the covered pixels
    where up does not point into the face. Also the crop's pixels per metre. -> dict."""
    cov = r["cov"]
    lx = np.linalg.norm(r["dpdx"], axis=-1)[cov]
    ly = np.linalg.norm(r["dpdy"], axis=-1)[cov]
    rt = r["dpdx"][cov] / np.maximum(lx, 1e-12)[:, None]      # image right, in the world
    up = -r["dpdy"][cov] / np.maximum(ly, 1e-12)[:, None]     # image up (rows go down)
    a, b = rt[:, 1], up[:, 1]                                 # world up along image right and image up
    keep = np.hypot(a, b) > 0.3
    ang = np.degrees(np.arctan2(a[keep], b[keep]))
    m = np.degrees(np.arctan2(np.sin(np.radians(ang)).mean(), np.cos(np.radians(ang)).mean()))
    rel = wrap180(ang - m)
    return dict(angle_deg=round(float(wrap180(m + np.median(rel))), 1),
                p10_deg=round(float(wrap180(m + np.percentile(rel, 10))), 1),
                p90_deg=round(float(wrap180(m + np.percentile(rel, 90))), 1),
                share_used=round(float(keep.mean()), 3),
                px_per_m_x=round(float(np.median(1.0 / np.maximum(lx, 1e-12))), 1),
                px_per_m_y=round(float(np.median(1.0 / np.maximum(ly, 1e-12))), 1))


def pick_turn(angle_deg):
    """k for np.rot90 (k quarter turns counter-clockwise) that brings real up, ``angle_deg`` clockwise of image up,
    closest to image up. -> (k, leftover degrees clockwise of image up)."""
    left = [float(wrap180(angle_deg - 90.0 * k)) for k in range(4)]
    k = int(np.argmin(np.abs(left)))
    return k, left[k]


def turn(k, *imgs):
    """Every image turned by the same k quarter turns counter-clockwise (np.rot90 in the image plane). A height
    map turns as it is; a normal map would need its x and y fixed, so the tool never turns one."""
    return [np.ascontiguousarray(np.rot90(x, k, axes=(0, 1))) for x in imgs]


# ============================================================ (e) the seamless wrap

def _mincut_cols(err, cyclic=False):
    """The top-to-bottom path through ``err`` (rows x band) of least summed error, moving at most one column a
    row: one column per row. ``cyclic``: the rows wrap (the image already tiles that way), so the last row's
    column must also sit within one of the first row's; every start column is tried at once."""
    h, w = err.shape
    big = np.inf
    if not cyclic:
        c = err[None, 0].copy()
    else:
        c = np.full((w, w), big)
        c[np.arange(w), np.arange(w)] = err[0]              # c[start, column]
    step = np.zeros((h, c.shape[0], w), np.int8)            # -1, 0, +1: where each cell came from
    pad = np.full((c.shape[0], 1), big)
    for i in range(1, h):
        cand = np.stack([np.hstack([pad, c[:, :-1]]), c, np.hstack([c[:, 1:], pad])])   # from j-1, j, j+1
        k = np.argmin(cand, axis=0)
        step[i] = k - 1
        c = np.take_along_axis(cand, k[None], 0)[0] + err[i][None, :]
    if not cyclic:
        s, j = 0, int(np.argmin(c[0]))
    else:
        cols = np.arange(w)
        ok = np.abs(cols[None, :] - cols[:, None]) <= 1      # end within one of the start
        s, j = np.unravel_index(int(np.argmin(np.where(ok, c, big))), c.shape)
    path = np.zeros(h, np.int32)
    path[-1] = j
    for i in range(h - 1, 0, -1):
        path[i - 1] = path[i] + step[i, s, path[i]]
    return path


def _wrap_across(imgs, ov, gi, cyclic=False):
    """One horizontal wrap: N columns -> N - ov, the last ov columns laid over the first along a min-cut found
    on imgs[gi]. The penalty keeps the path off the band's edges, so the tile's edge is a plain continuation.
    ``cyclic``: the images already tile top to bottom, and the path and its blur wrap that way too."""
    S = imgs[gi]
    M = S.shape[1] - ov
    err = ((S[:, M:] - S[:, :ov]) ** 2).sum(-1)
    err = err + (np.abs(np.arange(ov) - ov / 2.0) / (ov / 2.0))[None, :] ** 6 * err.mean() * 4
    path = _mincut_cols(err, cyclic)
    mask = gaussian_filter((np.arange(ov)[None, :] < path[:, None]).astype(np.float64), 1.5,
                           mode=["wrap" if cyclic else "reflect", "reflect"])[..., None]
    outs = []
    for X in imgs:
        Hx = X[:, :M].copy()
        Hx[:, :ov] = mask * X[:, M:] + (1.0 - mask) * X[:, :ov]
        outs.append(Hx)
    return outs, path


def wrap_mincut(imgs, ov, guide=None):
    """Toroidal min-cut wrap of square images ``imgs`` (H x W or H x W x C), across then down, every image along
    the same cuts. The cuts are found on ``guide`` (default imgs[0]). -> (images, (path across, path down))."""
    g = np.asarray(imgs[0] if guide is None else guide, np.float64)
    work = [np.asarray(x, np.float64) for x in imgs] + [g]
    flat = [x.ndim == 2 for x in work]
    work = [x[..., None] if f else x for x, f in zip(work, flat)]
    gi = len(work) - 1
    h, p1 = _wrap_across(work, ov, gi)
    # down: the columns already tile, so the second cut must meet itself across the tile's left-right edge
    v, p2 = _wrap_across([np.transpose(x, (1, 0, 2)) for x in h], ov, gi, cyclic=True)
    outs = [np.transpose(x, (1, 0, 2)) for x in v]
    outs = [x[..., 0] if f else x for x, f in zip(outs, flat)]
    return outs[:-1], (p1, p2)


def _grey(a):
    L = np.asarray(a, np.float64)
    return L @ LUMA if L.ndim == 3 else L


def seam_ratio(a):
    """Seam ratio (across, down): the mean step across the wrap edge over the mean step of the column (row) pairs
    d = 1/64 to 1/16 of the tile from the edge on both sides, in the same rows (columns). About 1 for a seamless
    tile. The neighbours sit past an enlargement's smear, and being near the edge they share its slope, so rock
    that is simply steep at the edge does not read as a seam. When the size is a multiple of 8 (a JPEG), only
    pairs on the 8 px block grid count, as the edge is always a block boundary and JPEG steps those up (by about
    a quarter at q90). ``a``: grey H x W, or RGB H x W x 3 (luminance)."""
    L = _grey(a)

    def one(X):
        w = X.shape[1]
        ds = [d for d in range(max(1, w // 64), max(2, w // 16)) if w % 8 or d % 8 == 0]
        near = [np.abs(X[:, d] - X[:, d - 1]).mean() for d in ds]          # pair (d-1 | d) by the left edge
        near += [np.abs(X[:, w - d] - X[:, w - d - 1]).mean() for d in ds]  # pair (w-d-1 | w-d) by the right
        return float(np.abs(X[:, 0] - X[:, -1]).mean() / max(float(np.mean(near)), 1e-12))
    return round(one(L), 3), round(one(L.T), 3)


def seam_ratio_global(a):
    """The design's seam ratio (across, down): the mean step across the wrap edge over the mean step of every
    neighbouring pair in the tile. It also reads a steep patch at the edge as a seam."""
    L = _grey(a)
    across = np.abs(L[:, 0] - L[:, -1]).mean() / max(float(np.abs(np.diff(L, axis=1)).mean()), 1e-12)
    down = np.abs(L[0] - L[-1]).mean() / max(float(np.abs(np.diff(L, axis=0)).mean()), 1e-12)
    return round(float(across), 3), round(float(down), 3)


# ============================================================ (f-h) flatten, green, contrast

def flatten(T, sigma, strength):
    """Take out what is larger than ``sigma`` px: linear colour times (mean / wrap-around blur of luminance) ^
    strength, then rescaled so the mean linear luminance is kept."""
    L = lum(T)
    B = gaussian_filter(L, sigma, mode="wrap")
    out = T * ((L.mean() / np.maximum(B, 1e-4)) ** strength)[..., None]
    return out * (L.mean() / max(float(lum(out).mean()), 1e-12))


def despeckle_green(T, sigma=16.0):
    """Pull green and grey-green pixels to the hue of the rock around them, keeping their luminance. The weight is
    1 for green pixels (green_mask) and ramps in as R/G falls from 1.2 to 1.0 (the lichen band). The local hue is
    a blur of the other pixels' chroma (the tile's mean chroma where none are near). -> (colour, info)."""
    Y = np.maximum(lum(T), 1e-6)
    c = T / Y[..., None]
    rg = c[..., 0] / np.maximum(c[..., 1], 1e-6)
    w = np.clip((1.2 - rg) / 0.2, 0.0, 1.0)
    w[green_mask(T)] = 1.0
    keep = 1.0 - w
    den = gaussian_filter(keep, sigma, mode="wrap")
    glob = (c * keep[..., None]).reshape(-1, 3).sum(0) / max(float(keep.sum()), 1e-9)
    loc = np.stack([gaussian_filter(c[..., i] * keep, sigma, mode="wrap") for i in range(3)], -1)
    loc = loc / np.maximum(den, 1e-6)[..., None]
    a = np.clip(den / 0.2, 0.0, 1.0)[..., None]                 # too few rock pixels near: the tile's mean hue
    loc = a * loc + (1.0 - a) * glob
    loc = loc / np.maximum(loc @ LUMA, 1e-6)[..., None]          # luminance 1, so Y stays
    c2 = c + w[..., None] * (loc - c)
    out = c2 * Y[..., None]
    return out, dict(green_before=round(float(green_mask(T).mean()), 5),
                     green_after=round(float(green_mask(out).mean()), 5),
                     weighted_share=round(float(w.mean()), 4))


def log_gain(T, g):
    """Scale log luminance around its mean (the geometric mean) by ``g``; hue kept."""
    Y = np.maximum(lum(T), 1e-6)
    L = np.log2(Y)
    Y2 = 2.0 ** (L.mean() + g * (L - L.mean()))
    return T * (Y2 / Y)[..., None]


# ============================================================ (i-j) enlarge and write

def upscale_wrap(a, out_px, pad=PAD_OUT):
    """Square tile ``a`` (H x W or H x W x C floats) enlarged to out_px with Lanczos, padded with its own wrap
    first so the result tiles too (the filter reads across the edge)."""
    a = np.asarray(a, np.float32)
    flat = a.ndim == 2
    if flat:
        a = a[..., None]
    n = a.shape[0]
    p = np.pad(a, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")
    chans = [np.asarray(Image.fromarray(np.ascontiguousarray(p[..., i]))      # float32: mode F
                        .resize((out_px, out_px), Image.LANCZOS, box=(pad, pad, pad + n, pad + n)), np.float32)
             for i in range(a.shape[2])]
    out = np.stack(chans, -1)
    return out[..., 0] if flat else out


def jpeg_bytes(im, quality, subsampling):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=subsampling, optimize=True)
    return buf.getvalue()


def write_file(path, data):
    """Write ``data`` atomically; leave the file alone when it already holds these bytes. -> 'written' or
    'unchanged'."""
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            if fh.read() == data:
                return "unchanged"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "wb") as fh:
        fh.write(data)
    os.replace(path + ".part", path)
    return "written"


def write_box_copy(src, dst, kind):
    """prep_textures.mjs's box copy of a 4k tile: an exact integer shrink to BOX_PX with wrap padding (Lanczos),
    JPEG q90 stepping down by 4 to q70 until under 5 MB; 'grey' is one channel. -> dict."""
    im = Image.open(src)
    im = im.convert("L" if kind == "grey" else "RGB")
    f = im.width / BOX_PX
    if f != int(f) or im.height / BOX_PX != f:
        raise SystemExit("TILE FAIL %s: %dx%d -> %d is not one integer shrink" % (src, im.width, im.height, BOX_PX))
    pad = PAD_OUT * int(f)
    a = np.asarray(im)
    a = np.pad(a, ((pad, pad), (pad, pad)) + (((0, 0),) if a.ndim == 3 else ()), mode="wrap")
    small = Image.fromarray(a).resize((BOX_PX, BOX_PX), Image.LANCZOS, box=(pad, pad, pad + im.width, pad + im.height))
    q = JPG_QUALITY
    while True:
        data = jpeg_bytes(small, q, 2)      # 4:2:0, as sharp writes
        if len(data) < JPG_MAX_BYTES or q <= JPG_MIN_QUALITY:
            break
        q -= 4
    return dict(state=write_file(dst, data), quality=q, bytes=len(data), md5=hashlib.md5(data).hexdigest())


def decode(path, mode):
    with Image.open(path) as im:
        return np.asarray(im.convert(mode))


# ============================================================ measures

def half_gaps(L):
    """Mean log brightness of the left half minus the right half, and top minus bottom, in stops (the tile's own
    phase); and the largest such gap over every cyclic split (any phase)."""
    n, m = L.shape
    lr = L[:, : m // 2].mean() - L[:, m // 2:].mean()
    tb = L[: n // 2].mean() - L[n // 2:].mean()

    def worst(p):
        h = len(p) // 2
        cs = np.cumsum(np.r_[0.0, p, p])
        a = (cs[h: h + len(p)] - cs[: len(p)]) / h
        b = (p.sum() - a * h) / (len(p) - h)
        return float(np.abs(a - b).max())
    return dict(lr=round(float(lr), 3), tb=round(float(tb), 3),
                worst_lr=round(worst(L.mean(0)), 3), worst_tb=round(worst(L.mean(1)), 3))


def repeat_score(L):
    """Std of a tile/4 wrap-around blur of log brightness: how strongly the tile's biggest blobs repeat."""
    return round(float(gaussian_filter(L, L.shape[0] / 4.0, mode="wrap").std()), 4)


def bands(T, tile_m=TILE_M):
    """The page's view of a linear tile at tile_m: log brightness spread per scale band and prep_textures.mjs's
    band normaliser bandK (0.12 / std of the 0.12-1.0 m band) and R k, on a 1024 px copy."""
    L = log_lum(T)
    pxm = L.shape[0] / tile_m
    blur = {s: gaussian_filter(L, s * pxm, mode="wrap") for s in (0.03, 0.12, 0.5, 1.0, 3.0)}
    blur[0.0] = L
    out = {}
    for lo, hi in ((0.0, 0.03), (0.03, 0.12), (0.12, 0.5), (0.5, 1.0), (1.0, 3.0)):
        out["std_stops_%g_to_%gm" % (lo, hi)] = round(float((blur[lo] - blur[hi]).std()), 3)
    b12, b100 = blur[0.12], blur[1.0]
    out["std_stops_total"] = round(float(L.std()), 3)
    out["bandK"] = round(0.12 / float((b12 - b100).std()), 4)
    out["page_full_gain"] = round(0.732 / out["bandK"], 3)
    out["R_k"] = round(0.12 / float((L - b12).std()), 4)
    return out


def hex_lin(h):
    return lin([int(h[i: i + 2], 16) for i in (1, 3, 5)])


def photo_mix(T):
    """materials._photo_mix on a flat rock_light albedo (MIX 0.6, CONTRAST 1, HUE 0.55; rel = photo over its mean
    luminance, as scan_mean does)."""
    rel = T / lum(T).mean()
    col = hex_lin(SIM_ROCK)
    shade = 1.0 + SIM_MIX * (lum(rel) - 1.0)
    w = SIM_MIX * SIM_HUE
    return (1.0 - w) * col * shade[..., None] + w * rel * float(col @ LUMA)


def wall(T_srgb8, tile_m, wall_w, out_w=1600, out_h=900):
    """A flat wall wall_w metres across covered with the tile, through photo_mix. -> PIL image."""
    tp = max(8, int(round(tile_m * out_w / wall_w)))
    t = np.asarray(Image.fromarray(T_srgb8).resize((tp, tp), Image.LANCZOS), np.float64)
    big = np.tile(photo_mix(lin(t)), (out_h // tp + 2, out_w // tp + 2, 1))[:out_h, :out_w]
    return Image.fromarray(u8(srgb(big)))


def md5_size(path):
    with open(path, "rb") as fh:
        b = fh.read()
    return dict(md5=hashlib.md5(b).hexdigest(), bytes=len(b))


# ============================================================ the run

def make_colour(col_w, tile_px, flat, gain):
    T = flatten(col_w, tile_px / flat[0], flat[1])
    T, green = despeckle_green(T)
    return log_gain(T, gain), green


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assets", default=ASSETS, help="the downloaded sources (polyhaven/...); derived/ is written here")
    ap.add_argument("--web-out", default=WEB_OUT, help="where the 2048 px box copies go")
    ap.add_argument("--out-dir", default=OUT_DIR, help="report and sheets")
    ap.add_argument("--gain", type=float, default=1.0, help="log contrast gain (1.35 for the _hc tile)")
    ap.add_argument("--name", default="mtn_cliff", help="file stem of the colour tile")
    ap.add_argument("--disp-name", default="mtn_cliff", help="file stem of the height tile (shared by every gain)")
    ap.add_argument("--flatten", default="%g,%g" % FLATTEN, help="'tile divisor,strength' of the flatten")
    args = ap.parse_args(argv)
    _below_normal()
    flat = tuple(float(v) for v in args.flatten.split(","))
    A = args.assets
    os.makedirs(args.out_dir, exist_ok=True)
    gates = []

    def gate(name, value, limit, ok):
        gates.append(dict(gate=name, value=value, limit=limit, ok=bool(ok)))

    # ---- sources
    with Image.open(os.path.join(A, SRC_DIFF)) as im:
        if im.size != (SRC_PX, SRC_PX):
            raise SystemExit("TILE FAIL %s is %s, not %d px" % (SRC_DIFF, im.size, SRC_PX))
        col = lin(np.asarray(im.convert("RGB").crop(CROP)))
    with Image.open(os.path.join(A, SRC_NOR)) as im:
        nor = normals_from_rgb(np.asarray(im.convert("RGB").crop(CROP)))
    N = col.shape[0]
    ov = N // 6
    tile_px = N - ov
    log("crop %s: %d px, wrap overlap %d, tile %d px" % (CROP, N, ov, tile_px))

    # ---- (a) mesh, (d) up
    r = raster_mesh(os.path.join(A, SRC_GLTF), CROP)
    up = measure_up(r)
    k, left = pick_turn(up["angle_deg"])
    pxm = 0.5 * (up["px_per_m_x"] + up["px_per_m_y"])
    real_m = tile_px / pxm
    mag = TILE_M / real_m
    log("mesh: %d triangles, coverage %.3f; %.0f x %.0f px/m; real up %.1f deg clockwise of image up (p10 %.1f, "
        "p90 %.1f); turn k=%d (counter-clockwise), %.1f deg left" % (
            r["triangles"], r["cov"].mean(), up["px_per_m_x"], up["px_per_m_y"], up["angle_deg"], up["p10_deg"],
            up["p90_deg"], k, left))
    log("tile %.2f m of real rock; at %.2f m it is magnified %.2f times" % (real_m, TILE_M, mag))

    # ---- (b) light
    col_dl, light = delight(col, r["nrm"], r["cov"])
    log("light: R2 %.3f -> %.3f; light from %s (glTF, elevation %.0f deg); crop gaps lr %.3f -> %.3f, tb %.3f -> "
        "%.3f stops" % (light["r2_before"], light["r2_after"], light["light_dir_gltf"], light["light_elevation_deg"],
                        light["gaps_before"]["lr"], light["gaps_after"]["lr"], light["gaps_before"]["tb"],
                        light["gaps_after"]["tb"]))

    # ---- (c) height
    sign, curl_gl, curl_dx = green_sign(nor)
    log("normal map curl residual: GL %.3f, DX %.3f" % (curl_gl, curl_dx))
    gate("normal map reads as GL (curl GL < DX)", [round(curl_gl, 3), round(curl_dx, 3)], "GL lower", sign > 0)
    if sign < 0:
        _finish(args, gates, dict(error="normal map green sign"))
    z = height_from_normals(nor, 1.0, highpass=tile_px / 5.0, clamp=(1.0, 99.0))

    # ---- (d) turn, (e) wrap: one cut for colour, height and the mesh normals
    col_t, z_t, nrm_t, cov_t = turn(k, col_dl, z, r["nrm"], r["cov"].astype(np.float64))
    rel = col_t / lum(col_t).mean()
    guide = np.concatenate([rel, (z_t / max(float(z_t.std()), 1e-9) * float(lum(rel).std()))[..., None]], -1)
    (col_w, z_w, nrm_w, cov_w), _ = wrap_mincut([col_t, z_t, nrm_t, cov_t], ov, guide)

    # ---- (f-h) colour, with the one retry on the repeat score
    marble = lin(np.asarray(Image.open(os.path.join(A, MARBLE)).convert("RGB").resize((1024, 1024), Image.LANCZOS)))
    Lm = log_lum(marble)
    marble_repeat = repeat_score(Lm)
    marble_gaps = half_gaps(Lm)
    used = flat
    T, green = make_colour(col_w, tile_px, flat, args.gain)
    rs = repeat_score(log_lum(T))
    log("flatten tile/%g strength %g: repeat score %.4f (marble %.4f)" % (flat[0], flat[1], rs, marble_repeat))
    retried = False
    if rs > marble_repeat and flat != FLATTEN_HARD:
        retried = True
        used = FLATTEN_HARD
        T, green = make_colour(col_w, tile_px, used, args.gain)
        log("RETRY: repeat score over marble's, flatten again at tile/%g strength %g: %.4f" % (
            used[0], used[1], repeat_score(log_lum(T))))
    m_ok = (cov_w > 0.99) & (np.linalg.norm(nrm_w, axis=-1) > 0.5)
    nrm_u = nrm_w / np.maximum(np.linalg.norm(nrm_w, axis=-1, keepdims=True), 1e-9)
    _, _, r2_final = light_fit(T, nrm_u, m_ok)
    clipped = float((T > 1.0).any(-1).mean())

    # ---- (i) enlarge, (j) write
    zr = (float(z_w.min()), float(z_w.max()))
    relief_m = (zr[1] - zr[0]) / pxm * mag
    zn = (z_w - zr[0]) / max(zr[1] - zr[0], 1e-9)
    diff4 = u8(upscale_wrap(srgb(T), OUT_PX))
    disp4 = u8(upscale_wrap(zn * 255.0, OUT_PX))
    p_diff4 = os.path.join(A, "derived", args.name, "%s_diff_4k.jpg" % args.name)
    p_disp4 = os.path.join(A, "derived", args.disp_name, "%s_disp_4k.jpg" % args.disp_name)
    p_diff = os.path.join(args.web_out, "%s_diff.jpg" % args.name)
    p_disp = os.path.join(args.web_out, "%s_disp.jpg" % args.disp_name)
    files = {}
    files[p_diff4] = dict(state=write_file(p_diff4, jpeg_bytes(Image.fromarray(diff4), SRC_QUALITY, 0)))
    files[p_disp4] = dict(state=write_file(p_disp4, jpeg_bytes(Image.fromarray(disp4), SRC_QUALITY, 0)))
    files[p_diff] = write_box_copy(p_diff4, p_diff, "colour")
    files[p_disp] = write_box_copy(p_disp4, p_disp, "grey")
    for p, info in files.items():
        info.update(md5_size(p))
        log("%-9s %s  %.2f MB  md5 %s%s" % (info["state"], p, info["bytes"] / 1e6, info["md5"],
                                            "  q%d" % info["quality"] if "quality" in info else ""))

    # ---- measures on what was written
    seams = {}
    for p, mode in ((p_diff4, "RGB"), (p_diff, "RGB"), (p_disp4, "L"), (p_disp, "L")):
        a = decode(p, mode)
        s, sg = seam_ratio(a), seam_ratio_global(a)
        seams[os.path.basename(p)] = dict(local=list(s), global_mean=list(sg))
        gate("seam %s (across, down)" % os.path.basename(p), list(s), SEAM_MAX, max(s) <= SEAM_MAX)
        log("seam %s against every step in the tile (the design's measure, not gated): %s" % (
            os.path.basename(p), list(sg)))
    for f, mode in (("marble_cliff_06_diff.jpg", "RGB"), ("marble_cliff_06_disp.jpg", "L")):
        p = os.path.join(args.web_out, f)
        if os.path.isfile(p):       # today's box copies, made by prep: the same measures for reference
            a = decode(p, mode)
            seams["reference " + f] = dict(local=list(seam_ratio(a)), global_mean=list(seam_ratio_global(a)))
            log("seam %s (today's, for reference): %s; against every step %s" % (
                f, list(seam_ratio(a)), list(seam_ratio_global(a))))
    box = decode(p_diff, "RGB")
    box_lin = lin(box)
    T1k = lin(np.asarray(Image.fromarray(box).resize((1024, 1024), Image.LANCZOS)))
    L1k = log_lum(T1k)
    rs = repeat_score(L1k)
    gaps = half_gaps(L1k)
    green_share = float(green_mask(box_lin).mean())
    gate("repeat score (std of a tile/4 blur, stops)", rs, marble_repeat, rs <= marble_repeat)
    gate("half-tile gap left-right (stops)", gaps["lr"], GAP_MAX, abs(gaps["lr"]) <= GAP_MAX)
    gate("half-tile gap top-bottom (stops)", gaps["tb"], GAP_MAX, abs(gaps["tb"]) <= GAP_MAX)
    gate("light-fit R2 on the finished tile", round(r2_final, 4), R2_MAX, r2_final <= R2_MAX)
    gate("green share of the box copy", round(green_share, 5), GREEN_MAX, green_share < GREEN_MAX)
    for p in (p_diff, p_disp):
        gate("size %s (bytes)" % os.path.basename(p), files[p]["bytes"], int(JPG_MAX_BYTES),
             files[p]["bytes"] < JPG_MAX_BYTES)
    Y = lum(box_lin)
    report = dict(
        name=args.name, disp_name=args.disp_name, gain=args.gain, source=SRC_DIFF, crop_box=list(CROP),
        crop_px=N, overlap_px=ov, tile_px=tile_px, real_m=round(real_m, 3), tile_m=TILE_M,
        magnification=round(mag, 3), px_per_m=round(pxm, 1), mesh=dict(triangles=r["triangles"],
                                                                        coverage=round(float(r["cov"].mean()), 4)),
        up=up, turn_k=k, leftover_deg=round(left, 1), light=light, r2_final=round(r2_final, 4),
        normal_curl=dict(gl=round(curl_gl, 3), dx=round(curl_dx, 3)),
        flatten=dict(asked=list(flat), used=list(used), retried_harder=retried), green=green,
        clipped_share=round(clipped, 5),
        relative_rgb=[round(float(v), 3) for v in box_lin.reshape(-1, 3).mean(0) / Y.mean()],
        mean_linear_luminance=round(float(Y.mean()), 4),
        darkest_1pct_over_mean=round(float(np.percentile(Y, 1) / Y.mean()), 3),
        bands=bands(T1k), marble=dict(repeat_score=marble_repeat, gaps=marble_gaps, bands=bands(marble)),
        repeat_score=rs, gaps=gaps, green_share=round(green_share, 5), seams=seams,
        relief_m=round(relief_m, 3), height_px_range=round(zr[1] - zr[0], 2),
        files={os.path.relpath(p, ROOT) if p.startswith(ROOT) else p: v for p, v in files.items()})

    # ---- sheets
    sheets = {}
    s2 = os.path.join(args.out_dir, "%s_2x2.jpg" % args.name)
    Image.fromarray(np.tile(box, (2, 2, 1))).save(s2, quality=90)
    t3 = np.asarray(Image.fromarray(box).resize((1024, 1024), Image.LANCZOS))
    s3 = os.path.join(args.out_dir, "%s_3x3.jpg" % args.name)
    Image.fromarray(np.tile(t3, (3, 3, 1))).save(s3, quality=90)
    sw = os.path.join(args.out_dir, "%s_wall60m.jpg" % args.name)
    wall(box, TILE_M, 60.0).save(sw, quality=90)
    sd = os.path.join(args.out_dir, "%s_disp_2x2.jpg" % args.disp_name)
    d1 = np.asarray(Image.fromarray(decode(p_disp, "L")).resize((1024, 1024), Image.LANCZOS))
    Image.fromarray(np.tile(d1, (2, 2))).save(sd, quality=90)
    sm = os.path.join(args.out_dir, "marble_wall60m.jpg")
    mb = np.asarray(Image.open(os.path.join(A, MARBLE)).convert("RGB").resize((2048, 2048), Image.LANCZOS))
    wall(mb, TILE_M, 60.0).save(sm, quality=90)
    sheets.update(two_by_two=s2, three_by_three=s3, wall_60m=sw, disp_2x2=sd, marble_wall_60m=sm)
    report["sheets"] = sheets
    _finish(args, gates, report)


def _finish(args, gates, report):
    report["gates"] = gates
    path = os.path.join(args.out_dir, "%s_report.json" % args.name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    log("report %s" % path)
    for g in gates:
        log("%-4s %-46s %s (limit %s)" % ("pass" if g["ok"] else "FAIL", g["gate"], g["value"], g["limit"]))
    bad = [g for g in gates if not g["ok"]]
    log("%d of %d gates pass" % (len(gates) - len(bad), len(gates)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
