"""World: the celestial realm around the Moonlit Sect (spec sections 0, 2, 4, 5).

Blocking pass for the AI video model: shape, scale, colour coding and depth matter, fine detail
does not. ``build(scene, anchors)`` creates

- sky + sun + haze + compositor (sect.lib.look, the same constants the previews use),
- the colossal moon (14 deg wide, NNE, 16 deg up, exact from the final summit shot) with a halo,
- THE FLOATING MOUNTAIN RANGE: one heightfield mass (top + inverted craggy underside, joined by a
  RIM_LIP m lip along the outline) that
  climbs from the gate (south, z = 40) to the summit (north, z = 320): a flat terrace at
  anchor z - 0.4 (radius >= footprint + 9) under every anchor except the arena, steep cliffs,
  ridges/saddles between consecutive anchors that stay >= 25 m under the anchor-to-anchor line,
  tall side peaks only > 120 m off that corridor, a gap under the floating arena, a slope under
  the gate stairway, Huangshan pines on its flatter tops and roots hanging from its underside,
- a geometry cloud sea (cheap, real parallax) with a fog layer the underside dissolves into,
  mid-level cloud banks between the peaks, faint high cirrus, the opening cloud bank,
- 30 floating islets (pines, no buildings), 5 waterfalls off the range's edges,
- connectors between consecutive areas (docs/scene/architecture-audit.md section 2, W1-W6): each runs
  from the area it leaves (AREA['depart']) to the area it reaches (AREA['arrival']). Marble
  stairways with 0.17 m risers, flights of at most 18 and landings between, an archway at the
  foot and a rest pavilion halfway up the long ones, on a stone footing near the ground and on
  corbelled stone piers 15-20 m apart where it falls away;
  a level arched bridge (library to steles), a stepped chain bridge to the arena and floating
  stepping stones from it. ``build_connectors`` prints one ``WORLD LINK`` report line per link.
  No two of their faces share a plane, and none shares one with the range (round 11: the web draws
  every baked face double-sided, so those z-fought): landings are flush with the treads and carry
  their walls inset, and the range sinks SINK m under the stairs where it lay at their level
  (sink_under_links).

World coordinates: metres, Z up, +Y north (direction of travel).
"""

import contextlib
import importlib
import json
import math
import time

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from sect.lib import look as L
from sect.lib import materials as M
from sect.lib import nature as N
from sect.lib import util as U

KEY = "world"

# spec section 4: key -> (x, y, z, footprint)
ANCHORS = {
    "gate": (0.0, 0.0, 40.0, 40.0),
    "mirror": (-95.0, 185.0, 70.0, 45.0),
    "forge": (115.0, 335.0, 95.0, 50.0),
    "arena": (-35.0, 485.0, 120.0, 48.0),
    "mission": (-150.0, 625.0, 140.0, 50.0),
    "library": (125.0, 765.0, 165.0, 42.0),
    "steles": (5.0, 905.0, 185.0, 50.0),
    "scroll": (-125.0, 1045.0, 205.0, 40.0),
    "formation": (65.0, 1195.0, 220.0, 58.0),
    "abode": (185.0, 1335.0, 250.0, 45.0),
    "summit": (0.0, 1500.0, 320.0, 40.0),
}
ORDER = ("gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll", "formation",
         "abode", "summit")
FLOATING = ("arena",)          # builds its own island; the range has a gap under it

# ---- tuned layout constants --------------------------------------------------------------
GRID = 2.5                     # heightfield cell (m). (Phase 3, 2026-10-21: was 5. Steep walls became 17-33 m
                               # slivers with zigzag folds, the stepped slabs at the arena 516 cliff and the abode
                               # skirt at 1208; at 2.5 m folds over 45 deg drop from 21.6 % to 6.3 %. The fields
                               # are unchanged and every 5 m node is still a node: the surface only moves between
                               # the old nodes, toward the analytic one)
EXTENT = (-640.0, 680.0, -340.0, 1920.0)   # heightfield x0, x1, y0, y1
RIM_DROP = 75.0                # the range's rim (top meets underside) sits this far under the corridor
CORRIDOR_CLEAR = 25.0          # ridges stay at least this far under the anchor-to-anchor line
CORRIDOR_HALF = 120.0          # taller-than-corridor peaks only beyond this distance from it
PEAK_WALL = 3.4                # peak wall steepness (m down per m out, ~74 deg)
TERRACE_PAD = 9.0              # flat terrace radius = footprint + TERRACE_PAD (+ up to 6 m bulges)
SUMMIT_FLAT_R = 39.5           # the summit's flat radius: no pad, no bulges (W7)
CLOUD_SEA_Z = -60.0            # cloud-sea top (billows reach ~15 m above, fog thickens below)
OPENING_BANK = (0.0, -260.0, 15.0)          # the film opens inside this cloud bank
MOON_VIEW = (0.0, 1500.0, 330.0)            # final shot camera: the moon is exactly 14 deg wide here
MOON_DISTANCE = 5000.0
MOON_GLOW = 1.25
FOREST_DENSITY = 0.0           # pines per m2 on the range's flatter tops (~0.7k tris each). Round 48: 0 (was 0.0008):
                               # scenery.build_canopy's broadleaf canopy covers the tops (no trunk carpet)
BANK_DENSITY = 2.2             # cloud_bank density (EEVEE thins distant volumes)
HAZE = dict(density=0.0003, base_z=100.0, falloff=220.0, z_min=CLOUD_SEA_Z - 60.0)

# Four review views (name, location, target, lens), also used by the preview script.
PREVIEW_CAMERAS = [
    ("south", (0.0, -200.0, 30.0), (-10.0, 420.0, 115.0), 26),
    ("overview", (-1250.0, -700.0, 760.0), (10.0, 760.0, 110.0), 30),
    ("formation", (25.0, 1105.0, 252.0), (265.0, 1420.0, 232.0), 24),
    ("moon", MOON_VIEW, tuple(Vector(MOON_VIEW) + L.MOON_DIR * 100.0 + Vector((0, 0, -4.0))), 24),
]


def _log(*a):
    print("WORLD", *a, flush=True)


def _strata(h, step):
    """Sandstone/granite bedding: mostly steep risers with narrow ledges every ``step`` m."""
    fr = np.mod(h / step, 1.0)
    return h - step * fr + step * _smooth(0.25, 1.0, fr)


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---- round 48: the range's tall peaks as karst pillars (scratchpad r45/plan_final.md P-1) ---------------------------
# Range(peak_mode=...): 'strata' is the range as built until round 47; 'pillars' cuts every peak's cone flat at its
# plinth (the highest rim over its footprint + PILLAR_RIM_CLEAR, at least its peak-free ground) and build_peak_pillars
# stands a lib.nature.peak_pillar on it, sunk PILLAR_SINK m, inside the old cone at every height; 'benches' (B0
# variant a, expected to lose: contour-line benches, critique P1) turns each cone's strata into irregular benches.
# world.range keeps every vertex and face in every mode (only heights change, Range.peak_height), so the area groves
# and gardens seeded on its faces stay where they are. The shrine peaks (life.SHRINES) stay cones.
PEAK_MODE = "pillars"          # a fresh build makes the round-48 range
PILLAR_RIM_CLEAR = 3.0         # m: a cut peak stays at least this far over the rim (keeps world.range's outline)
PILLAR_SINK = 9.0              # m the pillar's foot sinks into the plinth
PILLAR_MIN_H = 30.0            # m: a pillar shorter than this over its plinth is not built (the old cone stays)
PILLAR_FOOT_SHARE = 0.6        # a pillar's foot radius at most this share of the old cone's radius at the plinth
PILLAR_HERO_D = 180.0          # m: a pillar this near a hold camera is built at the "hero" level (1.25 m), else "mid"
PILLAR_PRESET = "sandstone"    # every cut peak (round 48 B0 pick: b). "auto": columns sandstone, granite cones granite
                               # (auto made the f870 wall, peak 72, a granite cone with no ledges)
PILLAR_FIT_SLACK = 1.5         # m: the pillar's radius may pass the old cone's (nominal) by this much at any height
# Peaks that stay cones in every mode, like the shrine peaks: their pillar would stand on an area's terrace (mirror 15
# 17, forge 4 5, steles 64 66, formation 61 62 63), within patch_r48_range.PATH_CLEAR m of chase.cam (15 18 44 64) or
# within LINK_CLEAR m of a link (15 18 44 62). Found by the patch's own checks in a dry run over the whole range with
# both presets on the box (2026-10-24, round 48 B0).
PILLAR_KEEP_CONE = frozenset((4, 5, 15, 17, 18, 44, 61, 62, 63, 64, 66))
BENCH_GAP = (14.0, 30.0)       # m between benches (variant a)
BENCH_SHARE = (0.3, 0.45)      # share of a riser a bench flattens


def _benches(h, levels, shares):
    """Terrace map of heights ``h`` onto irregular bench ``levels`` (ascending): within each gap the lower
    ``share`` stays flat, the rest rises smoothly (like _strata, but per peak and uneven)."""
    j = np.clip(np.searchsorted(levels, h, side="right") - 1, 0, len(levels) - 2)
    lo = levels[j]
    gap = levels[j + 1] - lo
    t = np.clip((h - lo) / gap, 0.0, 1.0)
    return lo + gap * _smooth(shares[j], 1.0, t)


def cone_radius(rc, hc, top, wall, z):
    """Nominal radius of a world.Range peak's cone (cap radius rc, cap height hc, top, wall slope) at height z."""
    if z > top - hc:
        return rc * math.sqrt(max(0.0, (top - z) / hc))
    return rc + (top - hc - z) / wall


def shrine_peaks(peaks):
    """Indices of the peaks life.SHRINES stand on (the nearest peak within life.PEAK_MATCH m of each shrine)."""
    from sect import life as LF
    out = set()
    for s in LF.SHRINES:
        d = [math.hypot(p[0] - s["xy"][0], p[1] - s["xy"][1]) for p in peaks]
        k = int(np.argmin(d))
        if d[k] <= LF.PEAK_MATCH:
            out.add(k)
    return out


# =========================================================================================
# deterministic numpy noise
# =========================================================================================

class _VNoise:
    """Smooth value noise / fBm / cellular spikes on numpy arrays (seeded, platform-stable)."""

    def __init__(self, seed, n=256):
        rs = np.random.RandomState(seed)
        self.n = n
        self.t = rs.uniform(-1.0, 1.0, (n, n))
        self.off = rs.uniform(0, n, (32, 2))
        self.jit = rs.uniform(0.15, 0.85, (64, 64, 2))
        self.amp = rs.uniform(0.0, 1.0, (64, 64))

    def __call__(self, x, y, scale, o=0):
        n = self.n
        u = np.asarray(x, float) * scale + self.off[o % 32, 0]
        v = np.asarray(y, float) * scale + self.off[o % 32, 1]
        i, j = np.floor(u), np.floor(v)
        fu, fv = u - i, v - j
        fu = fu * fu * (3.0 - 2.0 * fu)
        fv = fv * fv * (3.0 - 2.0 * fv)
        i = i.astype(np.int64) % n
        j = j.astype(np.int64) % n
        i1, j1 = (i + 1) % n, (j + 1) % n
        t = self.t
        a, b, c, d = t[i, j], t[i1, j], t[i, j1], t[i1, j1]
        return a + (b - a) * fu + (c - a) * fv + (a - b - c + d) * fu * fv

    def fbm(self, x, y, scale, octaves=3, o=0, gain=0.5):
        tot, amp, norm = 0.0, 1.0, 0.0
        for k in range(octaves):
            tot = tot + amp * self(x, y, scale * (2.03 ** k), o + 3 * k)
            norm += amp
            amp *= gain
        return tot / norm

    def cells(self, x, y, spacing):
        """Distance to the nearest jittered feature point and that point's random amplitude."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        ci = np.floor(x / spacing).astype(np.int64)
        cj = np.floor(y / spacing).astype(np.int64)
        best = np.full(x.shape, 1e9)
        bamp = np.zeros(x.shape)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                i, j = ci + di, cj + dj
                im, jm = i % 64, j % 64
                px = (i + self.jit[im, jm, 0]) * spacing
                py = (j + self.jit[im, jm, 1]) * spacing
                d = np.hypot(x - px, y - py)
                m = d < best
                best = np.where(m, d, best)
                bamp = np.where(m, self.amp[im, jm], bamp)
        return best, bamp


# =========================================================================================
# the mountain range as a height field
# =========================================================================================

def _norm_anchors(anchors):
    src = anchors if anchors else ANCHORS
    out = {}
    for k, v in src.items():
        v = tuple(float(c) for c in v)
        if len(v) < 4:
            v = v + (ANCHORS.get(k, (0, 0, 0, 40.0))[3],)
        out[k] = v[:4]
    return out


class Range:
    """Analytic top surface T(x, y), rim level and underside B(x, y) of the floating range.

    ``fields(x, y)`` works on numpy arrays of any shape (also used to place islets, waterfalls
    and stairways on the terrain)."""

    def __init__(self, anchors, yaws=None, peak_mode=None, plan_opts=None):
        self.anchors = anchors
        self.peak_mode = PEAK_MODE if peak_mode is None else peak_mode      # round 48: 'strata', 'benches', 'pillars'
        if self.peak_mode not in ("strata", "benches", "pillars"):
            raise ValueError("peak_mode must be 'strata', 'benches' or 'pillars' (got %r)" % (self.peak_mode,))
        self.plan_opts = dict(plan_opts or {})
        self.yaws = dict(yaws) if yaws else _anchor_yaws(anchors)
        self.keys = [k for k in ORDER if k in anchors] + [k for k in anchors if k not in ORDER]
        self.noise = _VNoise(1337)
        self.segs = []
        for i in range(len(self.keys) - 1):
            ka, kb = self.keys[i], self.keys[i + 1]
            a, b = anchors[ka], anchors[kb]
            d = Vector((b[0] - a[0], b[1] - a[1]))
            r = U.rng("world.ridge", ka, kb)
            self.segs.append(dict(
                i=i, ka=ka, kb=kb, a=a, b=b, L=d.length, u=d.normalized(),
                mass=(ka not in FLOATING and kb not in FLOATING),
                meander=r.uniform(10.0, 22.0) * (1 if r.random() < 0.5 else -1),
                notch=(ka == "library" and kb == "steles")))
        self.peaks = self._make_peaks()
        if self.peak_mode != "strata" and "skip" not in self.plan_opts:
            self.plan_opts["skip"] = shrine_peaks(self.peaks) | set(PILLAR_KEEP_CONE)

    # ---- corridor geometry
    def seg_coords(self, s, x, y):
        a, u, L_ = s["a"], s["u"], s["L"]
        rx, ry = x - a[0], y - a[1]
        along = rx * u.x + ry * u.y
        perp = -rx * u.y + ry * u.x                      # + = left of travel (west-ish)
        t = np.clip(along / L_, 0.0, 1.0)
        px, py = a[0] + t * u.x * L_, a[1] + t * u.y * L_
        dist = np.hypot(x - px, y - py)
        zl = a[2] + t * (s["b"][2] - a[2])
        return t, along, perp, dist, zl

    def seg_point(self, s, t, lateral=0.0):
        a, u, L_ = s["a"], s["u"], s["L"]
        return (a[0] + u.x * L_ * t - u.y * lateral, a[1] + u.y * L_ * t + u.x * lateral,
                a[2] + t * (s["b"][2] - a[2]))

    def _make_peaks(self):
        """(x, y, top, radius, wall, cap) per peak: about half are Zhangjiajie columns (near
        vertical walls, broad rounded cap), the rest Huangshan granite cones; each with 1-3
        lower fingers. All stay > CORRIDOR_HALF m off the corridor above its clearance line."""
        r = U.rng("world.peaks", 5)
        peaks = []
        for s in self.segs:
            count = 3 if s["mass"] else 4
            for k in range(count):
                t = (k + r.uniform(0.15, 0.85)) / count
                side = 1 if (k + s["i"]) % 2 == 0 else -1
                if r.random() < 0.3:
                    side = -side
                column = r.random() < 0.5
                wall, cap = (6.5, 0.62) if column else (PEAK_WALL, 0.38)
                rad = r.uniform(22.0, 40.0) if column else r.uniform(24.0, 46.0)
                zl = s["a"][2] + t * (s["b"][2] - s["a"][2])
                top = zl + r.choice((r.uniform(-30.0, 40.0), r.uniform(40.0, 150.0), r.uniform(60.0, 170.0)))
                rc = cap * rad
                above = max(0.0, top - (zl - CORRIDOR_CLEAR))
                dist = CORRIDOR_HALF + 40.0 + rc + above / wall + r.uniform(0.0, 120.0)
                cx, cy, _ = self.seg_point(s, t, side * dist)
                peaks.append((cx, cy, top, rad, wall, cap))
                for m in range(r.randint(1, 3)):
                    ang = r.uniform(0.0, 2.0 * math.pi)
                    dd = rad * r.uniform(0.8, 1.5)
                    peaks.append((cx + math.cos(ang) * dd, cy + math.sin(ang) * dd,
                                  top - r.uniform(15.0, 75.0), rad * r.uniform(0.35, 0.6), wall, cap))
        # a few big outliers framing the ends of the range
        for (x, y, z, rad) in ((-330.0, -120.0, 120.0, 40.0), (300.0, -60.0, 90.0, 34.0),
                               (-380.0, 1720.0, 380.0, 44.0), (330.0, 1760.0, 300.0, 38.0),
                               (-470.0, 900.0, 330.0, 46.0), (520.0, 1050.0, 290.0, 40.0)):
            peaks.append((x, y, z, rad, 6.0, 0.6))
        return peaks

    # ---- fields
    def _base(self, x, y):
        """The range without its peaks: dict(mass (the broad base and the ridges, the gap under the floating areas),
        rim, dmin, zl). fields() adds the peaks, the corridor cap and the terraces on top (round 48 split; the numbers
        are the same as before)."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        nz = self.noise
        S = [self.seg_coords(s, x, y) for s in self.segs]
        dist = np.stack([q[3] for q in S])
        zls = np.stack([q[4] for q in S])
        dmin = dist.min(axis=0)
        j = dist.argmin(axis=0)
        zl = np.take_along_axis(zls, j[None], axis=0)[0]
        w = np.exp(-(dist - dmin) / 30.0)
        rim = (w * zls).sum(axis=0) / w.sum(axis=0) - RIM_DROP + 9.0 * nz.fbm(x, y, 1 / 260.0, 2, o=1)

        mass = np.full(x.shape, -1e4)
        for s, (t, along, perp, dseg, zls_) in zip(self.segs, S):
            if not s["mass"]:
                continue
            sn = np.sin(np.pi * t)
            # broad base: gives the range its width, reaches the rim ~150 m off the corridor
            base = zls_ - RIM_DROP + 26.0 - 0.21 * np.maximum(0.0, dseg - 40.0) \
                + 16.0 * nz.fbm(x, y, 1 / 90.0, 3, o=2)
            mass = np.maximum(mass, base)
            # ridge / saddle along a meandering crest
            off = s["meander"] * sn
            ex = np.maximum(0.0, -along) + np.maximum(0.0, along - s["L"])
            rr = np.hypot(perp - off, ex)
            crest = zls_ - 33.0 - 22.0 * sn + 7.0 * nz(x, y, 1 / 45.0, o=3)
            if s["notch"]:
                crest = crest - 85.0 * np.exp(-((t - 0.5) / 0.07) ** 2)
            prof = 1.5 * np.minimum(rr, 14.0) + 0.62 * np.maximum(rr - 14.0, 0.0)
            ridge = crest - prof + 5.0 * nz.fbm(x, y, 1 / 16.0, 2, o=4)
            mass = np.maximum(mass, ridge)
        # gap under the floating areas
        for k in FLOATING:
            if k in self.anchors:
                a = self.anchors[k]
                da = np.hypot(x - a[0], y - a[1])
                mass = mass - 400.0 * _smooth(115.0, 80.0, da)
        return dict(mass=mass, rim=rim, dmin=dmin, zl=zl)

    def fields(self, x, y):
        """Returns dict(T, F, rim, flat, dmin, zl, near, T_full, F_under): top height, F = T - rim (> 0 inside the
        mass), rim level, flat-terrace mask, distance to the corridor and its line height. Round 48: with peak_mode
        'benches' or 'pillars' the peaks change (peak_height); T_full / F_under are the top with every peak as built
        until round 47 (the underside keeps its depth under a pillar, islets keep off the pillars)."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        nz = self.noise
        b = self._base(x, y)
        mass, rim, dmin, zl = b["mass"], b["rim"], b["dmin"], b["zl"]
        track = self.peak_mode != "strata"            # round 48: also keep the top with the old peaks
        mass_full = mass
        # tall peaks and their fingers (placed off the corridor)
        crag = 1.0 + 0.22 * nz(x, y, 1 / 22.0, o=5) + 0.12 * nz(x, y, 1 / 7.0, o=11)
        for k, (cx, cy, top, rad, wall, cap) in enumerate(self.peaks):
            d = np.hypot(x - cx, y - cy)
            if d.size > 1 and d.min() > 600.0:
                continue
            u = d * crag
            rc, hc = cap * rad, (0.14 if wall < 5.0 else 0.09) * rad
            h = np.where(u < rc, top - hc * (u / rc) ** 2, top - hc - wall * (u - rc))
            old = np.where(u < rc, h, _strata(h, 11.0))
            mass = np.maximum(mass, self.peak_height(k, old, h, u, rc, rim) if track else old)
            if track:
                mass_full = np.maximum(mass_full, old)
        # nothing taller than (line - clearance) near the camera corridor
        cap = zl - CORRIDOR_CLEAR + 3000.0 * _smooth(CORRIDOR_HALF, CORRIDOR_HALF + 40.0, dmin)
        T = np.minimum(mass, cap)
        T_full = np.minimum(mass_full, cap) if track else T

        flat = np.zeros(x.shape, bool)
        near = np.zeros(x.shape, bool)
        for k, (ax, ay, az, fp) in self.anchors.items():
            if k in FLOATING:
                continue
            d = np.hypot(x - ax, y - ay)
            th = np.arctan2(y - ay, x - ax)
            bulge = 6.0 * np.maximum(0.0, nz(ax + 40.0 * np.cos(th), ay + 40.0 * np.sin(th), 1 / 30.0, o=6))
            # (W7: the summit's flat ends right under its marble rim, so the balustrade is the
            # cliff rail; before, 10-16 m of unrailed grass ringed it)
            rf = SUMMIT_FLAT_R if k == "summit" else fp + TERRACE_PAD + bulge
            u = np.maximum(0.0, d - rf)
            drop = (3.2 * np.minimum(u, 10.0) + 1.15 * np.maximum(u - 10.0, 0.0)) \
                * (1.0 + 0.25 * nz(x, y, 1 / 30.0, o=7))
            T = np.maximum(T, az - 0.4 - drop)
            if T_full is not T:
                T_full = np.maximum(T_full, az - 0.4 - drop)
            flat |= d <= rf
            near |= d <= fp + TERRACE_PAD + 14.0
        # slope under the gate stairway (gate.py: stair top y = -46, foot y ~ -131 at local z -56)
        if "gate" in self.anchors:
            gx, gy, gz, gfp = self.anchors["gate"]
            along = (gy - 46.0) - y
            lat = np.abs(x - gx)
            # (max(along, 0): north of the stair top the slope stays under the plaza, z gz - 1.8;
            # before, it kept rising and left a 3.5 m grass mound over the forecourt)
            ramp = gz - 1.8 - 0.659 * np.maximum(along, 0.0) - 1.7 * np.maximum(0.0, lat - 13.0) \
                - 4.0 * np.maximum(0.0, nz(x, y, 1 / 20.0, o=8)) * _smooth(13.0, 25.0, lat)
            ramp = np.where(along > -12.0, ramp, -1e4)
            T = np.maximum(T, ramp)
            # (W7 / audit 1.1: a notch for the grand stair's top flights; the terrace, now 9 m
            # wider, buried about 20 of the top flight's 24 steps under up to 2.9 m of moss)
            cut = (along > 0) & (lat < 15.0)
            T = np.where(cut, np.minimum(T, gz - 1.0 - 0.82 * np.minimum(along, 5.3)
                                         - 0.6 * np.maximum(along - 5.3, 0)), T)
            if T_full is not T:
                T_full = np.maximum(T_full, ramp)
                T_full = np.where(cut, np.minimum(T_full, gz - 1.0 - 0.82 * np.minimum(along, 5.3)
                                                  - 0.6 * np.maximum(along - 5.3, 0)), T_full)
            near |= (along > -12.0) & (lat < 22.0)
        F = T - rim
        F_under = F if T_full is T else T_full - rim
        return dict(T=T, F=F, rim=rim, flat=flat, near=near, dmin=dmin, zl=zl, T_full=T_full, F_under=F_under)

    # ---- round 48: peaks as pillars (P-1) or benched cones (B0 variant a)
    def peak_height(self, k, old, h, u, rc, rim):
        """Height of peak k over the field points: ``old`` (the cone with _strata(h, 11), as built until round 47) in
        peak_mode 'strata' and for every peak the plan leaves alone; 'benches': per-peak irregular benches (B0 variant
        a); 'pillars': the cone cut flat at the peak's plinth (a peak_pillar object stands on it). Wherever ``old`` is
        over the rim the result stays over it by at least PILLAR_RIM_CLEAR (or ``old``), and where ``old`` is not it
        stays ``old``: world.range keeps exactly its vertices and faces (only heights move), so every scatter seeded
        on its faces keeps its trees where nothing moved."""
        if self.peak_mode == "strata":
            return old
        spec = self.pillar_plan().get(k) if self.peak_mode == "pillars" else self.bench_plan().get(k)
        if spec is None:
            return old
        if self.peak_mode == "pillars":
            new = np.minimum(old, spec["plinth"])
        else:
            new = np.where(u < rc, h, _benches(h, spec["levels"], spec["shares"]))
        over = old > rim
        return np.where(over, np.maximum(new, np.minimum(old, rim + PILLAR_RIM_CLEAR)), old)

    def _peak_base_stats(self, k, reach, foot):
        """(highest rim out to ``reach`` m from peak k, highest peak-free ground within ``foot`` m): polar samples."""
        cx, cy = self.peaks[k][:2]
        out = []
        for rmax in (reach, foot):
            rr = np.concatenate([[0.0], np.repeat(np.linspace(rmax / 6.0, rmax, 6), 24)])
            aa = np.concatenate([[0.0], np.tile(np.linspace(0.0, 2 * math.pi, 24, endpoint=False), 6)])
            out.append(self._base(cx + rr * np.cos(aa), cy + rr * np.sin(aa)))
        return float(out[0]["rim"].max()), float(out[1]["mass"].max())

    def bench_plan(self):
        """B0 variant a: {peak: dict(levels (ascending), shares)}: benches 14-30 m apart from each peak's own top down
        (no shared heights across peaks), each flattening 30-45 % of its riser."""
        if getattr(self, "_bench_cache", None) is None:
            out = {}
            only = self.plan_opts.get("only")
            for k, (cx, cy, top, rad, wall, cap) in enumerate(self.peaks):
                if k in self.plan_opts.get("skip", ()) or (only is not None and k not in only):
                    continue
                r = U.rng("world.bench", k)
                hc = (0.14 if wall < 5.0 else 0.09) * rad
                z = top - hc - r.uniform(4.0, 12.0)
                lv = [top + 5.0]
                while z > CLOUD_SEA_Z - 80.0:
                    lv.append(z)
                    z -= r.uniform(*BENCH_GAP)
                lv.append(CLOUD_SEA_Z - 400.0)
                lv = np.array(sorted(lv))
                out[k] = dict(levels=lv, shares=np.array([r.uniform(*BENCH_SHARE) for _ in lv]))
            self._bench_cache = out
        return self._bench_cache

    def pillar_plan(self):
        """{peak: pillar spec} for peak_mode 'pillars' (built once): plinth z (highest rim over the footprint +
        PILLAR_RIM_CLEAR, at least the peak-free ground there), the pillar's top (the old top less part of its rounded
        cap; plan_opts['limits'] can lower it: the composition's skyline, quiet-sky and moon rules), radii inside the
        old cone, preset (plan_opts['preset'], else PILLAR_PRESET; 'auto': columns sandstone, granite cones granite), LOD ('hero' within
        PILLAR_HERO_D m of a hold camera), seed. plan_opts: skip (peak indices that stay cones: the shrine peaks),
        only (peak indices to rebuild, the rest stay; B0 / slice scope), limits {peak: top z}, holds [xyz], preset."""
        if getattr(self, "_pillars", None) is not None:
            return self._pillars
        o = self.plan_opts
        out = {}
        only = o.get("only")
        holds = np.asarray(o.get("holds") or [a[:3] for a in self.anchors.values()], float).reshape(-1, 3)
        for k, (cx, cy, top, rad, wall, cap) in enumerate(self.peaks):
            if k in o.get("skip", ()) or (only is not None and k not in only):
                continue
            column = wall > 5.0
            rc, hc = cap * rad, (0.14 if wall < 5.0 else 0.09) * rad
            rim_c = float(self._base(np.array([cx]), np.array([cy]))["rim"][0])
            reach = rc + max(0.0, top - hc - (rim_c - 15.0)) / wall     # where the cone meets the rim
            rim_max, ground = self._peak_base_stats(k, min(reach * 1.5, 420.0), rc * 1.5 + 6.0)
            plinth = max(rim_max + PILLAR_RIM_CLEAR, min(ground + 2.0, top - PILLAR_MIN_H))
            preset = o.get("preset") or PILLAR_PRESET
            if preset == "auto":
                preset = "sandstone" if column else "granite"
            r = U.rng("world.pillar", k)
            top_z = top - hc * 0.6
            lim = (o.get("limits") or {}).get(k)
            if lim is not None and lim < top_z:
                top_z = max(float(lim), plinth + PILLAR_MIN_H)
            if top_z - plinth < PILLAR_MIN_H - 1e-3:
                continue                                       # a stub: the old cone stays
            top_r = float(np.clip(rc * r.uniform(0.78, 0.92), 4.5, 42.0))
            k_bot = r.uniform(1.05, 1.3) if preset == "sandstone" else r.uniform(1.6, 2.2)

            bot_r = float(min(top_r * k_bot, PILLAR_FOOT_SHARE * cone_radius(rc, hc, top, wall, plinth)))
            dh = float(np.min(np.linalg.norm(holds[:, :2] - np.array([cx, cy]), axis=1)))
            lod = "hero" if dh < PILLAR_HERO_D else "mid"
            out[k] = dict(k=k, x=float(cx), y=float(cy), plinth=float(plinth), top_z=float(top_z), top_r=top_r,
                          bot_r=max(bot_r, top_r * 0.9), height=float(top_z - plinth + PILLAR_SINK), preset=preset,
                          lod=lod, seed=int(4800 + k), column=bool(column), old_top=float(top), rc=float(rc),
                          hc=float(hc), wall=float(wall), limited=bool(lim is not None and lim < top - hc * 0.6))
        self._pillars = out
        # the foot: PILLAR_SINK m under the lowest ground round it (the plinth disc can be narrower than the cone
        # where the crag noise pinches it); needs the finished plan, so it runs after it is stored
        a = np.linspace(0.0, 2 * math.pi, 32, endpoint=False)
        for s in out.values():
            g = self.fields(s["x"] + 1.05 * s["bot_r"] * np.cos(a), s["y"] + 1.05 * s["bot_r"] * np.sin(a))["T"]
            foot = min(s["plinth"], float(g.min())) - PILLAR_SINK
            s["height"] = float(s["top_z"] - foot)
            s["foot"] = float(foot)
        return out

    def underside(self, x, y, F, rim):
        """Inverted craggy underside: deeper under taller ground, cellular stalactite spikes,
        pinched to the rim at the outline."""
        nz = self.noise
        Fp = np.maximum(F, 0.0)
        depth = 2.6 * Fp ** 0.8 * (0.75 + 0.5 * nz(x, y, 1 / 120.0, o=9))
        cd, camp = nz.cells(x, y, 46.0)
        spike = (18.0 + 60.0 * camp) * np.clip(1.0 - cd / 26.0, 0.0, 1.0) ** 1.6 * _smooth(8.0, 45.0, Fp)
        crag = 5.0 * nz.fbm(x, y, 1 / 14.0, 2, o=10)
        depth = (depth + spike + crag) * _smooth(0.0, 9.0, Fp)
        return rim - np.maximum(depth, 0.0)

    # ---- point helpers
    def top_at(self, x, y):
        f = self.fields(np.array([x], float), np.array([y], float))
        return float(f["T"][0]), float(f["F"][0])


# =========================================================================================
# mesh helpers
# =========================================================================================

def _mesh_np(name, coll, verts, faces, materials, mat_idx=None, smooth=True):
    """Mesh object from numpy verts (n,3) and quad faces (m,4). smooth=False flat-shades every face. (Round 11:
    it used to leave the faces alone, and faces made through the mesh API are smooth in Blender 5: every link
    stair box (treads, parapets, landings, walls, piers) and chain-bridge plank shaded as a pillow, its normals
    averaged round 90 deg corners. That baked a light-to-dark ramp into each 1.6 m parapet box (the scales on
    the curves) and into every tread.)"""
    me = bpy.data.meshes.new(name)
    nv, nf = len(verts), len(faces)
    me.vertices.add(nv)
    me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    me.loops.add(nf * 4)
    me.loops.foreach_set("vertex_index", np.asarray(faces, np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", np.arange(0, nf * 4, 4, dtype=np.int32))
    try:
        me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
    except Exception:
        pass
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_idx, np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    for m in materials:
        me.materials.append(M.get(m) if isinstance(m, str) else m)
    me.polygons.foreach_set("use_smooth", np.full(len(me.polygons), bool(smooth)))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _box_corners(c, yaw, sx, sy, sz, pitch=0.0):
    """8 corners of a box centred on c, sx along the yaw direction, sz vertical."""
    cy, sy_ = math.cos(yaw), math.sin(yaw)
    out = []
    for dz in (-0.5, 0.5):
        for dx, dy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
            lx, ly = dx * sx, dy * sy
            out.append((c[0] + lx * cy - ly * sy_, c[1] + lx * sy_ + ly * cy, c[2] + dz * sz + dx * sx * pitch))
    return out


_BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def _boxes_obj(name, coll, boxes, material, smooth=False):
    """One mesh object from many boxes: (centre, yaw, sx, sy, sz[, pitch])."""
    verts, faces = [], []
    for b in boxes:
        base = len(verts)
        verts.extend(_box_corners(*b))
        faces.extend(tuple(base + i for i in f) for f in _BOX_FACES)
    if not faces:
        return None
    return _mesh_np(name, coll, np.array(verts), np.array(faces), [material], smooth=smooth)


def _tube_bm(bm, pts, radius, sides=5, twist_free=False):
    """Tapered tube along points (x, y, z, radius factor) into a BMesh (no caps). ``twist_free``: each ring's frame is
    the last one carried along the tube (parallel transport) instead of to_track_quat's, which spins freely about a
    near-vertical tube: the hanging roots' rings turned by up to half a turn from one to the next, their quads twisted
    into bow ties whose two triangles folded onto each other (round 12: 7 m2 within 5 mm, 78 m2 within 12 mm)."""
    rings = []
    nrm = None
    for i, p in enumerate(pts):
        a = Vector(pts[min(i + 1, len(pts) - 1)][:3]) - Vector(pts[max(i - 1, 0)][:3])
        if a.length < 1e-6:
            a = Vector((0, 0, -1))
        r = radius * (p[3] if len(p) > 3 else 1.0)
        ring = []
        if twist_free:
            t = a.normalized()
            if nrm is None:
                ref = Vector((1.0, 0.0, 0.0)) if abs(t.x) < 0.9 else Vector((0.0, 1.0, 0.0))
                nrm = (ref - t * ref.dot(t)).normalized()
            else:
                nrm = (nrm - t * nrm.dot(t)).normalized()
            bi = t.cross(nrm)
            for k in range(sides):
                ang = 2 * math.pi * k / sides
                ring.append(bm.verts.new(Vector(p[:3]) + (nrm * math.cos(ang) + bi * math.sin(ang)) * r))
            rings.append(ring)
            continue
        q = a.normalized().to_track_quat("Z", "Y")
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            ring.append(bm.verts.new(Vector(p[:3]) + q @ Vector((math.cos(ang) * r, math.sin(ang) * r, 0))))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            try:
                bm.faces.new((a[k], a[k2], b[k2], b[k]))
            except ValueError:
                pass


# =========================================================================================
# materials registered by world.py (all 'world_*')
# =========================================================================================

def _mat_cloud_sea(g):
    """Opaque sea of cloud (world coords): billowy tones, warm tops, a soft self-glow, faded
    with view distance into the horizon colour the world shader uses below the horizon."""
    p = g.coord("world")
    n1 = g.noise(p, 0.0045, detail=6.0, roughness=0.62)
    n2 = g.noise(p, 0.03, detail=4.0, roughness=0.55)
    h = g.add(g.mul(n1, 0.8), g.mul(n2, 0.2))
    col = g.ramp(h, [(0.32, "#9d9cb4"), (0.52, "#ece6e2"), (0.72, "#fff6ec")])
    nrm = g.bump(h, 0.55, 40.0)
    bsdf = g.principled(base_color=col, roughness=1.0, normal=nrm, emission_color=col,
                        emission_strength=0.22)
    cam = g.node("ShaderNodeCameraData")
    dist = g._sock(cam, "View Distance", outputs=True)
    near = g.math("EXPONENT", g.math("DIVIDE", dist, -4200.0))
    hz = L.LOOK["below_horizon_color"]
    far = g.emission((hz[0], hz[1], hz[2], 1.0), 1.0)
    g.viewport("#eeeae6", 0.9)
    g.output(g.mix_shader(near, far, bsdf))


def _mat_cloud_fog(g, top=CLOUD_SEA_Z + 75.0, bottom=CLOUD_SEA_Z - 25.0, density=0.022):
    """Fog layer above the cloud sea: thickens toward the bottom so the range's underside and the
    waterfalls dissolve into cloud; soft at the domain's XY edges."""
    z = g.sep(g.geometry("Position"))[2]
    k = g.maprange(z, top, bottom, 0.0, 1.0)
    k = g.mul(k, k)
    p = g.coord("world")
    n = g.noise(p, 0.012, detail=4.0, roughness=0.6)
    k = g.mul(k, g.maprange(n, 0.3, 0.7, 0.45, 1.25))
    gen = g.sep(g.coord("generated"))
    ex = g.mul(g.mul(g.smooth(gen[0], 0.0, 0.12), g.smooth(gen[0], 1.0, 0.88)),
               g.mul(g.smooth(gen[1], 0.0, 0.12), g.smooth(gen[1], 1.0, 0.88)))
    g.viewport("#f2efea", 0.5)
    g.output(volume=g.volume(color="#f6f1ea", density=g.mul(g.mul(k, ex), density), anisotropy=0.35))


def _mat_cirrus(g):
    """High thin streaky cloud: additive pale glow, alpha from stretched noise."""
    p = g.coord("object")
    q = g.vmath("MULTIPLY", p, (0.35, 2.4, 1.0))
    n = g.noise(q, 0.004, detail=5.0, roughness=0.65, distortion=0.6)
    s = g.mul(g.smooth(n, 0.5, 0.72), 0.55)
    gen = g.sep(g.coord("generated"))
    edge = g.mul(g.mul(g.smooth(gen[0], 0.0, 0.25), g.smooth(gen[0], 1.0, 0.75)),
                 g.mul(g.smooth(gen[1], 0.0, 0.3), g.smooth(gen[1], 1.0, 0.7)))
    a = g.mul(s, edge)
    em = g.emission("#ffd9c4", g.mul(a, 0.9))
    g.blended(shadows=False)
    g.viewport("#ffe6d6", 0.9)
    g.output(g.add_shader(g.transparent(), em))


def _mat_moon_halo(g):
    """Soft additive halo around the moon (object coords: the moon radius is 1)."""
    p = g.coord("object_raw")
    r = g.vmath("LENGTH", p)
    f = g.maprange(r, 1.0, 3.2, 1.0, 0.0)
    f = g.mul(g.mul(f, f), f)
    em = g.emission("#cfe0ff", g.mul(f, 1.4))
    g.blended(shadows=False)
    g.viewport("#cfe0ff", 0.9)
    g.output(g.add_shader(g.transparent(), em))


def _register_materials():
    M.register("world_cloud_sea", _mat_cloud_sea)
    M.register("world_cloud_fog", _mat_cloud_fog)
    M.register("world_cirrus", _mat_cirrus)
    M.register("world_moon_halo", _mat_moon_halo)
    M.variant("world_rock_under", "rock_cliff", light="#8a8274", mid="#5f5a52", dark="#3a3733", scan="rock063")
    # the connectors' piers, footings, arch and stair undersides: under its own tag, so the
    # walkability check reads them as structure (solid), not as floors. The cliff rock's sandstone
    # (#8a8172 to #5e5a52), so the supports recede into the cliffs they stand on and the white stair
    # reads on top (they were stone_grey: pale, uniform, brighter than the halls; audit D1)
    M.variant("world_pier_stone", "rock_cliff", light="#8a8172", mid="#736c62", dark="#5e5a52",
              warm="#8a7a66", cool="#6c6e6c", moss_amt=0.5, joints=0.6)


_register_materials()


# =========================================================================================
# builders
# =========================================================================================

def build_sky(scene, coll):
    """Sky + painted sun + cheap procedural cloud floor (world shader), sun lamp, compositor
    and a haze volume tuned for the range's altitudes."""
    L.setup_lookdev(scene, haze=False, compositor=True, cloud_floor=True)
    haze = L.add_haze(scene, coll, name="world.haze", density=HAZE["density"], base_z=HAZE["base_z"],
                      falloff=HAZE["falloff"], z_min=HAZE["z_min"])
    return haze


def build_moon(coll):
    """The colossal full moon: 14 deg wide seen from MOON_VIEW, NNE at 16 deg, with a halo."""
    centre, radius = L.moon_placement(MOON_DISTANCE, MOON_VIEW)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
    for f in bm.faces:
        f.smooth = True
    moon = U.mesh_from_bmesh("world.moon", bm, coll, materials=["moon_surface"],
                             location=centre, rotation=(0.35, -0.2, 1.1), scale=(radius,) * 3)
    moon["glow"] = MOON_GLOW
    U.set_visibility(moon, shadow=False)
    # halo: a disc just behind the moon's centre, facing the final camera position
    bm = bmesh.new()
    n_r, n_s = 12, 64
    rings = []
    for i in range(n_r + 1):
        rr = 0.9 + (3.3 - 0.9) * (i / n_r) ** 1.3
        rings.append([bm.verts.new((math.cos(2 * math.pi * k / n_s) * rr, math.sin(2 * math.pi * k / n_s) * rr, 0))
                      for k in range(n_s)])
    for a, b in zip(rings, rings[1:]):
        for k in range(n_s):
            bm.faces.new((a[k], a[(k + 1) % n_s], b[(k + 1) % n_s], b[k]))
    rot = (-L.MOON_DIR).to_track_quat("Z", "Y").to_euler()
    halo = U.mesh_from_bmesh("world.moon_halo", bm, coll, materials=["world_moon_halo"],
                             location=centre + L.MOON_DIR * radius * 0.25, rotation=rot, scale=(radius,) * 3)
    U.set_visibility(halo, shadow=False)
    return moon


def build_terrain(rng_, coll, grid=None, name="world.range"):
    """The range mesh (top + underside, joined by a RIM_LIP m vertical lip along the outline) on a ``grid`` m
    heightfield (default GRID). Returns (obj, grid dict)."""
    d = terrain_data(rng_, grid)
    ob = _mesh_np(name, coll, d["verts"], d["faces"], ["rock_cliff", "nature_soil_moss", "world_rock_under"],
                  mat_idx=d["mats"])
    at = ob.data.attributes.new("world_veg", 'FLOAT', 'FACE')
    at.data.foreach_set("value", d["veg"].astype(np.float32))
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(55))
    except Exception:
        pass
    return ob, d["grid"]


RIM_LIP = 0.5              # round 12: the underside starts this far under the rim and meets the top through a
                           # vertical lip along the outline. It was a knife edge: the outline's vertices were the top's
                           # and the underside's at once, so wherever a grid cell had three of them, its top and
                           # underside triangle were one triangle twice (rock or moss against world_rock_under, 438 m2),
                           # and next to the outline both lay within mm-cm of each other where the top barely cleared
                           # the rim (another 460 m2). The web draws both sides of every face: they z-fought along
                           # every edge of the range. Now the two are RIM_LIP apart everywhere


def terrain_data(rng_, grid=None, lip=RIM_LIP):
    """build_terrain's mesh as arrays: dict(verts (n, 3), faces (m, 4) quads, mats, veg, grid, n_top, n_inside,
    n_rim, n_lip). Vertices: the top's (inside and outline nodes, row by row), the underside's under the inside nodes,
    then (with ``lip``) one more under each outline node. Faces: the top's, the underside's, then the lip's.
    ``lip`` None: the knife edge built before round 12 (outline vertices shared, no lip; patch_r12_world's guard)."""
    step = GRID if grid is None else grid
    x0, x1, y0, y1 = EXTENT
    xs = np.arange(x0, x1 + 1e-6, step)
    ys = np.arange(y0, y1 + 1e-6, step)
    X, Y = np.meshgrid(xs, ys)
    ny, nx = X.shape
    f = rng_.fields(X, Y)
    T, F, rim = f["T"], f["F"], f["rim"]
    B = rng_.underside(X, Y, f.get("F_under", F), rim)      # (round 48: a pillar's plinth keeps the old underside)
    if lip is not None:
        B = np.minimum(B, rim - lip)
    inside = F > 0.0
    dirs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def shift(a, di, dj, fill):
        p = np.pad(a, 1, constant_values=fill)
        return p[1 + di:1 + di + ny, 1 + dj:1 + dj + nx]

    nb = np.zeros_like(inside)
    for di, dj in dirs:
        nb |= shift(inside, di, dj, False)
    boundary = (~inside) & nb
    used = inside | boundary
    # move boundary verts onto the zero crossing of F toward their inside neighbours
    sx = np.zeros(X.shape)
    sy = np.zeros(X.shape)
    sz = np.zeros(X.shape)
    cnt = np.zeros(X.shape)
    for di, dj in dirs:
        Fn = shift(F, di, dj, -1e3)
        m = boundary & shift(inside, di, dj, False)
        fr = np.clip(-F / np.where(m, Fn - F, 1.0), 0.0, 1.0)
        sx += np.where(m, X + fr * dj * step, 0.0)
        sy += np.where(m, Y + fr * di * step, 0.0)
        sz += np.where(m, rim + fr * (shift(rim, di, dj, 0.0) - rim), 0.0)
        cnt += m
    cnt = np.maximum(cnt, 1)
    VX = np.where(boundary, sx / cnt, X)
    VY = np.where(boundary, sy / cnt, Y)
    # (round 12: an outline vertex stands at the rim's height where it is, on the crossing; it stood at the rim's
    # height of its grid node, up to 2.5 m away, so where the crossing lay a few mm from an inside node the top's rim
    # triangles stood on edge as slivers, and the underside's, 'lip' under them, lay in their plane)
    topz = np.where(inside, T, rim if lip is None else sz / cnt)
    rim_v = np.where(boundary, sz / cnt, rim)

    idx_t = -np.ones(X.shape, np.int64)
    idx_t[used] = np.arange(used.sum())
    n_used = int(used.sum())
    n_in = int(inside.sum())
    idx_b = idx_t.copy()
    idx_b[inside] = n_used + np.arange(n_in)
    vlist = [np.stack([VX[used], VY[used], topz[used]], axis=1),
             np.stack([X[inside], Y[inside], B[inside]], axis=1)]
    n_rim = 0
    if lip is not None:
        # the outline's own underside vertices, lip m under its top ones (rim level)
        n_rim = int(boundary.sum())
        idx_b[boundary] = n_used + n_in + np.arange(n_rim)
        vlist.append(np.stack([VX[boundary], VY[boundary], rim_v[boundary] - lip], axis=1))
    verts = np.concatenate(vlist)

    c00, c01 = (slice(0, -1), slice(0, -1)), (slice(0, -1), slice(1, None))
    c11, c10 = (slice(1, None), slice(1, None)), (slice(1, None), slice(0, -1))
    cell = inside[c00] | inside[c01] | inside[c11] | inside[c10]
    q_t = np.stack([idx_t[c00][cell], idx_t[c01][cell], idx_t[c11][cell], idx_t[c10][cell]], axis=1)
    q_b = np.stack([idx_b[c00][cell], idx_b[c10][cell], idx_b[c11][cell], idx_b[c01][cell]], axis=1)
    q_l = np.zeros((0, 4), np.int64)
    if lip is not None:
        bot_of = -np.ones(len(verts), np.int64)
        bot_of[idx_t[used]] = idx_b[used]
        q_l = rim_lip(q_t, bot_of)
    # top face slope -> rock (0) or green ledge (1); underside rock (2)
    P = verts
    d1 = P[q_t[:, 2]] - P[q_t[:, 0]]
    d2 = P[q_t[:, 3]] - P[q_t[:, 1]]
    nrm = np.cross(d1, d2)
    nzc = nrm[:, 2] / np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)
    near_c = f["near"][c00][cell] | f["near"][c11][cell]
    flat_c = f["flat"][c00][cell] & f["flat"][c11][cell]
    in_c = inside[c00][cell] & inside[c01][cell] & inside[c11][cell] & inside[c10][cell]
    green = (nzc > 0.8) & in_c & ~(near_c & ~flat_c)
    mat_t = np.where(green | flat_c, 1, 0)
    veg = (nzc > 0.78) & in_c & (~near_c) & (F[c00][cell] > 4.0)
    faces = np.concatenate([q_t, q_b, q_l])
    mats = np.concatenate([mat_t, np.full(len(q_b) + len(q_l), 2)])
    veg = np.concatenate([veg, np.zeros(len(q_b) + len(q_l), bool)])
    grid = dict(X=X, Y=Y, T=T, F=F, B=B, rim=rim, inside=inside)
    return dict(verts=verts, faces=faces, mats=mats, veg=veg, grid=grid, n_top=n_used, n_inside=n_in, n_rim=n_rim,
                n_lip=len(q_l), n_qt=len(q_t), n_qb=len(q_b))


def rim_lip(q_t, bot_of):
    """The lip quads under the top's outline: every edge only one top quad uses (bot_of: the underside vertex under
    each top vertex), in the top quads' order, facing out (the top quads run counter-clockwise seen from above, so
    their outside is right of each edge): (v, u, u', v') for the top's edge u -> v."""
    e = np.stack([q_t, np.roll(q_t, -1, axis=1)], axis=2).reshape(-1, 2)
    key = np.sort(e, axis=1)
    big = int(e.max()) + 1
    _u, inv, cnt = np.unique(key[:, 0] * big + key[:, 1], return_inverse=True, return_counts=True)
    out = cnt[inv.ravel()] == 1
    u, v = e[out, 0], e[out, 1]
    if len(u) and (bot_of[u].min() < 0 or bot_of[v].min() < 0):
        raise ValueError("rim_lip: an outline edge ends on a vertex with no underside vertex")
    return np.stack([v, u, bot_of[u], bot_of[v]], axis=1)


def build_forest(terrain, coll):
    """Far-LOD Huangshan pines and shrubs on the range's flatter tops (not on the terraces)."""
    return N.scatter_on(terrain, N.plant_prototypes("forest"), density=FOREST_DENSITY, seed=21,
                        max_slope=math.radians(38), scale_range=(1.4, 2.6), mask_attribute="world_veg",
                        collection=coll, name="world.range.forest", align=0.1)


def build_roots(grid, coll, count=90, twist_free=True):
    """Roots hanging from the underside, thinning out toward the cloud. ``twist_free`` False: the tubes built before
    round 12 (patch_r12_world's guard)."""
    r = U.rng("world.roots", 1)
    X, Y, B, F, inside = grid["X"], grid["Y"], grid["B"], grid["F"], grid["inside"]
    cand = np.argwhere(inside & (F > 12.0) & (F < 120.0))
    bm = bmesh.new()
    if len(cand) == 0:
        return None
    for i in range(count):
        a, b = cand[r.randrange(len(cand))]
        x, y, z = float(X[a, b]), float(Y[a, b]), float(B[a, b])
        Lr = r.uniform(14.0, 48.0)
        pts = []
        for k in range(6):
            s = k / 5.0
            pts.append((x + r.uniform(-1.5, 1.5) * s + 2.0 * s * s, y + r.uniform(-1.5, 1.5) * s,
                        z + 2.0 - Lr * s, 1.0 - 0.85 * s))
        _tube_bm(bm, pts, r.uniform(0.5, 1.3), sides=5, twist_free=twist_free)
        for c in range(r.randint(0, 2)):
            s0 = r.uniform(0.2, 0.5)
            px, py, pz = pts[int(s0 * 5)][:3]
            ang = r.uniform(0, 2 * math.pi)
            Lc = Lr * r.uniform(0.3, 0.6)
            _tube_bm(bm, [(px, py, pz, 0.6), (px + math.cos(ang) * 2, py + math.sin(ang) * 2, pz - Lc * 0.5, 0.4),
                          (px + math.cos(ang) * 3, py + math.sin(ang) * 3, pz - Lc, 0.08)], 0.6, sides=4,
                     twist_free=twist_free)
    ob = U.mesh_from_bmesh("world.roots", bm, coll, materials=["nature_bark_blossom"], smooth=True)
    return ob


def build_cloud_sea(coll):
    """Geometry cloud sea (billowy grid, denser near the range) + a fog layer above it."""
    n = 160
    u = np.linspace(-1.0, 1.0, n + 1)
    g = np.sign(u) * np.abs(u) ** 2
    cx, cy = 0.0, 700.0
    X, Y = np.meshgrid(cx + 9000.0 * g, cy + 9000.0 * g)
    nz = _VNoise(77)
    Z = CLOUD_SEA_Z - 8.0 + 16.0 * nz.fbm(X, Y, 1 / 420.0, 3, o=1) + 8.0 * nz(X, Y, 1 / 160.0, o=2)
    idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
    q = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], axis=1)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    sea = _mesh_np("world.cloud_sea", coll, verts, q, ["world_cloud_sea"])
    U.set_visibility(sea, shadow=False)
    # fog layer: a box from below the sea top to well above it
    me = U.shared_mesh("world.unit_cube", lambda: _unit_cube_mesh())
    fog = U.object_from_mesh("world.cloud_fog", me, coll, location=(0.0, 700.0, CLOUD_SEA_Z + 25.0),
                             scale=(5200.0, 6400.0, 110.0))
    U.set_materials(fog, ["world_cloud_fog"])
    U.set_visibility(fog, shadow=False)
    return sea


def _unit_cube_mesh():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new("world.unit_cube")
    bm.to_mesh(me)
    bm.free()
    return me


def build_clouds(rng_, coll):
    """Opening bank, a bank swallowing the stair foot, mid-level banks between the peaks,
    wisps at the base of the range, high cirrus."""
    objs = []
    ox, oy, oz = OPENING_BANK
    # the opening bank: the camera starts inside it and pushes north out of it
    objs.append(N.cloud_bank(coll, size=230.0, seed=3, density=1.4, name="world.cloud.opening",
                             location=(ox, oy - 25.0, oz - 12.0), rotation=0.0))
    for i, (dx, dy, dz, s) in enumerate(((0.0, -8.0, 2.0, 70.0), (-34.0, -20.0, -4.0, 60.0),
                                         (36.0, -16.0, 6.0, 64.0), (8.0, -42.0, 12.0, 80.0))):
        objs.append(N.cloud_puff(coll, size=s, seed=40 + i, density=1.5, flatten=0.6,
                                 name="world.cloud.opening_puff", location=(ox + dx, oy + dy, oz + dz)))
    # the gate stairway dives into cloud at its foot
    for i, (x, y, z, s) in enumerate(((-38.0, -150.0, -24.0, 70.0), (34.0, -140.0, -20.0, 62.0),
                                      (0.0, -172.0, -30.0, 80.0), (-70.0, -110.0, -34.0, 60.0),
                                      (72.0, -96.0, -36.0, 58.0))):
        objs.append(N.cloud_puff(coll, size=s, seed=60 + i, density=1.3, flatten=0.5,
                                 name="world.cloud.stairfoot", location=(x, y, z)))
    # mid-level banks drifting between the peaks (off the corridor, under its height). Puffs must
    # be ~60 m+ to survive EEVEE's coarse far volume slices, hence big banks.
    r = U.rng("world.banks", 2)
    for s in rng_.segs:
        if r.random() < 0.2:
            continue
        side = 1 if (s["i"] % 2) else -1
        t = r.uniform(0.3, 0.7)
        dist = r.uniform(190.0, 320.0)
        x, y, zl = rng_.seg_point(s, t, side * dist)
        yaw = math.atan2(s["u"].y, s["u"].x) + r.uniform(-0.4, 0.4)
        objs.append(N.cloud_bank(coll, size=r.uniform(320.0, 460.0), seed=100 + s["i"], density=BANK_DENSITY,
                                 name="world.cloud.bank", location=(x, y, zl - r.uniform(45.0, 80.0)),
                                 rotation=yaw))
    # the gap under the arena
    if "arena" in rng_.anchors:
        ax, ay, az, _ = rng_.anchors["arena"]
        objs.append(N.cloud_bank(coll, size=340.0, seed=150, density=BANK_DENSITY, name="world.cloud.gap",
                                 location=(ax + 40.0, ay - 10.0, az - 110.0), rotation=0.6))
    # wisps where the underside meets the cloud sea, and banks on the sea further out
    for i in range(12):
        k = rng_.keys[min(len(rng_.keys) - 1, i % len(rng_.keys))]
        ax, ay, az, fp = rng_.anchors[k]
        ang = r.uniform(0, 2 * math.pi)
        rad = r.uniform(180.0, 600.0)
        objs.append(N.cloud_bank(coll, size=r.uniform(380.0, 600.0), seed=170 + i, density=BANK_DENSITY,
                                 name="world.cloud.wisp",
                                 location=(ax + math.cos(ang) * rad, ay + math.sin(ang) * rad,
                                           CLOUD_SEA_Z + r.uniform(10.0, 35.0)), rotation=ang))
    # high cirrus (faint, additive)
    for i, (x, y, z, sx, sy, yaw) in enumerate(((-1800.0, 300.0, 1700.0, 2600.0, 900.0, 0.5),
                                                (1500.0, 2200.0, 2100.0, 3000.0, 1000.0, -0.3),
                                                (-600.0, 3600.0, 2400.0, 3400.0, 1100.0, 0.15))):
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        ob = U.mesh_from_bmesh("world.cirrus", bm, coll, materials=["world_cirrus"],
                               location=(x, y, z), rotation=(0.0, 0.0, yaw), scale=(sx, sy, 1.0))
        U.set_visibility(ob, shadow=False)
        objs.append(ob)
    return objs


# ---- round 48: pillars on the peaks' plinths --------------------------------------------------------------------

def pillar_fit(spec, profile):
    """Worst excess (m) of a pillar's radius over its old peak's nominal cone over ``profile`` [(z, radius)]
    (nature.pillar_radius_profile; the pillar's own z), and the z where it is. Under PILLAR_FIT_SLACK: the pillar
    stays inside the space the old peak took, so it keeps the corridor clearance the peaks were placed for."""
    worst, wz = -1e9, None
    for z, rr in profile:
        c = cone_radius(spec["rc"], spec["hc"], spec["old_top"], spec["wall"], z)
        if z > spec["old_top"]:
            c = 0.0
        e = rr - c
        if e > worst:
            worst, wz = e, z
    return worst, wz


def fit_pillar(spec, tries=6):
    """Shrink the pillar's radii (8 % a try) until pillar_fit passes. Returns (spec, excess, tries used); spec None
    when it never fits (the old cone stays)."""
    s = dict(spec)
    for t in range(tries + 1):
        prof = N.pillar_radius_profile(s["height"], s["top_r"], s["bot_r"], s["seed"], s["top_z"], s["preset"],
                                       s["lod"])
        e, _z = pillar_fit(s, prof)
        if e <= PILLAR_FIT_SLACK:
            return s, e, t
        s["top_r"] *= 0.92
        s["bot_r"] *= 0.92
    return None, e, tries


def build_peak_pillars(rng_, coll, plan=None, log=None):
    """One lib.nature.peak_pillar per entry of rng_.pillar_plan() (``plan``), named 'world.peak.<NNN>' (NNN = the
    peak's index in Range.peaks), tagged 'r48_peak', each fitted inside its old cone (fit_pillar). Returns
    [(peak, object, info)]."""
    log = log or _log
    plan = rng_.pillar_plan() if plan is None else plan
    out = []
    for k in sorted(plan):
        s, excess, tries = fit_pillar(plan[k])
        if s is None:
            log("WARN pillar", k, "does not fit inside its old cone (excess %.1f m): the cone stays" % excess)
            continue
        ob, info = N.peak_pillar(coll, height=s["height"], top_radius=s["top_r"], bottom_radius=s["bot_r"],
                                 seed=s["seed"], top_z=s["top_z"], preset=s["preset"], lod=s["lod"],
                                 name="world.peak.%03d" % k, location=(s["x"], s["y"], 0.0))
        ob["r48_peak"] = int(k)
        ob["r48_plinth"] = round(s["plinth"], 3)
        for ch in ob.children:
            ch["r48_peak"] = int(k)
        info.update(fit_excess=round(excess, 2), fit_tries=tries, top_r=round(s["top_r"], 2),
                    bot_r=round(s["bot_r"], 2), lod=s["lod"], preset=s["preset"], top_z=round(s["top_z"], 1),
                    plinth=round(s["plinth"], 1), limited=s["limited"])
        out.append((k, ob, info))
    return out


# ---- backdrop -----------------------------------------------------------------------------

# Round 48 (plan D9, intent 3.1): the horizon as 3 pillar families (one tall, three slimmer; far level, beds about
# hero thickness) and 2 low dome-capped mesas whose tops make level skylines, placed from the hold cameras
# (scratchpad r48 tools/horizon.py): family 1 is the pale pillars seen through the gate's arch (and behind the abode),
# family 2 the cool pillars right of the forge's smoke, family 3 the slim far pillars right of the steles; mesa A is
# the library's low level ridge under its empty right half, mesa B the level plateau left of the steles and the arena.
# None stands in the moon (from the gate, the poster, 1160 and the summit) or in a hold's quiet sky.
# (kind, x, y, top z, top radius, bottom radius, preset)
BACKDROP_R48 = (
    ("family1", 77.0, 3358.0, 290.0, 34.0, 44.0, "sandstone"),
    ("family1", -150.0, 3300.0, 230.0, 20.0, 26.0, "sandstone"),
    ("family1", 230.0, 3420.0, 205.0, 17.0, 23.0, "sandstone"),
    ("family1", -20.0, 3520.0, 175.0, 15.0, 21.0, "granite"),
    ("family2", 1712.0, 2705.0, 300.0, 38.0, 50.0, "granite"),
    ("family2", 1850.0, 2560.0, 240.0, 22.0, 30.0, "sandstone"),
    ("family2", 1580.0, 2860.0, 210.0, 19.0, 25.0, "sandstone"),
    ("family2", 1950.0, 2800.0, 180.0, 16.0, 22.0, "sandstone"),
    ("family3", -1037.0, 3501.0, 280.0, 30.0, 38.0, "sandstone"),
    ("family3", -1180.0, 3420.0, 220.0, 18.0, 24.0, "sandstone"),
    ("family3", -900.0, 3600.0, 195.0, 16.0, 21.0, "granite"),
    ("family3", -1250.0, 3600.0, 170.0, 15.0, 20.0, "sandstone"),
    ("mesaA", 2209.0, 851.0, 70.0, 360.0, 420.0, "mesa"),
    ("mesaB", -1801.0, 1887.0, 55.0, 330.0, 390.0, "mesa"),
)


def build_backdrop(coll, count=14):
    """Round 48: the BACKDROP_R48 horizon (lib.nature.peak_pillar at the far level, no fringe, rising out of the
    cloud sea), named 'world.backdrop' like the massifs before it (export_web counts them as backdrop massifs).
    ``count`` is kept for the old signature (build_backdrop_r47 builds the 14 massifs as before)."""
    out = []
    for i, (kind, x, y, top, tr, br, preset) in enumerate(BACKDROP_R48):
        ob, _info = N.peak_pillar(coll, height=top - (CLOUD_SEA_Z - 30.0), top_radius=tr, bottom_radius=br,
                                  seed=9400 + i, top_z=top, preset=preset, lod="far", name="world.backdrop",
                                  location=(x, y, 0.0), fringe=False)
        ob["r48_backdrop"] = kind
        out.append(ob)
    return out


def build_backdrop_r47(coll, count=14):
    """Distant karst massifs on a 1.3-3.5 km ring around the range, rising out of the cloud sea
    (cheap far-LOD rock_pillar without vegetation, flared toward the clouds; ~17k tris each).
    Depth for every wide shot, silhouettes on the horizon under the moon."""
    r = U.rng("world.backdrop", 4)
    cx, cy = 0.0, 760.0
    out = []
    for i in range(count):
        ang = 2.0 * math.pi * (i + r.uniform(0.2, 0.8)) / count
        rad = r.uniform(1400.0, 3500.0)
        x, y = cx + math.cos(ang) * rad * 0.8, cy + math.sin(ang) * rad
        top = r.uniform(60.0, 330.0)
        az = math.degrees(math.atan2(x - MOON_VIEW[0], y - MOON_VIEW[1]))
        if abs(az - L.MOON_AZIMUTH) < 14.0:       # keep the final moon shot clean
            x, y = MOON_VIEW[0] + (x - MOON_VIEW[0]) * 0.0 + math.sin(math.radians(L.MOON_AZIMUTH + 24.0)) * rad,                 MOON_VIEW[1] + math.cos(math.radians(L.MOON_AZIMUTH + 24.0)) * rad
        tr = r.uniform(55.0, 120.0)
        # (W8: no flat tops; the image model read a flat-topped pillar as a walled tower)
        out.append(N.rock_pillar(coll, height=top - (CLOUD_SEA_Z - 30.0), top_radius=tr,
                                 bottom_radius=tr * r.uniform(1.1, 1.5), seed=900 + i, top_flat=False,
                                 top_z=top, lod="far", pines=False, vegetation=False,
                                 name="world.backdrop", location=(x, y, 0.0)))
    return out


# ---- islets ------------------------------------------------------------------------------

def build_islets(rng_, coll, count=30):
    """Small floating islets around the range, most with a pine. No buildings: a pavilion on a
    rock with no bridge to it reads as an unreachable building (W8)."""
    r = U.rng("world.islets", 9)
    placed = []
    tries = 0
    out = []
    while len(placed) < count and tries < 900:
        tries += 1
        s = rng_.segs[r.randrange(len(rng_.segs))]
        t = r.uniform(0.0, 1.0)
        side = 1 if r.random() < 0.5 else -1
        dist = r.uniform(55.0, 620.0)
        x, y, zl = rng_.seg_point(s, t, side * dist)
        size = r.choice((r.uniform(6.0, 11.0), r.uniform(8.0, 16.0), r.uniform(12.0, 26.0)))
        z = zl + r.uniform(-85.0, 30.0)
        if dist < 90.0 and z > zl - 32.0:
            continue                                   # keep the camera corridor clear
        if z - size * 1.2 < CLOUD_SEA_Z + 10.0:
            continue
        # outside the range mass (sample the centre and a ring)
        ring = [(x, y)] + [(x + math.cos(a) * (size * 0.6 + 6.0), y + math.sin(a) * (size * 0.6 + 6.0))
                           for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
        ff = rng_.fields(np.array([p[0] for p in ring]), np.array([p[1] for p in ring]))
        # (round 48: T_full, the peaks before they became pillars, so an islet keeps off a pillar too)
        if (ff["F"] > -2.0).any() and (ff.get("T_full", ff["T"]) > z - size * 1.4 - 15.0).any():
            continue                                   # over the mass and not clearly above it
        # floating areas (arena island) and other islets
        bad = False
        for k in FLOATING:
            if k in rng_.anchors:
                a = rng_.anchors[k]
                if math.hypot(x - a[0], y - a[1]) < a[3] + 40.0 + size and abs(z - (a[2] - 30.0)) < 70.0:
                    bad = True
        for (px, py, pz, ps) in placed:
            if math.dist((x, y, z), (px, py, pz)) < (size + ps) * 1.1 + 12.0:
                bad = True
        if math.hypot(x - OPENING_BANK[0], y - OPENING_BANK[1]) < 110.0:
            bad = True
        if bad:
            continue
        i = len(placed)
        placed.append((x, y, z, size))
        rot = r.uniform(0, 2 * math.pi)
        rock = N.floating_rock(coll, size=size, seed=500 + i, vegetation=True, roots=True, pine_on_top=False,
                               name="world.islet", location=(x, y, z), rotation=rot)
        tidy_rock(rock)
        out.append(rock)
        roll = r.random()
        if size >= 12.0 and roll < 0.25:
            # formerly world.islet.pavilion; a pine instead. The draw below keeps the islet
            # sequence (positions, sizes) exactly as before; the pine uses its own generator.
            r.uniform(0, 1)
            q = U.rng("world.islet_pine", i)
            N.pine(coll, height=size * q.uniform(0.45, 0.7), seed=600 + i, style="huangshan", lod="mid",
                   name="world.islet.pine", location=(x + q.uniform(-0.15, 0.15) * size,
                                                      y + q.uniform(-0.15, 0.15) * size, z + 0.1))
        elif size >= 8.0 and roll < 0.85:
            N.pine(coll, height=size * r.uniform(0.45, 0.7), seed=600 + i, style="huangshan", lod="mid",
                   name="world.islet.pine", location=(x + r.uniform(-0.15, 0.15) * size,
                                                      y + r.uniform(-0.15, 0.15) * size, z + 0.1))
    _log("islets", len(placed), "tries", tries)
    return out


# ---- waterfalls --------------------------------------------------------------------------

def _edge_point(rng_, x, y, dx, dy, max_d=700.0):
    """Last point inside the range mass marching from (x, y) along (dx, dy)."""
    n = int(max_d / 2.0)
    ds = np.arange(n) * 2.0
    px, py = x + dx * ds, y + dy * ds
    F = rng_.fields(px, py)["F"]
    out = np.where(F <= 0.5)[0]
    out = out[out > 3]
    if len(out) == 0:
        return None
    k = max(0, int(out[0]) - 1)
    return float(px[k]), float(py[k])


def _fall_sheet(name, coll, width, height, seed, material="nature_waterfall"):
    """Ballistic falling sheet (local: lip at the origin, pours toward -Y), widening downward."""
    r = U.rng("world.fall", seed)
    rows, cols = 48, 6
    verts, faces = [], []
    v0 = r.uniform(2.0, 3.0)
    for j in range(rows + 1):
        t = j / rows
        d = height * t ** 1.15
        yy = -v0 * math.sqrt(2.0 * max(d, 0.0) / 9.81) - 0.2
        w = width * (1.0 + 0.9 * t)
        for i in range(cols + 1):
            u = i / cols - 0.5
            verts.append((u * w + 0.06 * width * math.sin(7 * t + 3 * u + seed), yy, -d))
    for j in range(rows):
        for i in range(cols):
            a = j * (cols + 1) + i
            faces.append((a, a + 1, a + cols + 2, a + cols + 1))
    ob = _mesh_np(name, coll, np.array(verts), np.array(faces), [material])
    U.set_visibility(ob, shadow=False)
    ob["exit_speed"] = v0             # m/s over the lip (the web export's fall time, bake_web water)
    return ob


# Round 48 (rule 9, intent C13): a fall leaves a cleft or shelf, widens and arcs, and breaks into mist part way down;
# never a 300 m light beam into the cloud sea. FALL_MAX_H caps its sheets, fall_mist hangs a chain of flattened puffs
# from about halfway down to its end ('world.cloud.fallmist', exported with the other volume puffs by export_web
# clouds).
FALL_MAX_H = 120.0             # m: tallest sheet
FALL_MIST_N = (3, 5)           # puffs in the chain
FALL_EXIT = (2.5, 4.0)         # m/s over the lip (nature.waterfall exit_speed)
FALL_SPREAD = (0.4, 0.6)       # sheet widening over its height


def fall_mist(coll, lip, yaw, height, width, seed, name="world.cloud.fallmist"):
    """The spray chain of a fall pouring from ``lip`` (xyz) toward yaw (local -Y turned by ``yaw``) for ``height``
    m: FALL_MIST_N flattened cloud puffs from 0.5 x height below the lip to its foot, growing and drifting out.
    Returns the puffs."""
    r = U.rng("world.fallmist", seed)
    dx, dy = math.sin(yaw), -math.cos(yaw)
    out = []
    n = r.randint(*FALL_MIST_N)
    for i in range(n):
        q = 0.5 + 0.5 * (i + 0.5) / n
        d = height * q
        s = max(14.0, width * r.uniform(2.2, 3.4)) * (0.8 + 0.5 * q)
        p = (lip[0] + dx * (3.0 + 0.1 * d) + r.uniform(-0.3, 0.3) * width,
             lip[1] + dy * (3.0 + 0.1 * d) + r.uniform(-0.3, 0.3) * width, lip[2] - d)
        out.append(N.cloud_puff(coll, size=s, seed=int(seed) * 7 + i, density=1.3, flatten=0.55, name=name,
                                location=p))
    return out


def build_waterfalls(rng_, coll):
    """Waterfalls pouring off the range's edges into the void (they dissolve into the fog). Round 48: at most
    FALL_MAX_H m of sheet, then the spray chain (fall_mist)."""
    specs = [("mirror", (-1.0, 0.25)), ("library", (1.0, 0.1)), ("abode", (1.0, -0.2)),
             ("scroll", (-1.0, 0.15)), ("forge", (0.7, -0.7))]
    out = []
    for i, (k, (dx, dy)) in enumerate(specs):
        if k not in rng_.anchors:
            continue
        ax, ay, az, fp = rng_.anchors[k]
        ln = math.hypot(dx, dy)
        dx, dy = dx / ln, dy / ln
        e = _edge_point(rng_, ax, ay, dx, dy)
        if e is None:
            continue
        T, _ = rng_.top_at(*e)
        lip = (e[0], e[1], T + 0.2)
        h = min(lip[2] - (CLOUD_SEA_Z - 15.0), FALL_MAX_H)
        yaw = math.atan2(dx, -dy)
        fall_mist(coll, lip, yaw, h, 12.0 + 3.0 * (i % 3), 7000 + i)
        root = U.empty("world.waterfall", coll, location=lip, rotation=(0, 0, yaw), display_size=4.0)
        w = 12.0 + 3.0 * (i % 3)
        roles = N.sheet_roles(2)                  # core, front veil (nature.SHEET_FRONT m in front; was 0.3 m)
        for s in range(2):
            sh = _fall_sheet("world.waterfall.sheet", coll, w * (1.0 - 0.25 * s), h, seed=i * 7 + s)
            sh.parent = root
            sh.location = (0.0, -N.SHEET_FRONT[roles[s]], 0.05 * s)
            sh["flow"] = (1.0, 1.25)[s]
            sh["water_layer"] = roles[s]
        # the stream that feeds it: a shallow water strip from the terrace edge down to the lip
        pts = []
        for t in np.linspace(0.0, 1.0, 24):
            sx = ax + dx * (fp + 6.0) * (1 - t) + e[0] * t
            sy = ay + dy * (fp + 6.0) * (1 - t) + e[1] * t
            pts.append((sx, sy))
        pts = np.array(pts)
        zz = rng_.fields(pts[:, 0], pts[:, 1])["T"] + 0.35
        verts, faces = [], []
        for j, ((sx, sy), sz) in enumerate(zip(pts, zz)):
            verts += [(sx - dy * 2.5, sy + dx * 2.5, sz), (sx + dy * 2.5, sy - dx * 2.5, sz)]
            if j:
                faces.append((2 * j - 2, 2 * j - 1, 2 * j + 1, 2 * j))
        st = _mesh_np("world.stream", coll, np.array(verts), np.array(faces), ["nature_waterfall"])
        U.set_visibility(st, shadow=False)
        out.append(root)
    _log("waterfalls", len(out))
    return out


# ---- connectors --------------------------------------------------------------------------
# docs/scene/architecture-audit.md section 2 (W1-W6). Each link runs from the area it leaves (that
# area's AREA['depart']) to the area it reaches (AREA['arrival']). Both are (x, y, z, heading)
# in the area's own frame: x right, y forward (the front is -y), z 0 = its walk level, heading =
# the walking direction in radians counter-clockwise from local +x (atan2(dy, dx), so +y = pi/2).
# World = anchor + rotation by the area's yaw (assembly turns each area the same way).
# PORTS holds the plan's section 1 values for any area module that does not declare them yet
# (or fails to import).

PORTS = {
    "gate": dict(depart=(0.0, 36.0, 0.0, math.pi / 2)),
    "mirror": dict(arrival=(-5.0, -51.5, -0.4, math.pi / 2), depart=(48.5, 13.0, -0.4, 0.0)),
    "forge": dict(arrival=(0.0, -58.0, 0.0, math.pi / 2), depart=(-53.3, -8.9, 0.0, math.radians(189.5))),
    "arena": dict(arrival=(0.0, -45.0, -1.5, math.pi / 2), depart=(-13.0, 43.0, -1.8, math.radians(107.0))),
    "mission": dict(arrival=(0.0, -58.0, 0.0, math.pi / 2), depart=(54.0, -12.0, -0.4, 0.0)),
    "library": dict(arrival=(0.0, -49.0, -0.25, math.pi / 2), depart=(-44.7, -10.8, -0.4, math.pi)),
    "steles": dict(arrival=(0.0, -56.0, -0.34, math.pi / 2), depart=(-15.0, 44.0, -0.34, math.pi / 2)),
    "scroll": dict(arrival=(12.0, -44.0, -0.35, math.pi / 2), depart=(44.0, -3.5, -0.35, 0.0)),
    "formation": dict(arrival=(0.0, -62.0, -0.4, math.pi / 2), depart=(0.0, 62.0, -0.4, math.pi / 2)),
    "abode": dict(arrival=(-8.0, -51.0, -0.4, math.pi / 2), depart=(-52.0, 0.0, -0.4, math.pi)),
    "summit": dict(arrival=(0.0, -38.5, 0.0, math.pi / 2)),
}

# stairways (W1-W4)
STAIR_W = 5.0              # walkway width (m); the parapets stand outside it
STAIR_DS = 0.8             # centreline sample spacing (m)
STAIR_STRAIGHT = 15.0      # straight run along the declared heading at both ends (W1)
STAIR_K = (0.4, 0.6, 0.8, 1.0, 1.2, 1.4)   # Hermite tangent lengths / chord tried at each end
STAIR_R_MIN = 20.0         # tightest bend of the centreline (m), 4 x the stair width
RISER = 0.17               # largest riser; each link uses one equal riser <= this (W3)
TREAD_MIN = 0.30           # 0.17 / 0.30: the 0.57 grade of W2
TREAD_FLIGHT = 0.40        # tread inside a flight when the climb leaves room
FLIGHT = 18                # risers per flight at most, then a landing (W3)
LANDING = 2.0              # shortest landing (m)
STAIR_CLEAR = 0.3          # treads at least this far over the ground off the terraces (W2)
STAIR_DEPTH = 1.6          # stair body under the nosing line
TOP_FLAT = 1.0             # flat tread before the arrival landing
FOOT_FLAT = 5.0            # flat foot landing that carries the archway (W3)
FOOT_GATE = dict(bays=1, width=10.0, height=9.0)        # opening about 6.8 m wide
FOOT_GATE_SKIP = ("steles", "scroll", "formation")     # their own gate stands at the depart (1.7-1.9)
REST_MIN_LEN = 100.0       # stairs longer than this get a rest pavilion on the middle landing (W3)
REST_LANDING = 9.0         # that landing's length (m)
REST_DEPTH = 8.5           # how far its terrace reaches out beside the stair
RAIL_W, RAIL_H = 0.4, 1.0  # parapet width, and height over the nosing line
COPING = 0.6               # parapet tops fall this much to the outer edge (a coping, not a floor)
# (round 11: all baked materials draw double-sided on the web, so two faces in one plane z-fight whichever way they
# face. The landings shared faces with their own walls and treads, and the treads lay on the terrace grass)
REVEAL = 0.02              # landing walls (rest_rail, foot_rail) stand this far in from their slab's outer faces and
WALL_SINK = 0.1            # ends, their bottoms this far down in the slab: no wall face lies in a slab face's plane
ARCH_REVEAL = 0.08         # round 12: a bridge arch's sides stand this far inside the parapets' outer faces. At REVEAL
                           # (2 cm) the 0.3 m band where the arch reaches up into the stair z-fought with the parapets
                           # from about 290 m on (24-bit depth, near 0.5 m), the whole length of the library -> steles
                           # bridge; 8 cm stays apart to about 580 m, where that band is under a pixel
SINK = 0.05                # the range sinks this far under a stairway's walking surfaces where it lay at their level
SINK_UP = 0.03             # ... range vertices from SINK under to this far over a walking level count as at it
SINK_REACH = 0.45          # ... a vertex inside the stair's own footprint takes the lowest walking level this near
                           # (XY). Only vertices inside the footprint move (the areas' steps and rails stand on the
                           # range just outside it). A 2.5 m grid triangle stays within 5 mm of an unmoved corner only
                           # within 0.354 m of it: beside the treads every unmoved corner is past the parapets, 0.4 m
                           # out, so no range face lies within 5 mm under a tread; along a landing's open edge a
                           # corner just outside can leave a sliver up to 0.354 m wide (sink_under_links)
SINK_END = 0.4             # ... and the footprint reaches this far past a stair's bare ends (no foot landing there)
# supports (W4, 2026-10-21; _supports): a pier every 4.8 m with a round-headed arcade and tie arches every 12 m down
# read as a Roman aqueduct in about 10 of 35 audit frames. Now: few heavy tapered piers with stepped corbel heads,
# and a solid footing under the lower stretches
PIER_GAP = 4.0             # piers where the treads are more than this over the ground (W4)
PIER_SPAN = (17.5, 20.0)   # target and longest span between supports (pier, footing end, bridge, area)
PIER_JITTER = 0.12         # each pier moves up to this share of its span, so a row of them is not a fence
PIER_ALONG, PIER_ACROSS = 1.8, STAIR_W * 0.7   # the rest pavilion terrace's pier (_pier): size at the top
SHAFT_ALONG = 3.4          # stair pier shaft at the top, along the stair
SHAFT_INSET = 0.25         # ... and across: this much inside the parapets' outer faces on each side
PIER_BATTER = 0.02         # the shaft widens by this share of its top size per metre down, up to PIER_FLARE_MAX
PIER_FLARE_MAX = 2.0
CORBEL = ((2.1, 0.75, 0.12), (1.4, 0.75, 0.18), (0.7, 0.75, 0.22))   # stepped cantilever courses under the
                           # soffit, top first: (reach past the shaft top along the stair on each side, depth, inset
                           # from the parapets' outer faces). They step out along the stair, not sideways: with a
                           # sideways lip they read as Doric capitals on columns
CORBEL_GAP = 0.02          # round 12: the shaft's top stands this far inside the lowest course all round. The courses
                           # were straight boxes between their two end stations: on a bend their sides cut out through
                           # the curved parapets' and treads' faces at a few degrees, and the shaft's top corners out
                           # through the lowest course's sides (z-fighting slivers along those cuts). Now each course
                           # follows the stair's centreline through every sample (a _ribbon), so it keeps its inset
TREAD_GAP = 0.02           # round 12: no tread ends within this of a riser or of the foot (round 11 used 1 cm): a tread
                           # 1-1.5 cm long put two parallel end faces that close, which fight from about 300 m on
FOOTING_INSET = 0.15       # the footing under the low stretches stands this far inside the parapets' faces
FOOTING_SINK = 1.0         # ... and reaches this far into the ground
PLAN_GRID = 5.0            # the stairs' riser plans read the range as the 5 m mesh they were planned on: planning
                           # them on GRID would move risers, landings, archways and pavilions. Their supports
                           # reach the range as GRID meshes it
BRIDGE_TS = (0.12, 0.1, 0.09, 0.08, 0.07, 0.06, 0.05)   # library -> steles: the arch spans
                           # |t - 0.5| < this on the segment; the widest that leaves room to climb
BRIDGE_LANDING = 3.0       # level deck reaches this far past each end of the arch (W4)
BRIDGE_CROWN = 2.5         # deck to intrados at the crown
# chain bridge (W5)
CHAIN_SAG = 2.0
CHAIN_LEVEL = 4.0          # level deck at each end (m)
CHAIN_PLANK = 0.35         # plank spacing (m)
CHAIN_W = 3.2
# stepping stones (W6)
STONE_HOP = 1.1            # count = ceil(rise / STONE_HOP) + 1
STONE_BULGE = 6.0
STONE_SIZE = (3.6, 4.4)
STONE_LAND0 = 3.0          # PORTS['arena'] depart is the 6 m deep rear landing's centre (plan 1.4)


def _anchor_yaws(anchors):
    """Yaw per area: the 5th anchor value when given, else as camera.area_yaws does it (local +Y
    along the flight from the previous anchor; the gate faces south, yaw 0)."""
    anchors = anchors if anchors else ANCHORS
    keys = [k for k in ORDER if k in anchors] + [k for k in anchors if k not in ORDER]
    yaws, prev = {}, None
    for k in keys:
        a = tuple(anchors[k])
        if len(a) > 4 and a[4] is not None:
            yaws[k] = float(a[4])
        elif prev is None:
            yaws[k] = 0.0
        else:
            p = anchors[prev]
            yaws[k] = math.atan2(-(a[0] - p[0]), a[1] - p[1])
        prev = k
    return yaws


def _unit2(v):
    v = np.asarray(v, float)[:2]
    n = float(np.hypot(v[0], v[1]))
    return v / n if n > 1e-9 else None


def _heading(h, loc, kind):
    """Local unit walking direction from an AREA heading (see the block comment above). Also
    takes '+y'-style strings and 2D vectors. If the angle read the documented way points more
    than ~70 deg away from the expected direction (into the area at an arrival, out of it at a
    depart), the reading closest to it among degrees / rotation_z-style (0 = +y) wins. None: the
    expected direction."""
    exp = _unit2(loc)
    exp = np.array([0.0, 1.0]) if exp is None else exp
    if kind == "arrival":
        exp = -exp
    if h is None:
        return exp, "derived"
    if isinstance(h, str):
        k = h.strip().lower()
        axes = {"+x": (1, 0), "x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "y": (0, 1), "-y": (0, -1)}
        if k in axes:
            return np.array(axes[k], float), "axis"
        try:
            h = float(k)
        except ValueError:
            return exp, "derived (unreadable %r)" % h
    if isinstance(h, (tuple, list, np.ndarray)):
        u = _unit2(h)
        return (u, "vector") if u is not None else (exp, "derived")
    a = float(h)
    cands = [(np.array([math.cos(a), math.sin(a)]), "rad"),
             (np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]), "deg"),
             (np.array([-math.sin(a), math.cos(a)]), "rad rot_z"),
             (np.array([-math.sin(math.radians(a)), math.cos(math.radians(a))]), "deg rot_z")]
    v, how = cands[0]
    if float(v @ exp) < 0.3:
        v, how = max(cands, key=lambda c: float(c[0] @ exp))
        how += " (reinterpreted)"
    return v, how


def _area_port(key, kind):
    """(raw value, source) of an area's 'arrival' / 'depart': its AREA dict, else PORTS."""
    try:
        mod = importlib.import_module("sect.areas." + key)
        area = getattr(mod, "AREA", None)
        if isinstance(area, dict) and area.get(kind) is not None:
            return area[kind], "AREA"
    except Exception as exc:
        _log("WARN sect.areas.%s did not import (%s: %s); %s from the plan table"
             % (key, exc.__class__.__name__, exc, kind))
    v = PORTS.get(key, {}).get(kind)
    return v, ("plan table" if v is not None else None)


def port(rng_, key, kind):
    """World position p (x, y, z) and walking direction h (unit 2D) of an area's 'arrival' or
    'depart'. Returns dict(p, h, local, src, heading) or None."""
    v, src = _area_port(key, kind)
    if v is None or key not in rng_.anchors:
        return None
    if isinstance(v, dict):
        loc = v.get("location", v.get("pos", v.get("point")))
        head = v.get("heading", v.get("dir"))
    else:
        loc, head = tuple(v)[:3], (tuple(v)[3] if len(v) > 3 else None)
    loc = np.array([float(c) for c in loc] + [0.0] * (3 - len(loc)), float)
    hl, how = _heading(head, loc, kind)
    ax, ay, az, _ = rng_.anchors[key]
    yaw = rng_.yaws.get(key, 0.0)
    c, s = math.cos(yaw), math.sin(yaw)
    p = np.array([ax + loc[0] * c - loc[1] * s, ay + loc[0] * s + loc[1] * c, az + loc[2]])
    h = np.array([hl[0] * c - hl[1] * s, hl[0] * s + hl[1] * c])
    return dict(p=p, h=h, local=tuple(round(float(q), 2) for q in loc), src=src, heading=how)


def _ground(rng_, x, y, grid=None):
    """Terrain under (x, y) as the range mesh shows it (cells of ``grid`` m, default GRID): the
    higher of the analytic top and both triangle splits of its grid cell (the mesh is linear
    between grid nodes, so it can stand above the analytic surface in hollows). Returns
    (h, F, flat) (F > 0: inside the mass)."""
    grid = GRID if grid is None else grid
    x = np.asarray(x, float).ravel()
    y = np.asarray(y, float).ravel()
    n = len(x)
    fx, fy = (x - EXTENT[0]) / grid, (y - EXTENT[2]) / grid
    i, j = np.floor(fx), np.floor(fy)
    u, v = fx - i, fy - j
    X0, Y0 = EXTENT[0] + i * grid, EXTENT[2] + j * grid
    f = rng_.fields(np.concatenate([X0, X0 + grid, X0, X0 + grid, x]),
                    np.concatenate([Y0, Y0, Y0 + grid, Y0 + grid, y]))
    T = f["T"]
    t00, t10, t01, t11, tc = (T[k * n:(k + 1) * n] for k in range(5))
    a = np.where(u >= v, t00 + u * (t10 - t00) + v * (t11 - t10), t00 + v * (t01 - t00) + u * (t11 - t01))
    b = np.where(u + v <= 1.0, t00 + u * (t10 - t00) + v * (t01 - t00),
                 t11 + (1.0 - u) * (t01 - t11) + (1.0 - v) * (t10 - t11))
    return np.maximum(tc, np.maximum(a, b)), f["F"][4 * n:], f["flat"][4 * n:]


def _centreline_k(p0, h0, p1, h1, meander, k0, k1, ds):
    a = p0[:2] + STAIR_STRAIGHT * h0
    b = p1[:2] - STAIR_STRAIGHT * h1
    ch = b - a
    lc = max(float(np.hypot(ch[0], ch[1])), 1e-6)
    nrm = np.array([-ch[1], ch[0]]) / lc
    u = np.linspace(0.0, 1.0, 1201)[:, None]
    base = ((2 * u ** 3 - 3 * u ** 2 + 1) * a + (u ** 3 - 2 * u ** 2 + u) * (k0 * lc * h0)
            + (-2 * u ** 3 + 3 * u ** 2) * b + (u ** 3 - u ** 2) * (k1 * lc * h1))
    mid = base + (meander * np.sin(np.pi * u) ** 2) * nrm
    poly = np.vstack([p0[:2], mid, p1[:2]])
    seg = np.hypot(*np.diff(poly, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(8, int(round(cum[-1] / ds))) + 1
    s = np.linspace(0.0, float(cum[-1]), n)
    xy = np.stack([np.interp(s, cum, poly[:, 0]), np.interp(s, cum, poly[:, 1])], axis=1)
    d = np.gradient(xy, axis=0)
    yaw = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    return s, xy, yaw


def meander_cap(p0, h0, p1, h1):
    """Largest sideways meander whose own bend stays at STAIR_R_MIN radius or more: the sin^2
    offset bends at 2 pi^2 M / Lc^2 at most over a middle part Lc long."""
    a = p0[:2] + STAIR_STRAIGHT * h0
    b = p1[:2] - STAIR_STRAIGHT * h1
    lc = float(np.hypot(*(b - a)))
    return lc * lc / (2.0 * math.pi ** 2 * STAIR_R_MIN)


def _centreline(p0, h0, p1, h1, meander, ds=STAIR_DS):
    """W1: STAIR_STRAIGHT m straight along h0 from p0, a Hermite curve (tangent to both straight
    runs) plus the sideways offset meander * sin(pi u)^2 (zero offset and zero turn where the
    straight runs start), STAIR_STRAIGHT m straight along h1 into p1, resampled every ds m.
    The meander is capped by meander_cap; the two Hermite tangent lengths are the pair from
    STAIR_K that gives the gentlest tightest bend. Where the ports' headings alone force a bend
    under STAIR_R_MIN, the meander shrinks (to zero if need be). Returns (s, xy, yaw, info)."""
    cap = meander_cap(p0, h0, p1, h1)
    m_req = math.copysign(min(abs(meander), cap), meander)
    overall = None
    for f in (1.0, 0.75, 0.5, 0.25, 0.0):
        m = m_req * f
        best = None
        for k0 in STAIR_K:
            for k1 in STAIR_K:
                s, xy, yaw = _centreline_k(p0, h0, p1, h1, m, k0, k1, ds)
                r = _radius_min(xy)
                if best is None or r > best[3]["radius"] + 1e-6:
                    best = (s, xy, yaw, dict(meander=m, cap=cap, k=(k0, k1), radius=r))
        if best[3]["radius"] >= STAIR_R_MIN:
            return best
        if overall is None or best[3]["radius"] > overall[3]["radius"]:
            overall = best
    return overall


def _radius_min(xy):
    """Smallest radius of curvature along a sampled polyline (m)."""
    d1 = np.gradient(xy, axis=0)
    d2 = np.gradient(d1, axis=0)
    k = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.hypot(*d1.T) ** 3, 1e-12)
    return float(1.0 / max(k.max(), 1e-9))


def _riser_plan(s, lb, ub, z0, z1, foot=0.0, top=TOP_FLAT, rest=False):
    """W2 + W3 together: where along s the N equal risers (<= RISER) from level z0 to z1 go.

    Target: one steady climb from s = foot to s = L - top: flights of at most FLIGHT risers at
    TREAD_FLIGHT (down to TREAD_MIN), the rest of the run spread over the landings between them
    (each >= LANDING; the middle one >= REST_LANDING when ``rest``). Two passes then move
    risers only where they must (the riser-space form of W2's two passes): later where the stair
    would stand above ub (a level bridge deck), earlier where it would sink under lb (the ground
    plus clearance). Moving keeps TREAD_MIN inside flights and the landing lengths between them,
    so the stair ramps up to a bump at the 0.57 grade and never dives after it. The backward
    (ground) pass runs last, so nothing ends up under lb; ``viol`` > 0 means some other rule
    could not be kept (a switchback would be needed)."""
    L = float(s[-1])
    rise = z1 - z0
    N = int(math.ceil(rise / RISER - 1e-9)) if rise > 1e-6 else 0
    if N == 0:
        return dict(sr=np.zeros(0), lev=np.array([z0]), r=0.0, N=0, gap=np.zeros(0),
                    land=np.zeros(0, bool), rest_k=None, viol=0.0, tread=0.0)
    r = rise / N
    lev = z0 + r * np.arange(N + 1)
    n = len(s)
    # deadline: at level lev[k] the stair may not pass the last sample before lb rises over it
    cm = np.maximum.accumulate(lb)
    i = np.searchsorted(cm, lev[:-1] + 1e-6, side="right")
    D = np.where(i < n, s[np.maximum(i - 1, 0)], L)
    D = np.minimum(D, L - top)
    # earliest: after riser k the stair (lev[k + 1]) may not stand where ub is under it
    rm = np.minimum.accumulate(ub[::-1])[::-1]
    j = np.searchsorted(rm, lev[1:] - 1e-6, side="left")
    E = np.where(j < n, s[np.minimum(j, n - 1)], L)
    E = np.maximum(E, foot)
    # flights and landings
    F = int(math.ceil(N / FLIGHT))
    sizes = np.full(F, N // F)
    sizes[: N % F] += 1
    last = np.cumsum(sizes) - 1
    land = np.zeros(N, bool)
    land[last[:-1]] = True
    gap = np.where(land, LANDING, TREAD_MIN)
    rest_k = None
    if rest and F > 1:
        rest_k = int(last[(F - 2) // 2])
        gap[rest_k] = REST_LANDING
    S0, S = foot, (L - top) - foot
    if S / N >= LANDING:                       # gentle: every tread is a landing
        tau = S0 + (np.arange(N) + 0.5) * S / N
        tread = S / N
    else:
        tread = float(np.clip((S - gap[land].sum()) / max(N - F, 1), TREAD_MIN, TREAD_FLIGHT))
        per = (S - (N - F) * tread - gap[land].sum()) / F      # spread over F-1 landings + 2 half ends
        tau = np.empty(N)
        c = S0 + per * 0.5
        for k in range(N):
            tau[k] = c
            c += gap[k] + per if land[k] else tread
    sr = tau.copy()
    viol = 0.0
    for _ in range(4):
        for k in range(N):
            lo = E[k] if k == 0 else max(E[k], sr[k - 1] + gap[k - 1])
            if sr[k] < lo:
                sr[k] = lo
        for k in range(N - 1, -1, -1):
            hi = D[k] if k == N - 1 else min(D[k], sr[k + 1] - gap[k])
            if sr[k] > hi:
                sr[k] = hi
        viol = float(max(0.0, (E - sr).max(), (sr[:-1] + gap[:-1] - sr[1:]).max() if N > 1 else 0.0,
                         -sr[0]))
        if viol < 1e-6:
            break
    return dict(sr=sr, lev=lev, r=r, N=N, gap=gap, land=land, rest_k=rest_k, viol=viol, tread=tread)


def _level_at(plan, q):
    return plan["lev"][np.searchsorted(plan["sr"], np.asarray(q, float), side="right")]


def _nosing(plan, s, z0, z1, q):
    """The line through the step nosings (the pitch line), at q."""
    L = float(s[-1])
    ns = np.concatenate([[0.0], plan["sr"], [L]])
    nz = np.concatenate([[z0], plan["lev"][1:], [z1]])
    return np.interp(q, ns, nz)


def _frame(s, xy, yaw, q):
    """Centre (n, 2) and left normal (n, 2) at stations q along the centreline."""
    q = np.asarray(q, float)
    c = np.stack([np.interp(q, s, xy[:, 0]), np.interp(q, s, xy[:, 1])], axis=-1)
    a = np.interp(q, s, yaw)
    return c, np.stack([-np.sin(a), np.cos(a)], axis=-1), a


def _strip(c, nl, qa, qb, l0, l1):
    """4 corners (CCW from above) of the strip between stations a and b, lateral l0 < l1."""
    return [c[qa] + nl[qa] * l0, c[qb] + nl[qb] * l0, c[qb] + nl[qb] * l1, c[qa] + nl[qa] * l1]


def _strip_l(c, nl, qa, qb, l0, l1):
    """_strip with its laterals per station: l0 = (at a, at b) < l1 = (at a, at b)."""
    return [c[qa] + nl[qa] * l0[0], c[qb] + nl[qb] * l0[1], c[qb] + nl[qb] * l1[1], c[qa] + nl[qa] * l1[0]]


def _chord_lateral(c, nl, a, b):
    """Per station (centres c (m, 2), left normals nl (m, 2)): the lateral t at which the station's
    line c + t nl crosses the straight line through points a and b."""
    d = np.asarray(b, float) - np.asarray(a, float)
    r = np.asarray(a, float)[None, :] - np.asarray(c, float)
    return (-r[:, 0] * d[1] + r[:, 1] * d[0]) / (-nl[:, 0] * d[1] + nl[:, 1] * d[0])


def _prism(q4, zb, zt):
    """8 corners: the 4 xy corners (CCW from above) at zb, then at zt (scalars or per corner)."""
    zb = np.broadcast_to(np.asarray(zb, float), (4,))
    zt = np.broadcast_to(np.asarray(zt, float), (4,))
    return [(float(p[0]), float(p[1]), float(z)) for p, z in zip(q4, zb)] + \
           [(float(p[0]), float(p[1]), float(z)) for p, z in zip(q4, zt)]


def _prisms_obj(name, coll, prisms, material, under=None, solids=(), smooth_solids=False):
    """One mesh object from closed 8-corner prisms (see _prism) and closed quad solids ((verts,
    faces), see _ribbon). ``under``: a second material for the prisms' bottom faces (the stairs'
    undersides) and the solids' (with ``smooth_solids``; their first face of every four, _ribbon's
    bottoms). Every face is flat-shaded, except with ``smooth_solids``: the solids then shade smooth
    along their run, sharp along the corners of their cross-section and round their end caps
    (_ribbon_sharp)."""
    verts, faces, mats, smooth, sharp = [], [], [], [], []
    for c in prisms:
        base = len(verts)
        verts.extend(c)
        faces.extend(tuple(base + i for i in f) for f in _BOX_FACES)
        mats.extend([1 if under else 0] + [0] * (len(_BOX_FACES) - 1))
        smooth.extend([False] * len(_BOX_FACES))
    for sv, sf in solids:
        base = len(verts)
        verts.extend(sv)
        faces.extend(tuple(base + i for i in f) for f in sf)
        m = len(sv) // 4
        mats.extend([1 if (under and smooth_solids and k < 4 * (m - 1) and k % 4 == 0) else 0 for k in range(len(sf))])
        smooth.extend([bool(smooth_solids)] * len(sf))
        if smooth_solids:
            sharp.extend((base + a, base + b) for a, b in _ribbon_sharp(m))
    if not faces:
        return None
    ob = _mesh_np(name, coll, np.array(verts), np.array(faces), [material] + ([under] if under else []),
                  mat_idx=mats if under else None, smooth=False)
    if smooth_solids and any(smooth):
        me = ob.data
        if len(me.polygons) != len(smooth) or len(me.vertices) != len(verts):
            _log("WARN", name, "lost faces in validate: left flat-shaded")
            return ob
        me.polygons.foreach_set("use_smooth", np.array(smooth, bool))
        ev = np.empty(len(me.edges) * 2, np.int32)
        me.edges.foreach_get("vertices", ev)
        ev = np.sort(ev.reshape(-1, 2), axis=1)
        keys = {(min(a, b), max(a, b)) for a, b in sharp}
        flags = np.array([(int(a), int(b)) in keys for a, b in ev], bool)
        at = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
        at.data.foreach_set("value", flags)
        me.update()
    return ob


def _ribbon_sharp(m):
    """Sharp edges of a _ribbon solid over m stations, as pairs of its own vertex indices: the four
    lengthwise corner edges and the edges round both end caps. The edges across the run, between
    one station's faces and the next's, stay smooth."""
    out = [(4 * i + k, 4 * (i + 1) + k) for i in range(m - 1) for k in range(4)]
    for i in (0, m - 1):
        p = 4 * i
        out += [(p, p + 1), (p + 2, p + 3), (p, p + 2), (p + 1, p + 3)]
    return out


def _ribbon(c, nl, l0, l1, zb, zt):
    """One closed solid along stations (centres c (m, 2), left normals nl (m, 2)) between lateral
    l0 < l1 (scalars or (m,) per station): bottom zb and top zt, each (m,) or (m, 2) for the l0 and
    l1 sides. No inner end faces (a row of prisms would bake their hidden ends into the atlas).
    Returns (verts, faces); face 4 i is segment i's bottom (_prisms_obj, _ribbon_sharp)."""
    m = len(c)
    zb = np.asarray(zb, float)
    zb = np.stack([zb, zb], axis=1) if zb.ndim == 1 else zb
    zt = np.asarray(zt, float)
    zt = np.stack([zt, zt], axis=1) if zt.ndim == 1 else zt
    l0 = np.asarray(l0, float).reshape(-1, 1)
    l1 = np.asarray(l1, float).reshape(-1, 1)
    a, b = c + nl * l0, c + nl * l1
    verts = []
    for i in range(m):            # per station: l0 bottom, l1 bottom, l0 top, l1 top
        verts += [(a[i][0], a[i][1], zb[i, 0]), (b[i][0], b[i][1], zb[i, 1]),
                  (a[i][0], a[i][1], zt[i, 0]), (b[i][0], b[i][1], zt[i, 1])]
    faces = []
    for i in range(m - 1):
        p, q = 4 * i, 4 * (i + 1)
        faces += [(p, p + 1, q + 1, q),             # bottom (down)
                  (p + 2, q + 2, q + 3, p + 3),     # top (up)
                  (p, q, q + 2, p + 2),             # l0 side
                  (p + 1, p + 3, q + 3, q + 1)]     # l1 side
    e = 4 * (m - 1)
    faces += [(0, 2, 3, 1), (e, e + 1, e + 3, e + 2)]   # end caps
    return verts, faces


def _footprint(c, nl, yaw, half_along, half_across):
    t = np.array([math.cos(yaw), math.sin(yaw)])
    return [c - t * half_along - nl * half_across, c + t * half_along - nl * half_across,
            c + t * half_along + nl * half_across, c - t * half_along + nl * half_across]


def _pier(rng_, c, nl, yaw, top, along=None, across=None, flare=1.3, sink=2.0):
    """Tapered stone pier from ``top`` down into the ground under centre c."""
    along = PIER_ALONG if along is None else along
    across = PIER_ACROSS if across is None else across
    q_top = _footprint(c, nl, yaw, along * 0.5, across * 0.5)
    q_bot = _footprint(c, nl, yaw, along * 0.5 * flare, across * 0.5 * flare)
    pts = np.array(q_bot + [c])
    h, _, _ = _ground(rng_, pts[:, 0], pts[:, 1])
    zb = float(h.min()) - sink
    return [(float(p[0]), float(p[1]), zb) for p in q_bot] + [(float(p[0]), float(p[1]), top) for p in q_top], \
        top - zb


def _corbel_pier(rng_, s, xy, yaw, q, soffit, lat, curved=True):
    """A stair pier at station q: CORBEL courses stepping out under the soffit (each level at the
    bottom, its top following the soffit 0.3 m into the stair body), then a shaft that widens by
    PIER_BATTER per metre down (at most PIER_FLARE_MAX) into the ground. Returns (prisms, solids, height): the shaft
    (a prism) and the courses (each a _ribbon through every centreline sample over its length; ``curved`` False: the
    straight boxes between its two end stations built before round 12, in prisms, for patch_r12_world's guard)."""
    prisms, solids = [], []
    top_q = None
    w3 = None
    for reach, depth, inset in CORBEL:
        h = SHAFT_ALONG * 0.5 + reach
        w = lat - inset
        if curved:
            qs = np.concatenate([[q - h], s[(s > q - h + 0.05) & (s < q + h - 0.05)], [q + h]])
        else:
            qs = np.array([q - h, q + h])
        cq, nq, _ = _frame(s, xy, yaw, qs)
        so = soffit(qs)
        zt = (so + 0.3) if top_q is None else np.full(len(qs), top_q + 0.05)
        zb = float(min(so)) - depth if top_q is None else top_q - depth
        if curved:
            solids.append(_ribbon(cq, nq, -w, w, np.full(len(qs), zb), zt))
        else:
            prisms.append(_prism(_strip(cq, nq, 0, 1, -w, w), zb, [zt[0], zt[1], zt[1], zt[0]]))
        top_q = zb
        w3 = w
    top = top_q + 0.05
    c, nl, a = _frame(s, xy, yaw, [q])
    c, nl, a = c[0], nl[0], float(a[0])
    hw, ha = lat - SHAFT_INSET, SHAFT_ALONG * 0.5
    if curved:
        # the shaft's top inside the lowest course by CORBEL_GAP all round: on a bend the course's sides follow the
        # arc, which leaves the straight shaft's tangent line by up to ha^2 / 2R over its length
        qq = np.linspace(q - ha, q + ha, 35)
        cc, nn, _ = _frame(s, xy, yaw, qq)
        dev = (cc - c) @ nl
        cosd = nn @ nl
        hw = min(hw, float((w3 * cosd - np.abs(dev)).min()) - CORBEL_GAP)
    q_top = _footprint(c, nl, a, ha, hw)
    g0, _, _ = _ground(rng_, np.array([c[0]]), np.array([c[1]]))
    zb = float(g0[0]) - 2.0
    for _ in range(2):              # the base's flare depends on the height, the height on the ground under the base
        f = min(1.0 + PIER_BATTER * max(top - zb, 0.0), PIER_FLARE_MAX)
        q_bot = _footprint(c, nl, a, ha * f, hw * f)
        pts = np.array(q_bot + [c])
        g, _, _ = _ground(rng_, pts[:, 0], pts[:, 1])
        zb = float(g.min()) - 2.0
    prisms.append([(float(p[0]), float(p[1]), zb) for p in q_bot] + [(float(p[0]), float(p[1]), top) for p in q_top])
    return prisms, solids, top - zb


def _supports(rng_, nm, s, xy, yaw, nl, lat, zs, soffit, skip, foot=0.0, curved=True):
    """W4 (2026-10-21): what carries a stairway, on the range as GRID meshes it.
    - Piers (_corbel_pier) where the treads stand more than PIER_GAP over the ground: each such run
      is split into equal spans near PIER_SPAN[0] and never over PIER_SPAN[1] between supports (its
      two ends rest on footing, the bridge or an area), each pier nudged by up to PIER_JITTER of
      its span.
    - A footing (_ribbon) from the soffit into the ground under the lower stretches where the
      soffit stands over it: the stair reads as built on a stone base, and the footing's end is the
      abutment where a run of piers starts.
    ``skip`` (per sample): the arched bridge, which carries itself. ``foot``: the foot landing's
    length (its own solid body carries it). Returns (prisms, solids, stats)."""
    n = len(s)
    pts = np.concatenate([xy, xy + nl * lat, xy - nl * lat])
    g3 = _ground(rng_, pts[:, 0], pts[:, 1])[0].reshape(3, n)
    gmax = g3.max(axis=0)
    sb = soffit(s)
    high = (zs - gmax > PIER_GAP) & ~skip
    r = U.rng("world.piers", nm)
    prisms, corbels, heights, spans, runs = [], [], [], [], 0
    k = 0
    while k < n:
        if not high[k]:
            k += 1
            continue
        k0 = k
        while k < n and high[k]:
            k += 1
        runs += 1
        a = float(s[k0 - 1]) if k0 > 0 else float(s[0])
        b = float(s[k]) if k < n else float(s[-1])
        Lr = b - a
        m = max(1, int(round(Lr / PIER_SPAN[0])))
        if Lr / m > PIER_SPAN[1]:
            m += 1
        step = Lr / m
        jit = min(PIER_JITTER * step, max(0.0, (PIER_SPAN[1] - step) * 0.5))
        qs = [a + j * step + r.uniform(-jit, jit) for j in range(1, m)]
        for q in qs:
            pr, so_, ph = _corbel_pier(rng_, s, xy, yaw, q, soffit, lat, curved=curved)
            prisms += pr
            corbels += so_
            heights.append(ph)
        sup = [a] + qs + [b]
        spans.append(max(y_ - x_ for x_, y_ in zip(sup, sup[1:])))
    # footing: runs of samples off the foot landing, off the bridge and the pier runs, whose soffit
    # stands over the ground somewhere across the stair
    low = ~high & ~skip & (s >= foot) & (sb > g3.min(axis=0) + 0.05)
    solids, foot_m, foot_h = [], 0.0, 0.0
    w = lat - FOOTING_INSET
    k = 0
    while k < n:
        if not low[k]:
            k += 1
            continue
        k0 = k
        while k < n and low[k]:
            k += 1
        k1 = min(k, n - 1)                 # one sample past the run, so the footing reaches the next support
        k0 = max(k0 - 1, 0)
        if k1 - k0 < 2:
            continue
        sl = slice(k0, k1 + 1)
        zt = sb[sl] + 0.3
        zb = np.stack([np.minimum(g3[2, sl], g3[0, sl]), np.minimum(g3[1, sl], g3[0, sl])], axis=1) - FOOTING_SINK
        zb = np.minimum(zb, zt[:, None] - 0.5)
        # (round 11: its end faces stand REVEAL in from the samples, where the treads' faces are; in
        # their plane they z-fought where the footing starts under a flight)
        cc = xy[sl].copy()
        for i, sg in ((0, 1.0), (-1, -1.0)):
            a = float(yaw[k0] if i == 0 else yaw[k1])
            cc[i] += sg * REVEAL * np.array([math.cos(a), math.sin(a)])
        solids.append(_ribbon(cc, nl[sl], -w, w, zb, zt))
        foot_m += float(s[k1] - s[k0])
        foot_h = max(foot_h, float((zt[:, None] - zb).max()))
    # treads under the GRID mesh anywhere across the stair (the plan read the PLAN_GRID mesh)
    under = gmax - zs
    solids = corbels + solids
    stats = dict(piers=len(heights), tallest_pier=round(max(heights), 1) if heights else 0.0,
                 pier_runs=runs, longest_span=round(max(spans), 1) if spans else 0.0,
                 footing_m=round(foot_m, 1), tallest_footing=round(foot_h, 1),
                 buried_mesh=int((under > 0.05).sum()), burial_max=round(max(float(under.max()), 0.0), 2))
    return prisms, solids, stats


@contextlib.contextmanager
def _low_roofs(A):
    """Inside this block arch roofs are built cheap (detail 'low', 0.6 m tile courses, one ridge
    beast): the connectors' archways and rest pavilions are seen from 20 m or more. Measured on
    a pavilion plus a one-bay archway: 205k triangles at the defaults, 139k like this."""
    orig = getattr(A, "_roof", None)
    if orig is None:
        yield
        return

    def low(*a, **k):
        k.setdefault("detail", "low")
        k.setdefault("tile_pitch", 0.6)
        k.setdefault("beasts", 1)
        return orig(*a, **k)

    A._roof = low
    try:
        yield
    finally:
        A._roof = orig


def _arch():
    """sect.lib.arch (archways, pavilions), imported on first use; None if it fails to import."""
    try:
        return importlib.import_module("sect.lib.arch")
    except Exception as exc:
        _log("WARN sect.lib.arch did not import:", exc)
        return None


def _try_stairway(rng_, seg, p0, p1, h0, h1, meander, bridge_t, foot):
    """Centreline, ground and riser plan for one meander (and bridge span on the notch link)."""
    z0, z1 = float(p0[2]), float(p1[2])
    s, xy, yaw, info = _centreline(p0, h0, p1, h1, meander)
    L, n = float(s[-1]), len(s)
    # ground under the walkway and parapets (centre and both outer edges); the clearance is
    # kept off the terraces, and not on the foot / top landings, which sit on the area's ground
    _, nl, _ = _frame(s, xy, yaw, s)
    lat = STAIR_W * 0.5 + RAIL_W
    pts = np.concatenate([xy, xy + nl * lat, xy - nl * lat])
    hh, FF, flat = _ground(rng_, pts[:, 0], pts[:, 1], grid=PLAN_GRID)
    hh, flat = hh.reshape(3, n), flat.reshape(3, n)
    h = hh.max(axis=0)
    lb = (hh + np.where(flat, 0.0, STAIR_CLEAR)).max(axis=0)
    lb = np.where((s <= foot + 1.0) | (s >= L - TOP_FLAT - 2.0), h, lb)
    lb[0], lb[-1] = min(lb[0], z0), min(lb[-1], z1)
    ub = np.full(n, 1e9)
    rest = L > REST_MIN_LEN
    # arched bridge over the library -> steles notch (W4): a level deck at the steady line's
    # height over |t - 0.5| < bridge_t of the segment, plus BRIDGE_LANDING m at each end
    arch = None
    if bridge_t is not None:
        t = rng_.seg_coords(seg, xy[:, 0], xy[:, 1])[0]
        idx = np.where(np.abs(t - 0.5) < bridge_t)[0]
        if len(idx) > 2:
            first = _riser_plan(s, lb, ub, z0, z1, foot=foot, rest=False)
            b0, b1 = float(s[idx[0]]), float(s[idx[-1]])
            zb = float(_level_at(first, 0.5 * (b0 + b1)))
            zone = (s >= b0 - BRIDGE_LANDING) & (s <= b1 + BRIDGE_LANDING)
            lb = np.where(zone, np.maximum(lb, zb), lb)
            ub = np.where(zone, zb, ub)
            arch = (b0, b1, zb, bridge_t)
            rest = False                      # the bridge marks this stage
    plan = _riser_plan(s, lb, ub, z0, z1, foot=foot, rest=rest)
    return dict(s=s, xy=xy, yaw=yaw, info=info, L=L, n=n, nl=nl, lat=lat, h=h,
                on_terrace=flat.all(axis=0), off_mass=int((FF[:n] <= 0.0).sum()), rest=rest,
                arch=arch, plan=plan)


def _plan_stairway(rng_, seg, pa, pb):
    """The segment's own meander first. If the climb does not fit the length (flights plus
    landings steeper than the link allows), longer serpentines up to meander_cap; on the notch
    link, shorter bridge spans first. The first plan that keeps every rule wins, else the one
    that breaks them least."""
    p0, p1 = pa["p"], pb["p"]
    gate = seg["ka"] not in FOOT_GATE_SKIP
    foot = FOOT_FLAT if gate else 0.0
    m0 = seg["meander"]
    cap = meander_cap(p0, pa["h"], p1, pb["h"])
    ms = [m0]
    for k in range(1, 16):
        m = math.copysign(min(cap, abs(m0) + 3.0 * k), m0 if m0 else 1.0)
        if abs(m) <= abs(ms[-1]) + 1e-6:
            break
        ms.append(m)
    best = None
    for bt in (BRIDGE_TS if seg["notch"] else (None,)):
        for m in ms:
            P = _try_stairway(rng_, seg, p0, p1, pa["h"], pb["h"], m, bt, foot)
            if best is None or P["plan"]["viol"] < best["plan"]["viol"] - 1e-6:
                best = P
            if P["plan"]["viol"] < 1e-6:
                break
        if best["plan"]["viol"] < 1e-6:
            break
    best.update(gate=gate, foot=foot, meander_seg=m0)
    return best


def _stairway(rng_, coll, seg, nm, pa, pb, arch_extras=True, r11=False):
    """One marble stairway from port pa (depart) to port pb (arrival); see the section notes.
    ``arch_extras``: build the foot archway and the rest pavilion (sect.lib.arch; patches that
    only replace the stair's own meshes skip them). ``r11``: the treads, piers and arch as round 11 built them (1 cm
    TREAD_GAP, straight corbel courses, the arch's sides REVEAL in; patch_r12_world's guard). Returns (objects, report,
    geometry)."""
    A = _arch() if arch_extras else None
    p0, p1 = pa["p"], pb["p"]
    z0, z1 = float(p0[2]), float(p1[2])
    P = _plan_stairway(rng_, seg, pa, pb)
    s, xy, yaw, L, n, nl, lat, h = (P[k] for k in ("s", "xy", "yaw", "L", "n", "nl", "lat", "h"))
    gate, arch, plan = P["gate"], P["arch"], P["plan"]
    sr, lev = plan["sr"], plan["lev"]
    zs = _level_at(plan, s)
    soffit = lambda q: np.minimum(_nosing(plan, s, z0, z1, q) - STAIR_DEPTH, _level_at(plan, q) - 0.6)

    # treads: one prism per stretch between centreline samples and risers. Round 11: none over the
    # foot landing, whose slab is the floor there, flush with the first tread (the treads lay 4 mm
    # over it and z-fought with it); and no sample within TREAD_GAP of a riser or of the foot (it cut a
    # tread a few mm long, whose riser face stood mm from the next one's: z-fighting risers)
    foot = P["foot"] if gate else 0.0
    fixed = np.concatenate([sr, [foot] if foot else []])
    gap = 0.01 if r11 else TREAD_GAP
    s_cut = s[np.abs(s[:, None] - fixed[None, :]).min(axis=1) > gap] if len(fixed) else s
    cuts = np.unique(np.concatenate([[0.0, L], s_cut, fixed]))
    cuts = cuts[np.concatenate([[True], np.diff(cuts) > 1e-4])]
    c, nlq, _ = _frame(s, xy, yaw, cuts)
    zc = _level_at(plan, 0.5 * (cuts[:-1] + cuts[1:]))
    sb = soffit(cuts)
    treads = []
    for k in range(len(cuts) - 1):
        if cuts[k + 1] <= foot + 1e-6:
            continue
        q4 = _strip(c, nlq, k, k + 1, -STAIR_W * 0.5, STAIR_W * 0.5)
        treads.append(_prism(q4, [sb[k], sb[k + 1], sb[k + 1], sb[k]], zc[k]))
    # parapets: solid side walls from the soffit to RAIL_H over the nosing line, the coping falling
    # COPING m to the outer edge (steeper than 45 deg: not a floor); open beside the rest
    # pavilion's terrace. Round 11: each is one continuous solid per run (_ribbon) through every
    # centreline sample, shaded smooth along the run and sharp at its corners. It was a separate
    # box every 2 samples, each baked with its own shade: light and dark scales round the bends.
    # The run breaks exactly at the rest landing's ends: the box rows broke on the nearest box,
    # up to 1.1 m wider than the opening, and ran 0.5 m over the slab at each end (its inner face
    # in the parapet's plane)
    side = 1.0 if P["info"]["meander"] >= 0.0 else -1.0
    rest_span = rest_open = None
    if plan["rest_k"] is not None:
        k = plan["rest_k"]
        mid = 0.5 * (sr[k] + sr[k + 1])
        rest_span = (mid - REST_LANDING * 0.5 + 0.5, mid + REST_LANDING * 0.5 - 0.5)
        rest_open = (rest_span[0] - 0.5, rest_span[1] + 0.5)          # the slab's ends, qa and qb below
    # (the parapets start where the first flight starts: the foot landing that carries the
    # archway stays one open landing; before, they ran through it from the depart edge and cut
    # it into a centre lane and two dead strips)
    keys = np.array([L] + ([foot] if foot else []) + (list(rest_open) if rest_open else []))
    st = np.unique(np.concatenate([s[np.abs(s[:, None] - keys[None, :]).min(axis=1) > 0.2], keys]))
    c2, nl2, _ = _frame(s, xy, yaw, st)
    top2 = _nosing(plan, s, z0, z1, st) + RAIL_H
    bot2 = soffit(st)
    rails = []
    for sd in (-1.0, 1.0):
        keep = st[:-1] >= foot - 1e-6                 # segment k runs from st[k] to st[k + 1]
        if rest_open and sd == side:
            keep &= ~((st[:-1] >= rest_open[0] - 1e-6) & (st[1:] <= rest_open[1] + 1e-6))
        l0, l1 = (STAIR_W * 0.5, lat) if sd > 0 else (-lat, -STAIR_W * 0.5)
        zt = np.stack([top2, top2 - COPING] if sd > 0 else [top2 - COPING, top2], axis=1)
        k = 0
        while k < len(keep):
            if not keep[k]:
                k += 1
                continue
            k0 = k
            while k < len(keep) and keep[k]:
                k += 1
            sl = slice(k0, k + 1)                     # stations k0 .. k (segments k0 .. k - 1)
            rails.append(_ribbon(c2[sl], nl2[sl], l0, l1, bot2[sl], zt[sl]))
    # supports (W4): corbelled piers at most PIER_SPAN[1] apart where the treads stand > PIER_GAP over
    # the ground, a footing under the lower stretches (_supports)
    on_bridge = np.zeros(n, bool)
    if arch:
        on_bridge = (s >= arch[0]) & (s <= arch[1])
    piers, footing, sup = _supports(rng_, nm, s, xy, yaw, nl, lat, zs, soffit, on_bridge,
                                    foot=P["foot"] if gate else 0.0, curved=not r11)
    # the arch (W4): intrados springs from the ground at both ends, BRIDGE_CROWN under the deck
    # at the crown, so the bridge reaches the ground instead of hanging a fixed 22 m
    arch_pr = []
    if arch:
        b0, b1, zb = arch[:3]
        k0, k1 = int(np.searchsorted(s, b0)), int(np.searchsorted(s, b1))
        crown = zb - BRIDGE_CROWN
        mid, half = 0.5 * (b0 + b1), max(0.5 * (b1 - b0), 1e-6)
        hs = h[k0] + (h[k1] - h[k0]) * (s - b0) / max(b1 - b0, 1e-6)
        x = np.clip((s - mid) / half, -1.0, 1.0)
        intr = hs + (crown - hs) * np.sqrt(np.maximum(0.0, 1.0 - x * x))
        bot = np.maximum(intr, h - 1.0)
        topa = soffit(s) + 0.3
        # (round 11: its sides stand REVEAL inside the parapets' outer faces; flush with them, the
        # two shared a 0.3 m band along the whole bridge, where the arch reaches up into the stair.
        # Round 12: ARCH_REVEAL, as 2 cm still fought from about 290 m on)
        ins = REVEAL if r11 else ARCH_REVEAL
        for k in range(k0, k1):
            q4 = _strip(xy, nl, k, k + 1, -lat + ins, lat - ins)
            arch_pr.append(_prism(q4, [bot[k], bot[k + 1], bot[k + 1], bot[k]],
                                  [topa[k], topa[k + 1], topa[k + 1], topa[k]]))
    # (the treads' and parapets' undersides in the supports' stone: a white soffit read as a lit band
    # under every flight)
    objs = [_prisms_obj(nm + ".stairs", coll, treads, "marble_white", under="world_pier_stone"),
            _prisms_obj(nm + ".rails", coll, [], "marble_white", under="world_pier_stone", solids=rails,
                        smooth_solids=True),
            _prisms_obj(nm + ".piers", coll, piers, "world_pier_stone", solids=footing),
            _prisms_obj(nm + ".arch", coll, arch_pr, "world_pier_stone")]
    extras = []
    foot_drop = 0.0
    # walking surfaces (sink_under_links): XY points every 0.15 x 0.25 m with their floor level over
    # the treads from the first flight on, then over the foot and rest landings (pads: their
    # outlines and levels)
    qw = np.unique(np.concatenate([np.arange(foot, L, 0.15), [L]]))
    cw_, nw_, _ = _frame(s, xy, yaw, qw)
    lw = np.linspace(-STAIR_W * 0.5, STAIR_W * 0.5, 21)
    walk_xy = [(cw_[:, None, :] + nw_[:, None, :] * lw[None, :, None]).reshape(-1, 2)]
    walk_z = [np.repeat(_level_at(plan, qw), len(lw))]
    pads = []
    # (the foot landing's depth and parapet, and whether the rest terrace stands on a pier, read the
    # PLAN_GRID mesh like the riser plan, so a finer range leaves them as they were)
    # foot landing + archway (W3)
    if gate:
        cf, nf, af = _frame(s, xy, yaw, [0.0, FOOT_FLAT, FOOT_FLAT * 0.5])
        hw = FOOT_GATE["width"] * 0.5 + 0.6
        q4 = [cf[0] - nf[0] * hw, cf[1] - nf[1] * hw, cf[1] + nf[1] * hw, cf[0] + nf[0] * hw]
        g, _, _ = _ground(rng_, np.array([p[0] for p in q4]), np.array([p[1] for p in q4]), grid=PLAN_GRID)
        # (round 11: its top is the floor from the area's edge to the first riser, flush with the
        # depart point and the first tread; it lay 4 mm under treads that ran over it, and the two
        # z-fought)
        objs.append(_prisms_obj(nm + ".foot_landing", coll, [_prism(q4, float(g.min()) - 0.6, z0)],
                                "marble_white"))
        qf = np.linspace(0.0, FOOT_FLAT, 34)
        cfq, nfq, _ = _frame(s, xy, yaw, qf)
        lf = np.linspace(-hw, hw, 46)
        walk_xy.append((cfq[:, None, :] + nfq[:, None, :] * lf[None, :, None]).reshape(-1, 2))
        walk_z.append(np.full(len(qf) * len(lf), z0))
        pads.append((np.array(q4, float), z0))
        foot_drop = z0 - float(g.min())
        if foot_drop > 0.5:
            # the landing stands over falling ground: a parapet along its two sides and across its
            # back corners beside the first flight (the front, toward the area, stays open). It
            # stands on the slab REVEAL in from the slab's faces, WALL_SINK down into it (round 11:
            # the walls shared the slab's side, back and bottom faces)
            cb, nb, _ = _frame(s, xy, yaw, [REVEAL, FOOT_FLAT - REVEAL - RAIL_W, FOOT_FLAT - REVEAL])
            zb_, top, ho = z0 - WALL_SINK, z0 + RAIL_H, hw - REVEAL
            walls = []
            for sd in (-1.0, 1.0):
                l0, l1 = (ho - RAIL_W, ho) if sd > 0 else (-ho, -ho + RAIL_W)
                cop = [top, top, top - COPING, top - COPING] if sd > 0 else [top - COPING, top - COPING, top, top]
                walls.append(_prism(_strip(cb, nb, 0, 2, l0, l1), zb_, cop))
                l0, l1 = (lat, ho - RAIL_W) if sd > 0 else (-ho + RAIL_W, -lat)
                walls.append(_prism(_strip(cb, nb, 1, 2, l0, l1), zb_, [top, top - COPING, top - COPING, top]))
            objs.append(_prisms_obj(nm + ".foot_rail", coll, walls, "marble_white"))
        if A is not None:
            try:
                with _low_roofs(A):
                    extras.append(A.paifang(nm + ".foot_gate", coll, bays=FOOT_GATE["bays"],
                                            width=FOOT_GATE["width"], height=FOOT_GATE["height"],
                                            roof_mat="roof_tile_teal",
                                            location=(float(cf[2][0]), float(cf[2][1]), z0),
                                            rotation_z=float(af[2]) - math.pi / 2))
            except Exception as exc:
                _log("WARN foot gate", nm, exc)
    # rest pavilion beside the middle landing, on its own railed terrace, front to the stair (W3)
    rest_at = None
    if rest_span:
        k = plan["rest_k"]
        zl = float(lev[k + 1])
        qa, qb = rest_span[0] - 0.5, rest_span[1] + 0.5
        cr, nr, ar = _frame(s, xy, yaw, [qa, qb, 0.5 * (qa + qb)])
        # the slab (round 11): its inner edge follows the stair's side through every centreline
        # sample, edge to edge with the treads and flush with them; its outer edge is the straight
        # line it always had. It used to run straight 0.2 m in under the treads, 4 mm down: one
        # plane on the web, and on a bend a gap on one side of the stair
        A_, B_ = cr[0] + nr[0] * side * (lat + REST_DEPTH), cr[1] + nr[1] * side * (lat + REST_DEPTH)
        qs = np.concatenate([[qa], s[(s > qa + 0.2) & (s < qb - 0.2)], [qb]])
        cq, nq, _ = _frame(s, xy, yaw, qs)
        l_in = np.full(len(qs), side * STAIR_W * 0.5)
        l_out = _chord_lateral(cq, nq, A_, B_)
        slab = _ribbon(cq, nq, *((l_in, l_out) if side > 0 else (l_out, l_in)),
                       np.full(len(qs), zl - STAIR_DEPTH), np.full(len(qs), zl))
        objs.append(_prisms_obj(nm + ".rest_landing", coll, [], "marble_white", solids=[slab]))
        pads.append((np.vstack([cq + nq * l_in[:, None], (cq + nq * l_out[:, None])[::-1]]), zl))
        qd = np.linspace(qa, qb, int((qb - qa) / 0.15) + 2)
        cd_, nd_, _ = _frame(s, xy, yaw, qd)
        for cc, nn, lo_ in zip(cd_, nd_, _chord_lateral(cd_, nd_, A_, B_)):
            lr = np.linspace(side * STAIR_W * 0.5, lo_, max(2, int(abs(lo_ - side * STAIR_W * 0.5) / 0.25) + 2))
            walk_xy.append(cc[None, :] + nn[None, :] * lr[:, None])
            walk_z.append(np.full(len(lr), zl))
        # its rail stands on the slab REVEAL in from the slab's faces, WALL_SINK down into it
        # (round 11: the walls shared the slab's outer, end and bottom faces exactly): a side wall
        # along the straight outer edge, and at each end a wall from the line of the stair's
        # parapet (which stops at the slab's ends) out to it
        mo = np.array([-(B_ - A_)[1], (B_ - A_)[0]]) / float(np.linalg.norm(B_ - A_))
        mo = mo if float(mo @ (cr[2] - A_)) > 0.0 else -mo           # the outer edge's normal, toward the stair
        zt, zo, zw = zl + RAIL_H, zl + RAIL_H - COPING, zl - WALL_SINK
        cw, nw, _ = _frame(s, xy, yaw, [qa + REVEAL, qb - REVEAL])
        t_out = _chord_lateral(cw, nw, A_ + mo * REVEAL, B_ + mo * REVEAL)
        t_in = _chord_lateral(cw, nw, A_ + mo * (REVEAL + RAIL_W), B_ + mo * (REVEAL + RAIL_W))
        lo, hi = (t_in, t_out) if side > 0 else (t_out, t_in)
        wall = [_prism(_strip_l(cw, nw, 0, 1, lo, hi), zw, [zt, zt, zo, zo] if side > 0 else [zo, zo, zt, zt])]
        for a_, b_, cop in ((qa + REVEAL, qa + REVEAL + RAIL_W, [zo, zt, zt, zo]),
                            (qb - REVEAL - RAIL_W, qb - REVEAL, [zt, zo, zo, zt])):
            cc, nn, _ = _frame(s, xy, yaw, [a_, b_])
            e_in = np.full(2, side * lat)
            e_out = _chord_lateral(cc, nn, A_ + mo * (REVEAL + RAIL_W), B_ + mo * (REVEAL + RAIL_W))
            wall.append(_prism(_strip_l(cc, nn, 0, 1, *((e_in, e_out) if side > 0 else (e_out, e_in))), zw, cop))
        objs.append(_prisms_obj(nm + ".rest_rail", coll, wall, "marble_white"))
        pc = cr[2] + nr[2] * side * (lat + REST_DEPTH * 0.5)
        hpc, _, _ = _ground(rng_, np.array([pc[0]]), np.array([pc[1]]), grid=PLAN_GRID)
        if zl - float(hpc[0]) > PIER_GAP:
            pr, _ = _pier(rng_, pc, nr[2], float(ar[2]), zl - STAIR_DEPTH + 0.3, along=4.0, across=4.0)
            objs.append(_prisms_obj(nm + ".rest_pier", coll, [pr], "world_pier_stone"))
        d = -side * nr[2]
        rest_at = (round(float(pc[0]), 1), round(float(pc[1]), 1), round(zl, 2))
        if A is not None:
            try:
                with _low_roofs(A):
                    extras.append(A.pavilion(nm + ".rest_pavilion", coll, sides=6, radius=3.0, height=3.4,
                                             platform_h=0.5, location=(float(pc[0]), float(pc[1]), zl),
                                             rotation_z=math.atan2(float(d[0]), -float(d[1]))))
            except Exception as exc:
                _log("WARN rest pavilion", nm, exc)
    # report
    gaps = np.diff(sr) if len(sr) > 1 else np.zeros(0)
    inner = ~plan["land"][:-1] if len(sr) > 1 else np.zeros(0, bool)
    tread_min = float(gaps[inner].min()) if inner.any() else float("nan")
    run = np.diff(np.concatenate([[-1], np.where(plan["land"])[0], [plan["N"] - 1]]))
    off = h < min(z0, z1) - 1.0                # off the two areas' ground (on terraces it rests flush)
    clear = zs - h
    rep = dict(kind="stairway" + (" + arched bridge" if arch else ""), length=round(L, 1),
               rise=round(z1 - z0, 2), steps=plan["N"], max_riser=round(plan["r"], 3),
               min_tread=round(tread_min, 3),
               max_slope=round(plan["r"] / tread_min, 3) if tread_min == tread_min else None,
               avg_slope=round((z1 - z0) / L, 3), flights=int(plan["land"].sum()) + 1,
               longest_flight=int(run.max()) if len(run) else 0,
               min_landing=round(float(gaps[plan["land"][:-1]].min()), 2) if plan["land"][:-1].any() else None,
               min_clear=round(float(clear[off].min()), 2) if off.any() else None,
               min_clear_all=round(float(clear.min()), 2), buried=int((zs < h - 0.05).sum()),
               max_height=round(float(clear.max()), 1), **sup,
               min_radius=round(P["info"]["radius"], 1), schedule_violation=round(plan["viol"], 3),
               meander=round(P["info"]["meander"], 1), meander_segment=round(P["meander_seg"], 1),
               meander_cap=round(P["info"]["cap"], 1), hermite_k=P["info"]["k"],
               off_mass=P["off_mass"], foot_gate=gate, rest_pavilion=rest_at,
               foot_drop=round(foot_drop, 2) if gate else None)
    if arch:
        rep["bridge"] = dict(deck_z=round(arch[2], 2), span=round(arch[1] - arch[0], 1), span_t=arch[3],
                             level=bool(np.ptp(zs[(s >= arch[0] - BRIDGE_LANDING) & (s <= arch[1] + BRIDGE_LANDING)]) < 1e-6),
                             max_depth=round(float((arch[2] - h[(s >= arch[0]) & (s <= arch[1])]).max()), 1))
    geo = dict(s=s, xy=xy, yaw=yaw, z=zs, h=h, plan=plan,
               sink=dict(walk=(np.vstack(walk_xy), np.concatenate(walk_z)), strip=(foot, lat), pads=pads))
    return [o for o in objs if o is not None] + extras, rep, geo


def _chain_bridge(rng_, coll, p0, p1, name, sag=CHAIN_SAG, width=CHAIN_W, steps=True, level=CHAIN_LEVEL,
                  spacing=CHAIN_PLANK):
    """Chain bridge from p0 to p1 (W5): a plank deck that is level for ``level`` m at each end and
    sags ``sag`` m between, planks every ``spacing`` m; ``steps`` rounds each plank's height to
    the riser of the climb (<= RISER), flat planks, so the deck is a stepped walk instead of a
    slope. Red posts at both ends, iron chain handrails and under-chains."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1[:2] - p0[:2]
    D = float(np.hypot(d[0], d[1]))
    u = d / D
    yaw = math.atan2(u[1], u[0])
    dz = float(p1[2] - p0[2])

    def zs(q):
        w = np.clip((np.asarray(q, float) - level) / max(D - 2.0 * level, 1e-6), 0.0, 1.0)
        return p0[2] + dz * w - 4.0 * sag * w * (1.0 - w)

    n = max(10, int(round(D / spacing)))
    sc = (np.arange(n) + 0.5) * D / n
    z = zs(sc)
    nr = max(1, int(math.ceil(abs(dz) / RISER - 1e-9)))
    r = dz / nr
    zq = p0[2] + r * np.round((z - p0[2]) / r) if steps else z
    slope = np.gradient(zs(sc), sc)
    planks = []
    for q, zz, sl in zip(sc, zq, slope):
        x, y = p0[0] + u[0] * q, p0[1] + u[1] * q
        planks.append(((x, y, zz + 0.02 - 0.09), yaw, D / n - 0.05, width, 0.18, 0.0 if steps else float(sl)))
    objs = [_boxes_obj(name + ".deck", coll, planks, "wood_light")]
    # boards under the planks, one per tread, 6 cm down: what the planks are nailed to (the
    # 5 cm plank gaps show them, and a walker never meets a hole)
    boards, k0 = [], 0
    for k in range(1, n + 1):
        if k == n or abs(zq[k] - zq[k0]) > 1e-6:
            q0, q1 = sc[k0] - 0.5 * D / n, sc[k - 1] + 0.5 * D / n
            qm = 0.5 * (q0 + q1)
            boards.append(((p0[0] + u[0] * qm, p0[1] + u[1] * qm, zq[k0] - 0.06 - 0.1), yaw, q1 - q0 + 0.02,
                           width - 0.5, 0.2))
            k0 = k
    objs.append(_boxes_obj(name + ".boards", coll, boards, "wood_dark"))
    posts = []
    nl = np.array([-u[1], u[0]])
    for q in (0.6, D + 0.6):     # forge end: on the bridgehead; arena end: p1 is the slab's edge
        b = p0[:2] + u * q
        zz = float(zs(min(q, D)))
        for sd in (-1, 1):
            o = b + nl * sd * (width * 0.5 + 0.3)
            posts.append(((o[0], o[1], zz + 1.6), yaw, 0.7, 0.7, 4.0))
    objs.append(_boxes_obj(name + ".posts", coll, posts, "lacquer_red"))
    bm = bmesh.new()
    qs = np.linspace(0.6, D + 0.6, max(4, int(D / 2.0)) + 1)
    for sd in (-1, 1):
        o = nl * sd * (width * 0.5 + 0.3)
        for dzc in (1.1, -0.25):
            pts = [(p0[0] + u[0] * q + o[0], p0[1] + u[1] * q + o[1], float(zs(min(q, D))) + dzc) for q in qs]
            pts = [(pts[0][0], pts[0][1], pts[0][2] + 2.0)] + pts + [(pts[-1][0], pts[-1][1], pts[-1][2] + 2.0)]
            _tube_bm(bm, pts, 0.14, sides=5)
    objs.append(U.mesh_from_bmesh(name + ".chains", bm, coll, materials=["iron"], smooth=True))
    hgr, _, _ = _ground(rng_, p0[0] + u[0] * sc, p0[1] + u[1] * sc)
    rises = np.abs(np.diff(zq))
    nz = rises[rises > 1e-6]
    treads = np.diff(sc[np.concatenate([[False], np.abs(np.diff(zq)) > 1e-6])]) if len(nz) > 1 else np.zeros(0)
    rep = dict(kind="chain bridge", length=round(D, 1), rise=round(dz, 2), steps=int(len(nz)) if steps else 0,
               max_riser=round(float(rises.max()), 3), min_tread=round(float(treads.min()), 2) if len(treads) else None,
               max_slope=round(float(np.abs(slope).max()), 3),
               max_slope_deg=round(math.degrees(math.atan(float(np.abs(slope).max()))), 1),
               sag=sag, planks=n, level_ends=level, min_clear=round(float((zq - hgr).min()), 1))
    geo = dict(s=sc, xy=np.stack([p0[0] + u[0] * sc, p0[1] + u[1] * sc], axis=1), z=zq, h=hgr)
    return [o for o in objs if o is not None], rep, geo


ROCK_TIP_RINGS = 4         # tidy_rock: the bottom rings of a floating_rock's cone that close into one point (3, 4, 6
                           # left 40, 36, 33 m2 of the 117 m2 within 12 mm on the 151 rocks: the rest is spread up the
                           # cone, mostly beyond 5 mm; 4 changes the shape of the smallest islets' last 2-3 m only)


def rock_rings(me):
    """The ring layout of a nature.floating_rock mesh: dict(segs, bands, ring(k) -> vertex indices of ring k, 0 = the
    rim, ``bands`` = the bottom line), or None when the mesh is not one. floating_rock builds its cone as 3 rim rings
    and nz rings down to a last ring of radius 0, with ``segs`` quads per band between consecutive rings (faces band by
    band; remove_doubles turns some of the last band's into triangles where it merged neighbours on the bottom line),
    then the grassy top (bands of segs quads and a centre fan of segs triangles, material 1), then the spurs. Ring k
    (0 < k < bands) is what bands k - 1 and k share; the bottom line is the last band less ring bands - 1."""
    npl = len(me.polygons)
    if npl == 0 or len(me.materials) < 2:
        return None
    lt = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    mi = np.empty(npl, np.int32)
    me.polygons.foreach_get("material_index", mi)
    top = np.nonzero(mi == 1)[0]
    if not len(top):
        return None
    segs = int(((lt == 3) & (mi == 1)).sum())
    first_top = int(top.min())
    if segs < 8 or first_top % segs or first_top // segs < 4:
        return None
    nb = first_top // segs
    if (lt[:(nb - 1) * segs] != 4).any() or (lt[(nb - 1) * segs:first_top] < 3).any() or             (lt[(nb - 1) * segs:first_top] > 4).any() or (mi[:first_top] != 0).any():
        return None
    ls = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    cv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", cv)

    def band(k):
        f = np.arange(k * segs, (k + 1) * segs)
        return set(np.concatenate([cv[ls[i]:ls[i] + lt[i]] for i in f.tolist()]).tolist())
    cache = {}

    def ring(k):
        if k not in cache:
            if k == nb:
                r = band(nb - 1) - band(nb - 2)
            elif k == 0:
                r = band(0) - band(1)
            else:
                r = band(k - 1) & band(k)
            cache[k] = np.array(sorted(r), np.int64)
        return cache[k]
    for k in (nb - 3, nb - 2, nb - 1):
        if len(ring(k)) != segs:
            return None
    if not 0 < len(ring(nb)) <= segs:
        return None
    return dict(segs=segs, bands=nb, ring=ring)


ROCK_TIP_PROP = "rock_tip"  # (round 39) tidy_rock: mesh property, ROCK_TIP_MERGED once the tip is one vertex
ROCK_TIP_MERGED = "merged"


def tidy_rock(ob, rings=ROCK_TIP_RINGS, info=None):
    """Close the bottom of a nature.floating_rock's cone in one vertex.

    Round 12: floating_rock ends the cone in a ring of radius 0 whose vertices keep their own heights (up to 0.15 x
    depth apart), so the last bands stood as vertical fins round one line, folded onto each other, and the rings just
    over it crumpled the same way: faces within 5 mm of each other on every island, islet and stepping stone (75 m2 in
    the last band, 16 m2 in the two over it, of 117 m2 within 12 mm on the 151 rocks). The last ``rings`` rings (the
    bottom line and the ones over it) move into one point, under the middle of the last ring kept and as low as the
    lowest of them: the band over them becomes one cone of triangles to that point.

    Round 39: round 12 left the moved vertices stacked on that point (538 on Ice-Fire Island) and the moved bands'
    faces in place with no area. The web bake's collapse decimation cannot take such a tip below about 6 %: it threw
    the rock's top away instead (r36: 148 of the 151 rocks lost their tops at 3 %, 33 of the 43 in the area
    stand-ins). Now the moved vertices merge into one tip vertex (_merge_tip): the moved bands' faces go and the band
    over them is a fan of triangles round the tip. The plants stay where they stood: nature.scatter's Distribute
    Points on Faces seeds each triangle by its index, so the faces before the grassy top keep their triangle count
    (the fan's radial edges get evenly spaced vertices and each fan triangle is cut into strips in its own plane: the
    same surface) and the top and the spurs keep their faces, their order and their corners exactly.
    Returns the vertices moved or merged (0 when it was already done, -1 when the mesh is not a floating_rock);
    ``info`` (a dict) gets the merge's counts."""
    me = ob.data
    if me.get(ROCK_TIP_PROP) == ROCK_TIP_MERGED:
        return 0
    lay = rock_rings(me)
    if lay is None:
        return -1
    idx = np.concatenate([lay["ring"](k) for k in range(lay["bands"] - rings + 1, lay["bands"] + 1)])
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    # (under the middle of the last ring kept, so the cone of triangles to it cannot fold over itself)
    apex = np.concatenate([co[lay["ring"](lay["bands"] - rings)][:, :2].mean(0), [co[idx, 2].min()]])
    apex = apex.astype(np.float32).astype(np.float64)        # as the mesh stores it: a second run finds it in place
    moved = int((np.abs(co[idx] - apex).max(axis=1) > 0.0).sum())
    if moved:
        co[idx] = apex
        me.vertices.foreach_set("co", co.ravel())
        me.update()
    merged = _merge_tip(me, lay, idx, rings, info if info is not None else {})
    me[ROCK_TIP_PROP] = ROCK_TIP_MERGED
    return moved + merged


def _face_corners(me, f0, f1):
    """Corner positions (float32, as stored), loop totals and material indices of faces f0..f1-1."""
    npl = len(me.polygons)
    ls = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    mi = np.empty(npl, np.int32)
    me.polygons.foreach_get("material_index", mi)
    cv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", cv)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    if f1 <= f0:
        return np.zeros((0, 3), np.float32), lt[:0].copy(), mi[:0].copy()
    start, end = int(ls[f0]), int(ls[f1 - 1] + lt[f1 - 1])       # a mesh's face loops are contiguous, in order
    return co[cv[start:end]], lt[f0:f1].copy(), mi[f0:f1].copy()


def _merge_tip(me, lay, idx, rings, info):
    """tidy_rock, round 39: the vertices ``idx`` (the moved rings, all on the tip point) become one vertex; the faces
    they made (the moved bands) go; the band over them, now triangles round the tip, gets cuts on its radial edges and
    each of its triangles is cut into strips (in its own plane) so the faces before the grassy top keep their triangle
    count. When the count to make up is odd, one fan triangle goes to the end of the face list instead (past the
    spurs). Checks that the top and the spurs come out exactly as they were. Returns the vertices merged."""
    segs, nb = lay["segs"], lay["bands"]
    first_top = nb * segs
    npl0 = len(me.polygons)
    lt0 = np.empty(npl0, np.int32)
    me.polygons.foreach_get("loop_total", lt0)
    tris0 = int((lt0[:first_top] - 2).sum())
    rest0 = _face_corners(me, first_top, npl0)
    ring = [int(i) for i in lay["ring"](nb - rings)]          # the last ring kept, in the build's (angular) order
    pos = {v: j for j, v in enumerate(ring)}
    tip_i = int(idx.min())
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        ordL = bm.faces.layers.int.new("~tip_ord")
        subL = bm.faces.layers.int.new("~tip_sub")
        vidL = bm.verts.layers.int.new("~tip_vid")
        for f in bm.faces:
            f[ordL] = f.index
            f[subL] = 0
        for v in bm.verts:
            v[vidL] = v.index
        bm.verts.ensure_lookup_table()
        tip = bm.verts[tip_i]
        bmesh.ops.weld_verts(bm, targetmap={bm.verts[int(i)]: tip for i in idx.tolist() if int(i) != tip_i})
        a = {}
        for v in bm.verts:
            if v[vidL] in pos:
                a[pos[v[vidL]]] = v
        fan = [None] * segs
        for f in tip.link_faces:
            js = sorted(pos.get(v[vidL], -1) for v in f.verts if v != tip)
            if len(f.verts) != 3 or len(js) != 2 or js[0] < 0:
                raise RuntimeError("tidy_rock: a face round the tip is not a fan triangle")
            j = js[0] if js[1] == (js[0] + 1) % segs else js[1]
            fan[j] = f
            f[ordL] = (nb - rings) * segs + j
            f[subL] = 0
        if any(f is None for f in fan) or len(a) != segs:
            raise RuntimeError("tidy_rock: the fan round the tip is not whole")
        tris1 = sum(len(f.verts) - 2 for f in bm.faces if f[ordL] < first_top)
        short = tris0 - tris1                                 # triangles to make up before the top
        if short < 0:
            raise RuntimeError("tidy_rock: more triangles before the top after the merge (%d -> %d)" % (tris0, tris1))
        odd = short % 2
        free = list(range(2, segs)) if odd else list(range(segs))   # radial edges that take cuts (odd: not fan 0's)
        cuts = (short + odd) // 2
        k = {j: cuts // len(free) for j in range(segs)}
        if odd:
            k[0] = k[1] = 0
        extra = cuts % len(free)
        for i in range(extra):
            k[free[(i * len(free)) // extra]] += 1
        chain = {}
        tip_co = tip.co.copy()
        for j in range(segs):
            prev, c0 = a[j], a[j].co.copy()
            chain[j] = [prev]
            for c in range(1, k[j] + 1):
                e = bm.edges.get((prev, tip))
                want = c0.lerp(tip_co, c / (k[j] + 1))
                _e, nv = bmesh.utils.edge_split(e, prev, 1.0 / (k[j] + 2 - c))
                if (nv.co - want).length > 1e-3:
                    raise RuntimeError("tidy_rock: edge_split put a vertex %.4f m off" % (nv.co - want).length)
                nv.co = want
                chain[j].append(nv)
                prev = nv
        for j in range(segs):
            face, L_, R_ = fan[j], chain[j], chain[(j + 1) % segs]
            if odd and j == 0:
                face[ordL] = 2 ** 30                          # past the spurs: off the count before the top
                continue
            p = q = sub = 0
            while p < len(L_) - 1 or q < len(R_) - 1:
                if q >= len(R_) - 1 or (p < len(L_) - 1 and (p + 1) * len(R_) <= (q + 1) * len(L_)):
                    va, vb = L_[p + 1], R_[q]
                    p += 1
                else:
                    va, vb = L_[p], R_[q + 1]
                    q += 1
                nf, _l = bmesh.utils.face_split(face, va, vb)
                rest, cut = (face, nf) if tip in face.verts else (nf, face)
                cut[ordL] = (nb - rings) * segs + j
                cut[subL] = sub
                sub += 1
                face = rest
            face[ordL] = (nb - rings) * segs + j
            face[subL] = sub
        tris2 = sum(len(f.verts) - 2 for f in bm.faces if f[ordL] < first_top)
        if tris2 != tris0:
            raise RuntimeError("tidy_rock: %d triangles before the top, want %d" % (tris2, tris0))
        bm.faces.sort(key=lambda f: f[ordL] * 1024.0 + f[subL])    # (a number: BMesh sorts by float keys)
        bm.faces.index_update()
        n_before = sum(1 for f in bm.faces if f[ordL] < first_top)
        n_after = sum(1 for f in bm.faces if first_top <= f[ordL] < 2 ** 30)
        bm.faces.layers.int.remove(ordL)
        bm.faces.layers.int.remove(subL)
        bm.verts.layers.int.remove(vidL)
        n_v0 = len(me.vertices)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    rest1 = _face_corners(me, n_before, n_before + n_after)
    if n_after != npl0 - first_top or not all(np.array_equal(x, y) for x, y in zip(rest0, rest1)):
        raise RuntimeError("tidy_rock: the top or the spurs changed")
    info.update(segs=segs, faces=[npl0, len(me.polygons)], verts=[n_v0, len(me.vertices)], merged=len(idx) - 1,
                cuts=cuts, odd=odd, tris_before_top=tris0)
    return len(idx) - 1


def _top_faces_up(ob, top_index=1):
    """nature.floating_rock recalculates normals over a mesh with overlapping spurs, and for some
    seeds that turns the whole rock inside out: its grassy top then faces down (walkcheck sees no
    floor, normal-based tools see the underside). Reverse every face when the top (material
    ``top_index``) faces down. Returns 1 if the mesh was flipped."""
    me = ob.data
    nz = [p.normal.z * p.area for p in me.polygons if p.material_index == top_index]
    if not nz or sum(nz) >= 0.0:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()
    return 1


def _stepping_stones(rng_, coll, p0, p1, name, seed=0, bulge=STONE_BULGE, land0=STONE_LAND0, land1=0.0):
    """Floating flat-topped stones from p0 to p1 (W6): count = ceil(rise / STONE_HOP) + 1, the
    first touching the landing around p0 (``land0`` m out) at its height, the last touching the
    landing edge at p1 at its height, tops evenly stepped, along a gentle sideways bulge."""
    r = U.rng("world.stones", seed)
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    rise = float(p1[2] - p0[2])
    count = int(math.ceil(abs(rise) / STONE_HOP)) + 1
    sizes = [r.uniform(*STONE_SIZE) for _ in range(count)]
    d = p1[:2] - p0[:2]
    D = float(np.hypot(d[0], d[1]))
    side = np.array([-d[1], d[0]]) / D
    tt = np.linspace(0.0, 1.0, 1601)
    C = p0[:2] + np.outer(tt, d) + np.outer(bulge * np.sin(np.pi * tt), side)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(C, axis=0).T))])
    a0 = land0 + sizes[0] * 0.5 - 0.2
    a1 = cum[-1] - (land1 + sizes[-1] * 0.5 - 0.2)
    arc = np.linspace(a0, a1, count)
    cx, cy = np.interp(arc, cum, C[:, 0]), np.interp(arc, cum, C[:, 1])
    tops = np.linspace(p0[2], p1[2], count)
    out, flipped = [], 0
    for i in range(count):
        ob = N.floating_rock(coll, size=sizes[i], seed=800 + seed * 50 + i, depth=sizes[i] * 0.8,
                             vegetation=False, roots=False, pine_on_top=False, name=name,
                             location=(float(cx[i]), float(cy[i]), float(tops[i]) - 0.12),
                             rotation=r.uniform(0, 6.28))
        flipped += _top_faces_up(ob)
        tidy_rock(ob)
        out.append(ob)
    cd = np.hypot(np.diff(cx), np.diff(cy))
    gaps = cd - (np.array(sizes[:-1]) + np.array(sizes[1:])) * 0.5
    rep = dict(kind="stepping stones", length=round(float(cum[-1]), 1), rise=round(rise, 2), stones=count,
               flipped_inside_out=flipped,
               max_hop_rise=round(float(np.abs(np.diff(tops)).max()), 2),
               max_edge_gap=round(float(gaps.max()), 2), min_edge_gap=round(float(gaps.min()), 2),
               first_top=round(float(tops[0]), 2), last_top=round(float(tops[-1]), 2))
    geo = dict(xy=np.stack([cx, cy], axis=1), z=tops, sizes=sizes)
    return out, rep, geo


def sink_under_links(rng_, terrain, links):
    """Round 11 (S2): lower the range SINK under each stairway's walking surfaces wherever it lay at
    their level. Where a stair runs onto a terrace, the riser plan keeps its lowest treads on the
    ground (lb = h), so they and the foot landing lay in the terrace's own plane: on the web the
    two z-fought, and in the bake each blocked the other's light (the dark band across the top of
    the gate -> mirror stair). The stairs stay exactly as they are (risers, landings and joins to
    the areas, as walkcheck measures them; the range on the terraces is never floor for it). Only
    the range moves, a few cm and out of sight under the stair, with one 2.5 m cell of slope beside it.

    Walking surfaces: geo['sink'] of each stairway: points over the tread tops (from the first
    flight on) and the foot and rest landings with their level L, and the stair's footprint (the
    treads with their parapets, the landings' outlines). A top vertex of the range inside that
    footprint, with L - SINK < T < L + SINK_UP for a walking point within SINK_REACH m (XY), goes to
    min(T, L - SINK) for the lowest such L. Nothing outside the footprint moves: the areas' steps,
    aprons and rails stand on the range right beside the stairs' ends. T is the range's analytic
    top there (Range.fields), not the mesh, so a second run lands on the same heights. Returns
    dict(vertices, by_link, max_drop)."""
    from mathutils import kdtree
    me = terrain.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    Mw = np.array(terrain.matrix_world)
    if not np.allclose(Mw, np.eye(4)):
        raise ValueError("sink_under_links: %s has a transform; the range is built in world space" % terrain.name)
    target = {}
    by_link = {}
    for nm, kind, objs, rep, geo in links:
        sk = geo.get("sink") if isinstance(geo, dict) else None
        if sk is None or not len(sk["walk"][0]):
            continue
        pts, lv = sk["walk"]
        lo, hi = pts.min(axis=0) - 1.0, pts.max(axis=0) + 1.0
        cand = np.nonzero((co[:, 0] >= lo[0]) & (co[:, 0] <= hi[0]) & (co[:, 1] >= lo[1]) & (co[:, 1] <= hi[1]))[0]
        if not len(cand):
            continue
        q0, lat = sk["strip"]
        sq, sl = _strip_coords(geo["s"], geo["xy"], geo["yaw"], co[cand, :2])
        # (past a bare stair end, SINK_END more: an unmoved corner just past it left a corner of the last tread
        # within 5 mm of the grass, the top of the gate -> mirror stair; a foot landing carries the other end)
        inside = (sq >= q0 - (SINK_END if q0 <= 0.0 else 0.0) - 1e-6) & \
            (sq <= float(geo["s"][-1]) + SINK_END + 1e-6) & (np.abs(sl) <= lat + 1e-6)
        for poly, _lvl in sk["pads"]:
            inside |= _in_poly(co[cand, :2], poly)
        cand = cand[inside]
        if not len(cand):
            continue
        T = rng_.fields(co[cand, 0], co[cand, 1])["T"]
        keep = (co[cand, 2] <= T + 0.01) & (co[cand, 2] >= T - SINK - SINK_UP - 0.01)      # top surface vertices
        keep &= (T > lv.min() - SINK) & (T < lv.max() + SINK_UP)
        cand, T = cand[keep], T[keep]
        kd = kdtree.KDTree(len(pts))
        for i, (x, y) in enumerate(pts):
            kd.insert((float(x), float(y), 0.0), i)
        kd.balance()
        moved = 0
        for v, t in zip(cand.tolist(), T.tolist()):
            hits = kd.find_range((float(co[v, 0]), float(co[v, 1]), 0.0), SINK_REACH)
            if not hits:
                continue
            L_ = lv[[h[1] for h in hits]]
            ok = L_[(L_ - SINK < t) & (t < L_ + SINK_UP)]
            if len(ok):
                z = min(t, float(ok.min()) - SINK)
                target[v] = min(target.get(v, z), z)
                moved += 1
        by_link[nm] = moved
    if target:
        idx = np.fromiter(target.keys(), np.int64)
        old = co[idx, 2].copy()
        co[idx, 2] = np.fromiter(target.values(), float)
        me.vertices.foreach_set("co", co.ravel().astype(np.float32))
        me.update()
        drop = float((old - co[idx, 2]).max())
    else:
        drop = 0.0
    return dict(vertices=len(target), by_link=by_link, max_drop=round(drop, 4))


def _strip_coords(s, xy, yaw, pts):
    """(station, lateral) of XY points against a centreline; past either end the line runs on
    along the end's tangent, so a point beyond an end gets a station outside [0, L]."""
    from mathutils import kdtree
    L = float(s[-1])
    q = np.arange(-2.0, L + 2.0 + 1e-9, 0.05)
    c, nl, _ = _frame(s, xy, yaw, np.clip(q, 0.0, L))
    t0 = np.array([math.cos(float(yaw[0])), math.sin(float(yaw[0]))])
    t1 = np.array([math.cos(float(yaw[-1])), math.sin(float(yaw[-1]))])
    c = c + np.minimum(q, 0.0)[:, None] * t0[None, :] + np.maximum(q - L, 0.0)[:, None] * t1[None, :]
    kd = kdtree.KDTree(len(q))
    for i, (x, y) in enumerate(c):
        kd.insert((float(x), float(y), 0.0), i)
    kd.balance()
    idx = np.array([kd.find((float(p[0]), float(p[1]), 0.0))[1] for p in pts], np.int64)
    lat = ((np.asarray(pts, float) - c[idx]) * nl[idx]).sum(axis=1)
    return q[idx], lat


def _in_poly(pts, poly):
    """Even-odd test of XY points against a closed polygon (k, 2)."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        cross = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / ((yj - yi) if yj != yi else 1e-30) + xi)
        inside ^= cross
        j = i
    return inside


LINK_TREE_CLEAR = 8.0      # terrain faces (5 m) whose centre is this close (XY) to a link part get no trees


def link_points():
    """(n, 2) XY points covering every world.link.* mesh (its vertices and triangle centres), so
    tree scatters can keep off stairs, landings, piers, arcades, bridges and stones."""
    pts = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith("world.link."):
            continue
        me = ob.data
        if not len(me.vertices):
            continue
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        M = np.array(ob.matrix_world)
        w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        pts.append(w[:, :2])
        if len(tri):
            pts.append(w[tri.reshape(-1, 3)].mean(axis=1)[:, :2])
    return np.vstack(pts) if pts else np.zeros((0, 2))


def clear_mask_near(surface, attrs, pts, radius=LINK_TREE_CLEAR):
    """Zero the FACE float attributes ``attrs`` of ``surface`` on faces whose centre lies within
    ``radius`` m (XY) of any of ``pts``. Returns the number of faces cleared."""
    from mathutils import kdtree
    me = surface.data
    if not len(pts):
        return 0
    kd = kdtree.KDTree(len(pts))
    for i, (x, y) in enumerate(pts):
        kd.insert((float(x), float(y), 0.0), i)
    kd.balance()
    n = len(me.polygons)
    cen = np.empty(n * 3)
    me.polygons.foreach_get("center", cen)
    cen = cen.reshape(-1, 3) @ np.array(surface.matrix_world)[:3, :3].T + np.array(surface.matrix_world)[:3, 3]
    vals = {}
    for a in attrs:
        at = me.attributes.get(a)
        if at is not None:
            v = np.empty(n, np.float32)
            at.data.foreach_get("value", v)
            vals[a] = (at, v)
    if not vals:
        return 0
    live = np.zeros(n, bool)
    for at, v in vals.values():
        live |= v > 0.5
    cleared = 0
    for f in np.nonzero(live)[0]:
        if kd.find((float(cen[f, 0]), float(cen[f, 1]), 0.0))[2] < radius:
            for at, v in vals.values():
                v[f] = 0.0
            cleared += 1
    for at, v in vals.values():
        at.data.foreach_set("value", v)
    me.update()
    return cleared


def build_connectors(rng_, coll):
    """Links between consecutive areas, each from the area's AREA['depart'] to the next one's
    AREA['arrival'] (PORTS as fallback): marble stairways on the range (one with a level arched
    bridge over the library -> steles notch), a chain bridge to the floating arena and stepping
    stones from it. Prints a 'WORLD LINK <json>' report per link; returns
    [(name, kind, objects, report, geometry)]."""
    made = []
    for seg in rng_.segs:
        ka, kb = seg["ka"], seg["kb"]
        nm = "world.link.%s_%s" % (ka, kb)
        pa, pb = port(rng_, ka, "depart"), port(rng_, kb, "arrival")
        if pa is None or pb is None:
            _log("WARN no depart / arrival for", nm)
            continue
        if seg["mass"]:
            objs, rep, geo = _stairway(rng_, coll, seg, nm, pa, pb)
        elif kb in FLOATING:
            objs, rep, geo = _chain_bridge(rng_, coll, pa["p"], pb["p"], nm + ".bridge")
        else:
            # the plan table's depart is the rear landing's centre; an area's own depart is
            # where the stones start
            land0 = STONE_LAND0 if pa["src"] == "plan table" else 0.0
            objs, rep, geo = _stepping_stones(rng_, coll, pa["p"], pb["p"], nm + ".stone", seed=seg["i"],
                                              land0=land0)
        rep = dict(link="%s-%s" % (ka, kb), **rep,
                   depart=dict(local=pa["local"], src=pa["src"], heading=pa["heading"],
                               world=[round(float(v), 2) for v in pa["p"]]),
                   arrival=dict(local=pb["local"], src=pb["src"], heading=pb["heading"],
                                world=[round(float(v), 2) for v in pb["p"]]))
        print("WORLD LINK", json.dumps(rep), flush=True)
        made.append((nm, rep["kind"], objs, rep, geo))
    _log("connectors", [(m[0], m[1]) for m in made])
    return made


# =========================================================================================
# entry point
# =========================================================================================

def build(scene=None, anchors=None):
    """Build the celestial realm into collection 'world' of ``scene``.

    ``anchors``: dict key -> (x, y, z, footprint[, yaw]) (default ANCHORS). Returns the root
    Empty 'world.root' (custom props: build_s, counts)."""
    t0 = time.perf_counter()
    scene = scene or bpy.context.scene
    yaws = _anchor_yaws(anchors)          # before normalising: keeps an explicit 5th (yaw) value
    anchors = _norm_anchors(anchors)
    top = U.get_collection("world", scene=scene)
    cols = {k: U.get_collection("world." + k, parent=top, scene=scene)
            for k in ("sky", "range", "clouds", "islets", "water", "links")}
    root = U.empty("world.root", top, display_size=20.0)
    times = {}

    def lap(k, t):
        times[k] = round(time.perf_counter() - t, 2)
        return time.perf_counter()

    t = time.perf_counter()
    build_sky(scene, cols["sky"])
    build_moon(cols["sky"])
    t = lap("sky", t)
    rng_ = Range(anchors, yaws)
    terrain, grid = build_terrain(rng_, cols["range"])
    if rng_.peak_mode == "pillars":         # round 48: a karst pillar on every cut peak
        _log("peak pillars", len(build_peak_pillars(rng_, cols["range"])))
    t = lap("terrain", t)
    build_forest(terrain, cols["range"])
    build_roots(grid, cols["range"])
    t = lap("forest_roots", t)
    build_cloud_sea(cols["clouds"])
    build_clouds(rng_, cols["clouds"])
    t = lap("clouds", t)
    build_islets(rng_, cols["islets"])
    build_backdrop(cols["range"])
    t = lap("islets_backdrop", t)
    build_waterfalls(rng_, cols["water"])
    t = lap("waterfalls", t)
    links = build_connectors(rng_, cols["links"])
    _log("range sunk under the stairs' walking surfaces:", sink_under_links(rng_, terrain, links))
    # (trees off the links: the forest scatter above knew nothing of them, and pines grew
    # through stair bodies and pier arcades)
    _log("forest faces cleared near links:", clear_mask_near(terrain, ["world_veg"], link_points()))
    t = lap("links", t)
    root["links"] = json.dumps([m[3] for m in links])
    root["build_s"] = round(time.perf_counter() - t0, 2)
    root["times"] = str(times)
    _log("built in", root["build_s"], "s", times)
    return root


def clearance_report(anchors=None, samples=80):
    """For each consecutive anchor pair: lowest clearance (m) between the straight anchor line
    and the range top, outside the two terraces and their first cliff drop (where the camera
    is at least 10 m over the terrace anyway). Spec: >= 25 m. Returns {pair: (clearance, t)}."""
    anchors = _norm_anchors(anchors)
    rng_ = Range(anchors)
    rep = {}
    for s in rng_.segs:
        A, B = anchors[s["ka"]], anchors[s["kb"]]
        t0 = (A[3] + TERRACE_PAD + 6.0 + 10.0) / s["L"]
        t1 = 1.0 - (B[3] + TERRACE_PAD + 6.0 + 10.0) / s["L"]
        ts = np.linspace(t0, t1, samples)
        p = np.array([rng_.seg_point(s, t) for t in ts])
        T = rng_.fields(p[:, 0], p[:, 1])["T"]
        c = p[:, 2] - T
        k = int(c.argmin())
        rep["%s-%s" % (s["ka"], s["kb"])] = (round(float(c[k]), 1), round(float(ts[k]), 2))
    return rep
