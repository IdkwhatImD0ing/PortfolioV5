"""Offline test of sect/bake_light.py, the night light's rules behind bake_web.py --light (no Blender, no bpy). Run on
the PC with

    python -P E:/Github/PortfolioV5/.claude/worktrees/guide-accessibility-4c9cf8/blender/xianxia-sect/tools/test_bake_light.py

Prints 'test_bake_light ok' when every check passes. bake_web.py imports bpy, so its BAKE_LIGHT is read from its
source (the dict(...) literal) rather than imported.
"""
import ast
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_light as BL  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def vclose(a, b, tol=1e-9):
    return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))


def bake_light_from_source():
    """bake_web.BAKE_LIGHT as its source writes it: the day keys, plus every key of the **-merged dict (which must be
    bake_light.NIGHT_DEFAULTS)."""
    with open(os.path.join(ROOT, "sect", "bake_web.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "BAKE_LIGHT" for t in node.targets):
            call = node.value
            assert isinstance(call, ast.Call) and call.func.id == "dict", "BAKE_LIGHT is not a dict(...) literal"
            out = {}
            merged = []
            for kw in call.keywords:
                if kw.arg is None:
                    merged.append(ast.unparse(kw.value))
                else:
                    out[kw.arg] = ast.literal_eval(kw.value)
            assert merged == ["BL.NIGHT_DEFAULTS"], merged
            day = dict(out)
            out.update(BL.NIGHT_DEFAULTS)
            return day, out
    raise AssertionError("no BAKE_LIGHT in bake_web.py")


DAY, LIGHT = bake_light_from_source()


def test_defaults():
    assert DAY == dict(world_strength=1.0, world_tint=(1.25, 1.0, 0.78), fill_energy=2.4, fill_elev_deg=27.0,
                       fill_angle_deg=6.0, fill_color=(1.0, 0.72, 0.5)), DAY       # round 57's day light, unchanged
    assert LIGHT["night"] == 0.0
    assert not set(DAY) & set(BL.NIGHT_DEFAULTS), "a night key would shadow a day key"
    BL.check_light(LIGHT)                         # a day light passes (and is not checked further)
    # every preset names known keys only, with the right shapes, and passes the checks
    for name, p in BL.LIGHT_PRESETS.items():
        for k, v in p.items():
            assert k in LIGHT, (name, k)
            assert isinstance(v, tuple) == isinstance(LIGHT[k], tuple), (name, k)
            if isinstance(v, tuple):
                assert len(v) == len(LIGHT[k]), (name, k)
        L = BL.parse_light_spec(name, LIGHT)
        assert L["night"] == 1.0 and L["fill_energy"] == 0.0 and L["world_tint"] == (1.0, 1.0, 1.0), name
        BL.check_light(L)


def test_parse():
    assert BL.parse_light_spec("", LIGHT) == LIGHT
    assert BL.parse_light_spec("", LIGHT) is not LIGHT
    # today's key=value overrides behave as before
    L = BL.parse_light_spec("fill_energy=0.5,world_strength=1.0,world_tint=1.1/1.0/0.9", LIGHT)
    assert L["fill_energy"] == 0.5 and L["world_strength"] == 1.0 and L["world_tint"] == (1.1, 1.0, 0.9)
    assert L["night"] == 0.0
    # presets expand where they stand
    n = BL.parse_light_spec("night", LIGHT)
    assert (n["key_az_deg"], n["key_elev_deg"], n["key_energy"], n["key_angle_deg"]) == (21.0, 20.0, 4.0, 3.0)
    assert n["key_color"] == (0.80, 0.88, 1.0) and n["sky_zenith"] == (0.10, 0.15, 0.28)
    assert n["sky_horizon"] == (0.16, 0.22, 0.38) and n["sky_below"] == 0.3 and n["sky_lobe"] == 0.5
    assert (n["sky_lobe_az_deg"], n["sky_lobe_elev_deg"]) == (21.0, 20.0)       # toward the key
    assert (n["lamp_boost"], n["lantern_boost"]) == (25.0, 8.0)
    assert (n["boost_near"], n["boost_far"]) == (0.3, 0.6)
    t = BL.parse_light_spec("twilight", LIGHT)
    assert (t["key_az_deg"], t["key_elev_deg"], t["key_energy"], t["key_angle_deg"]) == (252.0, 28.0, 2.5, 40.0)
    assert t["key_color"] == (0.84, 0.88, 1.0) and t["sky_zenith"] == (0.14, 0.20, 0.36)
    assert t["sky_horizon"] == (0.30, 0.30, 0.42) and t["sky_lobe"] == 0.6
    assert t["sky_lobe_color"] == (1.0, 0.78, 0.62) and (t["sky_lobe_az_deg"], t["sky_lobe_elev_deg"]) == (252.0, 5.0)
    assert BL.parse_light_spec("night,lamp_boost=50", LIGHT)["lamp_boost"] == 50.0
    assert BL.parse_light_spec("lamp_boost=50,night", LIGHT)["lamp_boost"] == 25.0       # the preset came later
    m = BL.parse_light_spec(" twilight , key_energy=3 ,sky_lobe_color=1/0.7/0.5", LIGHT)
    assert m["key_energy"] == 3.0 and m["sky_lobe_color"] == (1.0, 0.7, 0.5) and m["night"] == 1.0
    assert LIGHT["night"] == 0.0 and LIGHT["lamp_boost"] == 1.0                      # the input is never changed
    for bad, word in (("dusk", "preset"), ("foo=1", "unknown key"), ("key_color=1/2", "3 numbers"),
                      ("fill_energy=x", "not a number"), ("fill_energy=1/2/3", "not a number"),
                      ("night,,lamp_boost=2", "preset"), ("key_color=a/b/c", "not a number")):
        try:
            BL.parse_light_spec(bad, LIGHT)
        except ValueError as e:
            assert str(e).startswith("--light") and word in str(e), (bad, str(e))
        else:
            raise AssertionError("parsed %r" % bad)


def test_check():
    n = BL.parse_light_spec("night", LIGHT)
    for spec, word in (("night=2", "night is 0 or 1"), ("night,boost_near=0.7", "boost_far"),
                       ("night,key_elev_deg=95", "key_elev_deg"), ("night,lamp_boost=-1", "lamp_boost"),
                       ("night,sky_grad_pow=0", "sky_grad_pow"), ("night,key_color=1/-1/1", "key_color")):
        try:
            BL.check_light(BL.parse_light_spec(spec, LIGHT))
        except ValueError as e:
            assert word in str(e), (spec, str(e))
        else:
            raise AssertionError("passed %r" % spec)
    BL.check_light(n)
    # a day light is not checked beyond 'night'
    BL.check_light(BL.parse_light_spec("lamp_boost=-5", LIGHT))


def test_directions():
    # meta.json's sun (look.py SUN_AZIMUTH 252, SUN_ELEVATION 7) in three.js axes
    assert vclose(BL.three_dir(252.0, 7.0), (-0.94397, 0.12187, 0.30671), 5e-5), BL.three_dir(252.0, 7.0)
    assert vclose(BL.dir_from_az_el(0.0, 0.0), (0.0, 1.0, 0.0))            # north = +Y
    assert vclose(BL.dir_from_az_el(90.0, 0.0), (1.0, 0.0, 0.0))           # east = +X
    assert vclose(BL.dir_from_az_el(180.0, 0.0), (0.0, -1.0, 0.0))
    assert vclose(BL.dir_from_az_el(33.0, 90.0), (0.0, 0.0, 1.0))
    for az, el in ((21.0, 20.0), (252.0, 28.0), (252.0, 5.0), (-30.0, 45.0)):
        v = BL.dir_from_az_el(az, el)
        assert close(math.hypot(*v), 1.0)
        t = BL.three_dir(az, el)
        # the formula the task states: (sin az cos el, sin el, -cos az cos el)
        a, e = math.radians(az), math.radians(el)
        assert vclose(t, (math.sin(a) * math.cos(e), math.sin(e), -math.cos(a) * math.cos(e))), (az, el, t)
        assert vclose(BL.three_axes(v), t)
    # the night key stands on the moon's side (look.MOON_AZIMUTH 22.5): within 2 degrees of azimuth
    k = BL.dir_from_az_el(21.0, 20.0)
    assert abs(math.degrees(math.atan2(k[0], k[1])) - 22.5) < 2.0


def test_lamp_class():
    assert BL.lamp_class("M.paper_screen_lit") == "lamp"
    assert BL.lamp_class("M.library_lamplight") == "lamp"
    assert BL.lamp_class("M.props_lantern_silk") == "lantern"
    assert BL.lamp_class("M.props_lantern_panel") == "lantern"
    assert BL.lamp_class("M.paper_lantern") == "lantern"
    assert BL.lamp_class("M.lantern_red") == "lantern"
    assert BL.lamp_class("M.paper_screen") is None
    assert BL.lamp_class("M.marble_white") is None
    assert BL.lamp_class("M.paper_lantern@bake") is None
    assert BL.lamp_class("M.paper_screen_lit@bake.atlas_A0") is None


def test_boost():
    F, near, far = 25.0, 0.3, 0.6
    assert BL.boost_factor(F, True, 5.0, 2.4, near, far) == 1.0        # the camera sees the lamp as before
    assert BL.boost_factor(F, False, 0.1, 2.4, near, far) == 1.0       # its own inside: no boost
    assert BL.boost_factor(F, False, 0.3, 2.4, near, far) == 1.0
    assert BL.boost_factor(F, False, 0.6, 2.4, near, far) == F
    assert BL.boost_factor(F, False, 10.0, 2.4, near, far) == F
    assert close(BL.boost_factor(F, False, 0.45, 2.4, near, far), 1.0 + (F - 1.0) * 0.5)
    assert BL.boost_factor(F, False, 10.0, 0.0, near, far) == 1.0      # no glow property: never boosted
    assert BL.boost_factor(1.0, False, 10.0, 2.4, near, far) == 1.0
    assert BL.smoothstep(0.0, 1.0, -1.0) == 0.0 and BL.smoothstep(0.0, 1.0, 2.0) == 1.0
    assert close(BL.smoothstep(0.0, -0.06, -0.03), 0.5)                  # reversed edges, as the sky's below blend
    prev = 0.0
    for i in range(61):
        f = BL.boost_factor(F, False, 0.01 * i, 1.0, near, far)
        assert f >= prev - 1e-12
        prev = f


def test_sky():
    L = BL.parse_light_spec("night,sky_lobe=0", LIGHT)
    assert vclose(BL.sky_colour(L, (0.0, 0.0, 1.0)), L["sky_zenith"], 1e-12)
    assert vclose(BL.sky_colour(L, (1.0, 0.0, 0.0)), L["sky_horizon"], 1e-12)
    under = tuple(h * L["sky_below"] for h in L["sky_horizon"])
    assert vclose(BL.sky_colour(L, (0.0, 0.6, -0.8)), under, 1e-12)        # undersides darker than tops
    mid = BL.sky_colour(L, (0.0, math.cos(math.radians(30)), 0.5))
    g = 0.5 ** L["sky_grad_pow"]
    assert vclose(mid, tuple(h + (z - h) * g for h, z in zip(L["sky_horizon"], L["sky_zenith"])), 1e-12)
    # the lobe adds its colour toward its own direction, nothing away from it
    W = BL.parse_light_spec("twilight", LIGHT)
    lv = BL.dir_from_az_el(W["sky_lobe_az_deg"], W["sky_lobe_elev_deg"])
    W0 = dict(W, sky_lobe=0.0)
    toward = [a - b for a, b in zip(BL.sky_colour(W, lv), BL.sky_colour(W0, lv))]
    assert vclose(toward, tuple(c * W["sky_lobe"] for c in W["sky_lobe_color"]), 1e-9), toward
    away = (-lv[0], -lv[1], lv[2])
    assert vclose(BL.sky_colour(W, away), BL.sky_colour(W0, away), 1e-12)


def main():
    test_defaults()
    test_parse()
    test_check()
    test_directions()
    test_lamp_class()
    test_boost()
    test_sky()
    print("test_bake_light ok")


if __name__ == "__main__":
    main()
