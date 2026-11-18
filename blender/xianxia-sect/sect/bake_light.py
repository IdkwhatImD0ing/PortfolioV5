"""Pure rules behind bake_web.py's night light (no bpy, no mathutils, so they are tested offline by
tools/test_bake_light.py).

The abode (blue hour) and the summit (night) used to bake under the film's sunset sun and only got graded blue on the
page. A night bake (BAKE_LIGHT night=1) lights them for their hour instead: the scene's sun lamp turns into a key from
the moon (summit) or the afterglow (abode), the warm bake key goes off, a graded night sky replaces the film's sky, and
lanterns light what is round them. bake_web.night_scene does it in Blender; this module holds the numbers and the maths.

    NIGHT_DEFAULTS   the keys a night bake adds to bake_web.BAKE_LIGHT (night=0: a day bake, exactly as before)
    LIGHT_PRESETS    named sets for --light ("--light night", "--light twilight,lamp_boost=40")
    parse_light_spec --light's parser: comma parts, each a preset name or key=value, applied in order
    check_light      the values a night bake can use (raises ValueError)
    dir_from_az_el   compass azimuth / elevation -> Blender direction (sect/lib/look.py's convention)
    three_dir        the same in three.js axes (x east, y up, z = -Blender y), as meta.json and the live index store it
    lamp_class       'lamp' / 'lantern' / None for a material name (which boost a material gets)
    boost_factor     the emission multiplier night_scene's nodes compute for one shading call
    sky_colour       the colour night_scene's world nodes give a direction
"""
import math

# Night keys, merged into bake_web.BAKE_LIGHT. With night=0 none of them is read: a day bake is exactly as before.
# Directions are compass degrees (0 north = +Y, 90 east = +X) and degrees above the horizon, as sect/lib/look.py.
NIGHT_DEFAULTS = dict(
    night=0.0,                         # 1: night_scene re-aims the sun lamp, turns the warm key off, swaps the sky
    key_az_deg=21.0,                   # the re-aimed sun lamp (look.sun, in memory only)
    key_elev_deg=20.0,
    key_energy=4.0,
    key_color=(0.80, 0.88, 1.0),
    key_angle_deg=3.0,
    sky_zenith=(0.10, 0.15, 0.28),     # the graded night sky (linear), times world_strength
    sky_horizon=(0.16, 0.22, 0.38),
    sky_below=0.3,                     # share of the horizon colour below the horizon (undersides darker than tops)
    sky_grad_pow=0.5,                  # horizon -> zenith: mix by (direction z) ** this
    sky_lobe=0.0,                      # a soft glow in the sky (the moon's side, the afterglow), strength
    sky_lobe_color=(0.80, 0.88, 1.0),
    sky_lobe_az_deg=21.0,
    sky_lobe_elev_deg=20.0,
    sky_lobe_pow=8.0,                  # lobe = sky_lobe * max(cos(angle to the lobe), 0) ** this
    lamp_boost=1.0,                    # emission x this on materials named *paper_screen_lit* / *lamplight*
    lantern_boost=1.0,                 # emission x this on materials named *lantern*
    boost_near=0.3,                    # m: rays shorter than this get no boost (a lantern's own inside), ...
    boost_far=0.6,                     # m: ... rays longer than this the whole boost (smoothstep between)
)

# --light presets: a comma part without '=' names one. Starting points; stills on the box decide (preview_r59.py
# --bake-light). world_tint 1/1/1: bake_lighting multiplies whatever feeds the sky by world_tint, and the day's warm
# tint would turn these colours to grey-green.
LIGHT_PRESETS = dict(
    # the summit: moonlight from the moon's side (look.MOON_AZIMUTH 22.5, a little higher than the disc)
    night=dict(night=1.0, key_az_deg=21.0, key_elev_deg=20.0, key_energy=4.0, key_color=(0.80, 0.88, 1.0),
               key_angle_deg=3.0, fill_energy=0.0, world_tint=(1.0, 1.0, 1.0),
               sky_zenith=(0.10, 0.15, 0.28), sky_horizon=(0.16, 0.22, 0.38), sky_below=0.3,
               sky_lobe=0.5, sky_lobe_color=(0.80, 0.88, 1.0), sky_lobe_az_deg=21.0, sky_lobe_elev_deg=20.0,
               lamp_boost=25.0, lantern_boost=8.0),
    # the abode: its own 60 m cliff blocks the moon, so the afterglow in the west lights it (soft shadows)
    twilight=dict(night=1.0, key_az_deg=252.0, key_elev_deg=28.0, key_energy=2.5, key_color=(0.84, 0.88, 1.0),
                  key_angle_deg=40.0, fill_energy=0.0, world_tint=(1.0, 1.0, 1.0),
                  sky_zenith=(0.14, 0.20, 0.36), sky_horizon=(0.30, 0.30, 0.42), sky_below=0.3,
                  sky_lobe=0.6, sky_lobe_color=(1.0, 0.78, 0.62), sky_lobe_az_deg=252.0, sky_lobe_elev_deg=5.0,
                  lamp_boost=25.0, lantern_boost=8.0),
)

LAMP_WORDS = ("paper_screen_lit", "lamplight")   # lamp_boost (a stone lantern's lit core, lit screens)
LANTERN_WORDS = ("lantern",)                     # lantern_boost (paper and silk lanterns)


def parse_light_spec(spec, light, presets=None):
    """A copy of ``light`` with --light ``spec`` applied: comma parts in order, each a preset name (expanded in place)
    or key=value (numbers; three numbers joined by '/' for a colour). Raises ValueError naming what is wrong."""
    presets = LIGHT_PRESETS if presets is None else presets
    out = dict(light)
    if not spec:
        return out

    def put(k, v):
        if k not in out:
            raise ValueError("--light: unknown key %r (have %s)" % (k, ", ".join(sorted(out))))
        if isinstance(out[k], tuple):
            val = tuple(float(x) for x in v) if isinstance(v, (tuple, list)) else tuple(float(x) for x in
                                                                                       str(v).split("/"))
            if len(val) != len(out[k]):
                raise ValueError("--light: %s takes %d numbers joined by '/'" % (k, len(out[k])))
        else:
            if isinstance(v, (tuple, list)):
                raise ValueError("--light: %s takes one number" % k)
            val = float(v)
        out[k] = val

    for part in spec.split(","):
        k, eq, v = part.partition("=")
        k = k.strip()
        if not eq:
            if k not in presets:
                raise ValueError("--light: unknown preset %r (presets: %s; or key=value)" % (
                    k, ", ".join(sorted(presets))))
            for pk, pv in presets[k].items():
                put(pk, pv)
            continue
        try:
            put(k, v.strip())
        except ValueError as e:
            if str(e).startswith("--light"):
                raise
            raise ValueError("--light: %s=%r is not a number" % (k, v))
    return out


def check_light(L):
    """Raise ValueError when a night light's numbers cannot work. A day light (night=0) is not checked."""
    if L.get("night", 0.0) not in (0.0, 1.0):
        raise ValueError("--light: night is 0 or 1, not %r" % L.get("night"))
    if not L.get("night"):
        return
    bad = []
    if not -90.0 < L["key_elev_deg"] <= 90.0:
        bad.append("key_elev_deg %r outside (-90, 90]" % L["key_elev_deg"])
    if not -90.0 <= L["sky_lobe_elev_deg"] <= 90.0:
        bad.append("sky_lobe_elev_deg %r outside [-90, 90]" % L["sky_lobe_elev_deg"])
    if not 0.0 <= L["key_angle_deg"] <= 180.0:
        bad.append("key_angle_deg %r outside [0, 180]" % L["key_angle_deg"])
    for k in ("key_energy", "sky_below", "sky_lobe", "lamp_boost", "lantern_boost", "boost_near", "world_strength"):
        if L[k] < 0.0:
            bad.append("%s %r below 0" % (k, L[k]))
    for k in ("sky_grad_pow", "sky_lobe_pow"):
        if L[k] <= 0.0:
            bad.append("%s %r not above 0" % (k, L[k]))
    if not L["boost_far"] > L["boost_near"]:
        bad.append("boost_far %r not above boost_near %r" % (L["boost_far"], L["boost_near"]))
    for k in ("key_color", "sky_zenith", "sky_horizon", "sky_lobe_color"):
        if min(L[k]) < 0.0:
            bad.append("%s %r has a negative part" % (k, L[k]))
    if bad:
        raise ValueError("--light: " + "; ".join(bad))


def dir_from_az_el(az_deg, el_deg):
    """Unit direction (Blender axes: x east, y north, z up) toward compass azimuth ``az_deg`` (0 north = +Y, 90 east =
    +X) at ``el_deg`` above the horizon: sect/lib/look.py dir_from_az_el as a plain tuple."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))


def three_axes(v):
    """A Blender direction in three.js axes (x east, y up, z = -Blender y)."""
    return (v[0], v[2], -v[1])


def three_dir(az_deg, el_deg):
    """dir_from_az_el in three.js axes: the sun of meta.json (az 252, el 7) is (-0.94397, 0.12187, 0.30671)."""
    return three_axes(dir_from_az_el(az_deg, el_deg))


def lamp_class(name):
    """'lamp' (lamp_boost), 'lantern' (lantern_boost) or None for a material name. Lamp words win, so a material
    named after both gets the lamp boost. The bake's own copies ('<name>@...') are never boosted again."""
    if "@" in name:
        return None
    if any(w in name for w in LAMP_WORDS):
        return "lamp"
    if any(w in name for w in LANTERN_WORDS):
        return "lantern"
    return None


def smoothstep(e0, e1, x):
    """Blender's Map Range SMOOTHSTEP from [e0, e1] to [0, 1], clamped."""
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def boost_factor(F, camera_ray, ray_length, glow, near, far):
    """What night_scene's nodes multiply a lamp's emission strength by: 1 + (F - 1) * w, where
    w = (1 - Is Camera Ray) * smoothstep(near, far, Ray Length) * [glow > 0]. The camera (and a bake's own texels) sees
    the lamp as before; light reaching anything else is boosted, except over rays shorter than ``near`` (a stone
    lantern's core is a closed paper box: its own inside faces and its stone housing would wash white); ``glow`` is the
    piece's raw object property (missing reads 0: only pieces that carry it are boosted)."""
    w = (1.0 - float(bool(camera_ray))) * smoothstep(near, far, ray_length) * (1.0 if glow > 0.0 else 0.0)
    return 1.0 + (F - 1.0) * w


def sky_colour(L, d):
    """The night sky's colour (before world_strength and world_tint) toward unit direction ``d`` (Blender axes), as
    night_scene's world nodes compute it: horizon -> zenith by z ** sky_grad_pow above the horizon, the horizon colour
    x sky_below under it (blended over z 0 .. -0.06), plus the lobe (also x sky_below under the horizon)."""
    z = d[2]
    g = max(z, 0.0) ** L["sky_grad_pow"] if z > 0.0 else 0.0
    above = [h + (zc - h) * g for h, zc in zip(L["sky_horizon"], L["sky_zenith"])]
    under = [h * L["sky_below"] for h in L["sky_horizon"]]
    b = smoothstep(0.0, -SKY_BELOW_BLEND, z) if z < 0.0 else 0.0
    base = [a + (u - a) * b for a, u in zip(above, under)]
    lv = dir_from_az_el(L["sky_lobe_az_deg"], L["sky_lobe_elev_deg"])
    c = max(sum(p * q for p, q in zip(d, lv)), 0.0)
    amt = L["sky_lobe"] * c ** L["sky_lobe_pow"] * (1.0 - b * (1.0 - L["sky_below"]))
    return tuple(x + lc * amt for x, lc in zip(base, L["sky_lobe_color"]))


SKY_BELOW_BLEND = 0.06   # dir z range over which the sky turns into its under-horizon colour (look.below_horizon_blend)
