"""Chase camera planning in plain numpy (no bpy), so it can be tuned and measured offline.

Input: the flyer's route (the fly-through camera path, one point per frame), the designed view
direction per frame (look0) and the hero frames. Output: per-frame flyer position, heading and
bank, camera position and look direction, plus comfort metrics.

Comfort rules (from review: "turns too abruptly", "wavers too much"):
- The camera's look direction is rate- and acceleration-limited: it can never turn faster than
  YAW_RATE_MAX / PITCH_RATE_MAX, and eases into and out of every turn.
- Swings toward an area are small (MAX_LOOK_OFF) and slow (HERO_RAMP).
- The camera position is a smoothed follow of the ideal orbit position, so small wiggles of the
  route never reach the camera; the flyer floats a little in frame instead of being pinned.
- The flyer changes thirds rarely (SIDE_SWITCH, SIDE_MIN_HOLD) and slowly (SIDE_SLIDE_SIGMA).
- Almost no camera roll.
Flyer rules: always flies forward (heading = direction of travel), never dead centre by default.
"""
import math

import numpy as np

LENS = 32.0
SENSOR = 36.0
ASPECT = 16 / 9
DIST = 14.0                        # ideal camera distance to the flyer (m)
SCREEN_X = 0.34                    # flyer's ideal spot: this far from centre (fraction of half-width)
SCREEN_Y = -0.30                   # and this far below centre (fraction of half-height)
CENTER_UP = 0.9                    # aim point on the flyer above the sword (m)
LOOK_AHEAD = 90.0                  # travelling: look at the route this far ahead of the flyer (m)
MAX_LOOK_OFF = math.radians(50)    # never look further than this from the flyer's heading
MIN_PITCH = math.radians(-65)
HERO_HOLD = 24                     # frames each side of a hero frame on the designed view
HERO_RAMP = 72                     # frames to ease into / out of it
SIDE_SWITCH = math.radians(90)     # effectively never: the flyer stays on the left third (side changes read as wavering)
SIDE_MIN_HOLD = 10 ** 6                 # frames the flyer stays on a side before it may move again
SIDE_SLIDE_SIGMA = 24.0            # smoothing (frames) of the slide between thirds
YAW_RATE_MAX = math.radians(20)    # rad/s
PITCH_RATE_MAX = math.radians(20)
YAW_ACC_MAX = math.radians(20)     # rad/s^2
PITCH_ACC_MAX = math.radians(24)
FLY_SIGMA = 4.0                    # route smoothing for the flyer (frames)
CAM_POS_SIGMA = 8.0               # camera position follow smoothing (frames)
SAFE_X = 0.80                      # keep the flyer inside this part of the frame
SAFE_Y = 0.85
MAX_BANK = math.radians(35)        # the flyer's own bank into turns
ROLL_SIGMA = 20.0
CAM_BANK = 0.06                    # share of the flyer's bank the camera copies


def gauss(a, sigma):
    """Gaussian smoothing along axis 0 with edge padding (same as camera._gauss)."""
    a = np.asarray(a, float)
    if sigma <= 0:
        return a.copy()
    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a2 = a.reshape(len(a), -1)
    pad = np.concatenate([np.repeat(a2[:1], r, 0), a2, np.repeat(a2[-1:], r, 0)])
    out = np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(a2.shape[1])], 1)
    return out.reshape(a.shape)


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def resample(pos, s, s_query):
    out = np.empty((len(s_query), 3))
    for k in range(3):
        out[:, k] = np.interp(s_query, s, pos[:, k])
    t_end = unit(pos[-1] - pos[-6])
    over = s_query > s[-1]
    out[over] = pos[-1] + np.outer(s_query[over] - s[-1], t_end)
    return out


def yaw_pitch(v):
    return np.unwrap(np.arctan2(v[:, 1], v[:, 0])), np.arcsin(np.clip(v[:, 2], -1, 1))


def from_yaw_pitch(yaw, pitch):
    return np.c_[np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)]


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def smootherstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def hero_weights(frames, hero_frames):
    w = np.zeros(len(frames))
    for h in hero_frames:
        w = np.maximum(w, smootherstep((HERO_HOLD + HERO_RAMP - np.abs(frames - h)) / HERO_RAMP))
    return w


def limit_rate(a, fps, rate_max, acc_max, iters=60):
    """Smooth an angle track until its rate and acceleration stay under the caps. Only the
    offending stretches are smoothed (blended with a heavily smoothed copy), so calm parts keep
    their shape."""
    a = np.asarray(a, float).copy()
    for _ in range(iters):
        r = np.gradient(a) * fps
        acc = np.gradient(r) * fps
        bad = (np.abs(r) > rate_max) | (np.abs(acc) > acc_max)
        if not bad.any():
            break
        w = np.clip(gauss(bad.astype(float), 12.0) * 4.0, 0.0, 1.0)
        a = (1.0 - w) * a + w * gauss(a, 18.0)
    return a


def screen_pos(cam, look, target, lens=LENS):
    """Flyer position on screen (x, y in -1..1) and depth, for a camera with no roll."""
    tan_h = SENSOR / (2 * lens)
    tan_v = tan_h / ASPECT
    up = np.array([0.0, 0.0, 1.0])
    r = unit(np.cross(look, up))
    u = np.cross(r, look)
    d = target - cam
    z = np.einsum("ij,ij->i", d, look)
    x = np.einsum("ij,ij->i", d, r) / np.maximum(z, 1e-3) / tan_h
    y = np.einsum("ij,ij->i", d, u) / np.maximum(z, 1e-3) / tan_v
    return x, y, z


def sides(off):
    """Which third the flyer sits on (-1 left, +1 right), with hysteresis and a minimum hold."""
    n = len(off)
    out = np.empty(n)
    cur, since = -1.0, SIDE_MIN_HOLD
    for i in range(n):
        since += 1
        want = 1.0 if off[i] > SIDE_SWITCH else (-1.0 if off[i] < -SIDE_SWITCH else cur)
        if want != cur and since >= SIDE_MIN_HOLD:
            cur, since = want, 0
        out[i] = cur
    return out


def plan(pos, look0, frames, heroes, fps=24):
    """Plan the chase. Returns a dict of per-frame arrays (camera position before any clearance
    push; call finish() after pushing)."""
    fly = gauss(pos, FLY_SIGMA)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(fly, axis=0), axis=1))])
    fwd = unit(gauss(resample(fly, s, s + 2.0) - fly, 4.0))
    speed = np.gradient(s) * fps
    hy, _ = yaw_pitch(fwd)
    yaw_rate = np.gradient(hy) * fps
    roll = gauss(np.clip(np.arctan(speed * yaw_rate / 9.81), -MAX_BANK, MAX_BANK), ROLL_SIGMA)

    ahead = unit(gauss(resample(fly, s, s + LOOK_AHEAD) - fly, 8.0))
    w = hero_weights(frames, heroes)[:, None]
    view = unit((1 - w) * ahead + w * look0)
    vy, vp = yaw_pitch(view)
    off = np.clip(wrap(vy - hy), -MAX_LOOK_OFF, MAX_LOOK_OFF)
    vy = limit_rate(hy + gauss(off, 6.0), fps, YAW_RATE_MAX, YAW_ACC_MAX)
    vp = limit_rate(np.maximum(gauss(vp, 6.0), MIN_PITCH), fps, PITCH_RATE_MAX, PITCH_ACC_MAX)

    sx = gauss(sides(off) * SCREEN_X, SIDE_SLIDE_SIGMA)
    sy = np.full(len(fly), SCREEN_Y)
    tan_h = SENSOR / (2 * LENS)
    tan_v = tan_h / ASPECT
    to_flyer = from_yaw_pitch(vy - np.arctan(sx * tan_h), vp + np.arctan(sy * tan_v))
    target = fly + np.array([0.0, 0.0, CENTER_UP])
    cam = gauss(target - DIST * to_flyer, CAM_POS_SIGMA)
    return dict(fly=fly, fwd=fwd, roll=roll, cam=cam, target=target, vy=vy, vp=vp, sx=sx, sy=sy,
                off=off, speed=speed, fps=fps)


def finish(p, passes=4):
    """Final look direction for the (possibly pushed) camera: the smooth, rate-limited view,
    turned toward the flyer only where it would leave the safe part of the frame, then
    rate-limited again."""
    fps = p["fps"]
    vy, vp = p["vy"].copy(), p["vp"].copy()
    tan_h = SENSOR / (2 * LENS)
    tan_v = tan_h / ASPECT
    for _ in range(passes):
        look = from_yaw_pitch(vy, vp)
        x, y, z = screen_pos(p["cam"], look, p["target"])
        bad = (z <= 0) | (np.abs(x) > SAFE_X) | (np.abs(y) > SAFE_Y)
        if not bad.any():
            break
        d = unit(p["target"] - p["cam"])
        dy, dp = yaw_pitch(d)
        dy = vy + wrap(dy - vy)
        ly = dy + np.arctan(p["sx"] * tan_h)              # look that puts the flyer on its third line
        lp = dp - np.arctan(p["sy"] * tan_v)
        wgt = np.clip(gauss(bad.astype(float), 10.0) * 3.0, 0.0, 1.0)
        vy = limit_rate((1 - wgt) * vy + wgt * ly, fps, YAW_RATE_MAX * 1.3, YAW_ACC_MAX * 1.3)
        vp = limit_rate(np.maximum((1 - wgt) * vp + wgt * lp, MIN_PITCH), fps, PITCH_RATE_MAX * 1.3,
                        PITCH_ACC_MAX * 1.3)
    p["look"] = from_yaw_pitch(vy, vp)
    p["cam_roll"] = gauss(p["roll"] * CAM_BANK, ROLL_SIGMA)
    return p


def metrics(cam, look, target, roll, fps=24):
    """Comfort numbers: turn speeds (deg/s), turn accelerations (deg/s^2), camera speed and
    acceleration (m/s, m/s^2), and where the flyer sits on screen."""
    yaw, pitch = yaw_pitch(look)
    yr = np.degrees(np.gradient(yaw) * fps)
    pr = np.degrees(np.gradient(pitch) * fps)
    ya = np.gradient(yr) * fps
    rr = np.degrees(np.gradient(roll) * fps)
    v = np.linalg.norm(np.gradient(cam, axis=0), axis=1) * fps
    acc = np.abs(np.gradient(v)) * fps
    jitter = np.degrees(np.abs(np.gradient(np.gradient(np.gradient(yaw)))) * fps ** 3)
    x, y, z = screen_pos(cam, look, target)
    return dict(
        yaw_rate_max=round(float(np.abs(yr).max()), 1), yaw_rate_p95=round(float(np.percentile(np.abs(yr), 95)), 1),
        pitch_rate_max=round(float(np.abs(pr).max()), 1), yaw_acc_max=round(float(np.abs(ya).max()), 1),
        roll_rate_max=round(float(np.abs(rr).max()), 1), yaw_jerk_p95=round(float(np.percentile(jitter, 95)), 1),
        cam_speed_max=round(float(v.max()), 1), cam_acc_max=round(float(acc.max()), 1),
        flyer_out_of_frame=int(np.sum((z <= 0) | (np.abs(x) > 1) | (np.abs(y) > 1))),
        flyer_outside_safe=int(np.sum((np.abs(x) > SAFE_X) | (np.abs(y) > SAFE_Y))),
        flyer_near_centre=int(np.sum(np.abs(x) < 0.12)),
        flyer_x_range=[round(float(x.min()), 2), round(float(x.max()), 2)],
        flyer_y_range=[round(float(y.min()), 2), round(float(y.max()), 2)],
    )
