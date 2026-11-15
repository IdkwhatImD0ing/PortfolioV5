"""Offline test of sect/bake_rules.py's round 59 rock floor rules (no Blender, no bpy). Run on the PC with

    python -P E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/test_bake_rules.py

(-P, not -I: numpy lives in the user site on this PC). Prints 'test_bake_rules ok' when every check passes.
"""
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_rules as BR  # noqa: E402

EDGES = (0.0, 30.0, 60.0, 120.0, 250.0, 400.0)   # bake_web.ROCK_FLOOR_BINS
TAN_V = 0.3165                                   # the film's tan of half the vertical field of view
ASPECT = 768.0 / 360.0                           # export_web.DEPTH_RES


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def test_floor_bins():
    d = [0.0, 29.9, 30.0, 59.0, 60.0, 119.0, 120.0, 249.0, 250.0, 399.0, 400.0, np.inf, np.nan, -1.0]
    k = BR.floor_bins(d, EDGES)
    assert k.tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, -1, -1, -1, -1], k.tolist()
    assert BR.floor_bins([5.0], (0.0,)).tolist() == [-1]


def grid(n):
    """An n x n grid of quads: (vertex positions, corner vertices, loop starts)."""
    co = np.array([(x, y, 0.0) for y in range(n + 1) for x in range(n + 1)], float)
    vi, ls = [], []
    for y in range(n):
        for x in range(n):
            a = y * (n + 1) + x
            ls.append(len(vi))
            vi += [a, a + 1, a + n + 2, a + n + 1]
    return co, np.array(vi), np.array(ls)


def test_grow_faces():
    co, vi, ls = grid(5)
    m = np.zeros(25, bool)
    m[12] = True                                  # the middle face
    g = BR.grow_faces(vi, ls, m, len(co))
    assert int(g.sum()) == 9, int(g.sum())        # itself and its 8 neighbours
    assert g[6] and g[8] and g[16] and g[18] and not g[0] and not g[24]
    m2 = np.zeros(25, bool)
    m2[0] = True                                  # a corner face
    assert int(BR.grow_faces(vi, ls, m2).sum()) == 4
    assert int(BR.grow_faces(vi, ls, np.zeros(25, bool)).sum()) == 0


def camera(pos, fwd):
    """4x4 world matrix of a level camera at pos looking along fwd (Blender cameras look down their -Z)."""
    f = np.asarray(fwd, float) / np.linalg.norm(fwd)
    up = np.array([0.0, 0.0, 1.0])
    x = np.cross(f, up)
    x /= np.linalg.norm(x)
    y = np.cross(x, f)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, -f, pos
    return M


def test_yaw_and_facing():
    M = camera((10.0, 20.0, 5.0), (0.0, 1.0, 0.0))
    Y = BR.yaw_matrix(M, 90.0)
    assert np.allclose(Y[:3, 3], M[:3, 3])
    assert np.allclose(-Y[:3, 2], (-1.0, 0.0, 0.0)), -Y[:3, 2]      # +y turned 90 deg left is -x
    assert np.allclose(-BR.yaw_matrix(M, -60.0)[:3, 2], (math.sin(math.radians(60)), 0.5, 0.0))
    C = camera((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    side = np.array([100.0, 50.0, 0.0])
    cen = np.array([[0.0, 50.0, 0.0], [0.0, 50.0, 0.0], [0.0, -50.0, 0.0], side])
    nrm = np.array([[0.0, -1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 0.0], -side / np.linalg.norm(side)])
    d = BR.facing_dmin(cen, nrm, [C], TAN_V, ASPECT)
    assert close(d[0], 50.0) and np.isinf(d[1]) and np.isinf(d[2]) and np.isinf(d[3]), d
    d3 = BR.facing_dmin(cen, nrm, [C, BR.yaw_matrix(C, 60.0), BR.yaw_matrix(C, -60.0)], TAN_V, ASPECT)
    assert close(d3[3], float(np.linalg.norm(side))), d3                   # the turned view sees it
    assert close(d3[0], 50.0) and np.isinf(d3[1]) and np.isinf(d3[2])
    # the y margin: 1.5 lets a face 0.44 NDC under the frame edge in (formation's -8 deg pitch)
    lowc = np.array([[0.0, 100.0, -100.0 * TAN_V * 1.4]])
    assert np.isfinite(BR.facing_dmin(lowc, [[0.0, -1.0, 0.0]], [C], TAN_V, ASPECT, ndc=(1.3, 1.5))[0])
    assert np.isinf(BR.facing_dmin(lowc, [[0.0, -1.0, 0.0]], [C], TAN_V, ASPECT, ndc=(1.3, 1.3))[0])


def case_binding():
    """Five parts, one a bin, under a budget that binds: today's scale 0.5, the rest kept at 0.93 x 0.5."""
    limit = 1.0e7
    area = np.array([1000.0, 2000.0, 10000.0, 3000.0, 3000.0])
    base = np.full(5, 4.0)
    want = np.array([24.0, 12.0, 8.0, 5.0, 3.0])
    t_all = 4.0e7
    t_rest = t_all - float((area * base ** 2).sum())
    return limit, area, base, want, t_rest, t_all


def test_reserve_binding():
    limit, area, base, want, t_rest, t_all = case_binding()
    g_today = math.sqrt(limit / t_all)
    g_min = 0.93 * g_today
    rho, g, used, info = BR.floor_reserve([0, 1, 2, 3, 4], area, want, base, t_rest, limit, g_min, g_ref=g_today)
    assert rho[0] == 24.0 and rho[1] == 12.0, rho                # bins 0 and 1 whole
    assert 1.05 * g_today * 4.0 < rho[2] < 8.0, rho              # bin 2 scaled
    assert rho[3] == 0.0 and rho[4] == 0.0, rho                  # bins 3 and 4 dropped
    assert close(g, g_min), (g, g_min)                           # the rest at exactly g_min
    assert used <= limit + 1e-6
    t_r = t_all - float((area[rho > 0] * base[rho > 0] ** 2).sum())
    assert close(limit - used, g * g * t_r, 1e-7)                # the budget is spent, not exceeded
    json.dumps(info)
    for v in info.values():
        assert type(v) in (int, float), (v, type(v))
    # the order of the parts does not matter: nearest bin first whatever the list order
    p = [4, 2, 0, 3, 1]
    rho2, g2, used2, _ = BR.floor_reserve(np.array([0, 1, 2, 3, 4])[p], area[p], want[p], base[p], t_rest, limit,
                                          g_min, g_ref=g_today)
    assert np.allclose(rho2, rho[p]) and close(g2, g) and close(used2, used, 1e-7)


def test_reserve_room():
    """A budget with room to spare: every part gets its want and the rest keeps scale 1."""
    area = np.array([500.0, 800.0, 900.0])
    base = np.array([10.0, 5.0, 3.0])
    want = np.array([24.0, 12.0, 4.0])
    rho, g, used, info = BR.floor_reserve([0, 2, 4], area, want, base, 1.0e6, 1.0e8, 0.93, g_ref=1.0)
    assert np.allclose(rho, want) and g == 1.0, (rho, g)
    assert close(used, float((area * want ** 2).sum()))
    assert info["floor"] == 3


def test_reserve_keep_and_none():
    limit, area, base, want, t_rest, t_all = case_binding()
    g_today = math.sqrt(limit / t_all)
    # a part that would gain under 5 % over today is no candidate
    rho, g, used, _ = BR.floor_reserve([0], [1000.0], [1.04 * g_today * 4.0], [4.0], t_all - 16000.0, limit,
                                       0.93 * g_today, g_ref=g_today)
    assert rho[0] == 0.0 and used == 0.0 and close(g, g_today, 1e-7), (rho, g)
    # no room at all (g_min = today's scale): no floor, the rest at today's scale
    rho, g, used, _ = BR.floor_reserve([0, 1, 2, 3, 4], area, want, base, t_rest, limit, g_today, g_ref=g_today)
    assert not rho.any() and used == 0.0 and close(g, g_today, 1e-7)
    # a much bigger budget (--rock-floor-units): the rest reaches scale 1, so a part wanting 3 against a base of
    # 4 is no gain any more and goes back to the rest; the near parts stay
    rho, g, used, _ = BR.floor_reserve([0, 1, 2, 3, 4], area, want, base, t_rest, 1.0e9, 0.93 * g_today,
                                       g_ref=g_today)
    assert g == 1.0 and rho[0] == 24.0 and rho[4] == 0.0, (rho, g)
    assert BR.floor_reserve([], [], [], [], 1e6, 1e7, 0.5)[2] == 0.0


def test_reserve_random():
    """Random chunks: the budget holds, the rest never drops under g_min, and a scaled bin has no floor past it."""
    rng = np.random.default_rng(59)
    for _ in range(300):
        n = int(rng.integers(1, 30))
        bins = rng.integers(0, 5, n)
        area = rng.uniform(10.0, 2.0e4, n)
        base = rng.uniform(1.0, 40.0, n)
        want = np.minimum(1130.0 / np.array(EDGES)[bins + 1] * rng.uniform(1.0, 2.0, n), 24.0)
        t_rest = float(rng.uniform(1e5, 5e7))
        t_all = t_rest + float((area * base ** 2).sum())
        limit = float(rng.uniform(2e6, 3e7))
        g_today = min(1.0, math.sqrt(limit / t_all))
        g_min = 0.93 * g_today
        rho, g, used, info = BR.floor_reserve(bins, area, want, base, t_rest, limit, g_min, g_ref=g_today)
        assert used <= limit * (1.0 + 1e-9) + 1e-6, (used, limit)
        assert g >= g_min * (1.0 - 1e-9), (g, g_min)
        assert g <= g_today * (1.0 + 1e-9), (g, g_today)
        on = rho > 0
        assert np.all(rho[on] >= 1.05 * g_today * base[on] * (1.0 - 1e-9))
        assert np.all(rho <= want * (1.0 + 1e-12))
        scaled = on & (rho < want * (1.0 - 1e-9))
        if scaled.any():
            k = int(bins[scaled].min())
            assert not (on & (bins > k)).any(), "a floor past a scaled bin"
            cand = want > 1.05 * g_today * base
            assert np.all(rho[cand & (bins < k)] == want[cand & (bins < k)]), "a nearer bin was cut"
        json.dumps(info)


def test_groups_refit():
    cap = 100.0
    # in order: 60 | 50, 45 | 30 -> three groups, the last 30 % of cap (no spill merge)
    d = [60.0, 50.0, 45.0, 30.0]
    g = BR.greedy_groups(d, cap)
    assert g == [[0], [1, 2], [3]], g
    # a small last group goes into the one before
    assert BR.greedy_groups([60.0, 50.0, 45.0, 10.0], cap) == [[0], [1, 2, 3]]
    assert BR.greedy_groups([], cap) == [] and BR.greedy_groups([500.0], cap) == [[0]]
    # refit to two groups: the 30 fits the first group's 40 of room, nothing forced
    n, info = BR.refit_groups(g, d, cap, 2)
    assert sorted(sorted(x) for x in n) == [[0, 3], [1, 2]] and info["forced"] == 0 and info["moved"] == 1, (n, info)
    assert info["over"] <= 1.0
    # nothing fits: forced into the group with the most room, which goes past cap
    d2 = [90.0, 95.0, 30.0]
    n2, info2 = BR.refit_groups(BR.greedy_groups(d2, cap), d2, cap, 2)
    assert len(n2) == 2 and info2["forced"] == 1 and close(info2["over"], 1.2, 1e-6), (n2, info2)
    assert sorted(i for x in n2 for i in x) == [0, 1, 2]
    # already few enough: untouched
    n3, info3 = BR.refit_groups(g, d, cap, 3)
    assert n3 == g and info3["moved"] == 0 and info3["forced"] == 0
    # random: every item kept once, the count reached, no group past cap unless something was forced
    rng = np.random.RandomState(4)
    for _ in range(200):
        dd = rng.uniform(1.0, 40.0, size=rng.randint(3, 40)).tolist()
        gg = BR.greedy_groups(dd, cap)
        if len(gg) < 2:
            continue
        nn, ii = BR.refit_groups(gg, dd, cap, len(gg) - 1)
        assert len(nn) == len(gg) - 1
        assert sorted(i for x in nn for i in x) == list(range(len(dd)))
        if ii["forced"] == 0:
            assert max(sum(dd[i] for i in x) for x in nn) <= cap + 1e-9


def main():
    test_floor_bins()
    test_grow_faces()
    test_yaw_and_facing()
    test_reserve_binding()
    test_reserve_room()
    test_reserve_keep_and_none()
    test_reserve_random()
    test_groups_refit()
    print("test_bake_rules ok")


if __name__ == "__main__":
    main()
