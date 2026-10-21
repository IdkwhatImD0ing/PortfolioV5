"""Mist that wraps the mountains, for the web fly-through (/sect): Huangshan-style bands of soft cloud
around the peaks at mid-height (the tops float above them; a second, lower band on tall ones), wisps on
the range's own cliffs at mid-height where a hold looks at them, mist pooled in hollows and in the
gorges between pillars, and wisps drifting under (and hugging) the floating islands. Output is more
cloud puffs in clouds.json, so the page's existing puff renderer (soft camera-facing sprites, one
instanced draw) draws it; no client change.

Pure standard library (no bpy, no numpy): it runs with any Python 3.8+ on the PC or on the box, and
inside Blender (export_web.py `clouds --profile full` calls apply() after writing the Blender puffs).

Reads (out/web/full, three.js space: metres, Y up):
  raw/<area>.glb, raw/backdrop.glb  the baked web geometry (not *_trees / *_water), voxelised on an 8 m
                                    grid into mist_voxels.bin (a cache, rebuilt when a GLB changes)
  site/camera.json                  the flight path and holds (clearance, visibility, ranking)
  site/meta.json                    area anchors, footprints and hotspots (kept clear), the cloud sea
  site/clouds.json                  the Blender puffs; mist puffs from an earlier run are dropped first
Writes site/clouds.json = Blender puffs + mist puffs. Each mist puff carries "k": "mist.band",
"mist.gorge" or "mist.isle" (parseClouds ignores it); a "mist" summary sits at the top level.
Re-running replaces the mist (idempotent), never touches the Blender puffs.

    python -I sect/mist.py                      # out/web/full/site/clouds.json
    python -I sect/mist.py --client             # ... and copy it to client/public/sect/full/
    python -I sect/mist.py --dry --report r.json
    python -I sect/mist.py --strip              # remove the mist again

How a puff becomes a sprite on the page (materials.ts createCloudPuffMaterial): the optical depth through
the middle is d * wf * 2 (wf = the puff's half-depth along the view), alpha = 1 - exp(-0.28 * that *
(0.35 + 0.9 noise)), about 1 - exp(-0.45 d wf). So d = tau / (0.45 * half-size) gives a centre opacity
of 1 - exp(-tau) whatever the size. Mist uses tau about 0.6-1.4 (a veil: 45-75 % at the centre, soft
edges), the Blender cumulus 3+ (solid).

Rocks come from the voxels, not from world.py (which needs bpy): peaks are local maxima of the ground
height map (column tops without the floating islands), their pillar is followed down by cross-sections
(the ring of surface cells at each 16 m level, a circle fitted to it) to where it merges with the
ground; floating islands are small connected voxel groups hanging clear of the cloud sea. Puffs keep
off the camera path, the areas and each hold's sight lines to its hotspots, out of the rock, and are
ranked by how big they look from the holds and the path (line of sight tested on the voxels).
"""
import argparse
import array
import collections
import glob
import json
import math
import os
import random
import shutil
import struct
import sys
import time
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, "out", "web", "full")
CLIENT_FULL = "E:/Github/PortfolioV5/client/public/sect/full"

VERSION = 1
GRID = 8.0                  # voxel size (m); the range's own grid is 5 m, peaks are 20-120 m wide
OFF = 1024                  # voxel index offset in x and z (covers +-8 km)
YOFF = 64                   # ... and in y (covers -512 .. +1528 m)
CACHE = "mist_voxels.bin"
SEED = 7
TAG = "mist"

BUDGET = 620                # mist puffs at most (the Blender set has ~750; see the report for fill cost)
CLIENT_KEEP = 2600.0        # the page drops puffs farther than this from its path samples (scene.tsx)
VIEW_MAX = 2400.0           # rank only on views closer than this
MIN_SCORE = 0.03            # group radius / distance in its best view (0.03 = 43 px tall at 900 px)

PATH_CLEAR = 30.0           # puff surface to any camera position (m) ...
PATH_CLEAR_K = 2.4          # ... and its centre at least this many radii away (keeps the screen clear)
AREA_PAD = 22.0             # no mist within an area's footprint + this (2D, within 70 m of its height)
SIGHT_PAD = 0.85            # a hold's sight lines to its hotspots stay clear of puffs (x bounding radius)

PEAK_WIN = 5                # local maximum over +-5 cells (40 m)
PROM_MIN = 45.0             # m above the ring 72-104 m out
SECTORS = 24
MIN_VISIBLE = 55.0          # m of free-standing pillar before a peak gets a band
TOP_FREE = 30.0             # band centre at least this far under the top (the crown stays clear)
BAND_REL = (0.36, 0.6)      # band height between the visible base and the top
TAU = dict(band=1.25, gorge=1.0, isle=0.85)
POOL_WALL = 28.0            # a hollow's walls rise at least this far above its floor


def log(*a):
    print("MIST", *a, flush=True)


# =====================================================================================================
# voxels from the baked GLBs
# =====================================================================================================

def _glb_sources(raw):
    out = []
    for f in sorted(glob.glob(os.path.join(raw, "*.glb"))):
        b = os.path.basename(f)
        if b.endswith("_trees.glb") or b.endswith("_water.glb"):
            continue
        st = os.stat(f)
        out.append((b, st.st_size, int(st.st_mtime)))
    return out


def _voxelise_glb(path, occ, grid):
    """Adds the voxels of every non-glow primitive's vertices, plus samples on triangles longer than a
    voxel (big decimated faces), to occ. Positions are float32 in world space (no node transforms)."""
    inv = 1.0 / grid
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"glTF":
        raise ValueError("not a GLB: %s" % path)
    jl = struct.unpack("<I", data[12:16])[0]
    g = json.loads(data[20:20 + jl].decode("utf-8"))
    if any("translation" in n or "matrix" in n or "rotation" in n or "scale" in n for n in g.get("nodes", [])):
        raise ValueError("node transforms in %s (expected world-space meshes)" % path)
    base = 20 + jl + 8
    acc, bvs = g["accessors"], g["bufferViews"]
    lim = (grid * 0.9) ** 2
    nv = 0
    for m in g.get("meshes", []):
        for p in m["primitives"]:
            mat = g["materials"][p["material"]].get("name", "") if "material" in p else ""
            if ".glow." in mat:
                continue                                 # runes, lanterns, motes: not rock
            pa = acc[p["attributes"]["POSITION"]]
            bv = bvs[pa["bufferView"]]
            if pa.get("componentType") != 5126 or bv.get("byteStride", 12) != 12:
                raise ValueError("unexpected position layout in %s" % path)
            o = base + bv.get("byteOffset", 0) + pa.get("byteOffset", 0)
            pos = array.array("f")
            pos.frombytes(data[o:o + pa["count"] * 12])
            if sys.byteorder != "little":
                pos.byteswap()
            xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
            occ.update((int(x * inv + OFF) << 20) | (int(z * inv + OFF) << 8) | int(y * inv + YOFF)
                       for x, y, z in zip(xs, ys, zs))
            nv += pa["count"]
            if "indices" not in p:
                continue
            ia = acc[p["indices"]]
            ibv = bvs[ia["bufferView"]]
            idx = array.array({5121: "B", 5123: "H", 5125: "I"}[ia["componentType"]])
            io = base + ibv.get("byteOffset", 0) + ia.get("byteOffset", 0)
            idx.frombytes(data[io:io + ia["count"] * idx.itemsize])
            if sys.byteorder != "little":
                idx.byteswap()
            for a, b, c in zip(idx[0::3], idx[1::3], idx[2::3]):
                ax, ay, az = xs[a], ys[a], zs[a]
                bx, by, bz = xs[b], ys[b], zs[b]
                cx, cy, cz = xs[c], ys[c], zs[c]
                e = max((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2,
                        (cx - ax) ** 2 + (cy - ay) ** 2 + (cz - az) ** 2,
                        (cx - bx) ** 2 + (cy - by) ** 2 + (cz - bz) ** 2)
                if e <= lim:
                    continue
                k = int(math.sqrt(e) / (grid * 0.7)) + 1
                for u in range(k + 1):
                    for v in range(k + 1 - u):
                        fu, fv = u / k, v / k
                        fw = 1.0 - fu - fv
                        occ.add((int((ax * fw + bx * fu + cx * fv) * inv + OFF) << 20)
                                | (int((az * fw + bz * fu + cz * fv) * inv + OFF) << 8)
                                | int((ay * fw + by * fu + cy * fv) * inv + YOFF))
    return nv


def load_voxels(full, rebuild=False):
    """The occupied 8 m voxels of the baked scene (a set of packed keys), cached in <full>/mist_voxels.bin
    with a .json sidecar naming the GLBs it came from (rebuilt when any of them changes)."""
    raw = os.path.join(full, "raw")
    srcs = _glb_sources(raw)
    if not srcs:
        raise SystemExit("no raw GLBs in %s (the bake writes them)" % raw)
    bin_p = os.path.join(full, CACHE)
    meta_p = bin_p[:-4] + ".json"
    want = dict(version=VERSION, grid=GRID, off=OFF, yoff=YOFF, sources=[list(s) for s in srcs])
    if not rebuild and os.path.isfile(bin_p) and os.path.isfile(meta_p):
        with open(meta_p, encoding="utf-8") as fh:
            have = json.load(fh)
        if have == want:
            arr = array.array("q")
            with open(bin_p, "rb") as fh:
                arr.frombytes(fh.read())
            if sys.byteorder != "little":
                arr.byteswap()
            log("voxels from cache", len(arr))
            return set(arr)
    t0 = time.time()
    occ = set()
    nv = 0
    for name, _, _ in srcs:
        nv += _voxelise_glb(os.path.join(raw, name), occ, GRID)
    arr = array.array("q", sorted(occ))
    if sys.byteorder != "little":
        arr.byteswap()
    tmp = bin_p + ".tmp"
    with open(tmp, "wb") as fh:
        arr.tofile(fh)
    os.replace(tmp, bin_p)
    with open(meta_p, "w", encoding="utf-8") as fh:
        json.dump(want, fh, indent=1)
    log("voxelised", len(srcs), "GLBs,", nv, "vertices ->", len(occ), "voxels in %.1f s" % (time.time() - t0))
    return occ


class Vox:
    """Occupancy queries on the voxel set (three.js x, y, z in metres)."""

    def __init__(self, occ, grid=GRID):
        self.occ = occ
        self.s = grid
        self.inv = 1.0 / grid
        top, bot = {}, {}
        for k in occ:
            c, iy = k >> 8, k & 255
            if top.get(c, -1) < iy:
                top[c] = iy
            if bot.get(c, 1 << 30) > iy:
                bot[c] = iy
        self.top, self.bot = top, bot
        self.ground = top

    def set_ground(self, exclude):
        """Column tops without the voxels in `exclude` (the floating islands): the ground height map."""
        g = {}
        for k in self.occ:
            if k in exclude:
                continue
            c, iy = k >> 8, k & 255
            if g.get(c, -1) < iy:
                g[c] = iy
        self.ground = g

    def ixz(self, v):
        return int(v * self.inv + OFF)

    def iy(self, y):
        return int(y * self.inv + YOFF)

    def yc(self, iy):
        return (iy - YOFF + 0.5) * self.s

    def xc(self, ix):
        return (ix - OFF + 0.5) * self.s

    def col(self, x, z):
        return (self.ixz(x) << 12) | self.ixz(z)

    def has(self, x, y, z):
        return ((self.ixz(x) << 20) | (self.ixz(z) << 8) | self.iy(y)) in self.occ

    def slab(self, x, z, iy, half=1):
        k = (self.ixz(x) << 20) | (self.ixz(z) << 8)
        occ = self.occ
        return any((k | j) in occ for j in range(iy - half, iy + half + 1))

    def top_y(self, x, z):
        """Ground height (column top without the floating islands), None over the void."""
        t = self.ground.get(self.col(x, z))
        return None if t is None else self.yc(t) + self.s * 0.5

    def near_surface(self, x, y, z, r=1):
        ix, iy, iz = self.ixz(x), self.iy(y), self.ixz(z)
        occ = self.occ
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                k = ((ix + dx) << 20) | ((iz + dz) << 8)
                for dy in range(-r, r + 1):
                    if (k | (iy + dy)) in occ:
                        return True
        return False

    def inside(self, x, y, z):
        """True when the point is inside solid rock: off any surface, with an odd number of surface runs
        in its column both above and below it (a pillar, a terrace, the range mass; not the air between
        a floating island and the ground under it)."""
        ix, iz, iy = self.ixz(x), self.ixz(z), self.iy(y)
        c = (ix << 12) | iz
        t, b = self.top.get(c), self.bot.get(c)
        if t is None or not b < iy < t:
            return False
        k = (ix << 20) | (iz << 8)
        occ = self.occ
        if (k | iy) in occ:
            return False

        def runs(js):
            n, prev = 0, False
            for j in js:
                o = (k | j) in occ
                if o and not prev:
                    n += 1
                prev = o
            return n
        return runs(range(iy + 1, t + 1)) % 2 == 1 and runs(range(iy - 1, b - 1, -1)) % 2 == 1

    def blocked(self, a, b, stop=0.0, start=12.0, step=4.0):
        """Whether the segment a -> b (minus `start` m at a and `stop` m at b) passes through geometry."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d < 1e-6:
            return False
        dx, dy, dz = dx / d, dy / d, dz / d
        inv, occ = self.inv, self.occ
        t = start
        end = d - stop
        while t < end:
            x, y, z = a[0] + dx * t, a[1] + dy * t, a[2] + dz * t
            if ((int(x * inv + OFF) << 20) | (int(z * inv + OFF) << 8) | int(y * inv + YOFF)) in occ:
                return True
            t += step
        return False


# =====================================================================================================
# scene facts: path, holds, areas
# =====================================================================================================

def _qrot(q, v):
    x, y, z, w = q
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx))


class View:
    __slots__ = ("p", "fwd", "up", "right", "tan_y", "tan_x", "frame", "kind")

    def __init__(self, fr, aspect, kind):
        self.p = tuple(fr["p"])
        q = fr["q"]
        self.fwd = _qrot(q, (0.0, 0.0, -1.0))
        self.up = _qrot(q, (0.0, 1.0, 0.0))
        self.right = _qrot(q, (1.0, 0.0, 0.0))
        self.tan_y = math.tan(math.radians(fr.get("fovY", 35.0)) * 0.5)
        self.tan_x = self.tan_y * aspect
        self.frame = fr["f"]
        self.kind = kind

    def in_frustum(self, c, r, margin=1.1):
        d = (c[0] - self.p[0], c[1] - self.p[1], c[2] - self.p[2])
        z = d[0] * self.fwd[0] + d[1] * self.fwd[1] + d[2] * self.fwd[2]
        if z <= -r:
            return False
        zz = max(z, 1e-3)
        x = d[0] * self.right[0] + d[1] * self.right[1] + d[2] * self.right[2]
        y = d[0] * self.up[0] + d[1] * self.up[1] + d[2] * self.up[2]
        return abs(x) - r <= zz * self.tan_x * margin and abs(y) - r <= zz * self.tan_y * margin


class Scene:
    def __init__(self, site):
        with open(os.path.join(site, "camera.json"), encoding="utf-8") as fh:
            cam = json.load(fh)
        with open(os.path.join(site, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        self.frames = cam["frames"]
        self.aspect = float(cam.get("aspect", 16.0 / 9.0))
        by_f = {f["f"]: f for f in self.frames}
        self.holds = [dict(h, view=View(by_f[h["frame"]], self.aspect, "hold")) for h in cam["holds"]
                      if h["frame"] in by_f]
        self.path = [tuple(f["p"]) for f in self.frames]
        self.path_views = [View(f, self.aspect, "path") for f in self.frames[::12]]
        self.sea_y = float(meta["cloudSea"]["y"])
        self.fog_top = float(meta["cloudSea"].get("fogTopY", self.sea_y + 80.0))
        self.areas = [dict(id=a["id"], c=tuple(a["anchor"]), fp=float(a["footprint"]), hold=a.get("holdFrame"))
                      for a in meta["areas"]]
        spots = collections.defaultdict(list)
        for h in meta.get("hotspots", []):
            if h.get("area") and h.get("center"):
                spots[h["area"]].append(tuple(h["center"]))
        # the hold's sight lines: from the hold camera to its area's hotspots and anchor
        self.sights = []
        for h in self.holds:
            a = next((x for x in self.areas if x["id"] == h["id"]), None)
            tg = list(spots.get(h["id"], []))
            if a:
                tg.append((a["c"][0], a["c"][1] + 3.0, a["c"][2]))
            for t in tg:
                self.sights.append((h["view"].p, t))
        # coarse path samples, as the page keeps puffs (every 6th frame)
        self.client_path = [tuple(f["p"]) for i, f in enumerate(self.frames) if i % 6 == 0]
        # a coarse grid over the path for fast nearest-distance queries
        self.cell = 60.0
        self.grid = collections.defaultdict(list)
        for p in self.path:
            self.grid[(int(math.floor(p[0] / self.cell)), int(math.floor(p[2] / self.cell)))].append(p)

    def path_dist(self, c, reach):
        """Distance from c to the nearest camera position (every frame), searched within `reach` m."""
        best = float("inf")
        n = int(reach / self.cell) + 1
        gx, gz = int(math.floor(c[0] / self.cell)), int(math.floor(c[2] / self.cell))
        for i in range(gx - n, gx + n + 1):
            for j in range(gz - n, gz + n + 1):
                for p in self.grid.get((i, j), ()):
                    d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
                    if d < best:
                        best = d
        return math.sqrt(best)

    def client_dist(self, c):
        return min(math.dist(c, p) for p in self.client_path)


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2))
    return math.dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)), t


# =====================================================================================================
# peaks and their outline
# =====================================================================================================

def _slide_max(vals, n_rows, n_cols, r):
    """Max over a (2r+1)^2 window of a row-major grid (separable, monotone deques)."""
    def pass1d(get, put, n, count):
        for line in range(count):
            dq = collections.deque()
            for i in range(n + r):
                if i < n:
                    v = get(line, i)
                    while dq and dq[-1][0] <= v:
                        dq.pop()
                    dq.append((v, i))
                o = i - r
                if o >= 0:
                    while dq[0][1] < o - r:
                        dq.popleft()
                    put(line, o, dq[0][0])
    tmp = [0] * (n_rows * n_cols)
    out = [0] * (n_rows * n_cols)
    pass1d(lambda l, i: vals[l * n_cols + i], lambda l, i, v: tmp.__setitem__(l * n_cols + i, v), n_cols, n_rows)
    pass1d(lambda l, i: tmp[i * n_cols + l], lambda l, i, v: out.__setitem__(i * n_cols + l, v), n_rows, n_cols)
    return out


def find_peaks(vox, scene, ground):
    """Free-standing peaks: local maxima of the ground-height map (column tops without the floating
    islands) standing PROM_MIN m over a ring 72-104 m out, away from the areas. Returns
    [(x, z, top_y)], highest first."""
    sea = vox.iy(scene.sea_y)
    ixs = [c >> 12 for c in ground]
    izs = [c & 4095 for c in ground]
    x0, x1, z0, z1 = min(ixs), max(ixs), min(izs), max(izs)
    nr, nc = x1 - x0 + 1, z1 - z0 + 1
    hm = [sea] * (nr * nc)
    for c, t in ground.items():
        hm[((c >> 12) - x0) * nc + ((c & 4095) - z0)] = t
    mx = _slide_max(hm, nr, nc, PEAK_WIN)
    min_top = vox.iy(scene.sea_y + 70.0)
    cands = []
    for i in range(nr * nc):
        t = hm[i]
        if t == mx[i] and t >= min_top:
            cands.append((t, i // nc, i % nc))
    cands.sort(reverse=True)
    out = []
    for t, r, c in cands:
        ring = []
        for k in range(32):
            a = 2.0 * math.pi * k / 32
            for rad in (9, 11, 13):
                rr, cc = r + int(round(math.cos(a) * rad)), c + int(round(math.sin(a) * rad))
                ring.append(hm[rr * nc + cc] if 0 <= rr < nr and 0 <= cc < nc else sea)
        if (t - min(ring)) * vox.s < PROM_MIN:
            continue
        x, z, y = vox.xc(r + x0), vox.xc(c + z0), vox.yc(t) + vox.s * 0.5
        if any(math.hypot(x - p[0], z - p[1]) < 36.0 for p in out):
            continue
        if any(math.hypot(x - a["c"][0], z - a["c"][2]) < a["fp"] + AREA_PAD + 10.0 for a in scene.areas):
            continue
        out.append((x, z, y))
    return out


def _fit_circle(pts):
    """Least-squares circle (Kasa) through 2D points: (cx, cz, r) or None. Works on partial arcs."""
    n = len(pts)
    if n < 5:
        return None
    mx, mz = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    q = [(p[0] - mx, p[1] - mz) for p in pts]
    sxx = sum(x * x for x, _ in q)
    szz = sum(z * z for _, z in q)
    sxz = sum(x * z for x, z in q)
    w = [x * x + z * z for x, z in q]
    bx = -sum(x * ww for (x, _), ww in zip(q, w))
    bz = -sum(z * ww for (_, z), ww in zip(q, w))
    # [sxx sxz; sxz szz] [a b] = [bx bz]; c = -mean(w)   (sums of x and z vanish after centring)
    det = sxx * szz - sxz * sxz
    if abs(det) < 1e-9:
        return None
    a = (bx * szz - sxz * bz) / det
    b = (sxx * bz - sxz * bx) / det
    c = -sum(w) / n
    r2 = (a * a + b * b) / 4.0 - c
    if r2 <= 0:
        return None
    return mx - a / 2.0, mz - b / 2.0, math.sqrt(r2)


def section(vox, x, z, iy, win=32, seek=4):
    """The rock's cross-section at voxel level iy (a 24 m slab) around (x, z): the 8-connected ring of
    occupied cells reached from the cell nearest (x, z), its centre (a circle fitted to the ring, which
    copes with the far side missing: the export leaves out faces no camera sees), and the outer wall
    radius per sector (None where the ring has no cells: hidden, so no mist is needed there).
    The ring is reached from the occupied cell nearest (x, z) within `seek` cells (a pillar's middle is
    hollow: only its surface is voxelised). Returns None when there is no rock that near; 'touched' when
    the ring runs out of the +-win cell window (it has merged with the ground)."""
    ix0, iz0 = vox.ixz(x), vox.ixz(z)
    occ = vox.occ

    def cell(ix, iz):
        k = (ix << 20) | (iz << 8)
        return (k | (iy - 1)) in occ or (k | iy) in occ or (k | (iy + 1)) in occ
    seed = None
    for rr in range(0, seek + 1):
        for dx in range(-rr, rr + 1):
            for dz in range(-rr, rr + 1):
                if max(abs(dx), abs(dz)) == rr and cell(ix0 + dx, iz0 + dz):
                    seed = (ix0 + dx, iz0 + dz)
                    break
            if seed:
                break
        if seed:
            break
    if seed is None:
        return None
    comp, seen, touched = [seed], {seed}, False
    i = 0
    while i < len(comp):
        cx, cz = comp[i]
        i += 1
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                nb = (cx + dx, cz + dz)
                if nb in seen:
                    continue
                seen.add(nb)
                if abs(nb[0] - ix0) > win or abs(nb[1] - iz0) > win:
                    if cell(*nb):
                        touched = True
                    continue
                if cell(*nb):
                    comp.append(nb)
    pts = [(vox.xc(a), vox.xc(b)) for a, b in comp]
    n = len(pts)
    mx, mz = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    spread = max(math.hypot(p[0] - mx, p[1] - mz) for p in pts)
    fit = _fit_circle(pts) if n >= 8 else None
    if fit and fit[2] < spread * 1.3 + 10.0 and math.hypot(fit[0] - mx, fit[1] - mz) < spread + 10.0:
        cx, cz = fit[0], fit[1]
    else:
        cx, cz = mx, mz
    rs = [None] * SECTORS
    for px, pz in pts:
        k = int((math.atan2(pz - cz, px - cx) % (2.0 * math.pi)) / (2.0 * math.pi) * SECTORS) % SECTORS
        r = math.hypot(px - cx, pz - cz) + vox.s * 0.5
        if rs[k] is None or r > rs[k]:
            rs[k] = r
    return dict(x=cx, z=cz, rs=rs, touched=touched, n=n)


def pillar(vox, scene, x, z, top):
    """The pillar under a peak: cross-sections every 16 m from just under the top down to where the
    ring merges with the ground (the visible base) or runs out (the tip of a floating peak's underside,
    or nothing seen). For a floating peak the base is its widest level (the rim; below it the underside
    tapers away). Returns dict or None."""
    floor_iy = vox.iy(scene.sea_y + 10.0)
    levels = []
    iy = vox.iy(top - 2.0) - 2
    why = "floor"
    while iy > floor_iy:
        seek = 4 if not levels else int(levels[-1]["rm"] / vox.s) + 3
        sec = section(vox, x, z, iy, seek=seek)
        if sec is None:
            why = "open"
            break
        found = [r for r in sec["rs"] if r is not None]
        if sec["touched"]:
            why = "merge"
            break
        if len(found) < SECTORS * 0.3:
            why = "open"
            break
        rm = sum(found) / len(found)
        if levels and (rm > levels[-1]["rm"] * 1.35 + 10.0
                       or math.hypot(sec["x"] - levels[-1]["x"], sec["z"] - levels[-1]["z"]) > levels[-1]["rm"] * 0.6 + 8.0):
            why = "merge"
            break
        levels.append(dict(iy=iy, y=vox.yc(iy), x=sec["x"], z=sec["z"], rs=sec["rs"], rm=rm))
        x, z = sec["x"], sec["z"]
        iy -= 2
    if len(levels) < 2:
        return None
    if why == "open":
        widest = max(range(len(levels)), key=lambda i: levels[i]["rm"])
        levels = levels[:widest + 1]
    base = levels[-1]["y"] - vox.s
    if top - base < MIN_VISIBLE:
        return None
    return dict(x=levels[0]["x"], z=levels[0]["z"], top=top, base=base, levels=levels, why=why)


def dedupe_pillars(pills, isles):
    """One pillar per rock: drop a pillar whose top-level centre lies within another's top outline, or
    that is a floating island (find_islands covers those)."""
    out = []
    for p in sorted(pills, key=lambda p: -p["top"]):
        r0 = p["levels"][0]["rm"]
        if any(math.hypot(p["x"] - q["x"], p["z"] - q["z"]) < max(r0, q["levels"][0]["rm"]) * 0.8 + 6.0 for q in out):
            continue
        if any(math.hypot(p["x"] - i["x"], p["z"] - i["z"]) < i["size"] * 0.5 + 10.0 and abs(p["top"] - i["top"]) < 16.0
               for i in isles):
            continue
        out.append(p)
    return out


def _ring_r(rs, a):
    """Wall radius at angle a from the sector list (linear between sectors; None where neither
    neighbouring sector has a wall)."""
    f = (a % (2.0 * math.pi)) / (2.0 * math.pi) * SECTORS
    i0 = int(f) % SECTORS
    i1 = (i0 + 1) % SECTORS
    t = f - int(f)
    r0, r1 = rs[i0], rs[i1]
    if r0 is None and r1 is None:
        return None
    r0 = r1 if r0 is None else r0
    r1 = r0 if r1 is None else r1
    return r0 + (r1 - r0) * t


# =====================================================================================================
# puffs
# =====================================================================================================

def _rng(*parts):
    return random.Random(zlib.crc32(("|".join(str(p) for p in parts) + "|%d" % SEED).encode()) & 0x7FFFFFFF)


def _puff(c, axes, tau, kind):
    """A puff in the clouds.json contract (+ its kind and bounding radius for the checks)."""
    half = math.sqrt((axes[0][0] ** 2 + axes[0][1] ** 2 + axes[0][2] ** 2
                      + axes[2][0] ** 2 + axes[2][1] ** 2 + axes[2][2] ** 2) * 0.5)
    d = tau / (0.45 * max(half, 1.0))
    R = max(math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) for a in axes)
    return dict(c=[round(c[0], 2), round(c[1], 2), round(c[2], 2)],
                a=[[round(v, 3) for v in a] for a in axes], d=round(d, 4), k="%s.%s" % (TAG, kind), _R=R)


def _horiz_axes(ang, ra, rb, v):
    """Semi-axes of a flat ellipsoid: ra along the horizontal angle ang (three x/z plane), rb across, v up."""
    ca, sa = math.cos(ang), math.sin(ang)
    return [[ca * ra, 0.0, sa * ra], [0.0, v, 0.0], [-sa * rb, 0.0, ca * rb]]


def band_group(pl, rel, idx):
    """One band of mist hugging a pillar at relative height rel: overlapping flat puffs round the
    outline, their centres just outside the wall, the ring rising and falling a little."""
    vis = pl["top"] - pl["base"]
    yb = min(pl["base"] + vis * rel, pl["top"] - TOP_FREE)
    lv = min(pl["levels"], key=lambda L: abs(L["y"] - yb))
    rm = lv["rm"]
    ox, oz = lv["x"], lv["z"]
    r = _rng("band", round(pl["x"]), round(pl["z"]), idx)
    rh = max(11.0, min(55.0, 0.42 * rm + 7.0))
    v = max(rh * 0.45, min(rh * 0.9, 0.11 * vis))
    tg = rh * r.uniform(1.35, 1.65)
    out_off = 0.35 * rh
    circ = 2.0 * math.pi * (rm + out_off)
    n = max(4, min(16, int(round(circ / (1.4 * tg)))))
    ph0, ph1 = r.uniform(0, 2 * math.pi), r.uniform(0, 2 * math.pi)
    amp = r.uniform(0.25, 0.7) * v
    tau = TAU["band"] * r.uniform(0.85, 1.1)
    puffs = []
    for j in range(n):
        if r.random() < 0.16:
            continue                                 # a break in the band
        a = ph0 + 2.0 * math.pi * (j + r.uniform(-0.18, 0.18)) / n
        rw = _ring_r(lv["rs"], a)
        s = r.uniform(0.82, 1.18)
        if rw is None:
            continue                                 # merged into the ground, or never seen
        rr = rw + out_off * r.uniform(0.75, 1.3)
        c = (ox + math.cos(a) * rr, yb + amp * math.sin(a + ph1) + r.uniform(-0.25, 0.25) * v,
             oz + math.sin(a) * rr)
        axes = _horiz_axes(a, rh * s, tg * s * r.uniform(0.85, 1.15), v * s * r.uniform(0.85, 1.2))
        puffs.append(_puff(c, axes, tau * r.uniform(0.85, 1.12), "band"))
    return dict(kind="band", key="band:%d:%d:%d" % (round(pl["x"]), round(pl["z"]), idx), puffs=puffs,
                center=(ox, yb, oz), ring=rm + out_off, radius=rm + rh * 1.3, y=yb)


def pool_groups(vox, scene):
    """Mist pooled in hollows: ground cells (every 32 m) with walls at least POOL_WALL m higher within
    30-110 m in 5 of 8 directions, or on both sides of a gorge; one flat bank each (the lowest in its
    70 m neighbourhood), sitting on the floor. Away from the areas."""
    s = vox.s
    out = []
    cands = []
    step = 4                                         # cells (32 m)
    cols = [c for c in vox.ground if (c >> 12) % step == 0 and (c & 4095) % step == 0]
    sea = scene.sea_y + 15.0
    for c in cols:
        x, z = vox.xc(c >> 12), vox.xc(c & 4095)
        y = vox.yc(vox.ground[c]) + s * 0.5
        if y < sea + 10.0:
            continue
        if any(math.hypot(x - a["c"][0], z - a["c"][2]) < a["fp"] + AREA_PAD + 20.0 for a in scene.areas):
            continue
        walls = []
        for k in range(8):
            a = 2.0 * math.pi * k / 8
            hi = -1e9
            for d in (32.0, 56.0, 80.0, 104.0):
                ty = vox.top_y(x + math.cos(a) * d, z + math.sin(a) * d)
                if ty is not None and ty > hi:
                    hi = ty
            walls.append(hi - y >= POOL_WALL)
        gorge = any(walls[k] and walls[(k + 4) % 8] for k in range(4))
        if sum(walls) >= 5 or gorge:
            cands.append((y, x, z, sum(walls)))
    cands.sort()
    for y, x, z, nw in cands:
        if any(math.hypot(x - p[1], z - p[2]) < 70.0 for p in out):
            continue
        out.append((y, x, z, nw))
    groups = []
    for y, x, z, nw in out:
        r = _rng("pool", round(x), round(z))
        L = r.uniform(30.0, 55.0)
        v = r.uniform(7.0, 12.0)
        ang = r.uniform(0, 2 * math.pi)
        c = (x + r.uniform(-8, 8), y + v * 0.5, z + r.uniform(-8, 8))
        p = _puff(c, _horiz_axes(ang, L, L * r.uniform(0.55, 0.8), v), TAU["gorge"] * r.uniform(0.85, 1.1), "gorge")
        groups.append(dict(kind="pool", key="pool:%d:%d" % (round(x), round(z)), puffs=[p], center=c, ring=0.0,
                           radius=L, y=c[1]))
    return groups


def face_groups(vox, scene):
    """Wisps on the cliffs each hold looks at: a 16 x 7 grid of rays over the hold's own view. Where a ray
    meets rock 120-1400 m out with at least 50 m of relief under it (the floor in front of the face to
    the top of the face), the face is found again at 30-55 % of that relief, marching level along the
    ray's heading, and a flat puff hangs just in front of it, wider along it, if the hold sees that spot.
    Covers the range's own walls, which are not free-standing pillars."""
    cands = []
    for h in scene.holds:
        v = h["view"]
        for gy in range(7):
            for gx in range(16):
                sx = ((gx + 0.5) / 16 * 2 - 1) * v.tan_x * 0.95
                sy = ((gy + 0.5) / 7 * 2 - 1) * v.tan_y * 0.9
                d = [v.fwd[k] + v.right[k] * sx + v.up[k] * sy for k in range(3)]
                n = math.sqrt(sum(x * x for x in d))
                d = [x / n for x in d]
                t, hit = 40.0, None
                while t < 1400.0:
                    q = (v.p[0] + d[0] * t, v.p[1] + d[1] * t, v.p[2] + d[2] * t)
                    if vox.has(*q):
                        hit = q
                        break
                    t += 4.0
                if hit is None or t < 120.0:
                    continue
                dh = math.hypot(d[0], d[2]) or 1.0
                ux, uz = d[0] / dh, d[2] / dh
                tops = [vox.top_y(hit[0] + ux * k, hit[2] + uz * k) for k in (0.0, 8.0, 16.0, 28.0, 40.0)]
                tops = [y for y in tops if y is not None]
                if not tops:
                    continue
                top = max(tops)                       # the top of the face (a little way into it)
                fl = []
                for back in (20.0, 45.0, 70.0, 100.0, 140.0):
                    if back > t - 30.0:
                        break
                    g = vox.top_y(hit[0] - ux * back, hit[2] - uz * back)
                    fl.append(g if g is not None else scene.sea_y + 15.0)
                if not fl:
                    continue
                floor = max(min(fl), scene.sea_y + 15.0)
                relief = top - floor
                if relief < 50.0:
                    continue
                r = _rng("facey", round(hit[0]), round(hit[2]))
                ym = floor + relief * r.uniform(0.3, 0.55)
                # the face at that height, along the same heading
                th = math.hypot(hit[0] - v.p[0], hit[2] - v.p[2])
                iy = vox.iy(ym)
                face = None
                k = max(40.0, th - 200.0)
                while k < th + 80.0:
                    x, z = v.p[0] + ux * k, v.p[2] + uz * k
                    if vox.slab(x, z, iy, 0):
                        face = (x, ym, z, k)
                        break
                    k += 4.0
                if face is None or face[3] < 120.0:
                    continue
                cands.append((face[3], face[:3], (ux, uz), h["view"]))
    cands.sort(key=lambda c: -c[0])                  # far first: they need the size, near ones crowd
    kept = []
    for t, pt, u, v in cands:
        if any(math.dist(pt, k[1]) < 70.0 for k in kept):
            continue
        kept.append((t, pt, u, v))
    out = []
    for t, pt, (ux, uz), v in kept:
        r = _rng("face", round(pt[0]), round(pt[1]), round(pt[2]))
        R = max(14.0, min(45.0, 0.045 * t)) * r.uniform(0.85, 1.15)
        c = (pt[0] - ux * R * 0.4, pt[1] + r.uniform(-0.15, 0.15) * R, pt[2] - uz * R * 0.4)
        if vox.blocked(v.p, c, stop=R * 0.5):
            continue
        ang = math.atan2(uz, ux)
        axes = _horiz_axes(ang, R * r.uniform(0.7, 0.9), R * r.uniform(1.5, 1.9), R * r.uniform(0.38, 0.5))
        p = _puff(c, axes, TAU["band"] * r.uniform(0.8, 1.05), "band")
        out.append(dict(kind="face", key="face:%d:%d:%d" % (round(c[0]), round(c[1]), round(c[2])), puffs=[p],
                        center=c, ring=0.0, radius=R * 1.6, y=c[1]))
    return out


def gorge_groups(vox, scene, pills):
    """Mist pooled low in the gap between neighbouring pillars: a flat bank along the gorge (across the
    line joining them), with smaller banks either side, sitting on the gorge floor or the cloud sea."""
    out = []
    seen = set()
    for i, a in enumerate(pills):
        near = sorted(((math.hypot(b["x"] - a["x"], b["z"] - a["z"]), j) for j, b in enumerate(pills) if j != i))[:2]
        for d, j in near:
            if (min(i, j), max(i, j)) in seen:
                continue
            b = pills[j]
            ra = a["levels"][len(a["levels"]) // 2]["rm"]
            rb = b["levels"][len(b["levels"]) // 2]["rm"]
            gap = d - ra - rb
            if not 12.0 < gap < 170.0:
                continue
            seen.add((min(i, j), max(i, j)))
            ux, uz = (b["x"] - a["x"]) / d, (b["z"] - a["z"]) / d
            gx, gz = -uz, ux
            mx, mz = a["x"] + ux * (ra + gap * 0.5), a["z"] + uz * (ra + gap * 0.5)
            # gorge floor: the lowest top along the middle of the gap (no ground: the cloud sea)
            fl = []
            for k in range(-3, 4):
                t = k / 3.0 * gap * 0.3
                ty = vox.top_y(mx + ux * t, mz + uz * t)
                fl.append(ty if ty is not None else scene.sea_y + 15.0)
            floor = min(fl)
            r = _rng("gorge", round(mx), round(mz))
            L = max(26.0, min(75.0, 0.5 * (ra + rb) + 0.4 * gap))
            v = max(7.0, min(16.0, 0.2 * L))
            yc = max(floor + v * 0.55, scene.sea_y + 22.0)
            ceil = min(a["base"] + (a["top"] - a["base"]) * 0.45, b["base"] + (b["top"] - b["base"]) * 0.45)
            if yc > ceil:
                continue                             # the gorge floor is high: the bands cover it
            across = max(14.0, 0.55 * gap + 6.0)
            ang = math.atan2(gz, gx)
            tau = TAU["gorge"] * r.uniform(0.85, 1.1)
            puffs = []
            for off, sc in ((0.0, 1.0), (0.95, 0.72), (-0.95, 0.72)):
                if off and r.random() < 0.25:
                    continue
                cx, cz = mx + gx * L * off, mz + gz * L * off
                ty = vox.top_y(cx, cz)
                y = yc + r.uniform(-0.2, 0.3) * v
                if ty is not None and ty > y + v * 0.5 and off:
                    continue                         # this end runs into a slope
                axes = _horiz_axes(ang + r.uniform(-0.2, 0.2), L * sc * r.uniform(0.9, 1.1), across * sc,
                                   v * sc * r.uniform(0.9, 1.2))
                puffs.append(_puff((cx, y, cz), axes, tau * r.uniform(0.9, 1.1), "gorge"))
            out.append(dict(kind="gorge", key="gorge:%d:%d" % (round(mx), round(mz)), puffs=puffs,
                            center=(mx, yc, mz), ring=0.0, radius=L * 1.2, y=yc))
    return out


def find_islands(vox, scene):
    """Floating rocks: connected voxel groups (26-neighbourhood) at most 130 m across and 150 m tall
    whose bottom hangs well clear of the cloud sea. Returns (the ones away from the areas, the voxel
    keys of all of them)."""
    occ = vox.occ
    offs = [(dx << 20) + (dz << 8) + dy for dx in (-1, 0, 1) for dz in (-1, 0, 1) for dy in (-1, 0, 1)
            if dx or dz or dy]
    seen = set()
    out = []
    keys = set()
    lim_xz = int(130.0 / vox.s)
    lim_y = int(150.0 / vox.s)
    for k0 in occ:
        if k0 in seen:
            continue
        comp = [k0]
        seen.add(k0)
        i = 0
        big = False
        while i < len(comp):
            k = comp[i]
            i += 1
            for o in offs:
                n = k + o
                if n in occ and n not in seen:
                    seen.add(n)
                    comp.append(n)
            if len(comp) > 6000:
                big = True                            # the range, the backdrop massifs: keep marking
        if big or len(comp) < 6:
            continue
        xs = [k >> 20 for k in comp]
        zs = [(k >> 8) & 4095 for k in comp]
        ys = [k & 255 for k in comp]
        if max(xs) - min(xs) > lim_xz or max(zs) - min(zs) > lim_xz or max(ys) - min(ys) > lim_y:
            continue
        bottom, top = vox.yc(min(ys)) - vox.s * 0.5, vox.yc(max(ys)) + vox.s * 0.5
        if bottom < scene.sea_y + 25.0:
            continue
        ty = max(ys)
        tops = [k for k in comp if (k & 255) >= ty - 1]
        cx = sum(vox.xc(k >> 20) for k in tops) / len(tops)
        cz = sum(vox.xc((k >> 8) & 4095) for k in tops) / len(tops)
        size = max(max(xs) - min(xs), max(zs) - min(zs)) * vox.s + vox.s
        keys.update(comp)                            # floating: not ground, wherever it is
        if any(math.hypot(cx - a["c"][0], cz - a["c"][2]) < a["fp"] + AREA_PAD + size * 0.5 for a in scene.areas):
            continue
        out.append(dict(x=cx, z=cz, top=top, bottom=bottom, size=size, n=len(comp)))
    return out, keys


def isle_group(isl):
    """Wisps under a floating rock (a flat bank just under its tip, drifting a little off centre) and,
    on the bigger ones, a few puffs hugging its tapering underside, so it sits on cloud."""
    r = _rng("isle", round(isl["x"]), round(isl["z"]))
    s = isl["size"]
    puffs = []
    tau = TAU["isle"] * r.uniform(0.85, 1.1)
    a0 = r.uniform(0, 2 * math.pi)
    ra = max(12.0, min(55.0, 0.8 * s))
    v = max(6.0, min(16.0, 0.26 * s))
    c = (isl["x"] + math.cos(a0) * s * 0.18, isl["bottom"] - v * 0.3, isl["z"] + math.sin(a0) * s * 0.18)
    puffs.append(_puff(c, _horiz_axes(a0, ra, ra * r.uniform(0.6, 0.85), v), tau, "isle"))
    if s >= 22.0:
        h = isl["top"] - isl["bottom"]
        y = isl["top"] - h * r.uniform(0.3, 0.42)
        rh = max(8.0, min(24.0, 0.3 * s))
        n = 3 if s < 45.0 else 4
        ph = r.uniform(0, 2 * math.pi)
        for j in range(n):
            if r.random() < 0.2:
                continue
            a = ph + 2.0 * math.pi * (j + r.uniform(-0.15, 0.15)) / n
            rr = 0.3 * s + 0.4 * rh
            c = (isl["x"] + math.cos(a) * rr, y + r.uniform(-0.2, 0.2) * rh, isl["z"] + math.sin(a) * rr)
            puffs.append(_puff(c, _horiz_axes(a, rh, rh * r.uniform(1.3, 1.6), rh * r.uniform(0.4, 0.55)),
                               tau * r.uniform(0.85, 1.1), "isle"))
    return dict(kind="isle", key="isle:%d:%d" % (round(isl["x"]), round(isl["z"])), puffs=puffs,
                center=(isl["x"], isl["bottom"], isl["z"]), ring=0.0, radius=ra * 1.2, y=isl["bottom"])


# =====================================================================================================
# keep clear, rank, budget
# =====================================================================================================

def keep_clear(scene, vox, g):
    """Drops a group's puffs that crowd the camera, veil a hold's subject, sit on an area or inside rock,
    or that the page would cull; returns the count dropped per reason."""
    why = collections.Counter()
    kept = []
    for p in g["puffs"]:
        c, R = p["c"], p["_R"]
        reach = max(PATH_CLEAR + R, PATH_CLEAR_K * R) + 1.0
        dp = scene.path_dist(c, reach)
        if dp - R < PATH_CLEAR or dp < PATH_CLEAR_K * R:
            why[g["kind"] + ":path"] += 1
            continue
        if any(math.hypot(c[0] - a["c"][0], c[2] - a["c"][2]) < a["fp"] + AREA_PAD and abs(c[1] - a["c"][1]) < 70.0
               for a in scene.areas):
            why[g["kind"] + ":area"] += 1
            continue
        if any(_seg_dist(c, a, b)[0] < R * SIGHT_PAD for a, b in scene.sights):
            why[g["kind"] + ":sight"] += 1
            continue
        if vox.inside(*c):
            why[g["kind"] + ":buried"] += 1
            continue
        if scene.client_dist(c) - R > CLIENT_KEEP - 50.0:
            why[g["kind"] + ":far"] += 1
            continue
        kept.append(p)
    g["puffs"] = kept
    return why


def score(scene, vox, g):
    """Best apparent size (group radius / distance) over the hold cameras (any heading: the visitor can
    look round; the hold's own heading counts full, others 0.6) and every 12th path frame (in view),
    with the line of sight to the group's near side tested against the voxels."""
    cx, cy, cz = g["center"]
    best = 0.0
    views = []
    for h in scene.holds:
        views.append((h["view"], 1.0, True))
    for v in scene.path_views:
        views.append((v, 0.8, False))
    cand = []
    for v, w, hold in views:
        p = v.p
        dx, dz = p[0] - cx, p[2] - cz
        dh = math.hypot(dx, dz) or 1.0
        tgt = (cx + dx / dh * g["ring"], cy, cz + dz / dh * g["ring"])
        d = math.dist(p, tgt)
        if d > VIEW_MAX or d < 1.0:
            continue
        inview = v.in_frustum(tgt, g["radius"])
        if not hold and not inview:
            continue
        ww = w if (inview or not hold) else 0.6
        cand.append((g["radius"] / d * ww, v, tgt, d))
    cand.sort(key=lambda t: -t[0])
    for s, v, tgt, d in cand:
        if s <= best:
            break
        if not vox.blocked(v.p, tgt, stop=min(g["radius"] * 0.5, d * 0.5)):
            best = s
            break
    return best


# =====================================================================================================
# fill-rate estimate (the page's sprite maths, ignoring occlusion: an upper bound)
# =====================================================================================================

def fill(puffs, views, px_h=900):
    """Screens of sprite fragments per frame (quad area, as the GPU shades it, clipped to the screen)."""
    res = []
    for v in views:
        f_px = (px_h * 0.5) / v.tan_y
        W, H = px_h * v.tan_x / v.tan_y, float(px_h)
        tot = 0.0
        for p in puffs:
            c, A = p["c"], p["a"]
            to = (c[0] - v.p[0], c[1] - v.p[1], c[2] - v.p[2])
            dist = math.sqrt(to[0] ** 2 + to[1] ** 2 + to[2] ** 2)
            if dist < 1e-3:
                continue
            f = (to[0] / dist, to[1] / dist, to[2] / dist)
            up = (1.0, 0.0, 0.0) if abs(f[1]) > 0.985 else (0.0, 1.0, 0.0)
            r = (f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0])
            rl = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2) or 1.0
            r = (r[0] / rl, r[1] / rl, r[2] / rl)
            u = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
            sup = lambda e: math.sqrt(sum((a[0] * e[0] + a[1] * e[1] + a[2] * e[2]) ** 2 for a in A))  # noqa: E731
            wr, wu, wf = sup(r), sup(u), sup(f)
            fade = min(max((dist - 0.55 * wf) / (1.05 * wf), 0.0), 1.0)
            if fade * fade * (3 - 2 * fade) < 0.003:
                continue
            lift = min(0.6 * wf, 0.5 * dist)
            k = (dist - lift) / dist
            sc = (c[0] - f[0] * lift - v.p[0], c[1] - f[1] * lift - v.p[1], c[2] - f[2] * lift - v.p[2])
            z = sc[0] * v.fwd[0] + sc[1] * v.fwd[1] + sc[2] * v.fwd[2]
            ext = max(wr, wu) * k
            if z < 1.0:
                if z > -ext and dist < ext * 1.5:
                    tot += W * H * 0.5               # straddles the camera: assume half the screen
                continue
            x = (sc[0] * v.right[0] + sc[1] * v.right[1] + sc[2] * v.right[2]) / z * f_px
            y = (sc[0] * v.up[0] + sc[1] * v.up[1] + sc[2] * v.up[2]) / z * f_px
            hx, hy = wr * k / z * f_px, wu * k / z * f_px
            ox = max(0.0, min(x + hx, W / 2) - max(x - hx, -W / 2))
            oy = max(0.0, min(y + hy, H / 2) - max(y - hy, -H / 2))
            tot += ox * oy
        res.append(tot / (W * H))
    return res


def _stats(xs):
    xs = sorted(xs)
    n = len(xs)
    return dict(mean=round(sum(xs) / n, 3), p95=round(xs[min(n - 1, int(0.95 * n))], 3), max=round(xs[-1], 3))


# =====================================================================================================
# main
# =====================================================================================================

def build(full=FULL, site=None, budget=BUDGET, rebuild=False, report=None):
    """Computes the mist puffs. Returns (puffs, summary, scene)."""
    t0 = time.time()
    site = site or os.path.join(full, "site")
    scene = Scene(site)
    vox = Vox(load_voxels(full, rebuild))
    isles, isle_keys = find_islands(vox, scene)
    vox.set_ground(isle_keys)
    peaks = find_peaks(vox, scene, vox.ground)
    pills = []
    for x, z, top in peaks:
        pl = pillar(vox, scene, x, z, top)
        if pl:
            pills.append(pl)
    pills = dedupe_pillars(pills, isles)
    log("peaks", len(peaks), "pillars", len(pills), "islands", len(isles), "%.1f s" % (time.time() - t0))
    groups = []
    for pl in pills:
        vis = pl["top"] - pl["base"]
        groups.append(band_group(pl, _rng("rel", round(pl["x"]), round(pl["z"])).uniform(*BAND_REL), 0))
        if vis > 170.0:                              # tall: a second, lower band (the sea of clouds)
            groups.append(band_group(pl, _rng("rel2", round(pl["x"]), round(pl["z"])).uniform(0.14, 0.24), 1))
    groups += gorge_groups(vox, scene, pills)
    groups += pool_groups(vox, scene)
    groups += face_groups(vox, scene)
    groups += [isle_group(i) for i in isles]
    drops = collections.Counter()
    for g in groups:
        drops.update(keep_clear(scene, vox, g))
    groups = [g for g in groups if len(g["puffs"]) >= (3 if g["kind"] == "band" else 1)]
    for g in groups:
        g["score"] = score(scene, vox, g)
    groups = [g for g in groups if g["score"] >= MIN_SCORE]
    groups.sort(key=lambda g: -g["score"])
    chosen, n = [], 0
    for g in groups:
        if n + len(g["puffs"]) > budget:
            continue
        chosen.append(g)
        n += len(g["puffs"])
    puffs = [p for g in chosen for p in g["puffs"]]
    kinds = collections.Counter(g["kind"] for g in chosen)
    pk = collections.Counter(p["k"] for p in puffs)
    summary = dict(version=VERSION, puffs=len(puffs), groups=dict(kinds), byKind=dict(pk),
                   candidates=dict(peaks=len(peaks), pillars=len(pills), islands=len(isles), groups=len(groups)),
                   dropped=dict(drops), budget=budget,
                   source="sect/mist.py (voxels of out/web/full/raw/*.glb, site/camera.json, site/meta.json)")
    log("chosen", dict(kinds), "puffs", len(puffs), "dropped", dict(drops), "%.1f s" % (time.time() - t0))
    if report is not None:
        rep = dict(summary, chosen=[dict(key=g["key"], score=round(g["score"], 4), puffs=len(g["puffs"]),
                                         y=round(g["y"], 1)) for g in chosen],
                   pillars=[dict(x=round(p["x"], 1), z=round(p["z"], 1), top=round(p["top"], 1),
                                 base=round(p["base"], 1), why=p["why"], rTop=round(p["levels"][0]["rm"], 1),
                                 rBase=round(p["levels"][-1]["rm"], 1)) for p in pills],
                   islands=[{k: round(v, 1) for k, v in i.items()} for i in isles])
        rep["_puffs"] = puffs
        report.update(rep)
    return puffs, summary, scene


def strip(data):
    return [p for p in data.get("puffs", []) if not str(p.get("k", "")).startswith(TAG)]


def apply(full=FULL, site=None, budget=BUDGET, client=None, dry=False, rebuild=False, report_path=None,
          remove=False, out_path=None):
    """Rewrites <site>/clouds.json with the mist (old mist dropped first), or writes the result to
    out_path instead (a preview; site/ stays as it is). Returns the summary."""
    site = site or os.path.join(full, "site")
    cp = os.path.join(site, "clouds.json")
    with open(cp, encoding="utf-8") as fh:
        data = json.load(fh)
    base = strip(data)
    if remove:
        puffs, summary, scene = [], dict(version=VERSION, puffs=0), None
    else:
        rep = {} if report_path else None
        puffs, summary, scene = build(full, site, budget, rebuild, rep)
        # fill-rate estimate: Blender puffs vs + mist, at the holds and along the path (every 3rd frame)
        holds = [h["view"] for h in scene.holds]
        path = [View(f, scene.aspect, "path") for f in scene.frames[::3]]
        kept_base = [p for p in base if scene.client_dist(p["c"]) - max(math.sqrt(sum(v * v for v in a)) for a in p["a"])
                     <= CLIENT_KEEP]
        fb_h, fm_h = fill(kept_base, holds), fill(puffs, holds)
        fb_p, fm_p = fill(kept_base, path), fill(puffs, path)
        summary["fill"] = dict(
            note="screens of sprite fragments per frame (quad area clipped to a 16:9 screen, occlusion ignored)",
            holds={h["id"]: dict(blender=round(a, 2), mist=round(b, 2)) for h, a, b in zip(scene.holds, fb_h, fm_h)},
            path=dict(blender=_stats(fb_p), mist=_stats(fm_p), total=_stats([a + b for a, b in zip(fb_p, fm_p)])))
        log("fill holds", summary["fill"]["holds"])
        log("fill path", summary["fill"]["path"])
        if report_path:
            rep["fill"] = summary["fill"]
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(rep, fh, indent=1)
            log("report", report_path)
    for p in puffs:
        p.pop("_R", None)
    out = dict((k, v) for k, v in data.items() if k not in ("puffs", TAG))
    if puffs:
        out[TAG] = summary
    out["puffs"] = base + puffs
    log("clouds.json: %d Blender puffs + %d mist" % (len(base), len(puffs)))
    if dry:
        return summary
    dst = out_path or cp
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(tmp, dst)
    log("wrote", dst, os.path.getsize(dst), "bytes")
    if client and not out_path:
        os.makedirs(client, exist_ok=True)
        shutil.copyfile(cp, os.path.join(client, "clouds.json"))
        log("copied to", client)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mist.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--full", default=FULL, help="out/web/full (raw/ GLBs, the voxel cache)")
    ap.add_argument("--site", default="", help="data files folder (default <full>/site)")
    ap.add_argument("--budget", type=int, default=BUDGET, help="mist puffs at most")
    ap.add_argument("--client", nargs="?", const=CLIENT_FULL, default=None,
                    help="also copy clouds.json here (default %s)" % CLIENT_FULL)
    ap.add_argument("--dry", action="store_true", help="compute and report, write nothing")
    ap.add_argument("--rebuild", action="store_true", help="re-voxelise the GLBs even if the cache matches")
    ap.add_argument("--report", default="", help="write a JSON report (groups, pillars, islands, fill)")
    ap.add_argument("--strip", action="store_true", help="remove the mist puffs again")
    ap.add_argument("--out", default="", help="write the result here instead of <site>/clouds.json (preview)")
    a = ap.parse_args(argv)
    apply(a.full, a.site or None, a.budget, a.client, a.dry, a.rebuild, a.report or None, a.strip, a.out or None)


if __name__ == "__main__":
    main()
