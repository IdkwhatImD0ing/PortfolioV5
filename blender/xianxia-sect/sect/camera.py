"""sect.camera -- the single fly-through camera (spec sections 0, 4, 5).

    cam = camera.build(scene, anchors, area_modules)

One camera on one continuous, smooth path through every area in flight order
(gate -> mirror -> forge -> arena -> mission -> library -> steles -> scroll -> formation ->
abode -> summit):

- way points = each area's CAMERA_HINTS (local space, front = -Y) moved to world space with the
  area's anchor and yaw, filtered/extended by ROUTE below (hero views, a few extra local points
  where two hints would make the path double back or cut through the arena sword), plus the
  opening point inside the cloud bank, a transit point between areas and a final moon point;
- position: centripetal Catmull-Rom through the way points (no overshoot, no cusps);
- look: per way point direction (hint target - hint location), Catmull-Rom interpolated, then
  Gaussian smoothed over time, so the aim never snaps; lens interpolated the same way;
- speed: set per way point (slow at each hero view, fast in transit), smoothstep blended along
  the arc length, capped so the aim never pans faster than MAX_PAN and the camera never exceeds
  MAX_SPEED, smoothed, then acceleration-limited (ACCEL_MAX, forward/backward pass) so speed
  changes are ramps, never lurches; integrated to time; 24 fps;
- banking: roll from the path's turn rate (lateral acceleration), clamped and smoothed;
- clearance: every frame, a BVH nearest-point query against the evaluated scene (solid
  geometry near the path). Frames closer than CLEARANCE are pushed away with smooth bumps
  (except the gate's centre bay and the stele aisle, which are flown through on purpose);
- timeline: sections (one per area, hero frame = the hero way point, or hero_at of the way to
  the next one) and video segments of <= 288 frames covering 1-3 whole areas. Each area switch
  may fall anywhere calm in its transit (steady aim and speed, already looking at the next
  area); the cut frames and the grouping are chosen together (fewest segments, then the least
  time under 8 s, then the calmest cuts). Consecutive segments share their boundary frame.
  Written to out/section_timeline.json.

The planning half (ROUTE, waypoints(), plan_path(), timeline()) is pure numpy and runs outside
Blender for quick checks; build() adds the Blender parts.
"""

import json
import math
import os
import time

import numpy as np

try:  # Blender
    import bpy
    from mathutils import Matrix, Vector
    from mathutils.bvhtree import BVHTree
except ImportError:  # planning / tests outside Blender
    bpy = None

ORDER = ("gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll",
         "formation", "abode", "summit")
SECTION_IDS = dict(gate="hero", mirror="about", forge="projects", arena="hackathons",
                   mission="experience", library="education", steles="skills", scroll="resume",
                   formation="architecture", abode="personal", summit="footer")

FPS = 24
FRAME_START = 1
SEG_MAX_FRAMES = 288           # 12 s per video segment
SEG_MAX_AREAS = 3
SEG_MIN_FRAMES = 192           # 8 s: shorter clips are allowed but avoided
CUT_TOL = 0.15                 # cut candidates: cost within this of the calmest frame of a window
CLEARANCE = 5.0                # m to the nearest solid geometry (spec / task)
CLEARANCE_PUSH = 6.0           # push target (a little margin over CLEARANCE)
CLEARANCE_EXEMPT = 2.5         # inside the gate bay and the stele aisle
TRANSIT_SPEED = 62.0           # m/s between areas (relative; see TARGET_SECONDS)
TARGET_SECONDS = 72.0          # all speeds are scaled together so the flight lasts this long
MAX_PAN = math.radians(45.0)   # the camera slows down wherever its aim would turn faster
MAX_SPEED = 85.0               # m/s, absolute cap (review: 110 m/s transits made clips too short)
ACCEL_MAX = 22.0               # m/s^2, speed changes are ramps, never lurches (review: 320 m/s^2)
SPEED_DS = 0.5                 # m, arc-length grid of the speed profile
SPEED_SIGMA = 10.0             # m, Gaussian on the speed profile before the acceleration limit
TRANSIT_MIN_GAP = 90.0         # add a transit point when two way points are further apart
TRANSIT_LIFT = 8.0             # transit points ride this much over the straight line
BANK_GAIN = 0.55               # fraction of the "coordinated turn" bank angle
BANK_MAX = math.radians(9.0)
LOOK_SIGMA = 7.0               # frames, Gaussian on the look direction
LENS_SIGMA = 10.0
ROLL_SIGMA = 14.0
CAMERA_NAME = "cam.fly"
MOON_DIR = (0.368, 0.888, 0.276)   # look.MOON_DIR (unit vector toward the moon centre)

END_DRIFT = (22.0, 8.0)        # m forward (toward the moon) and up past the moon hint, slowly
OPENING = dict(location=(0.0, -240.0, 15.0), lens=28.0, speed=32.0)   # at the thin edge of world.cloud.opening


def H(name, speed, hero=False, exempt=False, hero_at=0.0, **override):
    """Use the area's CAMERA_HINT `name` (override location/target/lens if given, local space).
    hero_at: the hero frame sits this fraction of the way (in frames) toward the next way point."""
    return dict(kind="hint", name=name, speed=speed, hero=hero, exempt=exempt, hero_at=hero_at,
                override=override)


def P(name, location, target, lens, speed, hero=False, exempt=False, hero_at=0.0):
    """An extra local-space way point. target may be 'next' (use the next way point's target)."""
    return dict(kind="local", name=name, location=location, target=target, lens=lens, speed=speed,
                hero=hero, exempt=exempt, hero_at=hero_at)


# Per area: which hints, in which order, at which speed (m/s), and which one is the hero view.
ROUTE = {
    # out of the cloud bank, up the stair axis, through the centre bay (flown through: exempt)
    # ('climb' raised from z -2 to 7: below the terrace edge world.py's grass rim hid the gate base)
    # (hero frame 60 % of the way from 'climb' to 'gate': the whole gate fills the frame with the
    # plaza and lanterns showing through the bays; review)
    "gate": [H("rise", 22.0), H("climb", 13.0, hero=True, hero_at=0.6, location=(0.0, -68.0, 7.0),
                                target=(0.0, -12.0, 12.0)),
             H("gate", 12.0, exempt=True),
             H("through", 15.0, exempt=True)],
    # sweeping arc at 13-20 m, the mirror catching the sun
    # ('depart' looks back west while the forge lies east: it forced a 150 deg whip pan)
    "mirror": [H("approach", 26.0), H("hero", 12.0, hero=True)],
    # close pass in front of the hall: cauldron glow and the artifact ring
    # ('rise' looks back at the hall right before the arena view: dropped)
    # (hero frame late in the hero -> pass move: at the hero hint itself the luopan compass of the
    # artifact ring hides the cauldron; review)
    "forge": [H("approach", 26.0), H("hero", 12.0, hero=True, hero_at=0.75), H("pass", 14.0)],
    # low over the platform (12 m), banners sliding past; leave past the sword's west side
    # (the 'exit' hint looks back and would make the path double back toward the mission hall)
    # (approach pulled in from 150 m to 110 m so it does not sit on top of the forge)
    # (hero = 'rim': the whole round floor, taiji ring, banners and sword read together; at the
    # 'hero' hint the floor is out of frame; review)
    "arena": [H("approach", 30.0, location=(-24.0, -110.0, 6.0)), H("rim", 14.0, hero=True),
              H("hero", 15.0),
              P("past_sword", (-24.0, 44.0, 26.0), (14.0, 150.0, 26.0), 24.0, 22.0)],
    # frontal approach along the axis, the jade tablets, then up over the hall roof
    "mission": [H("approach", 28.0), H("wall", 12.0, hero=True), H("rise", 16.0),
                H("over_hall", 18.0)],
    # curve round the pagoda's west side while rising, then leave west toward the steles
    # (the 'depart' hint ends on the north side and would make a hairpin)
    # fly past with the pagoda on the right, curving left toward the steles (which lie behind
    # to the left); the 'rise'/'depart' hints orbit the far side and force a U-turn
    "library": [H("approach", 26.0), H("sweep", 13.0, hero=True, target=(-6.0, 10.0, 26.0)),
                P("exit_west", (-55.0, -8.0, 34.0), "next", 26.0, 24.0)],
    # low glide down the central aisle at 4 m (exempt), rise past the pavilion
    # (glide raised from z 4 to 5.5: the aisle floor is raised, 4 m local was 2.6 m above it)
    "steles": [H("approach", 24.0),
               H("aisle_entry", 11.0, hero=True, exempt=True, location=(0.0, -46.0, 5.5)),
               H("aisle_mid", 12.0, exempt=True, location=(0.0, -22.0, 5.5)),
               H("pavilion_rise", 15.0)],
    # in front of the floating scroll, almost reading it ('read_left' would zig-zag)
    "scroll": [H("approach", 24.0), H("read", 10.0, hero=True),
               H("exit", 16.0, target=(40.0, 20.0, 24.0))],
    # high overhead: the circuit reads as a diagram
    # leave past the east side of the 320 m light pillar (straight on to the abode hits it)
    "formation": [H("approach", 28.0), H("high", 20.0), H("overhead", 14.0, hero=True),
                  P("exit_east", (38.0, 10.0, 115.0), "next", 24.0, 30.0)],
    # swing in from the east side past the waterfall, truck left along the balcony, leave west
    "abode": [P("east", (30.0, -75.0, 32.0), (2.0, 15.0, 30.0), 26.0, 26.0),
              H("waterfall", 13.0), H("balcony", 11.0, hero=True),
              P("exit_west", (-90.0, -20.0, 45.0), "next", 26.0, 20.0)],
    # up past the terrace, end tilted up at the moon
    # (slow finale: review asked for an 8-10 s last clip with a longer drift up to the moon)
    "summit": [H("approach", 22.0), H("rise", 11.0), H("moon", 4.5, hero=True)],
}

# Generic hints for an area whose module failed to import (stand-in block at the anchor).
FALLBACK_HINTS = [
    dict(name="approach", location=(0.0, -95.0, 22.0), target=(0.0, 0.0, 8.0), lens=28),
    dict(name="hero", location=(26.0, -38.0, 16.0), target=(0.0, 0.0, 8.0), lens=24),
]


def _log(*a):
    print("CAMERA", *a, flush=True)


# ==========================================================================================
# way points
# ==========================================================================================

def area_yaws(anchors):
    """Yaw (radians, CCW about Z) per area so its front (local -Y) faces the incoming camera:
    local +Y points along the flight from the previous anchor. The gate faces south (the camera
    rises from the cloud bank straight up its stair axis). An explicit 5th anchor value wins."""
    yaws = {}
    prev = None
    for k in ORDER:
        if k not in anchors:
            continue
        a = anchors[k]
        if len(a) > 4 and a[4] is not None:
            yaws[k] = float(a[4])
        elif prev is None:
            yaws[k] = 0.0
        else:
            p = anchors[prev]
            yaws[k] = math.atan2(-(a[0] - p[0]), a[1] - p[1])
        prev = k
    return yaws


def _to_world(anchor, yaw, v):
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array((anchor[0] + v[0] * c - v[1] * s, anchor[1] + v[0] * s + v[1] * c,
                     anchor[2] + v[2]), float)


def _area_hints(key, module, yaw):
    hints = list(getattr(module, "CAMERA_HINTS", None) or []) if module is not None else []
    by = {h["name"]: dict(h) for h in hints}
    if key == "summit" and module is not None and hasattr(module, "moon_hint"):
        try:
            by["moon"] = dict(module.moon_hint(yaw))      # exact for the yaw actually used
        except Exception as exc:  # keep the module's own hint
            _log("WARN summit.moon_hint failed:", exc)
    return by


def waypoints(anchors, area_modules):
    """World-space way points along the flight: list of dicts with pos, tgt (or None until
    resolved), lens, speed, area, name, hero, exempt."""
    yaws = area_yaws(anchors)
    wps = []
    for key in ORDER:
        if key not in anchors:
            continue
        a, yaw = anchors[key], yaws[key]
        mod = (area_modules or {}).get(key)
        by = _area_hints(key, mod, yaw)
        steps = ROUTE.get(key) or [H(h["name"], 18.0, hero=(i == len(FALLBACK_HINTS) - 1))
                                    for i, h in enumerate(FALLBACK_HINTS)]
        area_wps = []
        for st in steps:
            if st["kind"] == "hint":
                h = by.get(st["name"])
                if h is None:   # module missing or hint renamed: fall back to a generic view
                    fb = {f["name"]: f for f in FALLBACK_HINTS}
                    h = dict(fb.get("hero" if st["hero"] else "approach"))
                    _log("WARN %s has no hint %r, using a generic view" % (key, st["name"]))
                h.update(st.get("override") or {})
                loc, tgt, lens = h["location"], h["target"], h["lens"]
            else:
                loc, tgt, lens = st["location"], st["target"], st["lens"]
            area_wps.append(dict(area=key, name=st["name"], pos=_to_world(a, yaw, loc),
                                 tgt=None if isinstance(tgt, str) else _to_world(a, yaw, tgt),
                                 lens=float(lens), speed=float(st["speed"]), hero=st["hero"],
                                 hero_at=float(st.get("hero_at", 0.0)), exempt=st["exempt"],
                                 kind=st["kind"]))
        if not any(w["hero"] for w in area_wps):
            area_wps[len(area_wps) // 2]["hero"] = True
        wps.extend(area_wps)

    # opening: inside the cloud bank, looking up the stair axis at the gate
    first = wps[0]
    wps.insert(0, dict(area=first["area"], name="opening", pos=np.array(OPENING["location"], float),
                       tgt=first["tgt"].copy(), lens=OPENING["lens"], speed=OPENING["speed"],
                       hero=False, exempt=False, kind="opening"))
    # ending: drift on past the moon hint and centre the moon
    last = wps[-1]
    md = np.array(MOON_DIR, float)
    hd = np.array((md[0], md[1], 0.0))
    hd /= np.linalg.norm(hd)
    end = last["pos"] + hd * END_DRIFT[0] + np.array((0.0, 0.0, END_DRIFT[1]))
    wps.append(dict(area=last["area"], name="end", pos=end, tgt=end + md * 1000.0, lens=55.0,
                    speed=1.5, hero=False, exempt=False, kind="end"))

    # transit points between areas (look ahead at the next area's first target)
    out = []
    for i, w in enumerate(wps):
        out.append(w)
        if i + 1 < len(wps) and wps[i + 1]["area"] != w["area"]:
            n = wps[i + 1]
            gap = float(np.linalg.norm(n["pos"] - w["pos"]))
            if gap > TRANSIT_MIN_GAP:
                mid = 0.5 * (w["pos"] + n["pos"]) + np.array((0.0, 0.0, TRANSIT_LIFT))
                out.append(dict(area=None, name="transit_%s_%s" % (w["area"], n["area"]), pos=mid,
                                tgt=None, lens=0.5 * (w["lens"] + n["lens"]), speed=TRANSIT_SPEED,
                                hero=False, exempt=False, kind="transit"))
    wps = out
    # resolve 'next' targets (custom exits, transits): the next way point that has a target
    for i in range(len(wps) - 1, -1, -1):
        if wps[i]["tgt"] is None:
            nxt = next((w for w in wps[i + 1:] if w["tgt"] is not None), None)
            wps[i]["tgt"] = nxt["tgt"].copy() if nxt else wps[i]["pos"] + np.array((0, 100.0, 0))
    return wps


# ==========================================================================================
# path planning (pure numpy)
# ==========================================================================================

def _gauss(a, sigma):
    """Gaussian smoothing along axis 0 with edge padding."""
    if sigma <= 0:
        return a.copy()
    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a2 = a.reshape(len(a), -1)
    pad = np.concatenate([np.repeat(a2[:1], r, 0), a2, np.repeat(a2[-1:], r, 0)])
    out = np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(a2.shape[1])], 1)
    return out.reshape(a.shape)


def _smoothstep(x):
    return x * x * (3.0 - 2.0 * x)


def _centripetal_dense(P, per=240, alpha=0.5):
    """Dense samples of a centripetal Catmull-Rom spline through P (n,3). Returns (pos, u)."""
    n = len(P)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    pos, us = [], []
    for i in range(n - 1):
        p0, p1, p2, p3 = ext[i:i + 4]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-3) ** alpha
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-3) ** alpha
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-3) ** alpha
        last = i == n - 2
        t = np.linspace(t1, t2, per + (1 if last else 0), endpoint=last)[:, None]
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        c = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
        pos.append(c)
        us.append(i + (t[:, 0] - t1) / (t2 - t1))
    return np.vstack(pos), np.concatenate(us)


def _uniform_cr(V, u):
    """Uniform Catmull-Rom of node values V (n,k) at fractional node parameters u."""
    n = len(V)
    ext = np.vstack([2 * V[0] - V[1], V, 2 * V[-1] - V[-2]])
    i = np.clip(np.floor(u).astype(int), 0, n - 2)
    f = (u - i)[:, None]
    p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
    return 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f +
                  (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f)


def _step_interp(vals, u):
    """Smoothstep blend of node scalars at fractional node parameters (flat at every node)."""
    vals = np.asarray(vals, float)
    i = np.clip(np.floor(u).astype(int), 0, len(vals) - 2)
    f = _smoothstep(np.clip(u - i, 0.0, 1.0))
    return vals[i] + (vals[i + 1] - vals[i]) * f


def _look_nodes(wps):
    Dn = np.array([(w["tgt"] - w["pos"]) / np.linalg.norm(w["tgt"] - w["pos"]) for w in wps])
    yaw_n = np.unwrap(np.arctan2(Dn[:, 1], Dn[:, 0]))
    pit_n = np.arcsin(np.clip(Dn[:, 2], -1.0, 1.0))
    return np.stack([yaw_n, pit_n], 1)


def _look_at(nodes, u):
    """Look direction at fractional node parameters: heading/pitch angles (heading unwrapped,
    so a big turn pans the short way round instead of collapsing through a zero vector)."""
    ang = _uniform_cr(nodes, u)
    return np.stack([np.cos(ang[:, 1]) * np.cos(ang[:, 0]), np.cos(ang[:, 1]) * np.sin(ang[:, 0]),
                     np.sin(ang[:, 1])], 1)


def accel_limit(v, ds, a_max):
    """Lower the speed profile v (per arc-length sample, spacing ds) so that it never speeds up
    or slows down faster than a_max (m/s^2): v1^2 <= v0^2 + 2 a ds, forward and backward.
    Only ever lowers v, so caps applied before stay valid."""
    v = np.array(v, float)
    v2 = v * v
    two_a = 2.0 * a_max * np.broadcast_to(np.asarray(ds, float), (len(v) - 1,))
    out = v2.tolist()
    ta = two_a.tolist()
    for i in range(1, len(out)):
        lim = out[i - 1] + ta[i - 1]
        if out[i] > lim:
            out[i] = lim
    for i in range(len(out) - 2, -1, -1):
        lim = out[i + 1] + ta[i]
        if out[i] > lim:
            out[i] = lim
    return np.sqrt(np.array(out))


def plan_path(wps, fps=FPS, target_seconds=TARGET_SECONDS):
    """Frames along the way points. Returns dict of per-frame arrays (pos, fwd, lens, roll,
    speed) plus the frame of every way point.

    Speed: the way-point speeds, smoothstep blended along the path, all multiplied by one
    factor k, then capped so the aim never turns faster than MAX_PAN and the camera never
    exceeds MAX_SPEED. k is solved so the flight lasts target_seconds."""
    Pn = np.array([w["pos"] for w in wps])
    nodes = _look_nodes(wps)
    pos_c, u_c = _centripetal_dense(Pn)
    seg_c = np.linalg.norm(np.diff(pos_c, axis=0), axis=1)
    s_c = np.concatenate([[0.0], np.cumsum(seg_c)])
    # uniform arc-length grid: the speed profile is smoothed and acceleration-limited on it
    L_ = float(s_c[-1])
    s_d = np.append(np.arange(0.0, L_, SPEED_DS), L_)
    u_d = np.interp(s_d, s_c, u_c)
    pos_d = np.stack([np.interp(s_d, s_c, pos_c[:, j]) for j in range(3)], 1)
    seg = np.diff(s_d)
    v_base = _step_interp([w["speed"] for w in wps], u_d)
    fwd_d = _look_at(nodes, u_d)
    dth = np.arccos(np.clip((fwd_d[1:] * fwd_d[:-1]).sum(1), -1.0, 1.0)) / np.maximum(seg, 1e-6)
    dth = np.concatenate([dth[:1], dth])                       # rad per metre
    r = int(8.0 / SPEED_DS)                                    # running max over +-8 m, then
    dth = np.lib.stride_tricks.sliding_window_view(            # smooth: the cap never lags
        np.concatenate([np.repeat(dth[:1], r), dth, np.repeat(dth[-1:], r)]), 2 * r + 1).max(1)
    dth = _gauss(dth, 4.0 / SPEED_DS)
    v_cap = np.minimum(MAX_SPEED, MAX_PAN / np.maximum(dth, 1e-9))

    def times(k):
        v = np.minimum(k * v_base, v_cap)
        v = np.minimum(_gauss(v, SPEED_SIGMA / SPEED_DS), v_cap)
        v = accel_limit(v, seg, ACCEL_MAX)
        return np.concatenate([[0.0], np.cumsum(seg / (0.5 * (v[1:] + v[:-1])))]), v

    lo, hi = 0.05, 20.0
    for _ in range(40):
        k = math.sqrt(lo * hi)
        if times(k)[0][-1] > target_seconds:
            lo = k
        else:
            hi = k
    t_d, v_d = times(hi)
    T = float(t_d[-1])
    n = int(round(T * fps)) + 1
    t_d *= (n - 1) / fps / T          # whole number of frames
    tk = np.arange(n) / fps
    sk = np.interp(tk, t_d, s_d)
    uk = np.interp(sk, s_d, u_d)
    pos = np.stack([np.interp(sk, s_d, pos_d[:, j]) for j in range(3)], 1)
    fwd = _gauss(_look_at(nodes, uk), LOOK_SIGMA)
    fwd /= np.linalg.norm(fwd, axis=1)[:, None]
    lens = _gauss(_step_interp([w["lens"] for w in wps], uk), LENS_SIGMA)
    wp_frames = [int(round(np.interp(i, u_d, t_d) * fps)) + FRAME_START for i in range(len(wps))]
    out = dict(pos=pos, fwd=fwd, lens=lens, n=n, wp_frames=wp_frames, length=float(s_d[-1]),
               seconds=(n - 1) / fps, speed_scale=round(hi, 3))
    out["roll"], out["speed"] = bank(pos, fwd, fps)
    return out


def bank(pos, fwd, fps=FPS):
    """Roll (radians, + = bank left) from the horizontal turn rate, only while looking roughly
    along the motion. Returns (roll, speed)."""
    vel = np.gradient(_gauss(pos, 3.0), axis=0) * fps
    sp = np.linalg.norm(vel, axis=1)
    head = np.unwrap(np.arctan2(vel[:, 1], vel[:, 0]))
    om = np.gradient(_gauss(head, 6.0)) * fps
    vh = np.linalg.norm(vel[:, :2], axis=1)
    lat = vh * om
    roll = BANK_GAIN * np.arctan(lat / 9.81)
    fh = fwd[:, :2] / np.maximum(np.linalg.norm(fwd[:, :2], axis=1), 1e-6)[:, None]
    vhn = vel[:, :2] / np.maximum(vh, 1e-6)[:, None]
    roll *= np.clip((fh * vhn).sum(1), 0.0, 1.0)
    roll = _gauss(np.clip(roll, -BANK_MAX, BANK_MAX), ROLL_SIGMA)
    return roll, sp


def turn_activity(fwd, pos, fps=FPS):
    """Per-frame 'how much is happening': look angular speed + heading rate (rad/s)."""
    ang = np.arccos(np.clip((fwd[1:] * fwd[:-1]).sum(1), -1, 1)) * fps
    ang = np.concatenate([ang[:1], ang])
    vel = np.gradient(pos, axis=0)
    head = np.unwrap(np.arctan2(vel[:, 1], vel[:, 0]))
    hr = np.abs(np.gradient(head)) * fps
    return _gauss(ang + hr, 6.0)


def cut_windows(wps, plan, fps=FPS):
    """For each pair of consecutive areas (a, b): the frames where the flight may switch from a
    to b, with a cost (low = calm: steady aim, steady speed, already looking at b). The window
    runs from late in a's exit to half way to b's second way point (a long pan may only settle
    after b's approach point); frames past b's first way point cost a little extra."""
    act = turn_activity(plan["fwd"], plan["pos"], fps)
    areas = [k for k in ORDER if any(w["area"] == k for w in wps)]
    wf = plan["wp_frames"]
    first = {k: min(wf[i] for i, w in enumerate(wps) if w["area"] == k) for k in areas}
    last = {k: max(wf[i] for i, w in enumerate(wps) if w["area"] == k and w["kind"] != "end")
            for k in areas}
    sp = plan.get("speed")
    if sp is None:
        sp = np.linalg.norm(np.gradient(plan["pos"], axis=0), axis=1) * fps
    acc = np.abs(np.gradient(_gauss(sp, 3.0))) * fps
    fwd, pos = plan["fwd"], plan["pos"]
    out = []
    for a, b in zip(areas, areas[1:]):
        fa, fb = last[a], first[b]
        fbs = sorted(wf[i] for i, w in enumerate(wps) if w["area"] == b)
        fb2 = fbs[1] if len(fbs) > 1 else fb
        tgt_b = next(w["tgt"] for w in wps if w["area"] == b)
        lo = int(fa + 0.15 * (fb - fa))
        hi = max(lo + 1, int(fb + 0.5 * (fb2 - fb)))
        idx = np.arange(lo, hi + 1) - FRAME_START
        to_b = tgt_b[None, :] - pos[idx]
        to_b /= np.linalg.norm(to_b, axis=1)[:, None]
        ang = np.arccos(np.clip((fwd[idx] * to_b).sum(1), -1.0, 1.0))
        late = np.maximum(0.0, (idx + FRAME_START - fb) / max(fb2 - fb, 1))
        cost = (act[idx] + 0.8 * np.maximum(ang - math.radians(15.0), 0.0) + 0.012 * acc[idx]
                + 0.4 * late)
        out.append(dict(a=a, b=b, frames=idx + FRAME_START, cost=cost))
    return areas, out


def timeline(wps, plan, fps=FPS):
    """Sections (one per area) and video segments. Every switch from one area to the next sits
    in a calm stretch of the transit (cut_windows); segments group 1-3 whole sections into
    <= SEG_MAX_FRAMES frames. The cut frames and the grouping are chosen together: fewest
    segments, then the least shortfall under SEG_MIN_FRAMES, then the calmest cuts."""
    n = plan["n"]
    f_end = FRAME_START + n - 1
    wf = plan["wp_frames"]
    areas, wins = cut_windows(wps, plan, fps)
    m = len(areas)
    # candidate frames per boundary: 0 = flight start, m = flight end, 1..m-1 = area switches
    B = [[(FRAME_START, 0.0)]]
    for w in wins:
        c = w["cost"]
        ok = np.flatnonzero(c <= c.min() + CUT_TOL)
        ok = sorted(set(ok[::2].tolist()) | {int(np.argmin(c))})
        B.append([(int(w["frames"][i]), float(c[i])) for i in ok])
    B.append([(f_end, 0.0)])
    best = {(m, f_end): (0, 0, 0.0, [])}
    for i in range(m - 1, -1, -1):
        for f, cf in B[i]:
            opts = []
            for j in range(i + 1, min(m, i + SEG_MAX_AREAS) + 1):
                for g, _cg in B[j]:
                    nxt = best.get((j, g))
                    ln = g - f + 1
                    if nxt is None or ln > SEG_MAX_FRAMES or ln < 2:
                        continue
                    cnt, short, cc, path = nxt
                    opts.append((cnt + 1, short + max(0, SEG_MIN_FRAMES - ln) ** 2, cc + cf,
                                 [(i, f, j, g)] + path))
            if opts:
                best[(i, f)] = min(opts, key=lambda o: (o[0], o[1], o[2]))
    if (0, FRAME_START) not in best:
        raise RuntimeError("no segmentation with clips <= %d frames" % SEG_MAX_FRAMES)
    plan_cuts = best[(0, FRAME_START)][3]
    starts = {0: FRAME_START}
    for (i, f, j, g) in plan_cuts:
        starts[i] = f
        if j < m:
            starts[j] = g
    for i in range(1, m):           # switches inside a segment: their calmest frame
        if i not in starts:
            w = wins[i - 1]
            starts[i] = int(w["frames"][int(np.argmin(w["cost"]))])
    sections = []
    for j, k in enumerate(areas):
        s0 = starts[j]
        s1 = starts[j + 1] - 1 if j + 1 < m else f_end
        hero = [wf[i] + w.get("hero_at", 0.0) * (wf[min(i + 1, len(wf) - 1)] - wf[i])
                for i, w in enumerate(wps) if w["area"] == k and w["hero"]]
        sections.append(dict(section_id=SECTION_IDS.get(k, k), area=k, frame_start=s0,
                             frame_end=s1, hero_frame=int(min(max(round(hero[0]), s0), s1))))
    segments = []
    for idx, (i, f, j, g) in enumerate(plan_cuts):
        segments.append(dict(index=idx + 1, frame_start=f, frame_end=g, areas=areas[i:j]))
    return dict(fps=fps, frame_start=FRAME_START, frame_end=f_end, sections=sections,
                segments=segments)


# ==========================================================================================
# Blender: clearance, camera, keys
# ==========================================================================================

NON_SOLID = ("haze", "cloud", "fog", "smoke", "mist", "halo", "cirrus", "mote", "spark",
             "moon", "dome", "shield", "god_ray", "godray", "beam_glow", "spray", "plume")
_solid_cache = {}


def _material_is_solid(mat):
    if mat is None:
        return True
    hit = _solid_cache.get(mat.name)
    if hit is not None:
        return hit
    solid = True
    try:
        if mat.use_nodes and mat.node_tree:
            outs = [nd for nd in mat.node_tree.nodes if nd.bl_idname == "ShaderNodeOutputMaterial"]
            if outs:
                o = next((nd for nd in outs if nd.is_active_output), outs[0])
                solid = o.inputs["Surface"].is_linked
    except Exception:
        solid = True
    _solid_cache[mat.name] = solid
    return solid


def _is_solid(ob):
    nm = ob.name.lower()
    if any(t in nm for t in NON_SOLID):
        return False
    mats = [s.material for s in ob.material_slots]
    if mats and not any(_material_is_solid(m) for m in mats):
        return False
    return True


def collect_bvh(scene, path_pos, cell=30.0):
    """BVH of the evaluated solid triangles near the path (every instance counted).
    Returns (bvh, tri_owner_names, owner_index_per_triangle, stats)."""
    t0 = time.perf_counter()
    dg = bpy.context.evaluated_depsgraph_get()
    keys = set()
    pc = np.floor(path_pos / cell).astype(np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                q = pc + (dx, dy, dz)
                keys.update(map(tuple, np.unique(q, axis=0)))
    lo = path_pos.min(0) - 2 * cell
    hi = path_pos.max(0) + 2 * cell
    karr = np.array(sorted(keys), dtype=np.int64)
    kcode = set(((karr[:, 0] + 100000) * 200001 + (karr[:, 1] + 100000)) * 200001 + (karr[:, 2] + 100000))
    kcode = np.array(sorted(kcode), dtype=np.int64)
    mesh_cache = {}
    V, F, owners, own_idx = [], [], [], []
    nv = 0
    n_inst = n_used = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH":
            continue
        n_inst += 1
        if not _is_solid(ob):
            continue
        mw = np.array(inst.matrix_world, float)
        bb = np.array([tuple(c) for c in ob.bound_box], float)
        bbw = bb @ mw[:3, :3].T + mw[:3, 3]
        if (bbw.max(0) < lo).any() or (bbw.min(0) > hi).any():
            continue
        me = ob.data
        key = me.as_pointer()
        hitm = mesh_cache.get(key)
        if hitm is None:
            try:
                nvert = len(me.vertices)
                co = np.empty(nvert * 3, np.float32)
                me.vertices.foreach_get("co", co)
                try:
                    me.calc_loop_triangles()
                except Exception:
                    pass
                nt = len(me.loop_triangles)
                tri = np.empty(nt * 3, np.int32)
                me.loop_triangles.foreach_get("vertices", tri)
                hitm = (co.reshape(-1, 3).astype(float), tri.reshape(-1, 3))
            except Exception:
                hitm = (np.zeros((0, 3)), np.zeros((0, 3), np.int32))
            mesh_cache[key] = hitm
        co, tri = hitm
        if len(tri) == 0:
            continue
        cw = co @ mw[:3, :3].T + mw[:3, 3]
        cen = cw[tri].mean(1)
        cc = np.floor(cen / cell).astype(np.int64)
        code = ((cc[:, 0] + 100000) * 200001 + (cc[:, 1] + 100000)) * 200001 + (cc[:, 2] + 100000)
        keep = np.isin(code, kcode)
        if not keep.any():
            continue
        t = tri[keep]
        used = np.unique(t)
        remap = -np.ones(len(cw), np.int64)
        remap[used] = np.arange(len(used)) + nv
        V.append(cw[used])
        F.append(remap[t])
        own_idx.append(np.full(len(t), len(owners), np.int32))
        owners.append(ob.name)
        nv += len(used)
        n_used += 1
    if not V:
        return None, [], np.zeros(0, np.int32), dict(tris=0)
    V = np.vstack(V)
    F = np.vstack(F)
    own_idx = np.concatenate(own_idx)
    bvh = BVHTree.FromPolygons(V.tolist(), F.tolist(), all_triangles=True)
    st = dict(instances=n_inst, used=n_used, tris=int(len(F)), verts=int(len(V)),
              seconds=round(time.perf_counter() - t0, 1))
    _log("bvh", st)
    return bvh, owners, own_idx, st


def clearance(bvh, owners, own_idx, pos, max_dist=60.0):
    """Per frame: distance to the nearest solid triangle, nearest point, owner name."""
    n = len(pos)
    d = np.full(n, max_dist)
    near = pos.copy()
    who = [""] * n
    for i in range(n):
        hit = bvh.find_nearest(Vector(pos[i]), max_dist)
        if hit[0] is not None:
            d[i] = hit[3]
            near[i] = tuple(hit[0])
            who[i] = owners[own_idx[hit[2]]] if hit[2] is not None and hit[2] < len(own_idx) else ""
    return d, near, who


def _bump(n, c0, c1, ramp):
    """1 on [c0, c1], raised-cosine ramps of `ramp` frames on both sides."""
    f = np.arange(n, dtype=float)
    w = np.zeros(n)
    w[(f >= c0) & (f <= c1)] = 1.0
    left = (f < c0) & (f > c0 - ramp)
    w[left] = 0.5 - 0.5 * np.cos(math.pi * (f[left] - (c0 - ramp)) / ramp)
    right = (f > c1) & (f < c1 + ramp)
    w[right] = 0.5 + 0.5 * np.cos(math.pi * (f[right] - c1) / ramp)
    return w


def resolve_clearance(bvh, owners, own_idx, pos, exempt, iters=6, ramp=30):
    """Push frames that are too close away from the nearest geometry with smooth bumps.
    Returns (offset (n,3), final distances, owners, log)."""
    n = len(pos)
    off = np.zeros((n, 3))
    req = np.where(exempt, CLEARANCE_EXEMPT, CLEARANCE_PUSH)
    log = []
    for it in range(iters):
        p = pos + off
        d, near, who = clearance(bvh, owners, own_idx, p)
        lim = np.where(exempt, CLEARANCE_EXEMPT, CLEARANCE)
        bad = d < lim - 1e-3
        if not bad.any():
            break
        # contiguous runs of bad frames
        idx = np.flatnonzero(bad)
        runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        for r in runs:
            k = r[np.argmin(d[r] - req[r])]
            v = p[k] - near[k]
            ln = np.linalg.norm(v)
            v = v / ln if ln > 1e-6 else np.array((0.0, 0.0, 1.0))
            need = (req[k] - d[k]) * 1.15
            off += _bump(n, r[0], r[-1], ramp)[:, None] * (v * need)[None, :]
            log.append(dict(iter=it, frames=[int(r[0]) + FRAME_START, int(r[-1]) + FRAME_START],
                            min_d=round(float(d[k]), 2), push=round(float(need), 2), near=who[k]))
    d, near, who = clearance(bvh, owners, own_idx, pos + off)
    return off, d, who, log


def _camera_object(scene, name=CAMERA_NAME):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    cd = bpy.data.cameras.get(name)
    if cd is not None and cd.users == 0:
        bpy.data.cameras.remove(cd)
    cd = bpy.data.cameras.new(name)
    cd.sensor_width = 36.0
    cd.sensor_fit = "AUTO"
    cd.clip_start = 0.1
    cd.clip_end = 9000.0
    ob = bpy.data.objects.new(name, cd)
    coll = bpy.data.collections.get("camera") or bpy.data.collections.new("camera")
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    coll.objects.link(ob)
    ob.rotation_mode = "XYZ"
    return ob


def _fcurves_of(idblock):
    ad = idblock.animation_data
    act = ad.action
    out = []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb is not None:
            out = list(cb.fcurves)
    except Exception:
        out = []
    if not out:
        try:
            out = list(act.fcurves)
        except Exception:
            out = []
    if not out:
        for layer in getattr(act, "layers", ()):
            for strip in getattr(layer, "strips", ()):
                for cb in getattr(strip, "channelbags", ()):
                    out.extend(cb.fcurves)
    return out


def _bake(idblock, data_path, values, frames):
    """Linear keys for every frame: values (n, k) for data_path indices 0..k-1."""
    values = np.asarray(values, float).reshape(len(frames), -1)
    for j in range(values.shape[1]):
        idblock.keyframe_insert(data_path=data_path, index=j if values.shape[1] > 1 else -1,
                                frame=float(frames[0]))
    fcs = [fc for fc in _fcurves_of(idblock) if fc.data_path == data_path]
    for fc in fcs:
        j = fc.array_index if values.shape[1] > 1 else 0
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(frames))
        co = np.empty(len(frames) * 2)
        co[0::2] = frames
        co[1::2] = values[:, j]
        fc.keyframe_points.foreach_set("co", co)
        try:
            fc.keyframe_points.foreach_set("interpolation", [1] * len(frames))   # LINEAR
        except Exception:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        fc.update()
    return len(fcs)


def orientations(fwd, roll):
    """XYZ Euler per frame (continuous) for a camera looking along fwd with roll."""
    eul = []
    prev = None
    up = Vector((0.0, 0.0, 1.0))
    for f, r in zip(fwd, roll):
        F = Vector(f).normalized()
        R = F.cross(up)
        if R.length < 1e-6:
            R = Vector((1.0, 0.0, 0.0))
        R.normalize()
        U = R.cross(F).normalized()
        U2 = U * math.cos(r) - R * math.sin(r)       # + roll leans the up vector into a left turn
        R2 = F.cross(U2).normalized()
        m = Matrix((R2, U2, -F)).transposed()
        e = m.to_euler("XYZ", prev) if prev is not None else m.to_euler("XYZ")
        eul.append((e.x, e.y, e.z))
        prev = e
    return np.array(eul)


def build(scene=None, anchors=None, area_modules=None, timeline_path=None, check=True):
    """Create the fly-through camera (CAMERA_NAME), make it the scene camera, set the frame
    range and fps, write the section timeline JSON. Returns a report dict (camera, timeline,
    clearance stats)."""
    t0 = time.perf_counter()
    scene = scene or bpy.context.scene
    if anchors is None:
        from sect import world as W
        anchors = dict(W.ANCHORS)
    wps = waypoints(anchors, area_modules or {})
    plan = plan_path(wps)
    n = plan["n"]
    frames = np.arange(n) + FRAME_START
    exempt = np.zeros(n, bool)
    wf = plan["wp_frames"]
    for i, w in enumerate(wps):
        if w["exempt"]:
            a = (wf[i - 1] + wf[i]) // 2 if i > 0 else wf[i]
            b = (wf[i] + wf[i + 1]) // 2 if i + 1 < len(wps) else wf[i]
            exempt[a - FRAME_START:b - FRAME_START + 1] = True
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_START + n - 1
    scene.frame_set(FRAME_START)

    pos = plan["pos"]
    rep = dict(seconds=plan["seconds"], frames=n, length_m=round(plan["length"], 1))
    if check:
        bvh, owners, own_idx, st = collect_bvh(scene, pos)
        rep["bvh"] = st
        if bvh is not None:
            off, d, who, log = resolve_clearance(bvh, owners, own_idx, pos, exempt)
            pos = pos + off
            rep["pushes"] = log
            rep["max_push_m"] = round(float(np.linalg.norm(off, axis=1).max()), 2)
            bad = [(int(frames[i]), round(float(d[i]), 2), who[i]) for i in range(n)
                   if d[i] < (CLEARANCE_EXEMPT if exempt[i] else CLEARANCE)]
            rep["violations"] = bad[:40]
            rep["n_violations"] = len(bad)
            rep["min_clearance"] = round(float(d[~exempt].min()), 2) if (~exempt).any() else None
            rep["min_clearance_exempt"] = round(float(d[exempt].min()), 2) if exempt.any() else None
            plan["clearance"] = d
            plan["clear_who"] = who
    plan["pos"] = pos
    plan["roll"], plan["speed"] = bank(pos, plan["fwd"])

    cam = _camera_object(scene)
    eul = orientations(plan["fwd"], plan["roll"])
    _bake(cam, "location", pos, frames)
    _bake(cam, "rotation_euler", eul, frames)
    _bake(cam.data, "lens", plan["lens"][:, None], frames)
    scene.camera = cam

    tl = timeline(wps, plan)
    # per-section facts for the report
    for s in tl["sections"]:
        a, b = s["frame_start"] - FRAME_START, s["frame_end"] - FRAME_START + 1
        s_info = dict(seconds=round((b - a) / FPS, 2),
                      speed_min=round(float(plan["speed"][a:b].min()), 1),
                      speed_max=round(float(plan["speed"][a:b].max()), 1))
        if "clearance" in plan:
            k = a + int(np.argmin(plan["clearance"][a:b]))
            s_info.update(min_clearance=round(float(plan["clearance"][k]), 2), at_frame=k + FRAME_START,
                          nearest=plan["clear_who"][k], exempt=bool(exempt[k]))
        rep.setdefault("sections", {})[s["area"]] = s_info
    rep["segments"] = [(g["index"], g["frame_start"], g["frame_end"],
                        round((g["frame_end"] - g["frame_start"] + 1) / FPS, 2), g["areas"])
                       for g in tl["segments"]]
    rep["waypoints"] = [(w["area"], w["name"], wf[i], [round(float(c), 1) for c in w["pos"]])
                        for i, w in enumerate(wps)]
    rep["max_roll_deg"] = round(math.degrees(float(np.abs(plan["roll"]).max())), 1)
    rep["build_s"] = round(time.perf_counter() - t0, 1)
    if timeline_path:
        os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(tl, f, indent=1)
    cam["timeline"] = json.dumps(tl)
    _log("REPORT", json.dumps({k: v for k, v in rep.items() if k not in ("waypoints",)}))
    _log("WAYPOINTS", json.dumps(rep["waypoints"]))
    return dict(camera=cam, timeline=tl, report=rep, plan=plan, waypoints=wps)
