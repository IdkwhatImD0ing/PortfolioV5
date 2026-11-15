"""Offline test of the round 59 rock relief rules (sect/relief_rules.py, applied in Blender by sect/relief.py). No
Blender, no bpy. Run on the PC with

    python -P E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/test_relief_rules.py

(-P, not -I: numpy lives in the user site on this PC). Prints 'test_relief_rules ok' when every check passes.
"""
import hashlib
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import relief_rules as RR  # noqa: E402


def digest(*arrays):
    h = hashlib.sha1()
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def test_hash():
    a = RR.hash_u(7, np.arange(-500, 500), 3)
    b = RR.hash_u(7, np.arange(-500, 500), 3)
    assert np.array_equal(a, b)
    assert a.min() >= 0.0 and a.max() < 1.0
    assert 0.45 < a.mean() < 0.55, a.mean()
    assert abs(float(RR.hash_u(7, 1, 2)) - float(RR.hash_u(7, 1, 3))) > 1e-9      # neighbours differ
    assert float(RR.hash_u(7, 5)) != float(RR.hash_u(8, 5))                        # the salt counts


def test_beds():
    g1, g2 = RR.Geo(5901), RR.Geo(5901)
    assert digest(g1.z0, g1.t, g1.soft, g1.off) == digest(g2.z0, g2.t, g2.soft, g2.off)   # bit-identical re-run
    g3 = RR.Geo(5902)
    assert digest(g1.z0, g1.t) != digest(g3.z0, g3.t)
    hard, soft = g1.t[~g1.soft], g1.t[g1.soft]
    assert hard.min() >= RR.GEO_BED_T[0] - 1e-9 and hard.max() <= RR.GEO_BED_T[1] + 1e-9
    assert soft.min() >= RR.GEO_SOFT["t"][0] - 1e-9 and soft.max() <= RR.GEO_SOFT["t"][1] + 1e-9
    share = g1.soft.mean()
    assert 0.18 <= share <= 0.26, share
    assert np.all(g1.off[g1.soft] <= -RR.GEO_SOFT["recess"][0] + 1e-9)
    assert np.all(np.abs(g1.off[~g1.soft]) <= RR.GEO_HARD_OFF + 1e-9)
    assert g1.z0[0] == RR.GEO_BED_RANGE[0] and g1.z0[-1] + g1.t[-1] >= RR.GEO_BED_RANGE[1]
    assert np.allclose(np.diff(g1.z0), g1.t[:-1])                                  # beds stack with no gap


def test_field_range_and_blocks():
    g = RR.Geo()
    rng = np.random.RandomState(3)
    x, y, z = rng.uniform(-600, 700, 20000), rng.uniform(-300, 1900, 20000), rng.uniform(-100, 600, 20000)
    D, key = g.raw(x, y, z)
    assert D.min() >= RR.GEO_CLAMP[0] - 1e-9 and D.max() <= RR.GEO_CLAMP[1] + 1e-9
    assert D.min() < -1.0 and D.max() > 0.3                                     # recesses and blocks are there
    assert len(np.unique(key)) > 1000
    # two points 0.2 m apart in the middle of one block: same key, nearly the same value (the tilt is 0.06 m/m)
    found = 0
    i, ph, t = g.bed(g.zb(x, y, z))
    _ja, fa, _wa = g.joints_a(x, y)
    _jb, fb, _wb = g.joints_b(x, y, i)
    mid = (np.abs(ph - 0.5) < 0.2) & (np.abs(fa) < 0.3) & (np.abs(fb) < 0.3) & (t > 4.0)
    for k in np.nonzero(mid)[0][:200]:
        p = np.array([[x[k], y[k], z[k]], [x[k] + 0.12, y[k] + 0.1, z[k] + 0.1]])
        d2, k2 = g.raw(p[:, 0], p[:, 1], p[:, 2])
        assert k2[0] == k2[1], (p, k2)
        assert abs(d2[0] - d2[1]) < 0.05, (p, d2)
        found += 1
    assert found > 50, found
    # either side of a joint A position: different keys
    J = RR.GEO_JOINT_A
    d = math.radians(J["az"])
    n = np.array([math.cos(d), math.sin(d), 0.0])
    p0 = np.array([100.0, 400.0, 50.0])
    s = np.linspace(-40.0, 40.0, 8001)
    pts = p0[None] + s[:, None] * n[None]
    ja = g.joints_a(pts[:, 0], pts[:, 1])[0]
    cut = np.nonzero(np.diff(ja) != 0)[0]
    assert len(cut) >= 2, len(cut)
    a, b = pts[cut[0]], pts[cut[0] + 1]
    ka = g.raw(np.array([a[0], b[0]]), np.array([a[1], b[1]]), np.array([a[2], b[2]]))[1]
    assert ka[0] != ka[1]
    # joint spacing: about GEO_JOINT_A's gap, 7-22 m
    gaps = np.diff(s[cut])
    assert gaps.min() > 6.5 and gaps.max() < 23.0, (gaps.min(), gaps.max())


def test_low_pass_thin_bed():
    """A soft bed thinner than the filter is drawn shallower, not as a zigzag (attack_0's rule: nothing narrower than
    two vertex spacings)."""
    g = RR.Geo()
    g.blocks = False
    g.warp = ()
    g.kx = g.ky = 0.0
    g.z0 = np.array([-100.0, 0.0, 1.0, 50.0])
    g.t = np.array([100.0, 1.0, 49.0, 100.0])
    g.soft = np.array([False, True, False, False])
    g.off = np.array([0.0, -2.0, 0.0, 0.0])
    p = np.array([[0.0, 0.0, 0.5]])
    td = np.array([[1.0, 0.0, 0.0]])
    sharp = g.field(p, td, 0.01, 0.01)[0][0]
    wide = g.field(p, td, 2.0, 2.0)[0][0]
    assert abs(sharp + 2.0) < 1e-6, sharp
    assert -1.5 < wide < -0.9, wide                    # 1 m bed under a 2 m filter: about half its recess
    # sampled every h = 1 m with the 2 m filter, a 2 m recess never jumps by its full depth between neighbours
    zs = np.arange(-6.0, 8.0, 1.0) + 0.37
    P = np.stack([np.zeros_like(zs), np.zeros_like(zs), zs], 1)
    Dz = g.field(P, np.tile(td, (len(zs), 1)), 2.0, 2.0)[0]
    raw = g.raw(P[:, 0], P[:, 1], P[:, 2])[0]
    assert np.abs(np.diff(Dz)).max() < np.abs(np.diff(raw)).max() + 1e-9
    assert np.abs(np.diff(Dz)).max() <= 0.65 * 2.0 + 0.5      # 3 of 5 taps cross per step (+ the hard beds' grooves)


def test_planarize():
    rng = np.random.RandomState(5)
    n = 400
    u = rng.uniform(-6, 6, n)
    z = rng.uniform(0, 8, n)
    nrm = np.array([0.0, -1.0, 0.0])
    noise = 0.5 * np.sin(1.3 * u) * np.cos(0.9 * z)
    p = np.stack([u, 10.0 - noise + 0.1 * u, z], 1)     # a wall facing -y, leaning a little across, plus 0.5 m folds
    nh = np.tile(nrm, (n, 1))
    key = np.zeros(n, np.int64)
    w = np.ones(n)
    k = 0.7
    mv = RR.planarize(p, nh, key, w, k)
    s0 = (p @ nrm)
    s1 = ((p + mv) @ nrm)
    A = np.stack([np.ones(n), u, z], 1)
    r0 = s0 - A @ np.linalg.lstsq(A, s0, rcond=None)[0]
    r1 = s1 - A @ np.linalg.lstsq(A, s1, rcond=None)[0]
    ratio = r1.std() / r0.std()
    assert abs(ratio - (1.0 - k)) < 0.1 * (1.0 - k), ratio
    assert np.allclose(mv[:, 2], 0.0)                     # moves along the block's horizontal normal only
    # a block wrapped round a 90 degree corner: its normals do not agree, so it is left alone
    nh2 = np.where((u < 0)[:, None], np.array([[0.0, -1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))
    assert np.abs(RR.planarize(p, nh2, key, w, k)).max() == 0.0
    # too few vertices: left alone
    assert np.abs(RR.planarize(p[:4], nh[:4], key[:4], w[:4], k)).max() == 0.0


def test_column_bed_tops():
    tops = RR.column_bed_tops(np.array([100.0, 99.96, 99.04, 98.8, 98.55, 98.1, 96.5, 96.46, 96.36]))
    assert np.allclose(tops, [96.43, 99.98]), tops          # attack_0: one top per cluster of close rings
    hero = [100.04, 99.96, 99.8, 99.55, 99.1, 97.5, 96.04, 95.96, 95.8, 95.55]
    assert np.allclose(RR.column_bed_tops(hero), [96.0, 100.0])
    mid = [50.04, 49.94, 48.8, 46.0, 43.0, 40.04, 39.94, 38.8]
    assert np.allclose(RR.column_bed_tops(mid), [39.99, 49.99])
    # float32 positions: a ring's vertices up to ~2 mm apart are one ring, never a pair on their own
    rng = np.random.RandomState(1)
    jittered = np.concatenate([np.full(200, z) + rng.uniform(-0.002, 0.002, 200) for z in hero])
    assert np.allclose(RR.column_bed_tops(jittered), [96.0, 100.0], atol=0.003)
    flat_lip = [10.0, 9.78, 9.45, 9.05, 7.0]            # the flat top's lip rings: no bed top
    assert len(RR.column_bed_tops(flat_lip)) == 0
    # with radii: a shelf pair steps by its shoulder and is a top; an interior ring that falls 0.05 m from a bed's
    # base ring (no step) is not
    rings = [(30.04, 20.0), (29.96, 20.25), (29.0, 20.3), (25.32, 20.0), (25.3, 20.0), (24.0, 20.0)]
    th = np.linspace(0.0, 2.0 * math.pi, 64, endpoint=False)
    z0 = np.concatenate([np.full(64, z) for z, _ in rings])
    rr = np.concatenate([np.full(64, r) + 0.01 * np.sin(3 * th) for _, r in rings])
    tt = np.tile(th, len(rings))
    assert np.allclose(RR.column_bed_tops(z0), [25.31, 30.0])                     # z alone: both look like pairs
    assert np.allclose(RR.column_bed_tops(z0, r=rr, theta=tt), [30.0])            # the radii tell them apart


def test_columns():
    seed = 1234
    jA, jB = math.radians(RR.GEO_JOINT_A["az"]), math.radians(RR.GEO_JOINT_B["az"])
    planes = RR.column_planes(seed, (jA, jB))
    phi, fac, main = planes
    assert len(phi) == 8 and main.sum() == 4
    assert np.all(np.diff(phi) > 0)
    # the main faces follow the joint sets (within the column's jitter)
    for a in (jA, jB, jA + math.pi, jB + math.pi):
        d = np.abs(np.angle(np.exp(1j * (phi[main] - a))))
        assert d.min() <= math.radians(RR.COL["az_jitter"]) + 1e-9
    # the main faces are the wide ones (attack_0)
    th = np.linspace(0.0, 2.0 * math.pi, 7201)[:-1]
    R = np.full(len(th), 20.0)
    rp, f = RR.column_poly(th, R, phi, fac)
    width = np.bincount(f, minlength=8) * (2.0 * math.pi / len(th))
    assert width[main].min() > width[~main].max(), width
    # a round column of radius 20: the faces shave it, never push out, never past max_in
    z0 = np.linspace(0.0, 60.0, len(th))
    D = RR.column_field(th, z0, R, R, np.array([20.0, 40.0]), seed, planes, 0.02)
    assert D.max() <= 0.0 and D.min() >= -min(RR.COL["max_in"], RR.COL["rel_max"] * 20.0) - 1e-9
    face_mid = np.abs(np.angle(np.exp(1j * (th - phi[0])))) < 0.01
    facet = -RR.COL["k"] * (1.0 - fac[0]) * 20.0              # a main face's middle: in by about 1.9 m ...
    assert np.all(D[face_mid] <= 0.98 * facet), (D[face_mid].max(), facet)    # ... plus its block's set-back
    assert np.all(D[face_mid] >= -RR.COL["max_in"] - 1e-9)
    # the outline: lumps flattened, beds kept
    rng = np.random.RandomState(4)
    zz = rng.uniform(0.0, 80.0, 20000)
    tt = rng.uniform(0.0, 2.0 * math.pi, 20000)
    lobes = 1.2 * np.sin(3.0 * tt) * np.cos(zz / 15.0)
    beds = np.where(np.mod(zz, 7.0) < 1.0, 0.8, 0.0)
    r = 20.0 + lobes + beds
    r_env, Rz = RR.envelope(tt, zz, r)
    assert np.abs(r_env - (20.0 + lobes + 0.8 / 7.0)).max() < 0.6     # follows the lobes, not the 1 m beds
    assert np.abs(Rz - 20.1).max() < 0.5
    # a 'mid' lathe: 40 segments in 2.8 m rings leave whole sectors of the 72 empty. They are filled round the column,
    # so the outline still follows the lobes (filled with the row's mean it missed them by up to 0.75 m)
    th40 = 2.0 * math.pi * np.arange(40) / 40.0
    T, Z = np.meshgrid(th40, np.arange(0.0, 80.0, 2.8))
    T, Z = T.ravel(), Z.ravel()
    r40 = 15.0 + 1.5 * np.sin(3.0 * T)
    e40, _R40 = RR.envelope(T, Z, r40)
    mid = (Z > 15.0) & (Z < 65.0)
    assert np.abs(e40 - r40)[mid].max() < 0.25, np.abs(e40 - r40)[mid].max()


def test_mesh_helpers():
    # a chain 0-1-2-...-9 with a step: smoothing spreads it over neighbours
    e = np.stack([np.arange(9), np.arange(1, 10)], 1)
    v = np.where(np.arange(10) < 5, 0.0, 1.0)
    s = RR.mesh_smooth(v, e, iters=2)
    assert np.abs(np.diff(s)).max() < 0.6 and abs(s.sum() - v.sum()) < 0.5
    s3 = RR.mesh_smooth(np.stack([v, -v, v], 1), e, iters=2)
    assert np.allclose(s3[:, 0], s) and np.allclose(s3[:, 1], -s)
    # LP_LAMBDA is read at the call, so a KEY=value override reaches it
    keep = RR.LP_LAMBDA
    try:
        RR.LP_LAMBDA = 0.0
        assert np.array_equal(RR.mesh_smooth(v, e, iters=2), v)
    finally:
        RR.LP_LAMBDA = keep
    # loop edges from the vertex pairs: a quad and a triangle sharing the edge 1-2, edges listed in any order
    vi = np.array([0, 1, 2, 3, 2, 1, 4])
    ls, lt = np.array([0, 4]), np.array([4, 3])
    ed = np.array([[4, 1], [1, 2], [3, 0], [0, 1], [2, 3], [2, 4]])
    le = RR.loop_edges(vi, ls, lt, ed, 5)
    want = []
    for f in range(2):
        cs = vi[ls[f]:ls[f] + lt[f]]
        for k in range(lt[f]):
            a, b = sorted((cs[k], cs[(k + 1) % lt[f]]))
            want.append(next(j for j, (p, q) in enumerate(ed) if sorted((p, q)) == [a, b]))
    assert np.array_equal(le, want), (le, want)
    assert np.array_equal(np.bincount(le, minlength=len(ed)), [1, 2, 1, 1, 1, 1])     # the shared edge has two loops
    # the whole move is capped, direction kept
    dm = RR.cap_moves(np.array([[4.0, 0.0, 3.0], [0.0, -1.0, 0.0], [0.0, 0.0, 0.0]]), 3.0)
    assert np.allclose(dm, [[2.4, 0.0, 1.8], [0.0, -1.0, 0.0], [0.0, 0.0, 0.0]])
    co = np.array([[0, 0, 0], [0, 0, 0.8], [0.8, 0, 0], [0.8, 0, 0.8]], float)
    ed = np.array([[0, 1], [0, 2], [1, 3], [2, 3]])
    hz, ht = RR.vertex_spacing(co, ed, np.tile([1.0, 0.0, 0.0], (4, 1)))
    assert np.allclose(hz, 0.8) and np.allclose(ht, 0.8)
    assert np.allclose(RR.lp_width([0.1, 0.83, 10.0]), [0.5, 1.66, 6.0])
    pts = RR.edge_samples(np.array([[0, 0, 0], [2.0, 0, 0]]), np.array([[0, 1]]), 0.5)
    assert len(pts) == 5 and np.allclose(np.sort(pts[:, 0]), [0, 0.5, 1.0, 1.5, 2.0])
    # two cubes, the second inside out: outward_sign flips only its faces
    cube = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]   # outward
    co = np.concatenate([cube, cube + [5.0, 0, 0]])
    faces = quads + [tuple(v + 8 for v in q[::-1]) for q in quads]                                # second inward
    vi = np.array([v for f in faces for v in f])
    ls = np.arange(0, len(vi), 4)
    fn, ar = [], []
    for f in faces:
        p = co[list(f)]
        c = 0.5 * (np.cross(p[1] - p[0], p[2] - p[0]) + np.cross(p[2] - p[0], p[3] - p[0]))
        fn.append(c / np.linalg.norm(c))
        ar.append(np.linalg.norm(c))
    edges = np.array(sorted({(min(f[k], f[(k + 1) % 4]), max(f[k], f[(k + 1) % 4])) for f in faces for k in range(4)}))
    assert len(np.unique(RR.components(len(co), edges))) == 2
    sg = RR.outward_sign(co, vi, ls, np.array(fn), np.array(ar), edges)
    assert np.all(sg[:6] == 1.0) and np.all(sg[6:] == -1.0), sg


def test_pins():
    rng = np.random.RandomState(9)
    src = rng.uniform(0, 50, (300, 3))
    q = rng.uniform(-10, 60, (3000, 3))
    true = np.sqrt(((q[:, None] - src[None]) ** 2).sum(2)).min(1)
    m = RR.near_voxels(q, src, 5.0)
    assert np.all(m[true < 5.0])                           # never misses a near one
    assert m.mean() < 1.0
    lo = rng.uniform(0, 40, (50, 3))
    hi = lo + rng.uniform(0.5, 8, (50, 3))
    d = RR.box_dist(q, lo, hi)
    g = np.maximum(np.maximum(lo[None] - q[:, None], q[:, None] - hi[None]), 0.0)
    assert np.allclose(d, np.sqrt((g * g).sum(2)).min(1))
    assert np.all(np.isinf(RR.box_dist(q[:3], np.zeros((0, 3)), np.zeros((0, 3)))))
    w = RR.pin(np.array([0.0, 2.5, 5.0, 10.0, np.inf]), RR.PIN_VEG)
    assert w[0] == 0.0 and w[1] == 0.0 and w[2] == 1.0 and w[3] == 1.0 and w[4] == 1.0
    assert np.allclose(RR.thick_scale([0.2, 0.5, 6.0, 9.0]), [0.0, 0.0, 1.0, 1.0])
    gm = RR.guard_move(np.array([-3.0, -3.0, 0.5, -1.0]), np.array([8.0, 2.0, 0.4, 0.5]))
    assert gm[0] == -3.0 and -0.8 - 1e-9 <= gm[1] < 0.0 and gm[2] == 0.0 and gm[3] == 0.0
    assert np.allclose(RR.fold_deg(np.array([[0, 0, 1.0]]), np.array([[0, 1.0, 0]])), 90.0)


def test_abode_zone():
    Z = dict(rect=(-16.0, 10.0, -2.0, 17.0, 5.0), insc=(-30.5, -23.5, 18.5, 41.0, 3.0), chute=(15.0, 6.5),
             cap=(-16.0, 8.5, 5.0, 2.5, 17.0, 0.25, 26.0, 1.0), top=1.5)
    x = np.array([-8.0, -8.0, -27.0, 15.0, -40.0, 30.0, -40.0, 0.0])
    z = np.array([9.0, 25.0, 30.0, 30.0, 30.0, 30.0, 59.0, 30.0])
    y = np.array([26.0, 28.0, 30.0, 30.0, 26.0, 20.0, 30.0, 20.0])
    top = np.full(8, 60.0)
    w = RR.abode_zone(x, y, z, top, Z)
    assert w[0] == 0.0          # the dressed rock round the gate
    assert w[1] == 0.0          # on the slope cap (y at its line)
    assert w[2] == 0.0          # the inscription panel
    assert w[3] == 0.0          # the water chute
    assert w[4] == 1.0          # plain cliff, far from all of them
    assert w[5] == 1.0
    assert w[6] == 0.0          # the front edge
    assert w[7] == 1.0          # over the cap but well in front of its line: natural rock, relieved


def _constants(path, names):
    """Module-level constants of a file that imports bpy (so it cannot be imported here), read from its source:
    literals, dict(...) calls and re.compile(<literal>) (as its pattern)."""
    import ast
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    def lit(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
            return {kw.arg: lit(kw.value) for kw in node.keywords}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "compile":
            return lit(node.args[0])
        return ast.literal_eval(node)

    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in names:
                out[node.targets[0].id] = lit(node.value)
    return out


def test_wiring():
    """relief.py, materials.py and bake_web.py agree on the attribute, the objects and the floor kinds."""
    import re
    sect = os.path.join(ROOT, "sect")
    rf = _constants(os.path.join(sect, "relief.py"), {"GEO_ATTR", "RELIEF_OWNER_RE", "COLUMN_RE", "CLIFF_RE",
                                                       "RELIEF_MAT", "ROOT_RE"})
    mt = _constants(os.path.join(sect, "lib", "materials.py"), {"ROCK_GEO_ATTR"})
    bw = _constants(os.path.join(sect, "bake_web.py"), {"COPY_ATTRS", "RELIEF_FLOORS", "RELIEF"})
    assert rf["GEO_ATTR"] == mt["ROCK_GEO_ATTR"] == "geo_w"
    assert "geo_w" in bw["COPY_ATTRS"]
    assert set(bw["RELIEF_FLOORS"]) == {"column", "island", "cliff"} and bw["RELIEF"] is False   # off: rock-r59.md
    assert rf["RELIEF_MAT"] == "rock_cliff"
    own, col, cliff, root = (re.compile(rf[k]) for k in ("RELIEF_OWNER_RE", "COLUMN_RE", "CLIFF_RE", "ROOT_RE"))
    for nm in ("abode.cliff", "world.peak.012", "abode.pinnacle", "abode.pinnacle.001", "summit.condor_crag",
               "arena.island", "scenery.island", "scenery.island.004", "world.islet", "world.islet.017"):
        assert own.match(nm), nm
    for nm in ("world.range", "world.roots", "arena.islet.003", "scenery.island.roots.003", "summit.condor_crag_rock",
               "gate.stair_ridge", "world.backdrop", "abode.cliff.001", "world.peak.012.fringe"):
        assert not own.match(nm), nm
    assert col.match("world.peak.001") and col.match("abode.pinnacle.001") and col.match("summit.condor_crag")
    assert not col.match("arena.island") and cliff.match("abode.cliff") and not cliff.match("world.peak.001")
    for nm in ("scenery.island.roots", "scenery.island.roots.003", "arena.root", "arena.root.012", "world.roots"):
        assert root.search(nm), nm
    for nm in ("arena.island", "abode.cliff", "nature.proto.pine.v0.hero", "forge.rooftop"):
        assert not root.search(nm), nm
    with open(os.path.join(sect, "relief.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert '"edge_index"' not in src and "RR.loop_edges(" in src     # only foreach_get names the repo already reads
    assert "RR.cap_moves(" in src


def main():
    test_wiring()
    test_hash()
    test_beds()
    test_field_range_and_blocks()
    test_low_pass_thin_bed()
    test_planarize()
    test_column_bed_tops()
    test_columns()
    test_mesh_helpers()
    test_pins()
    test_abode_zone()
    print("test_relief_rules ok")


if __name__ == "__main__":
    main()
