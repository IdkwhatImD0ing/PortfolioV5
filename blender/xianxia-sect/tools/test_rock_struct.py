"""Offline test of the round 59 rock structure's maths (sect/lib/rock_struct.py, the twin of materials._rock_r59's
node graph). No Blender, no bpy. Run on the PC with

    python -P E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/test_rock_struct.py

(-P, not -I: numpy lives in the user site on this PC). Prints 'test_rock_struct ok' when every check passes.
"""
import ast
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.lib import rock_struct as RS  # noqa: E402

MATERIALS = os.path.join(ROOT, "sect", "lib", "materials.py")


def noise2(u, v):
    """A smooth 0-1 stand-in for Blender's Noise 2D (slope under 0.7 per unit)."""
    return 0.5 + 0.25 * np.sin(1.7 * u + 0.3) * np.sin(2.3 * v + 1.1) + 0.2 * np.sin(0.9 * u + 1.9 * v)


def noise1(w):
    """Two smooth 0-1 channels, a stand-in for Blender's Noise 1D Color."""
    return 0.5 + 0.4 * np.sin(1.3 * w + 0.7), 0.5 + 0.4 * np.sin(1.1 * w + 2.9)


def hash01(i, seed):
    """A per-bed random value 0-1 (Blender's White Noise in the graph)."""
    h = np.sin(np.asarray(i, float) * 12.9898 + seed * 78.233) * 43758.5453
    return h - np.floor(h)


def _literal(node):
    """A Python literal, with dict(k=v, ...) calls (materials.py's style) read as dicts, nested too."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
        return {kw.arg: _literal(kw.value) for kw in node.keywords}
    return ast.literal_eval(node)


def materials_constants():
    """ROCK_* constants of materials.py read from its source (it imports bpy, so it cannot be imported here)."""
    with open(MATERIALS, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if not name.startswith("ROCK_"):
            continue
        try:
            out[name] = _literal(node.value)
        except ValueError:
            continue
    return out


def test_constants_match_materials():
    c = materials_constants()
    for name, twin in (("ROCK_BED", RS.BED), ("ROCK_JOINT", RS.JOINT)):
        assert name in c, "materials.py has no %s" % name
        assert c[name] == twin, (name, c[name], twin)
    assert tuple(c["ROCK_GEO_FADE"]) == RS.GEO_FADE, c["ROCK_GEO_FADE"]
    assert tuple(tuple(h) for h in c["ROCK_BED_HARM"]) == RS.HARM, c["ROCK_BED_HARM"]
    for tag in ("nature_rock_small", "forge_tomb_rock", "forge_cairn_rock", "flute_qingshi"):
        assert c["ROCK_STRUCT_VARIANTS"][tag]["bed"] == 0.0, tag       # beds off on the small rocks
    assert "nature_top_radius" in c["ROCK_FLAT_PROPS"] and c["ROCK_GEO_ATTR"] == "geo_w"
    assert c.get("ROCK_STRUCT") is False, "ROCK_STRUCT is off until it passes a look review (rock-r59.md)"
    # rollback keeps the old graph's scan constants the page's tests parse
    assert c["ROCK_SCAN_MIX"] == 0.6 and c["ROCK_SCAN_SHARP"] == 4.0
    assert c["ROCK_SCANS"]["marble_cliff_06"]["tile"] == (8.14, 8.14)
    # round 60: rock_cliff reads the derived tile mtn_cliff at marble's tile (the page's detail.ts ROCK_SCAN.tileM)
    assert c["ROCK_SCANS"]["mtn_cliff"]["tile"] == (8.14, 8.14) and c["ROCK_SCANS"]["mtn_cliff"]["relief"] == 0.3


def test_beds():
    lo, hi = RS.thickness_range()
    assert 1.80 < lo < 1.84 and 5.58 < hi < 5.62, (lo, hi)
    z = np.linspace(-200.0, 400.0, 200001)
    for x, y in ((0.0, 0.0), (125.0, 765.0), (-150.0, 625.0), (185.0, 1335.0)):
        t, i, f, thk = RS.bed_world(np.full_like(z, x), np.full_like(z, y), z, noise2)
        assert np.all(np.diff(t) > 0.0), "t runs backward at (%s, %s)" % (x, y)
        assert thk.min() >= 1.80 and thk.max() <= 5.62, (thk.min(), thk.max())
        assert np.all((f >= 0.0) & (f < 1.0))
        mean = (z[-1] - z[0]) / (t[-1] - t[0])
        assert abs(mean / RS.BED["m"] - 1.0) < 0.05, mean
        # beds as the reader sees them: from one boundary to the next, 1.8 to 5.6 m, about 2.75 on average
        edges = z[1:][np.diff(i) > 0]
        th = np.diff(edges)
        assert th.min() > 1.7 and th.max() < 5.8, (th.min(), th.max())
    # beds dip and wander but stay level-ish: the same bed boundary 50 m across moves by under 6 m
    zz = np.linspace(0.0, 30.0, 30001)
    a = RS.bed_world(np.zeros_like(zz), np.zeros_like(zz), zz, noise2)[0]
    b = RS.bed_world(np.full_like(zz, 50.0), np.zeros_like(zz), zz, noise2)[0]
    k = np.floor(a[15000]) + 1.0
    za, zb = zz[np.argmax(a >= k)], zz[np.argmax(b >= k)]
    assert abs(za - zb) < 6.0, (za, zb)


def test_hard_share():
    rng = np.random.default_rng(5)
    hard, P = RS.protrusion(rng.uniform(size=10000), rng.uniform(size=10000))
    assert abs(hard.mean() - RS.BED["hard"]) <= 0.02, hard.mean()
    lo, hi = RS.BED["hard_out"]
    assert np.all(P[hard > 0] >= lo) and np.all(P[hard > 0] <= lo + hi)
    assert np.all(np.abs(P[hard == 0]) <= RS.BED["soft_out"])


def test_profile_continuity():
    rng = np.random.default_rng(7)
    lo, hi = RS.thickness_range()
    n = 1000
    P = RS.protrusion(rng.uniform(size=(3, n)), rng.uniform(size=(3, n)))[1]
    t1, t2 = rng.uniform(lo, hi, n), rng.uniform(lo, hi, n)
    top = RS.bed_profile(np.full(n, 1.0 - 1e-9), t1, P[0], P[1])
    bot = RS.bed_profile(np.zeros(n), t2, P[1], P[2])
    assert np.max(np.abs(top["h"] - bot["h"])) < 1e-6, np.max(np.abs(top["h"] - bot["h"]))
    for k in ("ledge", "overhang"):
        assert np.max(top[k]) < 1e-6 and np.max(bot[k]) < 1e-6, k
    # the undercut and the lip bands start inside the bed even in the thinnest one
    e = min(RS.BED["edge"] / lo, RS.BED["edge_max"])
    assert 1.0 - e - RS.BED["under_w"] / lo > 0.0 and 1.0 - e - RS.BED["overhang_w"] / lo > 0.0
    # the eased tone: the top of a bed takes the next bed's value
    c = rng.uniform(size=(2, n))
    assert np.max(np.abs(RS.eased(c[0], c[1], np.full(n, 1.0)) - c[1])) < 1e-12
    assert np.max(np.abs(RS.eased(c[0], c[1], np.zeros(n)) - c[0])) < 1e-12


def column(x, y, z):
    """Height, tone and masks of the bed structure up a vertical line, as the graph computes them."""
    t, i, f, thk = RS.bed_world(np.full_like(z, x), np.full_like(z, y), z, noise2)
    _, P = RS.protrusion(hash01(i, 1), hash01(i, 2))
    hard_hi, P_hi = RS.protrusion(hash01(i + 1, 1), hash01(i + 1, 2))
    prof = RS.bed_profile(f, thk, P, P_hi)
    tone = RS.BED["tone"] * (2.0 * RS.eased(hash01(i, 3), hash01(i + 1, 3), f) - 1.0)
    return prof, tone, i


def test_column_has_no_steps():
    """No step anywhere up a wall: a height step would bake as a one-texel hairline (attack_2)."""
    dz = 1e-3
    z = np.arange(20.0, 120.0, dz)
    worst = 0.0
    for x, y in ((0.0, 0.0), (-95.0, 185.0), (5.0, 905.0)):
        prof, tone, i = column(x, y, z)
        slope = np.abs(np.diff(prof["h"])) / dz
        worst = max(worst, float(slope.max()))
        assert slope.max() < 3.0, (x, y, slope.max())
        assert np.abs(np.diff(tone)).max() < 0.002, np.abs(np.diff(tone)).max()
        for k in ("ledge", "overhang"):
            assert np.abs(np.diff(prof[k])).max() < 0.02, (k, np.abs(np.diff(prof[k])).max())
        assert len(np.unique(i)) > 20                  # many bed boundaries were crossed
        assert (prof["ledge"] > 0.5).any() and (prof["overhang"] > 0.5).any()
    assert worst > 0.5                                 # the ledges are there (not flattened by a mistake)


def test_joints():
    cell, width, depth = RS.joint_scale(2.5)
    assert (cell, width, depth) == (12.0, 0.6, 0.35)
    c2, w2, d2 = RS.joint_scale(0.45)                  # nature_rock_small: no fixed minimum width (attack_2)
    assert abs(c2 - 2.16) < 1e-9 and abs(w2 - 0.108) < 1e-9 and abs(d2 - 0.063) < 1e-9
    dx = 1e-3
    x = np.arange(0.0, 60.0, dx)
    qx, qy = RS.wiggle(x, np.full_like(x, 3.0), np.full_like(x, 40.0), noise1)
    e = RS.voronoi_edge(qx / cell, qy / cell) * cell
    g, h = RS.joint_groove(e, width, depth)
    assert h.min() >= -depth - 1e-12 and h.max() <= 0.0
    assert (h < -0.9 * depth).any() and (h == 0.0).any()   # grooves crossed, and plain rock between them
    assert np.abs(np.diff(h)).max() / dx < 2.0, np.abs(np.diff(h)).max() / dx
    # flat tops get none; walls all of it; the relief steps aside where geo_w is set
    assert RS.steep_mask(0.95) == 0.0 and RS.steep_mask(0.0) == 1.0
    # the beds: none on a 45 degree slope (|nz| 0.71), whole on a wall leaning 20 degrees (|nz| 0.34)
    assert RS.bed_steep_mask(0.71) == 0.0 and RS.bed_steep_mask(0.34) == 1.0
    assert 0.0 < RS.bed_steep_mask(0.5) < 1.0
    for gap in (RS.BED["gap"], RS.JOINT["gap"]):
        assert RS.gap_mask(0.0, gap) == gap[3] and RS.gap_mask(1.0, gap) == 1.0
        assert gap[3] < RS.gap_mask(0.5 * (gap[1] + gap[2]), gap) < 1.0
    assert RS.fade_geo(0.0) == 1.0 and RS.fade_geo(0.25) == 0.0 and 0.0 < RS.fade_geo(0.1) < 1.0
    # struct_height: beds off (pillars, boulders) leaves the joints only; both off leaves nothing
    hb = np.array([0.4, -0.1])
    hj = np.array([-0.2, 0.0])
    assert np.allclose(RS.struct_height(hb, hj, 1.0, 0.0, 1.0), hj)
    assert np.allclose(RS.struct_height(hb, hj, 1.0, 0.0, 0.0), 0.0)


def main():
    test_constants_match_materials()
    test_beds()
    test_hard_share()
    test_profile_continuity()
    test_column_has_no_steps()
    test_joints()
    print("test_rock_struct ok")


if __name__ == "__main__":
    main()
