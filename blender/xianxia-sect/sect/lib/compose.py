"""Round 48: composition rules for the background (scratchpad r49/intent.md, sect/holds_intent.json).

Pure numpy and math at import (no bpy), so the rules run on the PC without Blender too (scratchpad r48/tools); the
helpers that read the scene (views_from_blend, star_boxes) import bpy when called.

- load_intent(): sect/holds_intent.json (per hold: story, host, skyline, quiet rects, moon, islets, falls, mist).
- View: one camera (position, axes, field of view) with a pinhole projection in the 16:9 frame (u right, v down).
- peak_limits(): the highest top each pillar may have so that, at every hold, (1) the star's roofline stays against
  sky where the hold asks for it (skyline), (2) the hold's quiet sky stays empty (quiet), (3) the moon is fully clear
  where it must be (moon: the gate, the poster, 1160, the summit, 1729). Hosts and exempt peaks are never cut.
- cull_islands(): which floating islands go so that each hold shows at most its 'islets.max' (inside its zone, none
  near the star, none in quiet sky), every sampled flight frame at most 'islets_max' (7 by default), and the totals
  fall to the targets (about 40 islands and 12 islets).
- cull_falls(): which waterfalls go (none in the arena, mission, library, steles and scroll holds; about one island in
  four keeps its fall), location falls kept.
"""
import json
import math
import os

import numpy as np

SECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTENT_PATH = os.path.join(SECT, "holds_intent.json")
ASPECT = 16.0 / 9.0
MOON_MARGIN_DEG = 1.5          # the moon's disc plus this all round is 'clear' sky
SKY_MARGIN_V = 0.02            # a cut pillar's top ends this far (frame heights) under the line it must stay under
SKY_MARGIN_U = 0.015           # ... and a pillar counts as over a rect when it reaches this near it sideways
STAR_DEPTH_PAD = 30.0          # m: the skyline rule cuts only peaks this far behind the star
NO_TWIN = 0.25                 # kept islets of one hold differ in on-screen size by at least this share (rule C6)
# A peak serves many views. Cuts stay local and moderate: the quiet-sky and skyline rules reach only QUIET_MAX_D m
# from the hold camera and never take more than CUT_SHARE_MAX of a pillar's height over its plinth (a bigger cut is
# logged as a conflict for the critic instead); the moon rule reaches MOON_MAX_D m and may take MOON_CUT_SHARE_MAX.
# Farther peaks are left to the per-hold haze (phase A): pale layers, not shapes.
QUIET_MAX_D = 650.0
CUT_SHARE_MAX = 0.55
MOON_MAX_D = 750.0
MOON_CUT_SHARE_MAX = 0.9


def load_intent(path=None):
    with open(path or INTENT_PATH, encoding="utf-8") as f:
        return json.load(f)


class View:
    """A camera: pos, fwd, up, right (unit, world), tan of half the vertical / horizontal FOV."""

    def __init__(self, name, frame, pos, fwd, up, tv, aspect=ASPECT):
        self.name, self.frame = name, int(frame)
        self.pos = np.asarray(pos, float)
        self.fwd = np.asarray(fwd, float) / np.linalg.norm(fwd)
        up = np.asarray(up, float)
        self.right = np.cross(self.fwd, up)
        self.right /= np.linalg.norm(self.right)
        self.up = np.cross(self.right, self.fwd)
        self.tv = float(tv)
        self.th = float(tv) * aspect

    def project(self, pts):
        """(u, v, depth) of world points (n, 3); u, v in 0..1 inside the frame (v from the top)."""
        P = np.atleast_2d(np.asarray(pts, float)) - self.pos
        d = P @ self.fwd
        x = P @ self.right
        y = P @ self.up
        with np.errstate(divide="ignore", invalid="ignore"):
            u = 0.5 + 0.5 * x / (d * self.th)
            v = 0.5 - 0.5 * y / (d * self.tv)
        return u, v, d

    def half_u(self, radius, depth):
        """Half width in u of something ``radius`` m wide at ``depth`` m."""
        return radius / np.maximum(depth, 1e-3) / (2.0 * self.th)

    def px(self, size, depth, height=720):
        return size / np.maximum(depth, 1e-3) * height / (2.0 * self.tv)

    def z_at_v(self, x, y, v):
        """Height of the point on the vertical line through (x, y) that projects to row ``v`` (None if that row is
        never reached in front of the camera)."""
        p0 = np.array([x, y, self.pos[2]]) - self.pos
        y0, d0 = p0 @ self.up, p0 @ self.fwd
        a, b = self.up[2], self.fwd[2]
        k = (1.0 - 2.0 * v) * self.tv            # y / d at row v
        den = a - k * b
        if abs(den) < 1e-9:
            return None
        return float(self.pos[2] + (k * d0 - y0) / den)


def views_from_matrices(names_frames, mats, tv, aspect=ASPECT):
    """Views from 4x4 world matrices of a Blender camera (looks down local -Z, up local +Y)."""
    out = []
    for (name, f), M in zip(names_frames, mats):
        M = np.asarray(M, float)
        out.append(View(name, f, M[:3, 3], -M[:3, 2], M[:3, 1], tv, aspect))
    return out


def views_from_blend(names_frames, camera="chase.cam"):
    """Views of chase.cam at the given (name, frame) pairs (export_web.sample_matrices / camera_tan)."""
    import bpy
    from sect import export_web as EW
    cam = bpy.data.objects[camera]
    _th, tv = EW.camera_tan(cam)
    mats = EW.sample_matrices(cam, [f for _n, f in names_frames])
    return views_from_matrices(names_frames, [np.array(m) for m in mats], tv)


def views_from_camera_json(path, names_frames):
    """Views from the exported camera.json (three.js: p = (bx, bz, -by), q looks down local -Z)."""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    fr = {int(x["f"]): x for x in c["frames"]}

    def rot(q, v):
        x, y, z, w = q
        qv = np.array([x, y, z])
        t = 2.0 * np.cross(qv, v)
        return v + w * t + np.cross(qv, t)

    def b(v):
        return np.array([v[0], -v[2], v[1]], float)
    out = []
    for name, f in names_frames:
        x = fr[int(f)]
        q = x["q"]
        out.append(View(name, f, b(x["p"]), b(rot(q, np.array([0.0, 0.0, -1.0]))),
                        b(rot(q, np.array([0.0, 1.0, 0.0]))), math.tan(math.radians(x["fovY"]) / 2.0)))
    return out


def intent_views(intent):
    """[(name, frame)] of every hold and every listed flight frame."""
    out = [(k, h["frame"]) for k, h in intent["holds"].items()]
    out += [("f%d" % f["frame"], f["frame"]) for f in intent["flights"]]
    return out


def moon_world(moon_view, moon_dir, moon_distance):
    return np.asarray(moon_view, float) + np.asarray(moon_dir, float) * float(moon_distance)


def moon_disc(view, moon, ang_size_deg=14.0, margin_deg=MOON_MARGIN_DEG):
    """(u, v, ru, rv, depth) of the moon's disc plus margin in ``view``."""
    u, v, d = view.project([moon])
    rv = math.tan(math.radians(ang_size_deg / 2.0 + margin_deg)) / (2.0 * view.tv)
    return float(u[0]), float(v[0]), rv / ASPECT, rv, float(d[0])


# ---- pillars -------------------------------------------------------------------------------------------------

def _band_limit(view, s, rect, top_z, star_depth=None):
    """The highest top (z) pillar spec ``s`` may keep so it stays out of ``rect`` (u0, v0, u1, v1) in ``view``, or
    None when it never enters it. A pillar is a vertical band from its top down, top_r wide."""
    u, v, d = view.project([(s["x"], s["y"], top_z)])
    u, v, d = float(u[0]), float(v[0]), float(d[0])
    if d <= 1.0:
        return None
    if star_depth is not None and d < star_depth + STAR_DEPTH_PAD:
        return None
    hw = float(view.half_u(s["top_r"], d))
    u0, v0, u1, v1 = rect
    if u + hw < u0 - SKY_MARGIN_U or u - hw > u1 + SKY_MARGIN_U:
        return None
    if v >= v1 + SKY_MARGIN_V:
        return None
    z = view.z_at_v(s["x"], s["y"], min(0.999, v1 + SKY_MARGIN_V))
    return z


def _moon_limit(view, s, top_z, disc):
    mu, mv, ru, rv, md = disc
    if md <= 0:
        return None
    u, v, d = view.project([(s["x"], s["y"], top_z)])
    u, v, d = float(u[0]), float(v[0]), float(d[0])
    if d <= 1.0:
        return None
    hw = float(view.half_u(s["top_r"], d)) + SKY_MARGIN_U
    du = 0.0 if (u - hw) <= mu <= (u + hw) else min(abs(u - hw - mu), abs(u + hw - mu))
    if du >= ru:
        return None
    bottom = mv + rv * math.sqrt(max(0.0, 1.0 - (du / ru) ** 2))
    if v >= bottom + SKY_MARGIN_V:
        return None
    return view.z_at_v(s["x"], s["y"], min(0.999, bottom + SKY_MARGIN_V))


def peak_limits(plan, views, intent, star=None, moon=None, log=print):
    """{peak: highest allowed pillar top z} for the pillar plan (Range.pillar_plan(): x, y, top_z, top_r per peak)
    from the intent rules at the views (View list named by hold or 'f<frame>'). ``star``: {hold: dict(u0, u1, v_top,
    depth)} (star_boxes) for the skyline rule; ``moon``: world xyz of the moon's centre. Returns (limits, rows)."""
    holds = intent["holds"]
    flights = {"f%d" % f["frame"]: f for f in intent["flights"]}
    limits, rows = {}, []
    conflicts = []

    def cut(k, z, why, view=None, moon_rule=False):
        if z is None:
            return
        s = plan[k]
        if view is not None:
            d = float(np.linalg.norm(np.array([s["x"], s["y"], s["top_z"]]) - view.pos))
            if d > (MOON_MAX_D if moon_rule else QUIET_MAX_D):
                return
        share = (s["top_z"] - z) / max(1.0, s["top_z"] - s.get("plinth", s["top_z"] - 100.0))
        if share > (MOON_CUT_SHARE_MAX if moon_rule else CUT_SHARE_MAX):
            conflicts.append(dict(peak=k, z=round(z, 1), why=why, share=round(share, 2)))
            return
        if k not in limits or z < limits[k]:
            limits[k] = z
        rows.append(dict(peak=k, z=round(z, 1), why=why))
    for view in views:
        h = holds.get(view.name)
        f = flights.get(view.name)
        exempt = set(h.get("exempt_peaks", [])) if h else set()
        if h and h.get("host", {}).get("kind") == "peak":
            exempt.add(int(h["host"]["index"]))
        quiet = (h or {}).get("quiet", [])
        keep_n = (h or {}).get("quiet_keep", 0)
        for qi, rect in enumerate(quiet):
            hits = []
            for k, s in plan.items():
                if k in exempt:
                    continue
                z = _band_limit(view, s, rect, s["top_z"])
                if z is not None:
                    d = float(view.project([(s["x"], s["y"], s["top_z"])])[2][0])
                    hits.append((float(view.px(2 * s["top_r"], d)), k, z))
            hits.sort(reverse=True)
            for _px, k, z in hits[keep_n:]:
                cut(k, z, "%s quiet %d" % (view.name, qi), view)
        if h and h.get("skyline") and star and view.name in star:
            sb = star[view.name]
            rect = (sb["u0"], 0.0, sb["u1"], sb["v_top"])
            for k, s in plan.items():
                if k not in exempt:
                    cut(k, _band_limit(view, s, rect, s["top_z"], star_depth=sb["depth"]), "%s skyline" % view.name,
                        view)
        want_moon = (h or {}).get("moon") == "clear" or (f or {}).get("moon") == "clear" or \
            (view.name == "f%d" % intent.get("frames_poster", 27))
        if want_moon and moon is not None:
            disc = moon_disc(view, moon)
            for k, s in plan.items():
                if k not in exempt:
                    cut(k, _moon_limit(view, s, s["top_z"], disc), "%s moon" % view.name, view, moon_rule=True)
    for k in sorted(limits):
        log("COMPOSE pillar %d top %.1f -> at most %.1f (%s)" % (k, plan[k]["top_z"], limits[k],
                                                                ", ".join(sorted({r["why"] for r in rows
                                                                                  if r["peak"] == k}))))
    for c in conflicts:
        log("COMPOSE conflict: pillar %d would need its top at %.1f for %s (%.0f %% of its height): left as it is"
            % (c["peak"], c["z"], c["why"], 100 * c["share"]))
    return limits, rows + [dict(c, conflict=True) for c in conflicts]


# ---- islands ---------------------------------------------------------------------------------------------------

def _in_rect(u, v, rect):
    return rect[0] <= u <= rect[2] and rect[1] <= v <= rect[3]


def island_visibility(islands, views, max_dist=2200.0, min_px=6.0):
    """{view name: [(island index, u, v, depth, px, cut by the frame edge)]} of the islands each view shows (centre in
    the frame widened by its own radius, nearer than max_dist, at least min_px tall)."""
    C = np.array([i["c"] for i in islands], float)
    S = np.array([i["size"] for i in islands], float)
    out = {}
    for view in views:
        u, v, d = view.project(C)
        hw = view.half_u(S * 0.5, d)
        hv = hw * ASPECT
        px = view.px(S, d)
        ok = (d > 1.0) & (d < max_dist) & (px >= min_px) & (u + hw > 0) & (u - hw < 1) & (v + hv > 0) & (v - hv < 1)
        cut = (u - hw < 0) | (u + hw > 1) | (v - hv < 0) | (v + hv > 1)
        out[view.name] = [(int(i), float(u[i]), float(v[i]), float(d[i]), float(px[i]), bool(cut[i]))
                          for i in np.nonzero(ok)[0]]
    return out


def cull_islands(islands, views, intent, star=None, log=print):
    """Indices of ``islands`` (dicts: name, c, size, kind 'island' | 'islet', protected) to remove, with reasons.
    ``views``: the hold views (named by hold) and the flight sample (named 'f<frame>'); ``star``: star_boxes."""
    fd = intent.get("flight_default", {})
    vis = island_visibility(islands, views, fd.get("max_dist", 2200.0), fd.get("min_px", 6.0))
    holds = intent["holds"]
    flights = {"f%d" % f["frame"]: f for f in intent["flights"]}
    gone = {}

    def drop(i, why):
        if islands[i].get("protected"):
            return False
        if i not in gone:
            gone[i] = why
        return True
    for name, h in holds.items():
        seen = vis.get(name, [])
        isl = h.get("islets", {"max": 7})
        mx = int(isl.get("max", 7))
        zone = isl.get("zone")
        sb = (star or {}).get(name)
        cand = []
        for (i, u, v, d, px, cut) in seen:
            if islands[i].get("protected"):
                continue
            bad = None
            if sb is not None:
                m = min(0.08, 0.25 * max(0.05, sb["u1"] - sb["u0"]))
                if sb["u0"] - m < u < sb["u1"] + m and sb["v_top"] - 0.06 < v < sb.get("v_bot", 1.0):
                    bad = "near the star"
            if bad is None and zone is not None and not _in_rect(u, v, zone):
                bad = "outside the zone"
            if bad is None and d < isl.get("min_dist", 0.0):
                bad = "too near"
            if bad is None and any(_in_rect(u, v, q) for q in h.get("quiet", [])) and \
                    not (zone is not None and _in_rect(u, v, zone)):
                bad = "in quiet sky"
            if bad is not None:
                drop(i, "%s: %s" % (name, bad))
            else:
                cand.append((px, i))
        cand.sort(reverse=True)
        kept = []
        for px, i in cand:
            if len(kept) >= mx or any(abs(px - q) < NO_TWIN * max(px, q) for q in kept):
                drop(i, "%s: over its %d islets or a twin" % (name, mx))
            else:
                kept.append(px)
    for name in sorted(vis, key=lambda n: (n[0] != "f", n)):
        if name in holds:
            continue
        f = flights.get(name, {})
        mx = int(f.get("islets_max", fd.get("islets_max", 7)))
        seen = [x for x in vis[name] if x[0] not in gone and not islands[x[0]].get("protected")]
        for (i, u, v, d, px, cut) in list(seen):
            if any(_in_rect(u, v, q) for q in f.get("no_islets", [])):
                drop(i, "%s: in its no-islet band" % name)
            elif f.get("no_edge_cut") and cut and px > 40.0:
                drop(i, "%s: cut by the frame" % name)
        seen = [x for x in seen if x[0] not in gone]
        n_prot = sum(1 for x in vis[name] if islands[x[0]].get("protected"))
        if len(seen) + n_prot > mx:
            for (i, u, v, d, px, cut) in sorted(seen, key=lambda x: x[4])[:len(seen) + n_prot - mx]:
                drop(i, "%s: over %d islets in the frame" % (name, mx))
    seen_n = {}
    for name, lst in vis.items():
        for x in lst:
            seen_n[x[0]] = seen_n.get(x[0], 0) + 1
    tg = intent.get("targets", {})
    for kind, key in (("island", "scenery_islands"), ("islet", "world_islets")):
        want = tg.get(key)
        if want is None:
            continue
        left = [i for i, s in enumerate(islands) if s["kind"] == kind and i not in gone and not s.get("protected")]
        if len(left) > want:
            left.sort(key=lambda i: (seen_n.get(i, 0), islands[i]["size"]))
            for i in left[:len(left) - want]:
                drop(i, "over the %s target (%d), seen in %d sampled frames" % (kind, want, seen_n.get(i, 0)))
    log("COMPOSE islands: %d of %d go (%s)" % (len(gone), len(islands), ", ".join(
        "%s %d" % (k, sum(1 for i in gone if islands[i]["kind"] == k)) for k in ("island", "islet"))))
    return gone, vis


def cull_falls(falls, views, intent, kept_islands=None, log=print):
    """Indices of ``falls`` (dicts: name, lip, foot, island (rock name or None), location (bool)) to remove: every
    fall the no-fall holds show, every fall of a removed island, and island falls past the share target (those seen
    least go first). Returns (gone {index: reason}, keep [indices])."""
    nofall = set(intent.get("no_fall_holds", []))
    share = intent.get("targets", {}).get("island_fall_share", 0.25)
    gone = {}
    seen_n = {}
    for view in views:
        for i, fl in enumerate(falls):
            P = np.array([fl["lip"], fl["foot"]], float)
            u, v, d = view.project(P)
            if (d <= 1.0).all() or (d > 2200.0).all():
                continue
            ins = (d > 1.0) & (u > -0.05) & (u < 1.05) & (v > -0.05) & (v < 1.05)
            if not ins.any():
                continue
            seen_n[i] = seen_n.get(i, 0) + 1
            if view.name in nofall and not fl.get("location"):
                gone.setdefault(i, "seen in the %s hold" % view.name)
    for i, fl in enumerate(falls):
        if fl.get("island") and kept_islands is not None and fl["island"] not in kept_islands and not fl.get("location"):
            gone.setdefault(i, "its island goes")
    isl = [i for i, fl in enumerate(falls) if fl.get("island") and i not in gone and not fl.get("location")]
    n_isl = len(kept_islands) if kept_islands is not None else len(isl)
    want = int(round(share * n_isl))
    if len(isl) > want:
        isl.sort(key=lambda i: -seen_n.get(i, 0))
        for i in isl[want:]:
            gone.setdefault(i, "over the island fall share (%d of %d islands)" % (want, n_isl))
    keep = [i for i in range(len(falls)) if i not in gone]
    log("COMPOSE falls: %d of %d go, %d stay" % (len(gone), len(falls), len(keep)))
    return gone, keep
