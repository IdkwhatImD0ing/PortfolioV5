"""Audit D2 (2026-10-21): stop composition in out/sect_chase.blend, the way sect/areas/scroll.py and sect/scenery.py
now build it. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r2_compose.py [-- DRY_RUN=1]

Object transforms only; nothing is added, removed, renamed or reshaped:
- 1103 (Jade Slip Pavilion): about half the jade scroll lay off the frame's left edge. scroll.jade_scroll turns
  scroll.SCROLL_YAW (-40 deg), scales to SCROLL_SCALE (0.9) and moves to SCROLL_C (6 m right, 10 m back); its two
  rune rings and its motes move with it (scroll.ring, scroll.ring_in, scroll.motes).
- 772 (library): scenery.island.092 sat on the pagoda's spire; 1647 (summit): scenery.island.052 stood between the
  pavilion's finial and the moon. Each moves by scenery.ISLAND_NUDGES with its companions (scenery.island_companions:
  its top pines, blossoms and fall, which are not its children).

Guards (nothing is saved when one fails): each object is where the old build put it, or already where the new one
does (then it is left: idempotent); the flight (chase.cam, every frame) stays at least SCROLL_CLEAR m from the scroll's
box and ISLAND_CLEAR m from each moved island's; at its hold frame the scroll is on screen (ON_SCREEN of its vertices)
and the islands' boxes are clear of the protected screen boxes (the spire; the finial and the moon).

Afterwards: export_web audit (the hotspot 'resume' box and the islands' visibility change), chunks,meta, bakefull
scroll, library, summit, the chunks of the islands (see cmp_chunks) and backdrop, then the pack.
"""
import ast
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402

CAM = "chase.cam"
TOL = 0.05
OLD_SCROLL_C = (-10.0, -4.0, 13.0)                  # scroll.py before D2
RING_DY = 1.0                                       # scroll._scroll: the rings sit at (cx, cy + 1, 0)
ISLAND_FROM = {"scenery.island.092": (276.33, 826.66, 285.07), "scenery.island.052": (125.6, 1865.44, 388.34)}
SCROLL_CLEAR = 18.0
ISLAND_CLEAR = 120.0
ON_SCREEN = 0.97
RES = (1600, 900)
SC_HOLD = 1103                                      # the scroll's hold frame (export_web full profile)
# (hold frame, object, protected screen boxes [x0, x1, y0, y1] in a 1600 x 900 frame)
HOLD_CHECKS = ((772, "scenery.island.092", [[700, 940, -1e9, 240]]),
               (1647, "scenery.island.052", [[862, 1258, 520, 1e9], [975, 1366, 136, 517]]),
               (1380, "scenery.island.052", [[-1e9, 300, -1e9, 1e9], [1150, 1e9, -1e9, 1e9]]))   # the abode's open sky


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(dry=False)
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            opt["dry"] = bool(ast.literal_eval(v))
        else:
            raise SystemExit("patch_r2_compose: unknown argument %r (DRY_RUN=1)" % a)
    return opt


def close(a, b, tol=TOL):
    return max(abs(float(x) - float(y)) for x, y in zip(a, b)) <= tol


def state(ob, old, new, turn=True):
    """'old' / 'new' when ``ob``'s (location, rotation z, scale) matches one of the two, else None. ``turn`` False:
    location only (the rune rings spin about z on their own)."""
    cur = (tuple(ob.location), ob.rotation_euler.z, ob.scale.x)
    for tag, want in (("old", old), ("new", new)):
        if close(cur[0], want[0]) and (not turn or (abs(cur[1] - want[1]) < 1e-3 and abs(cur[2] - want[2]) < 1e-3)):
            return tag
    return None


def tree_box(ob):
    pts = []
    for x in [ob] + list(ob.children_recursive):
        if x.type in ('MESH', 'CURVE'):
            pts += [tuple(x.matrix_world @ Vector(c)) for c in x.bound_box]
    P = np.array(pts)
    return P.min(0), P.max(0)


def path_clearance(sc, cam, lo, hi):
    best = (1e9, None)
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        c = np.array(cam.matrix_world.translation)
        d = float(np.linalg.norm(np.maximum(np.maximum(lo - c, c - hi), 0.0)))
        if d < best[0]:
            best = (d, f)
    return best


def screen_box(sc, cam, lo, hi):
    q = []
    for c in [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]:
        v = world_to_camera_view(sc, cam, Vector(c))
        q.append((v.x * RES[0], (1 - v.y) * RES[1], v.z))
    q = np.array(q)
    return [float(q[:, 0].min()), float(q[:, 0].max()), float(q[:, 1].min()), float(q[:, 1].max())], bool((q[:, 2] > 0).all())


def on_screen(sc, cam, ob):
    """Share of the vertices of ``ob`` and its children inside the frame."""
    dg = bpy.context.evaluated_depsgraph_get()
    n = inside = 0
    for x in [ob] + list(ob.children_recursive):
        if x.type != 'MESH':
            continue
        e = x.evaluated_get(dg)
        me = e.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        e.to_mesh_clear()
        M = x.matrix_world
        for c in co.reshape(-1, 3)[::7]:
            p = world_to_camera_view(sc, cam, M @ Vector(c))
            n += 1
            inside += (0.0 <= p.x <= 1.0) and (0.0 <= p.y <= 1.0) and p.z > 0
    return inside / max(n, 1)


def main():
    opt = options()
    sc = bpy.context.scene
    keep = (sc.frame_current, sc.render.resolution_x, sc.render.resolution_y)
    sc.render.resolution_x, sc.render.resolution_y = RES
    cam = bpy.data.objects.get(CAM)
    if cam is None:
        raise SystemExit("patch_r2_compose: no %s; is this out/sect_chase.blend?" % CAM)
    # ---- 1103: the jade scroll
    dx, dy = SC.SCROLL_C[0] - OLD_SCROLL_C[0], SC.SCROLL_C[1] - OLD_SCROLL_C[1]
    plan = {
        "scroll.jade_scroll": ((OLD_SCROLL_C, 0.0, 1.0), (SC.SCROLL_C, SC.SCROLL_YAW, SC.SCROLL_SCALE)),
    }
    for nm in ("scroll.ring", "scroll.ring_in"):
        o0 = (OLD_SCROLL_C[0], OLD_SCROLL_C[1] + RING_DY, 0.0)
        plan[nm] = ((o0, 0.0, 1.0), ((o0[0] + dx, o0[1] + dy, 0.0), 0.0, 1.0))
    plan["scroll.motes"] = (((0.0, 0.0, 0.0), 0.0, 1.0), ((dx, dy, 0.0), 0.0, 1.0))
    for nm, (old, new) in plan.items():
        ob = bpy.data.objects.get(nm)
        if ob is None:
            raise RuntimeError("%s not found" % nm)
        if ob.parent is None or ob.parent.name != "scroll.root":
            raise RuntimeError("%s is not under scroll.root" % nm)
        turn = nm == "scroll.jade_scroll"
        st = state(ob, old, new, turn)
        if st is None:
            raise RuntimeError("%s is neither where the old build put it nor where the new one does: loc %s rot z %.3f "
                               "scale %.3f" % (nm, tuple(round(c, 3) for c in ob.location), ob.rotation_euler.z,
                                               ob.scale.x))
        if st == "new":
            log(nm, "already in place")
            continue
        ob.location = new[0]
        if turn:
            ob.rotation_euler.z = new[1]
            ob.scale = (new[2],) * 3
        log("moved", nm, "to", tuple(round(c, 2) for c in new[0]), "rot z %.1f deg scale %.2f"
            % (math.degrees(new[1]), new[2]))
    # ---- 772 / 1647: the islands
    for nm, off in S.ISLAND_NUDGES.items():
        rock = bpy.data.objects.get(nm)
        if rock is None:
            raise RuntimeError("%s not found" % nm)
        p0 = ISLAND_FROM[nm]
        p1 = tuple(a + b for a, b in zip(p0, off))
        if close(rock.location, p1):
            log(nm, "already in place")
            continue
        if not close(rock.location, p0):
            raise RuntimeError("%s is at %s, not %s" % (nm, tuple(round(c, 2) for c in rock.location), p0))
        moved = S.nudge_islands({nm: off})
        log("moved", nm, "by", off, "with", moved.get(nm))
    bpy.context.view_layer.update()
    # ---- checks
    js = bpy.data.objects["scroll.jade_scroll"]
    lo, hi = tree_box(js)
    d, f = path_clearance(sc, cam, lo, hi)
    log("scroll box", lo.round(1).tolist(), hi.round(1).tolist(), "flight clearance %.1f m (frame %d)" % (d, f))
    if d < SCROLL_CLEAR:
        raise RuntimeError("the flight passes %.1f m from the scroll (< %.1f)" % (d, SCROLL_CLEAR))
    hold = SC_HOLD
    sc.frame_set(hold)
    share = on_screen(sc, cam, js)
    box, _ = screen_box(sc, cam, lo, hi)
    log("hold %d: the scroll's box spans x %.0f..%.0f y %.0f..%.0f of 1600 x 900; %.0f%% of its vertices on screen"
        % (hold, box[0], box[1], box[2], box[3], 100.0 * share))
    if share < ON_SCREEN:
        raise RuntimeError("only %.0f%% of the scroll on screen at %d" % (100.0 * share, hold))
    for hold, nm, protect in HOLD_CHECKS:
        lo, hi = tree_box(bpy.data.objects[nm])
        d, f = path_clearance(sc, cam, lo, hi)
        sc.frame_set(hold)
        box, front = screen_box(sc, cam, lo, hi)
        off = box[1] < 0 or box[0] > RES[0] or box[3] < 0 or box[2] > RES[1]
        hit = [p for p in protect if front and not off and box[0] < p[1] and p[0] < box[1] and box[2] < p[3]
               and p[2] < box[3]]
        log("hold %d: %s box x %.0f..%.0f y %.0f..%.0f; flight clearance %.1f m (frame %d)"
            % (hold, nm, box[0], box[1], box[2], box[3], d, f))
        if hit or d < ISLAND_CLEAR:
            raise RuntimeError("%s: overlaps %s on screen / %.1f m from the flight" % (nm, hit, d))
    log("TRANSFORMS ONLY: export_web audit + chunks,meta (hotspot 'resume' moved), then bakefull scroll, library, "
        "summit, the islands' chunks and backdrop")
    # the checks scrubbed the timeline: save the file at its own frame (352) and render size, as it came
    sc.frame_set(keep[0])
    sc.render.resolution_x, sc.render.resolution_y = keep[1], keep[2]
    if opt["dry"]:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
