"""Tests for walkcheck.analyse() on synthetic grids (no Blender needed).

Run:  python -I .claude/skills/sect-architecture/scripts/test_walkcheck.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import walkcheck as W  # noqa: E402

STEP = 0.5


def rect(cells, x0, x1, y0, y1, z, owner, skip=None):
    """Fill cells for x0 <= x <= x1, y0 <= y <= y1 (metres). z may be a function of (x, y)."""
    for i in range(round(x0 / STEP), round(x1 / STEP) + 1):
        for j in range(round(y0 / STEP), round(y1 / STEP) + 1):
            if skip and skip(i, j):
                continue
            zz = z(i * STEP, j * STEP) if callable(z) else z
            cells[(i, j)] = [(zz, owner)]


def scene(stair_riser):
    c = {}
    rect(c, 0, 20, 0, 20, 0.0, "gate.plaza")                                    # start plaza
    rect(c, 4, 12, 14, 20, 1.5, "gate.hall.platform")                           # hall platform
    rect(c, 7, 9, 11, 13.5, lambda x, y: 0.25 + (y - 11) / STEP * 0.25, "gate.hall.stairs")
    # plank bridge east, every third plank row missing (gaps of 0.5 m)
    rect(c, 20.5, 35, 9, 11, 0.0, "world.link.gate_mirror.bridge.deck", skip=lambda i, j: i % 3 == 0)
    rect(c, 35.5, 45, 5, 15, 0.0, "mirror.plaza")
    rect(c, 39, 41, 15.5, 25, 0.0, "mirror.walkway")                            # dead end in the air
    rect(c, 43, 44, -5, 4.5, 0.0, "mirror.view.walkway")                        # ends at a viewpoint
    for k in range(4):                                                          # stones 1.7 m up per hop
        x = 47 + k * 3.5
        rect(c, x, x + 1.5, 9, 10.5, 1.7 * (k + 1), "world.link.mirror_arena.stone.%03d" % (k + 1))
    rect(c, 40, 46, 40, 46, 5.0, "mission.hall.platform")                       # hall with no way in
    # tall-riser stairway from the gate plaza going south: 1 m treads (2 cells), riser stair_riser
    rect(c, 9, 11, -10, -0.5, lambda x, y: -stair_riser * (int((-y - 0.01) // 1.0) + 1),
         "world.link.gate_south.stairs")
    rect(c, 5, 15, -20, -10.5, -stair_riser * 10, "gate.lower_landing")
    return c


DOORS = [("gate.hall.door0", 8.0, 17.0, 1.5, 0.0, -1.0),
         ("cliff.hall.door0", 30.0, 30.0, 0.0, 0.0, -1.0),
         ("mission.hall.door0", 43.0, 45.0, 5.0, 0.0, -1.0)]
MARKERS = [("vista.cliff", 43.5, -5.0, 0.0)]


def by_name(items, name):
    return next(x for x in items if x["name"] == name)


def test_human_scale():
    rep = W.analyse(scene(0.6), STEP, (10, 10, 0), DOORS, MARKERS, max_rise=0.45)
    W.print_report(rep)
    assert not rep["ok"]
    assert by_name(rep["doors"], "gate.hall.door0")["ok"]
    assert "no landing" in by_name(rep["doors"], "cliff.hall.door0")["why"]
    assert "not reachable" in by_name(rep["doors"], "mission.hall.door0")["why"]
    bridge = by_name(rep["connectors"], "world.link.gate_mirror")
    assert bridge["ok"] and bridge["pieces"] == 1 and bridge["reached"], bridge
    walk = by_name(rep["connectors"], "mirror.walkway")
    assert not walk["ok"] and sum(not e["ok"] for e in walk["ends"]) == 1, walk
    assert by_name(rep["connectors"], "mirror.view.walkway")["ok"]
    stones = by_name(rep["connectors"], "world.link.mirror_arena")
    assert not stones["ok"] and stones["pieces"] == 4 and "1.7 m up" in stones["why"], stones
    south = by_name(rep["connectors"], "world.link.gate_south")
    assert not south["ok"] and south["pieces"] > 1, south                       # 0.6 m risers break it
    hall = [o for o in rep["orphans"] if "mission.hall.platform" in o["owners"]]
    assert hall and hall[0]["has_door"], rep["orphans"]
    assert not any(o["owners"] == ["world.link.mirror_arena"] for o in rep["orphans"])   # no repeats


def test_blocking_scale():
    rep = W.analyse(scene(0.6), STEP, (10, 10, 0), DOORS, MARKERS, max_rise=0.7)
    south = by_name(rep["connectors"], "world.link.gate_south")
    assert south["ok"] and south["pieces"] == 1 and south["reached"], south
    assert not any("gate.lower_landing" in o["owners"] for o in rep["orphans"])


def test_bad_start():
    rep = W.analyse(scene(0.15), STEP, (500, 500, 0), DOORS)
    assert rep["ok"] is False and "error" in rep


def stones_scene(rise):
    c = {}
    rect(c, 0, 6, 0, 6, 0.0, "arena.rear_landing")
    for k in range(4):                                                          # 0.5 m edge gaps
        x = 6.5 + k * 3.0
        rect(c, x, x + 2.5, 2, 4, rise * (k + 1), "world.link.arena_mission.stone.%03d" % (k + 1))
    rect(c, 18.5, 24, 0, 6, rise * 5, "mission.arrival")
    return c


def test_hops():
    hop = dict(is_hop=W.is_hop)
    ok = W.analyse(stones_scene(1.0), STEP, (3, 3, 0), max_rise=0.45, hop=hop)
    stones = by_name(ok["connectors"], "world.link.arena_mission")
    assert stones["ok"] and stones["pieces"] == 1 and ok["_reach"](21, 3, 5.0), stones
    high = W.analyse(stones_scene(1.5), STEP, (3, 3, 0), max_rise=0.45, hop=hop)
    assert not by_name(high["connectors"], "world.link.arena_mission")["ok"]   # 1.5 m > 1.2 m hop
    plain = W.analyse(stones_scene(1.0), STEP, (3, 3, 0), max_rise=0.45)
    assert not by_name(plain["connectors"], "world.link.arena_mission")["ok"]  # no hop rule


def test_wall_blocks():
    c = {}
    rect(c, 0, 20, 0, 10, 0.0, "court.paving")
    wall = lambda a, b: not ((a[0] <= 20 < b[0] or b[0] <= 20 < a[0]) and min(a[1], b[1]) * STEP > 2.0)
    rep = W.analyse(c, STEP, (2, 5, 0), max_rise=0.45, open_edge=wall)       # wall at x 10, gap y < 2
    assert rep["_reach"](18, 8, 0.0)                                           # round through the gap
    shut = lambda a, b: not (a[0] <= 20 < b[0] or b[0] <= 20 < a[0])
    rep = W.analyse(c, STEP, (2, 5, 0), max_rise=0.45, open_edge=shut)
    assert not rep["_reach"](18, 8, 0.0) and rep["orphans"]


if __name__ == "__main__":
    for t in (test_human_scale, test_blocking_scale, test_bad_start, test_hops, test_wall_blocks):
        t()
        print("ok", t.__name__)
