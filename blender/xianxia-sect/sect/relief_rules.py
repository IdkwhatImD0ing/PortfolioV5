"""Round 59 rock relief (docs/scene/rock-r59.md, "Shape") as plain numpy: the rules sect/relief.py applies to the bake's
captured copies of the rock that already has a fine mesh and is seen close. No bpy, no mathutils, so
tools/test_relief_rules.py tests them on the PC.

    Geo               one geology field for the whole range, in world space: beds with hard and soft members (a soft
                      bed sits back under the bed above), two near-vertical joint sets (set A runs through every bed,
                      set B is cut again in each bed with a spacing that follows the bed's thickness), blocks between
                      the joints that stand out or back and lean a little, and a few lost blocks (a notch where a
                      block fell out). raw() is the field itself; field() is the field box-filtered over the local
                      vertex spacing (supersampled), so no bed, joint or notch narrower than two vertex spacings
                      reaches the mesh as a zigzag along the vertex lattice (attack_0)
    planarize         per block, the vertices pulled toward the block's fitted plane, measured on smoothed normals,
                      so a block reads as one face instead of crumpled fabric
    column_*          karst columns: the round drums become columns with wide flat faces that follow the two joint
                      sets (the main faces, at MAIN of the radius, are the wide ones), with steps at the bed joints the
                      lathe already has (its ring pairs) and a few missing-block notches. The faces shave the
                      column's smoothed outline (envelope), so its own beds, shelves and fissures ride on top
    pins              distances to what must not move (plants, halls, water, roots, open edges) turned into weights
    abode_zone        the abode cliff's dressed rock, slope cap, inscription panel, water chute and top edge
    thick_scale       less relief where the rock is thin, so nothing folds through itself

Every constant can be changed for one run with KEY=value (sect/relief.py apply_overrides; preview_r59.py and
bake_web.py --relief-set pass them through).
"""
import math

import numpy as np

# ---- the geology field (world space) -----------------------------------------------------------------------------
GEO_SEED = 5901                # the bed list and every hash; one value for the whole range, so beds and joints line up
                               # across the cliff, the columns and the floating rocks
GEO_DIP = (2.2, 35.0)          # deg: the beds dip 2.2 deg toward azimuth 35 deg (from +x toward +y): about 3.8 m over
                               # 100 m, so a bed line reads level on one cliff and still drifts across the range
GEO_BED_WARP = ((1.6, 310.0, 17.0, 0.3), (0.9, 140.0, 104.0, 1.9), (0.5, 61.0, 61.0, 4.1))
                               # the beds wander: (amplitude m, wavelength m, direction deg, phase rad). 3 m at most,
                               # over 60 to 310 m, so a bed is never a ruled line
GEO_BED_RANGE = (-1500.0, 2500.0)   # m of bed coordinate the bed list covers (the scene's rock lies inside)
GEO_BED_T = (2.5, 11.0, 1.5)   # hard bed thickness m: lo + (hi - lo) x u ** 1.5, so thin beds are common and an 11 m
                               # massive bed is rare (Zhangjiajie sandstone: beds of 2 to 10 m)
GEO_SOFT = dict(p=0.22,        # share of soft beds (shale partings between the sandstone)
                t=(1.2, 2.6),  # m thick: at least about two vertex rows of the abode cliff (0.83 m), so the filter
                               # keeps most of their recess (attack_0: 0.8 m beds could not be drawn)
                recess=(1.0, 2.0))   # m: how far a soft bed sits back under the bed above (the overhang's depth)
GEO_HARD_OFF = 0.7             # m: a hard bed's own offset, triangular in +-0.7 (sd 0.29): neighbouring beds stand
                               # out or back a little against each other
GEO_SHOULDER = (0.35, 0.6)     # a hard bed's rounded top edge: depth m, over min(0.6 m, a quarter of the bed)
GEO_UNDERCUT = (0.45, 0.15)    # the groove at a hard bed's base: depth m, over the lowest 15 % of the bed
GEO_JOINT_A = dict(az=28.0,    # deg: the joint planes' normal (master joints, through every bed)
                   gap=14.5,   # m: mean spacing; with the jitter 7 to 22 m
                   jitter=0.25,   # each joint moves up to a quarter of the spacing from its regular place
                   warp=((2.5, 90.0, 118.0, 0.7), (1.2, 37.0, 70.0, 2.3)))   # m, m, deg, rad: the joints wander
GEO_JOINT_B = dict(az=115.0,   # deg: the second set, 87 deg from the first (near-orthogonal joints, as on real karst)
                   k=1.6,      # spacing = k x the bed's thickness (attack_0: an even spacing staggered bed by bed is a
                   gap=(6.0, 16.0),   # running bond, masonry); clipped to 6-16 m
                   jitter=0.25,
                   warp=((2.0, 75.0, 30.0, 1.1),))
GEO_BLOCK = dict(amp=0.35,     # m: a block stands out or back up to this much (the plan's 0.45, less: masonry risk)
                 soft=0.3,     # ... x this on a soft bed
                 tilt=0.06,    # m per m: a block's face leans across its width and up its height ...
                 tilt_max=0.5,   # ... at most this many metres either way
                 lost_p=0.07,  # share of hard-bed blocks that fell out (a notch)
                 lost=(0.8, 2.0))   # m: how deep a lost block's notch is
GEO_CLAMP = (-3.0, 0.8)        # m along the outward horizontal normal: never deeper than 3 m in, 0.8 m out
MOVE_MAX = 3.0                 # m: no vertex moves farther than this in all. The field (3 m in) plus the block
                               # flattening (PLANAR_CLIP 1.5 m) could reach 4.5 m in and 2.3 m out; the whole move is
                               # scaled down to this, so the log's max and the look gate's 3 m hold by construction
GEO_SCALE = (20.0, 0.25)       # an object narrower than 20 m in radius gets its relief scaled by radius / 20, at least
                               # x0.25 (a 6 m islet would otherwise lose a third of its width to one soft bed)

# ---- the low-pass: nothing narrower than two vertex spacings -----------------------------------------------------
LP_K = 2.0                     # filter width = this x the local vertex spacing (attack_0's rule)
LP_RANGE = (0.5, 6.0)          # m: the filter width stays inside this (a fan of long edges must not blur a whole bed)
LP_TAPS = (5, 3)               # supersampling taps of the box filter: vertical (beds), across the face (joints)
NRM_ITERS = 3                  # Laplacian passes over the vertex normals before they give the move direction
LP_LAMBDA = 0.5                # each pass moves a value half way to its neighbours' mean
PLANAR_LP_ITERS = 3            # Laplacian passes over the planarize move (it steps at block edges)

# ---- planarize ---------------------------------------------------------------------------------------------------
PLANARIZE = dict(cliff=0.7, island=0.6)   # share of the in-block undulation flattened (the cliff's fluting and fBm
                                          # folds, the islands' crag fBm)
PLANAR_MIN_N = 6               # a block needs this many weighted vertices to be fitted
PLANAR_MIN_R = 0.85            # ... and its smoothed horizontal normals must agree this well (mean resultant length;
                               # attack_0: 0.9 on raw normals skipped the abode's most folded blocks)
PLANAR_CLIP = 1.5              # m: a vertex moves at most this far toward its block's plane

# ---- karst columns -----------------------------------------------------------------------------------------------
COL = dict(main=0.86,          # the four faces that follow the joint sets sit at 0.86 x the radius: the wide faces
           chamfer=0.93,       # the four between them at 0.93: narrower (main faces 0.91 R wide, chamfers 0.57 R;
                               # attack_0: the plan had them swapped, so the big faces ran 45 deg off the joints)
           k=0.7,              # share of the outline outside the polygon that is shaved to it
           jitter=0.05,        # each face's distance +-5 %
           az_jitter=12.0,     # deg: each column turns its faces up to this far from the shared joint directions
           min_cos=0.25,       # a face only counts within 75 deg of its normal
           block=0.25,         # m: a column bed's face sits back up to this much (inward only)
           lost_p=0.06,        # share of column blocks (bed x face) that fell out
           lost=(0.6, 1.5),    # m deep
           max_in=3.0,         # m: never deeper than this ...
           rel_max=0.2)        # ... or than this share of the radius (slim columns)
COL_ENV = dict(nth=72,         # 5 deg sectors for the column's outline
               dz=1.0,         # m rows
               sigma=6.0)      # m: the outline is smoothed up the column over this (Gaussian), so beds and shelves are
                               # not shaved, only the slow lobes
COL_CAP = (1.0, 10.0)          # m from the cap's dome (or flat top): relief fades in over this, so the cap never
                               # overhangs a shaved wall as a mushroom
COL_FOOT = (2.0, 12.0)         # m above the plinth (world.peak r48_plinth): relief fades in over this
COL_FOOT_SINK = 8.0            # m: without a plinth the foot is the lowest wall point + this (peak_pillar sinks 8-10 m)
RING_PAIR_GAP = 0.12           # m: lathe rings this close (and in a run) mark a bed top: nature._pillar_rings puts
                               # zt + 0.04 with zt - 0.04 (hero) or zt - 0.06 (mid) there; the next ring is 0.16 m or
                               # more away
RING_EPS = 0.01                # m: vertex heights closer than this are one ring
RING_STEP_MIN = 0.04           # m: a ring pair is a bed top only if its two rings differ in radius by this much (median
                               # round the column). A real pair steps by the bed's shoulder (0.1-0.4 m on the scene's
                               # columns); two interior rings 0.01-0.12 m apart differ by under 0.01 m

# ---- pins: (distance m where relief is 0, distance m where it is whole) ------------------------------------------
RELIEF_STEEP = (0.75, 0.45)    # |smoothed normal z|: none from 0.75 (flat tops, ledges' floors), whole from 0.45. The
                               # cliff and the floating rocks only: a column moves radially, so its shelves move with
                               # their rings (weighted down, a shelf's lip stayed out as a flange round a shaved face)
PIN_NONROCK = (0.5, 3.0)       # from a vertex of a face that is not rock_cliff (grass tops, the underside, a cushion)
PIN_VEG = (2.5, 5.0)           # from a plant's origin (every nature.proto.* instance): it stands on unmoved rock
PIN_STRUCT = (2.5, 6.5)        # from the box of a hall, stair, bridge, plaque, prop, lawn or rock prop
PIN_WATER = (1.5, 4.5)         # from a waterfall sheet's surface (its vertices and edge samples, not its box)
PIN_ROOT = (0.8, 3.0)          # from a hanging root's surface (vertices and edge samples)
PIN_EDGE = (0.5, 4.0)          # from an open edge of the mesh (where it meets the terrain or ends)
STRUCT_MAX_DIAG = 150.0        # m: boxes larger than this are terrain or canopy shells, not structures
STRUCT_POINTS = (20.0, 2.0)    # a structure whose box is over 20 m long and over 2 x its middle side (the arena's
                               # chains, a link stair, a long rail) pins by its surface (vertices and edge samples),
                               # not its box: the box of a diagonal chain covers a whole island flank
ROCK_PROP_MAX_DIAG = 40.0      # m: a rock piece that is not relieved pins as a prop only up to this size
SAMPLE_STEP = 0.5              # m between samples along the edges of water sheets and roots
ABODE_FADE = 3.0               # m over which the abode's pinned zones fade back to full relief
RELIEF_THICK = (0.5, 6.0, 8.0, 0.4)   # thin rock: no relief under 0.5 m of rock behind a vertex, whole from 6 m (the
                               # ray looks 8 m in), and an inward move never deeper than 0.4 x the thickness
RELIEF_SHARP_DEG = 40.0        # deg: an edge relief folded past this, by RELIEF_SHARP_GAIN more than before, shades sharp
RELIEF_SHARP_GAIN = 10.0


def smoothstep(e0, e1, x):
    """0 at e0, 1 at e1 (either order, arrays fine), smooth in between, clamped."""
    e0 = np.asarray(e0, float)
    t = np.clip((np.asarray(x, float) - e0) / (np.asarray(e1, float) - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# splitmix64 on uint64 arrays. Every constant is np.uint64: mixing a uint64 array with a Python int casts to float64 on
# older numpy, which would silently break the hash
_C0 = np.uint64(0x9E3779B97F4A7C15)
_C1 = np.uint64(0xBF58476D1CE4E5B9)
_C2 = np.uint64(0x94D049BB133111EB)
_S11, _S27, _S30, _S31 = np.uint64(11), np.uint64(27), np.uint64(30), np.uint64(31)


def _mix(z):
    z = z + _C0
    z = (z ^ (z >> _S30)) * _C1
    z = (z ^ (z >> _S27)) * _C2
    return z ^ (z >> _S31)


def hash_u(salt, *keys):
    """A uniform value in [0, 1) per element, the same on every machine: splitmix64 chained over the integer keys
    (arrays broadcast; negative keys fine)."""
    arrs = [np.asarray(k).astype(np.int64) for k in keys]
    shape = np.broadcast(*arrs).shape if arrs else ()
    h = np.full(shape, int(salt) & 0xFFFFFFFFFFFFFFFF, dtype=np.uint64)
    with np.errstate(over="ignore"):
        h = _mix(h)
        for a in arrs:
            h = _mix(h ^ a.astype(np.uint64))
    return (h >> _S11).astype(np.float64) * (1.0 / 9007199254740992.0)


def _warp(x, y, terms):
    s = np.zeros(np.broadcast(x, y).shape)
    for amp, length, deg, ph in terms:
        d = math.radians(deg)
        s = s + amp * np.sin(2.0 * math.pi * (x * math.cos(d) + y * math.sin(d)) / length + ph)
    return s


def _cells(un, salt, extra, jit):
    """Cells of a joint set along its normalised coordinate un (one cell per unit, each boundary moved up to `jit` by a
    hash of (extra, boundary)). Returns (cell index, position in the cell -0.5..0.5, cell width in units)."""
    j0 = np.floor(un).astype(np.int64)

    def b(j):
        return j + jit * (2.0 * hash_u(salt, extra, j) - 1.0)

    j = np.where(un < b(j0), j0 - 1, np.where(un >= b(j0 + 1), j0 + 1, j0))
    lo, hi = b(j), b(j + 1)
    return j, (un - lo) / (hi - lo) - 0.5, hi - lo


def block_key(i, ja, jb):
    """One int64 per block (bed, A cell, B cell)."""
    i, ja, jb = (np.asarray(v).astype(np.int64) for v in (i, ja, jb))
    return ((i + 1) << 40) | ((ja + (1 << 19)) << 20) | (jb + (1 << 19))


class Geo:
    """The geology field. The bed list is drawn once from GEO_SEED (four draws a bed, in a fixed order, so a re-run is
    bit-identical); joints and blocks come from hashes, so any point can be asked for on its own."""

    def __init__(self, seed=None):
        self.seed = GEO_SEED if seed is None else int(seed)
        dip, az = math.radians(GEO_DIP[0]), math.radians(GEO_DIP[1])
        k = math.tan(dip)
        self.kx, self.ky = k * math.cos(az), k * math.sin(az)
        self.warp = tuple(GEO_BED_WARP)
        self.blocks = True              # False: beds only (the tests)
        rng = np.random.RandomState(self.seed)
        lo, hi = GEO_BED_RANGE
        t_lo, t_hi, ex = GEO_BED_T
        z, z0, ts, soft, off = lo, [], [], [], []
        while z < hi:
            a, b, c, d = rng.random_sample(4)
            s = a < GEO_SOFT["p"]
            if s:
                t = GEO_SOFT["t"][0] + (GEO_SOFT["t"][1] - GEO_SOFT["t"][0]) * b
                o = -(GEO_SOFT["recess"][0] + (GEO_SOFT["recess"][1] - GEO_SOFT["recess"][0]) * c)
            else:
                t = t_lo + (t_hi - t_lo) * b ** ex
                o = (c + d - 1.0) * GEO_HARD_OFF
            z0.append(z)
            ts.append(t)
            soft.append(bool(s))
            off.append(o)
            z += t
        self.z0 = np.array(z0)
        self.t = np.array(ts)
        self.soft = np.array(soft, bool)
        self.off = np.array(off)

    def zb(self, x, y, z):
        """Bed coordinate: height, plus the dip, plus the wander."""
        return z + self.kx * x + self.ky * y + _warp(x, y, self.warp)

    def bed(self, zb):
        """(bed index, position in the bed 0 at its base .. 1 at its top, bed thickness m)."""
        i = np.clip(np.searchsorted(self.z0, zb, side="right") - 1, 0, len(self.z0) - 1)
        t = self.t[i]
        return i, np.clip((zb - self.z0[i]) / t, 0.0, 1.0), t

    def profile(self, i, ph, t):
        """A bed's own relief: its offset; a hard bed also gets the rounded shoulder at its top and the groove at its
        base."""
        d_top = (1.0 - ph) * t
        sh = GEO_SHOULDER[0] * (1.0 - smoothstep(0.0, np.minimum(GEO_SHOULDER[1], 0.25 * t), d_top))
        uc = GEO_UNDERCUT[0] * smoothstep(GEO_UNDERCUT[1], 0.0, ph)
        return self.off[i] + np.where(self.soft[i], 0.0, -sh - uc)

    def joints_a(self, x, y):
        J = GEO_JOINT_A
        d = math.radians(J["az"])
        u = x * math.cos(d) + y * math.sin(d) + _warp(x, y, J["warp"])
        j, f, w = _cells(u / J["gap"], self.seed * 7 + 11, 0, J["jitter"])
        return j, f, w * J["gap"]

    def joints_b(self, x, y, i):
        J = GEO_JOINT_B
        gap = np.clip(J["k"] * self.t[i], J["gap"][0], J["gap"][1])
        shift = hash_u(self.seed * 7 + 21, i) * gap
        d = math.radians(J["az"])
        u = x * math.cos(d) + y * math.sin(d) + _warp(x, y, J["warp"]) - shift
        j, f, w = _cells(u / gap, self.seed * 7 + 23, i, J["jitter"])
        return j, f, w * gap

    def raw(self, x, y, z):
        """The field at points (x, y, z), m along the outward horizontal normal, unfiltered (it steps at bed and joint
        boundaries), and the block key of each point."""
        x, y, z = (np.asarray(v, float) for v in (x, y, z))
        i, ph, t = self.bed(self.zb(x, y, z))
        D = self.profile(i, ph, t)
        ja, fa, wa = self.joints_a(x, y)
        jb, _fb, _wb = self.joints_b(x, y, i)
        if self.blocks:
            B = GEO_BLOCK
            s = self.seed * 7 + 31
            soft = self.soft[i]
            h1, h2, h3, h4, h5 = (hash_u(s + k, i, ja, jb) for k in range(1, 6))
            D = D + (h1 - 0.5) * 2.0 * B["amp"] * np.where(soft, B["soft"], 1.0)
            tilt = B["tilt"] * ((h2 - 0.5) * 2.0 * fa * wa + (h3 - 0.5) * 2.0 * (ph - 0.5) * t)
            D = D + np.clip(tilt, -B["tilt_max"], B["tilt_max"])
            lost = (~soft) & (h4 < B["lost_p"])
            D = D - np.where(lost, B["lost"][0] + (B["lost"][1] - B["lost"][0]) * h5, 0.0)
        return np.clip(D, GEO_CLAMP[0], GEO_CLAMP[1]), block_key(i, ja, jb)

    def field(self, p, tdir, wz, wt, taps=None):
        """The field box-filtered at points p (n, 3): the mean of raw() over LP_TAPS samples spread wz m up and down
        (world z, the beds) and wt m across the face (tdir, unit horizontal tangents: the joints). wz, wt per point.
        Returns (D, the block key at each point itself)."""
        nz, nt = LP_TAPS if taps is None else taps
        p = np.asarray(p, float)
        tdir = np.asarray(tdir, float)
        wz = np.broadcast_to(np.asarray(wz, float), (len(p),))
        wt = np.broadcast_to(np.asarray(wt, float), (len(p),))
        acc = np.zeros(len(p))
        for a in range(nz):
            oz = ((a + 0.5) / nz - 0.5) * wz
            for b in range(nt):
                ot = ((b + 0.5) / nt - 0.5) * wt
                q = p + ot[:, None] * tdir
                acc += self.raw(q[:, 0], q[:, 1], q[:, 2] + oz)[0]
        _d0, key = self.raw(p[:, 0], p[:, 1], p[:, 2])
        return acc / float(nz * nt), key


def object_scale(radius):
    """Relief scale for an object of this radius (m): GEO_SCALE."""
    return float(np.clip(radius / GEO_SCALE[0], GEO_SCALE[1], 1.0))


# ---- mesh helpers -------------------------------------------------------------------------------------------------

def mesh_smooth(val, edges, iters=1, lam=None, nv=None):
    """Laplacian smoothing of a per-vertex value (n,) or (n, k) over the mesh edges (m, 2): each pass moves a vertex
    `lam` (None: LP_LAMBDA, read at the call so a KEY=value override reaches it) of the way to its neighbours' mean.
    Vertices without edges keep their value."""
    lam = LP_LAMBDA if lam is None else lam
    v = np.array(val, float, copy=True)
    nv = len(v) if nv is None else int(nv)
    e = np.asarray(edges, np.int64).reshape(-1, 2)
    if not len(e) or iters <= 0:
        return v
    e0, e1 = e[:, 0], e[:, 1]
    deg = np.bincount(e0, minlength=nv) + np.bincount(e1, minlength=nv)
    has = deg > 0
    cols = v.reshape(nv, -1)
    for _ in range(int(iters)):
        acc = np.empty_like(cols)
        for c in range(cols.shape[1]):
            acc[:, c] = np.bincount(e0, cols[e1, c], minlength=nv) + np.bincount(e1, cols[e0, c], minlength=nv)
        avg = acc / np.maximum(deg, 1)[:, None]
        cols = np.where(has[:, None], (1.0 - lam) * cols + lam * avg, cols)
    return cols.reshape(v.shape)


def vertex_spacing(co, edges, tdir):
    """Per vertex: (the largest |dz| over its edges, the largest |d . tdir| over its edges): the vertical and the
    across-the-face vertex spacing (m) the low-pass scales with."""
    co = np.asarray(co, float)
    e = np.asarray(edges, np.int64).reshape(-1, 2)
    nv = len(co)
    hz = np.zeros(nv)
    ht = np.zeros(nv)
    if not len(e):
        return hz, ht
    d = co[e[:, 1]] - co[e[:, 0]]
    dz = np.abs(d[:, 2])
    np.maximum.at(hz, e[:, 0], dz)
    np.maximum.at(hz, e[:, 1], dz)
    tdir = np.asarray(tdir, float)
    np.maximum.at(ht, e[:, 0], np.abs((d * tdir[e[:, 0]]).sum(1)))
    np.maximum.at(ht, e[:, 1], np.abs((d * tdir[e[:, 1]]).sum(1)))
    return hz, ht


def loop_edges(vi, ls, lt, edges, nv):
    """Per loop (face corner): the index of the edge from its vertex to the next corner of its face, found among the
    mesh edges (m, 2) by their vertex pairs. The same as Blender's loop edge index, from the loops' vertex indices and
    the edges' vertices only (both read with foreach_get elsewhere in the repo)."""
    vi = np.asarray(vi, np.int64)
    ls = np.asarray(ls, np.int64)
    lt = np.asarray(lt, np.int64)
    e = np.asarray(edges, np.int64).reshape(-1, 2)
    nv = int(nv)
    if not len(vi):
        return np.zeros(0, np.int64)
    lf = np.repeat(np.arange(len(ls)), lt)
    nxt = ls[lf] + (np.arange(len(vi)) - ls[lf] + 1) % lt[lf]
    a, b = vi, vi[nxt]
    key = np.minimum(a, b) * nv + np.maximum(a, b)
    ek = np.minimum(e[:, 0], e[:, 1]) * nv + np.maximum(e[:, 0], e[:, 1])
    order = np.argsort(ek, kind="stable")
    j = np.clip(np.searchsorted(ek[order], key), 0, max(len(ek) - 1, 0))
    if not len(ek) or np.any(ek[order][j] != key):
        raise RuntimeError("loop_edges: a face side has no mesh edge (%d of %d)" % (
            int(np.sum(ek[order][j] != key)) if len(ek) else len(key), len(key)))
    return order[j]


def cap_moves(d, cap=None):
    """Moves d (n, 3) scaled down where longer than `cap` m (None: MOVE_MAX), direction kept."""
    cap = MOVE_MAX if cap is None else cap
    d = np.asarray(d, float)
    n = np.linalg.norm(d, axis=1)
    return d * np.minimum(1.0, cap / np.maximum(n, 1e-12))[:, None]


def components(nv, edges):
    """Connected component label (the smallest vertex index in it) per vertex, over the mesh edges."""
    lab = np.arange(int(nv))
    e = np.asarray(edges, np.int64).reshape(-1, 2)
    if not len(e):
        return lab
    while True:
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        new = lab.copy()
        np.minimum.at(new, e[:, 0], m)
        np.minimum.at(new, e[:, 1], m)
        new = new[new]
        if np.array_equal(new, lab):
            return lab
        lab = new


def outward_sign(co, vi, ls, fn, ar, edges):
    """Per face: +1 where its normal points out of its connected part, -1 where the part is inside out (some floating
    rocks are, world.py: recalc_face_normals over overlapping spurs). A part is inside out when the sum over its faces
    of area x normal . (face centre - the part's centre) is negative."""
    co = np.asarray(co, float)
    vi = np.asarray(vi, np.int64)
    ls = np.asarray(ls, np.int64)
    lab = components(len(co), edges)
    _u, comp_v = np.unique(lab, return_inverse=True)
    comp_v = comp_v.reshape(-1)
    nc = int(comp_v.max()) + 1 if len(comp_v) else 0
    cnt = np.bincount(comp_v, minlength=nc)
    cen = np.stack([np.bincount(comp_v, co[:, c], minlength=nc) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
    lt = np.diff(np.append(ls, len(vi)))
    lf = np.repeat(np.arange(len(ls)), lt)
    fc = np.stack([np.bincount(lf, co[vi, c], minlength=len(ls)) for c in range(3)], 1) / np.maximum(lt, 1)[:, None]
    cf = comp_v[vi[ls]]
    s = np.bincount(cf, ((fc - cen[cf]) * np.asarray(fn, float)).sum(1) * np.asarray(ar, float), minlength=nc)
    return np.where(s[cf] < 0.0, -1.0, 1.0)


def lp_width(h):
    """Filter width (m) for a vertex spacing h: LP_K x h inside LP_RANGE."""
    return np.clip(LP_K * np.asarray(h, float), LP_RANGE[0], LP_RANGE[1])


def edge_samples(co, edges, step=SAMPLE_STEP):
    """The vertices plus points every `step` m along each edge (a sheet's or a root's surface as a point cloud)."""
    co = np.asarray(co, float)
    e = np.asarray(edges, np.int64).reshape(-1, 2)
    if not len(e):
        return co.copy()
    a, b = co[e[:, 0]], co[e[:, 1]]
    n = np.maximum(np.ceil(np.linalg.norm(b - a, axis=1) / step).astype(np.int64) - 1, 0)
    if not n.sum():
        return co.copy()
    k = np.repeat(np.arange(len(e)), n)
    first = np.repeat(np.cumsum(n) - n, n)
    j = np.arange(len(k)) - first + 1
    f = (j / (n[k] + 1.0))[:, None]
    return np.concatenate([co, a[k] + (b[k] - a[k]) * f])


_VOX_OFF = 1 << 20


def _vox_keys(cells):
    c = np.asarray(cells, np.int64) + _VOX_OFF
    return (c[:, 0] << 42) | (c[:, 1] << 21) | c[:, 2]


def near_voxels(q, src, reach):
    """Per query point: may a source point lie within `reach` m of it? (voxels of size reach, the 27 around each
    source; never False when the true distance is under reach). The cheap filter before the exact distance."""
    q = np.asarray(q, float).reshape(-1, 3)
    src = np.asarray(src, float).reshape(-1, 3)
    if not len(q) or not len(src):
        return np.zeros(len(q), bool)
    cs = np.floor(src / reach).astype(np.int64)
    cs = np.unique(cs, axis=0)
    off = np.array([(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)], np.int64)
    keys = np.unique(_vox_keys((cs[:, None, :] + off[None, :, :]).reshape(-1, 3)))
    return np.isin(_vox_keys(np.floor(q / reach).astype(np.int64)), keys)


def box_dist(p, lo, hi):
    """Per point: the distance (m) to the nearest of the boxes lo, hi (0 inside one); inf without boxes. Boxes go in
    chunks of about 1.5M point x box pairs, so memory stays near 40 MB."""
    p = np.asarray(p, float).reshape(-1, 3)
    lo = np.asarray(lo, float).reshape(-1, 3)
    hi = np.asarray(hi, float).reshape(-1, 3)
    out = np.full(len(p), np.inf)
    chunk = max(1, int(1.5e6 // max(len(p), 1)))
    for s in range(0, len(lo), chunk):
        a, b = lo[s:s + chunk], hi[s:s + chunk]
        d2 = np.zeros((len(p), len(a)))
        for c in range(3):
            g = np.maximum(np.maximum(a[None, :, c] - p[:, None, c], p[:, None, c] - b[None, :, c]), 0.0)
            d2 += g * g
        out = np.minimum(out, np.sqrt(d2.min(1)))
    return out


def pin(d, fade):
    """Weight from a distance: 0 up to fade[0] m, 1 from fade[1] m (inf: 1)."""
    d = np.asarray(d, float)
    return np.where(np.isfinite(d), smoothstep(fade[0], fade[1], np.where(np.isfinite(d), d, 0.0)), 1.0)


def thick_scale(t):
    """Relief scale for rock `t` m thick behind a vertex (RELIEF_THICK)."""
    return np.clip((np.asarray(t, float) - RELIEF_THICK[0]) / (RELIEF_THICK[1] - RELIEF_THICK[0]), 0.0, 1.0)


def guard_move(m, t):
    """A signed move m (m, + outward) on rock `t` m thick: scaled by thick_scale, and an inward move kept above
    -RELIEF_THICK[3] x t."""
    m2 = np.asarray(m, float) * thick_scale(t)
    return np.where(m2 < 0.0, np.maximum(m2, -RELIEF_THICK[3] * np.asarray(t, float)), m2)


def fold_deg(fa, fb):
    """Angle in degrees between face normals fa and fb (rows)."""
    a = np.asarray(fa, float)
    b = np.asarray(fb, float)
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))


# ---- planarize ---------------------------------------------------------------------------------------------------

def planarize(p, nh, key, w, k, min_n=None, min_r=None, clip=None):
    """Per vertex: the move (n, 3) toward its block's fitted plane. p (n, 3) world positions, nh (n, 3) smoothed
    horizontal unit normals (0 where none), key (n,) block keys, w (n,) relief weights (vertices over 0.5 fit the
    plane). A block with at least min_n of them whose normals agree (mean resultant length >= min_r) fits
    s = a + b e1 + c z by least squares, s the offset along the block's mean normal, e1 across it; each vertex then
    moves k x (s_fit - s), at most `clip` m, along that normal. Other blocks: 0."""
    min_n = PLANAR_MIN_N if min_n is None else min_n
    min_r = PLANAR_MIN_R if min_r is None else min_r
    clip = PLANAR_CLIP if clip is None else clip
    p = np.asarray(p, float)
    nh = np.asarray(nh, float)
    out = np.zeros_like(p)
    if not len(p):
        return out
    uk, inv = np.unique(np.asarray(key), return_inverse=True)
    inv = inv.reshape(-1)
    m = len(uk)
    ww = (np.asarray(w, float) > 0.5).astype(float)
    cnt = np.bincount(inv, ww, minlength=m)
    sn = np.stack([np.bincount(inv, ww * nh[:, c], minlength=m) for c in range(3)], 1)
    sn[:, 2] = 0.0
    ln = np.linalg.norm(sn, axis=1)
    rlen = ln / np.maximum(cnt, 1.0)
    ok = (cnt >= min_n) & (rlen >= min_r)
    if not ok.any():
        return out
    nb = sn / np.maximum(ln, 1e-12)[:, None]
    cen = np.stack([np.bincount(inv, ww * p[:, c], minlength=m) for c in range(3)], 1) / np.maximum(cnt, 1.0)[:, None]
    d = p - cen[inv]
    nv = nb[inv]
    s = (d * nv).sum(1)
    e1 = np.stack([-nv[:, 1], nv[:, 0], np.zeros(len(p))], 1)
    a1 = (d * e1).sum(1)
    a2 = d[:, 2]
    X = np.stack([np.ones(len(p)), a1, a2], 1)
    A = np.zeros((m, 3, 3))
    bv = np.zeros((m, 3))
    for r in range(3):
        bv[:, r] = np.bincount(inv, ww * X[:, r] * s, minlength=m)
        for c in range(3):
            A[:, r, c] = np.bincount(inv, ww * X[:, r] * X[:, c], minlength=m)
    tr = np.trace(A, axis1=1, axis2=2)
    A = A + (1e-6 * np.maximum(tr, 1e-9))[:, None, None] * np.eye(3)[None]
    coef = np.linalg.solve(A, bv[:, :, None])[:, :, 0]
    fit = (coef[inv] * X).sum(1)
    mv = np.clip(k * (fit - s), -clip, clip) * ok[inv]
    return mv[:, None] * nv


# ---- karst columns -----------------------------------------------------------------------------------------------

def ring_levels(z0):
    """(the distinct ring heights of a lathe column, sorted up; each vertex's ring) from its vertices' unsheared heights
    z0: heights closer than RING_EPS are one ring (float32 positions and the rounded dip put a ring's vertices up to
    ~2 mm apart)."""
    u, inv = np.unique(np.round(np.asarray(z0, float), 4), return_inverse=True)
    if len(u) < 2:
        return u, np.zeros(len(np.atleast_1d(z0)), np.int64)
    ids = np.concatenate([[0], np.cumsum(np.diff(u) >= RING_EPS)])
    return np.bincount(ids, u) / np.bincount(ids), ids[inv.reshape(-1)]


def _ring_step(ring, theta, r, a, b, nth=72):
    """Median over the sectors both rings have of |radius of ring a - radius of ring b| (m)."""
    s = np.clip(np.floor(np.mod(theta, 2.0 * math.pi) / (2.0 * math.pi) * nth).astype(np.int64), 0, nth - 1)
    out = []
    for q in (a, b):
        m = ring == q
        c = np.bincount(s[m], minlength=nth)
        out.append((np.bincount(s[m], r[m], minlength=nth) / np.maximum(c, 1), c > 0))
    both = out[0][1] & out[1][1]
    return float(np.median(np.abs(out[0][0] - out[1][0])[both])) if both.any() else 0.0


def column_bed_tops(z0, gap=None, r=None, theta=None, step=None):
    """Bed tops of a lathe column from its vertices' unsheared heights z0 (sorted up). Runs of rings (ring_levels) each
    closer than `gap` to the next form a cluster. Without r and theta a cluster of two or more rings is a bed top at
    its middle. With them (each vertex's radius and angle), only a cluster where two neighbouring rings differ in
    radius by at least `step` m (median over the sectors) is one, at that pair's middle: the lathe's shelf pairs step
    by a shoulder or more, while an interior ring that happens to fall next to a bed's base ring does not."""
    gap = RING_PAIR_GAP if gap is None else gap
    step = RING_STEP_MIN if step is None else step
    u, ring = ring_levels(z0)
    if len(u) < 2:
        return np.zeros(0)
    close = np.diff(u) < gap
    tops = []
    k = 0
    while k < len(close):
        if not close[k]:
            k += 1
            continue
        e = k
        while e < len(close) and close[e]:
            e += 1
        if r is None or theta is None:
            tops.append(0.5 * (u[k] + u[e]))
        else:
            st = [(_ring_step(ring, np.asarray(theta, float), np.asarray(r, float), q, q + 1), q) for q in range(k, e)]
            best, q = max(st)
            if best >= step:
                tops.append(0.5 * (u[q] + u[q + 1]))
        k = e
    return np.array(tops)


def column_planes(seed, az_joint):
    """The column's eight face planes: (normal azimuths in the object's frame, rad, sorted; distance factors x the
    radius; True for a main face). Main faces follow the two joint sets (az_joint, rad, in the object's frame, both
    turned by one jitter per column); chamfers halve the angles between them."""
    dj = math.radians(COL["az_jitter"]) * (2.0 * float(hash_u(seed, 1)) - 1.0)
    a, b = az_joint[0] + dj, az_joint[1] + dj
    mains = np.sort(np.mod(np.array([a, b, a + math.pi, b + math.pi]), 2.0 * math.pi))
    nxt = np.roll(mains, -1)
    nxt[-1] += 2.0 * math.pi
    ch = np.mod(0.5 * (mains + nxt), 2.0 * math.pi)
    phi = np.empty(8)
    phi[0::2], phi[1::2] = mains, ch
    main = np.zeros(8, bool)
    main[0::2] = True
    fac = np.where(main, COL["main"], COL["chamfer"])
    fac = fac * (1.0 + COL["jitter"] * (2.0 * hash_u(seed, 10 + np.arange(8)) - 1.0))
    return phi, fac, main


def column_poly(theta, R, phi, fac):
    """The polygon's radius at angles theta for column radii R (per point), and which face (0-7) it is."""
    c = np.cos(np.asarray(theta, float)[:, None] - phi[None, :])
    dk = np.asarray(R, float)[:, None] * fac[None, :]
    val = np.where(c > COL["min_cos"], dk / np.maximum(c, 1e-6), np.inf)
    f = np.argmin(val, axis=1)
    return val[np.arange(len(f)), f], f


def envelope(theta, z0, r, nth=None, dz=None, sigma=None):
    """The column's smoothed outline: the mean radius per 360 / nth deg sector and dz m row, rows with no vertex
    filled up and down, smoothed up the column with a Gaussian of sigma m and a little round it. Returns (r_env per
    point, the outline's median radius per point's height)."""
    nth = COL_ENV["nth"] if nth is None else nth
    dz = COL_ENV["dz"] if dz is None else dz
    sigma = COL_ENV["sigma"] if sigma is None else sigma
    theta, z0, r = (np.asarray(v, float) for v in (theta, z0, r))
    th = np.mod(theta, 2.0 * math.pi) / (2.0 * math.pi) * nth
    ti = np.clip(np.floor(th).astype(np.int64), 0, nth - 1)
    zmin = float(z0.min())
    zi = np.floor((z0 - zmin) / dz).astype(np.int64)
    nz = int(zi.max()) + 1
    key = ti * nz + zi
    s = np.bincount(key, r, minlength=nth * nz).reshape(nth, nz)
    c = np.bincount(key, minlength=nth * nz).reshape(nth, nz)
    g = np.where(c > 0, s / np.maximum(c, 1), np.nan)
    rows = np.arange(nz)
    for k in range(nth):
        ok = ~np.isnan(g[k])
        if ok.any():
            g[k] = np.interp(rows, rows[ok], g[k][ok])
    empty = np.isnan(g).all(1)
    if empty.all():
        g[:] = float(np.median(r))
    elif empty.any():
        # a lathe with fewer segments than sectors (a 'mid' peak pillar has 40) leaves whole sectors empty: each is
        # filled round the column from its neighbours, row by row. The row's mean would pull the outline halfway to
        # round between every two segments, and the lobes would survive the faces at half their size
        ks = np.arange(nth)
        have = ks[~empty]
        for j in range(nz):
            g[empty, j] = np.interp(ks[empty], have, g[~empty, j], period=nth)
    m = max(1, int(math.ceil(3.0 * sigma / dz)))
    kern = np.exp(-0.5 * (np.arange(-m, m + 1) * dz / sigma) ** 2)
    kern /= kern.sum()
    pad = np.pad(g, ((0, 0), (m, m)), mode="edge")
    sm = np.zeros_like(g)
    for j, kv in enumerate(kern):
        sm += kv * pad[:, j:j + nz]
    sm = 0.25 * np.roll(sm, 1, axis=0) + 0.5 * sm + 0.25 * np.roll(sm, -1, axis=0)
    Rrow = np.median(sm, axis=0)
    # bilinear lookup: sectors wrap round, rows clamp
    tc = th - 0.5
    t0 = np.floor(tc).astype(np.int64)
    ft = tc - t0
    zc = np.clip((z0 - zmin) / dz - 0.5, 0.0, nz - 1.0)
    z0i = np.clip(np.floor(zc).astype(np.int64), 0, nz - 1)
    z1i = np.minimum(z0i + 1, nz - 1)
    fz = zc - z0i
    ta, tb = np.mod(t0, nth), np.mod(t0 + 1, nth)
    r_env = ((1 - ft) * ((1 - fz) * sm[ta, z0i] + fz * sm[ta, z1i])
             + ft * ((1 - fz) * sm[tb, z0i] + fz * sm[tb, z1i]))
    Rz = (1 - fz) * Rrow[z0i] + fz * Rrow[z1i]
    return r_env, Rz


def column_field(theta, z0, r_env, Rz, tops, seed, planes, w_theta, taps=None):
    """A column's inward move (m, <= 0) per point: the faces shave the outline (k x (min(r_env, polygon) - r_env)),
    each bed's face sits back by a hashed share of COL['block'], a few blocks are lost notches; filtered across the
    face over w_theta rad (per point) so a face corner never steps along the lattice. Bed steps stay sharp: they fall
    on the lathe's ring pairs (column_bed_tops). Clipped to COL['max_in'] and COL['rel_max'] x the radius."""
    nt = LP_TAPS[1] if taps is None else taps
    phi, fac, _main = planes
    theta = np.asarray(theta, float)
    r_env = np.asarray(r_env, float)
    Rz = np.asarray(Rz, float)
    b = np.searchsorted(np.asarray(tops, float), np.asarray(z0, float), side="right")
    w_theta = np.broadcast_to(np.asarray(w_theta, float), theta.shape)
    acc = np.zeros(len(theta))
    lo, hi = COL["lost"]
    for k in range(nt):
        th = theta + ((k + 0.5) / nt - 0.5) * w_theta
        rp, f = column_poly(th, Rz, phi, fac)
        facet = COL["k"] * (np.minimum(r_env, rp) - r_env)
        h1 = hash_u(seed, 31, b, f)
        h2 = hash_u(seed, 32, b, f)
        h3 = hash_u(seed, 33, b, f)
        acc += facet - COL["block"] * h1 - np.where(h2 < COL["lost_p"], lo + (hi - lo) * h3, 0.0)
    cap = np.minimum(COL["max_in"], COL["rel_max"] * Rz)
    return np.clip(acc / float(nt), -cap, 0.0)


# ---- the abode cliff's zones (its mesh frame: x across, y into the rock, z up) -------------------------------------

def _rect_dist(x, z, x0, x1, z0, z1):
    ex = np.maximum(np.maximum(x0 - x, x - x1), 0.0)
    ez = np.maximum(np.maximum(z0 - z, z - z1), 0.0)
    return np.hypot(ex, ez)


def abode_zone(x, y, z, top, Z, fade=None):
    """Weight 0-1 on the abode cliff: 0 on its dressed rock and the band its blend reaches (rect), on the slope cap over
    it where the cap holds the rock (cap: the vertex lies within tol m of the cap line), on the inscription panel
    (insc), in the water chute (chute) and within top[0] m of the front edge, back to 1 over `fade` m. Z holds the
    numbers sect/relief.py reads from sect.areas.abode; top is _top(x) per vertex."""
    fade = ABODE_FADE if fade is None else fade
    x, y, z, top = (np.asarray(v, float) for v in (x, y, z, top))
    x0, x1, z0, z1, grow = Z["rect"]
    w = smoothstep(grow, grow + fade, _rect_dist(x, z, x0, x1, z0, z1))
    x0, x1, z0, z1, grow = Z["insc"]
    w = w * smoothstep(grow, grow + fade, _rect_dist(x, z, x0, x1, z0, z1))
    xc, half = Z["chute"]
    w = w * smoothstep(half, half + fade, np.abs(x - xc))
    cx0, cx1, bl, br, cz1, slope, yg, tol = Z["cap"]
    wx = np.where(x < cx0, 1.0 - smoothstep(0.0, bl, cx0 - x), np.where(x > cx1, 1.0 - smoothstep(0.0, br, x - cx1), 1.0))
    cap_w = wx * smoothstep(cz1 - 1.5, cz1 - 0.5, z)
    line = yg + slope * np.maximum(0.0, z - cz1)
    w = w * (1.0 - cap_w * (1.0 - smoothstep(tol, tol + fade, line - y)))
    below = Z["top"]
    return w * smoothstep(top - below, top - below - fade, z)
