"""Turn the Jade Slip Pavilion's great jade scroll to face the reader at the hold (round 10, lane 'scroll'): bring an
existing out/sect_chase.blend to the design in sect/areas/scroll.py and save it. Run on the cloud box (on a copy first):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r10_scroll_face.py [-- DRY_RUN=1]

Why (owner, 2026-10-22): "The jade slip does not seem to be facing the user when the user gets to the scene." Audit D2
(patch_r2_compose.py) stood it at (-4, 6, 13), 0.9x, turned -40 deg so it fit the 1103 frame: its face was ~30 deg off
square to the hold view. The site shows the hold turned 6 deg left (client framing.ts STOP_FRAMING.scroll, mirrored as
scroll.HOLD_TURN / hold_turn). Square to that turned view (its face parallel to the picture, so both ends are equally
tall) it is wider on screen, so to stay whole in the frame, clear of the pavilion at the hold and never over it on the
approach it moves back and shrinks (scroll.SCROLL_C, SCROLL_SCALE: the largest that fits) and turns to
scroll.SCROLL_YAW (scroll.HOLD_HEADING + the turn - 90 deg).

What it does (a fresh build makes the same through scroll.build); everything that belongs to the scroll display moves
together, nothing else is touched:
1. scroll.jade_scroll (the 'resume' hotspot; its meshes untouched): location, turn and scale to SCROLL_C, SCROLL_YAW,
   SCROLL_SCALE.
2. The standing frame (Empty scroll.scroll_frame and .posts / .rails / .bases / .emblems, tagged scroll.FRAME_ITEM) is
   REBUILT with scroll.scroll_frame: its posts' length follows the scroll's height and scale, their place along the arc
   the rings. The previous frame objects and their meshes are removed first; the new ones get the same names.
3. The rune rings scroll.ring (with its child .groove) and scroll.ring_in move to scroll.RING_C and take the object
   scale scroll.RING_K in x and y (z 1: they keep their 8 mm lift; same meshes; their spin drivers keep turning them).
4. scroll.motes (one point instancer whose points the first build made around (-10, -4), up to z 19) moves by the
   scroll's shift: location (SCROLL_C x + 10, SCROLL_C y + 4, 0); scroll.MOTES_TOP keeps a fresh build's points equal.
Idempotent: the file must be in the r5/r8 state (the r2 placement) or already in this one; a re-run rebuilds the frame
again and sets the same transforms.

Checks before saving (it stops without saving when one fails): names exact (no '.001') and the object count unchanged;
every frame mesh closed; the sill and the top rail meet the slips; each post's plinth stands between the two ring bands
(scroll.ring_bands); the frame's feet stand on the terrace (rays straight down from each plinth's corners meet the
paving within 2 cm); the rings lie on the terrace, off the axis walk, and nothing standing on the paving sits on a band;
no scene piece cuts into the scroll or its frame (BVH overlap; only the paving under the sunk plinths is allowed); the
flight (chase.cam, every frame) stays FLIGHT_CLEAR m from the display's box. Every view check uses the view the site
shows (site_view: chase.cam turned by scroll.hold_turn, the client's field of view for the screen size). chase.cam at
the hold must still be at scroll.HOLD_CAM / HOLD_HEADING. At the hold (1103), at 1600 x 900 and 1366 x 768: the scroll's
face is square to the turned view (plan within FACE_PLAN_MAX deg, 3D within FACE_3D_MAX), the scroll, the rails and the
emblems are wholly in frame (MARGIN_PX from the edges), every slip is in frame and a character cell is at least
MIN_CELL_PX tall (scaled with the screen), and the display keeps PAV_GAP_PX (scaled) left of the pavilion's silhouette
row by row; on the approach (1056-1102, the turn easing in) it never overlaps the pavilion on screen. It logs the
approach and departure framing too.

Caches: the scroll, its frame and the rings change boxes (the frame also its meshes), so it prints 'PATCH CACHES needs
audit': run the export_web audit, then chunks,meta (the 'resume' hotspot box moves), then bakefull the scroll chunk (and
whatever chunks the audit's cmp_chunks reports changed, at least the backdrop), then the pack.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402

AREA_ROOT = SC.K + ".root"
SCROLL = SC.K + ".jade_scroll"
RINGS = (SC.K + ".ring", SC.K + ".ring_in")
MOTES = SC.K + ".motes"
CAM = "chase.cam"
HOLD = 1103
APPROACH = tuple(range(1056, 1103, 2))
DEPART = (1106, 1110, 1116, 1120, 1126)
RES = (1600, 900)                  # the film's frame (the web's reference aspect)
RES_SMALL = (1366, 768)            # a common laptop screen: same aspect, so the same picture 0.85x smaller
TOL = 1e-3
# the r5 / r8 file: r2's placement
OLD = dict(c=(-4.0, 6.0, 13.0), yaw=math.radians(-40.0), s=0.9, ring=(-4.0, 7.0), ring_s=1.0, motes=(6.0, 10.0))
MOTES_BUILT_C = (-10.0, -4.0)      # the motes' points were made around this (cx, cy) by the first build (r2 moved them)
FACE_PLAN_MAX = 1.0                # deg off square to the turned hold view, in plan
FACE_3D_MAX = 2.0                  # deg in 3D (the hold view looks down 0.6 deg)
MARGIN_PX = 12                     # from the frame's edges, at either screen size
PAV_GAP_PX = 20                    # at 1600 x 900 (scaled for the smaller screen)
MIN_CELL_PX = 11.0                 # at 1600 x 900 (scaled)
FLIGHT_CLEAR = 18.0
NEAR = 0.3
CLASH_OK = ("scroll.terrace",)     # the plinths sink 0.12 m into the paving by design


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r10_scroll_face: unknown option %r (DRY_RUN=1)" % a)
    return dry


def new_state():
    k = SC.RING_K
    return dict(c=tuple(SC.SCROLL_C), yaw=SC.SCROLL_YAW, s=SC.SCROLL_SCALE, ring=tuple(SC.RING_C), ring_s=k,
                motes=(SC.SCROLL_C[0] - MOTES_BUILT_C[0], SC.SCROLL_C[1] - MOTES_BUILT_C[1]))


def close(a, b, tol=TOL):
    return max(abs(float(x) - float(y)) for x, y in zip(a, b)) <= tol


def which(ob, key, states):
    """'old' / 'new' when ob matches that state's transform for ``key`` ('scroll', 'ring', 'motes'), else None."""
    for tag, st in states.items():
        if key == "scroll":
            ok = close(ob.location, st["c"]) and abs(ob.rotation_euler.z - st["yaw"]) < 1e-4 and \
                close(ob.scale, (st["s"],) * 3, 1e-4) and close(ob.rotation_euler[:2], (0.0, 0.0), 1e-6)
        elif key == "ring":
            ok = close(ob.location, (st["ring"][0], st["ring"][1], 0.0)) and \
                close(ob.scale, (st["ring_s"], st["ring_s"], 1.0), 1e-4)
        else:
            ok = close(ob.location, (st["motes"][0], st["motes"][1], 0.0)) and close(ob.scale, (1.0,) * 3)
        if ok:
            return tag
    return None


def frame_names():
    return [SC.FRAME] + [SC.FRAME + "." + p for p in ("posts", "rails", "bases", "emblems")]


def remove_frame():
    """Remove the frame (tagged objects or the frame names, with their children) and free their meshes."""
    want = set(frame_names())
    obs = [o for o in bpy.data.objects if o.get("sect_item") == SC.FRAME_ITEM or o.name in want]
    for o in list(obs):
        obs.extend(c for c in o.children_recursive if c not in obs)
    gone, meshes = [], set()
    for o in sorted(obs, key=lambda o: -len(o.children_recursive)):
        if o.name not in bpy.data.objects:
            continue
        if o.type == 'MESH' and o.data is not None:
            meshes.add(o.data.name)
        gone.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if m.users == 0 and (m.name in meshes or any(m.name == w or m.name.startswith(w + ".") for w in want)):
            bpy.data.meshes.remove(m)
    return sorted(gone)


def open_edges(me):
    cnt = {}
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            k = (a, b) if a < b else (b, a)
            cnt[k] = cnt.get(k, 0) + 1
    return sum(1 for e in me.edges if cnt.get(tuple(sorted(e.vertices)), 0) < 2)


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def world_pts(ob, step=1):
    n = len(ob.data.vertices)
    co = np.empty(n * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)[::step]
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def world_box(ob):
    if ob.type != 'MESH' or not len(ob.data.vertices):
        return None
    P = world_pts(ob)
    return tuple(np.round(P.min(0), 3).tolist()), tuple(np.round(P.max(0), 3).tolist())


def inst_box(ob):
    """World box of an object's own mesh, or of the evaluated instances it carries (point instancers, rings)."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob and inst.object.type == 'MESH':
            M = inst.matrix_world
            pts += [M @ Vector(c) for c in inst.object.bound_box]
    if not pts and ob.type == 'MESH' and len(ob.data.vertices):
        P = world_pts(ob)
        return tuple(np.round(P.min(0), 3).tolist()), tuple(np.round(P.max(0), 3).tolist())
    if not pts:
        return None
    return (tuple(round(min(p[k] for p in pts), 3) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 3) for k in range(3)))


def inside(box, outer, tol=1e-3):
    return all(box[0][k] >= outer[0][k] - tol and box[1][k] <= outer[1][k] + tol for k in range(3))


def top_under(o, root):
    """The child of ``root`` that owns ``o`` (o itself, or its ancestor), or None when o is not in the area."""
    while o is not None and o.parent is not None and o.parent != root:
        o = o.parent
    return o if o is not None and o.parent == root else None


def area_points(root, tops=None, n=300):
    """{top-level owner under root: world points} of every mesh the area shows (evaluated instances included), about
    ``n`` points per mesh; only owners in ``tops`` when given. The points are taken inside the depsgraph walk: its
    instance objects are not valid after it."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent is not None else o.original
        top = top_under(src, root)
        if top is None or (tops is not None and top.name not in tops):
            continue
        me = o.data
        k = len(me.vertices)
        if not k:
            continue
        co = np.empty(k * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)[::max(1, k // n)]
        A = np.array(inst.matrix_world)
        out.setdefault(top.name, []).append(co @ A[:3, :3].T + A[:3, 3])
    return {k: np.concatenate(v) for k, v in out.items()}


def site_view(sc, cam, f, res=RES):
    """The view the site shows at path frame ``f`` on a res[0] x res[1] screen: chase.cam's place and orientation there,
    turned by the client's stop framing (scroll.hold_turn: yaw about world up, then pitch about the view's own right
    axis, as free-look.ts composeLook), with the client's field of view for that screen (camera-path.ts fovForAspect:
    the film's vertical FOV, widened only to keep its horizontal FOV on screens narrower than the film)."""
    sc.frame_set(f)
    M = cam.matrix_world
    yaw, pitch = SC.hold_turn(f)
    R = Matrix.Rotation(yaw, 3, 'Z') @ M.to_3x3().normalized() @ Matrix.Rotation(pitch, 3, 'X')
    film = RES[0] / RES[1]
    tx_film = cam.data.sensor_width / 2.0 / cam.data.lens          # sensor fit AUTO, landscape: horizontal
    aspect = res[0] / res[1]
    ty = max(tx_film / film, tx_film / aspect)
    return dict(loc=np.array(M.translation), R=np.array(R), tx=ty * aspect, ty=ty, res=res, f=f, yaw=yaw)


def project(view, P):
    """World points -> (x px, y px from the top, depth) on the view's screen."""
    L = (np.asarray(P, dtype=float) - view["loc"]) @ view["R"]
    depth = -L[:, 2]
    d = np.where(np.abs(depth) < 1e-9, 1e-9, depth)
    W, H = view["res"]
    return np.stack([(1.0 + L[:, 0] / (d * view["tx"])) * W / 2.0, (1.0 - L[:, 1] / (d * view["ty"])) * H / 2.0,
                     depth], -1)


# ---- checks -----------------------------------------------------------------------------------------------------------
def frame_fit_check(fails):
    """The sill's top and the top rail's bottom meet the slips (scroll frame z, unscaled) (patch_r5_scroll)."""
    js = bpy.data.objects[SCROLL]
    sl = [c for c in js.children if c.type == 'MESH' and c.name.startswith(SCROLL + ".slips")]
    fr = bpy.data.objects[SC.FRAME]
    Mi = fr.matrix_world.inverted()
    zs = [(Mi @ (o.matrix_world @ v.co)).z for o in sl for v in o.data.vertices]
    lv = SC._frame_levels()
    d0, d1 = min(zs) - lv["sill"][1], lv["top"][0] - max(zs)
    ok = abs(d0) < 0.02 and abs(d1) < 0.02
    log("frame fit: slips z %.3f .. %.3f (scroll frame); gap to the sill top %.3f, to the top rail %.3f" % (
        min(zs), max(zs), d0, d1), "ok" if ok else "BAD")
    if not ok:
        fails.append("frame does not meet the slips")


def post_plinth_check(fails):
    (t0, t1), (s0, s1) = SC.ring_bands()
    lo, hi = t1 + 0.02, s0 - 0.02
    fp = SC.frame_points()
    zg = SC._ground_z()
    for side, a in ((-1, fp["a_l"]), (1, fp["a_r"])):
        off = SC.FRAME_POST_GAP + SC.FRAME_POST_R
        x, y = SC._arc_xy(a, off)
        tang = (math.cos(a), -math.sin(a))
        back = (math.sin(a), math.cos(a))
        w, d = SC.FRAME_PLINTH[0] / 2.0, SC.FRAME_PLINTH[1] / 2.0
        rs = []
        for su in (-1, 1):
            for sv in (-1, 1):
                q = (x + su * w * tang[0] + sv * d * back[0], y + su * w * tang[1] + sv * d * back[1], zg)
                X, Y, _ = SC.scroll_to_root(q)
                rs.append(math.hypot(X - SC.RING_C[0], Y - SC.RING_C[1]))
        ok = lo <= min(rs) and max(rs) <= hi
        log("post", "left" if side < 0 else "right", "arc angle %.2f deg (%.0f %% of the half width), at x %.2f "
            "(scroll frame)" % (math.degrees(a), 100.0 * abs(a) / SC._arc()[1], x),
            "plinth corners %.2f .. %.2f m from the ring centre (free paving %.2f .. %.2f)" % (min(rs), max(rs), lo, hi),
            "ok" if ok else "ON A RING BAND")
        if not ok:
            fails.append("post plinth on a ring band")


def ground_check(root, fails, tol=0.02):
    """Rays straight down from each plinth's four corners (pulled 5 cm in) meet the paving within ``tol`` of the
    plinth's bottom (the rings' bands lie flush on it, so a ring hit counts as paving)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    M, Mi = root.matrix_world, root.matrix_world.inverted()
    down = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    skip = set(frame_names()) | {SCROLL} | {c.name for c in bpy.data.objects[SCROLL].children_recursive}
    fp = SC.frame_points()
    zb = SC.scroll_to_root((0.0, 0.0, SC._ground_z() - SC.FRAME_PLINTH[3]))[2]   # plinth bottom (root z)
    bad = []
    for side, a in ((-1, fp["a_l"]), (1, fp["a_r"])):
        off = SC.FRAME_POST_GAP + SC.FRAME_POST_R
        x, y = SC._arc_xy(a, off)
        tang = (math.cos(a), -math.sin(a))
        back = (math.sin(a), math.cos(a))
        w, d = SC.FRAME_PLINTH[0] / 2.0 - 0.05 / SC.SCROLL_SCALE, SC.FRAME_PLINTH[1] / 2.0 - 0.05 / SC.SCROLL_SCALE
        for su in (-1, 1):
            for sv in (-1, 1):
                X, Y, _ = SC.scroll_to_root((x + su * w * tang[0] + sv * d * back[0],
                                             y + su * w * tang[1] + sv * d * back[1], 0.0))
                o = M @ Vector((X, Y, zb + 0.5))
                hit = None
                for _ in range(8):
                    ok, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, down, distance=3.5)
                    if not ok:
                        break
                    if ob.original.name in skip:
                        o = loc + down * 1e-3
                        continue
                    hit = ((Mi @ loc).z, ob.original.name)
                    break
                if hit is None or not (zb - tol <= hit[0] <= zb + SC.FRAME_PLINTH[3] * SC.SCROLL_SCALE + tol):
                    bad.append(((round(X, 2), round(Y, 2)), hit))
    log("ground: plinth bottoms at z %.3f;" % zb, "all 8 plinth corners stand on the paving, ok" if not bad else
        "OFF THE PAVING %s" % bad)
    if bad:
        fails.append("frame feet not on the terrace")


def ring_check(root, fails):
    """The rings lie on the terrace and off the axis walk; nothing standing on the paving sits on a band."""
    (t0, t1), (s0, s1) = SC.ring_bands()
    rx, ry = SC.RING_C
    x0, x1 = SC.TERRACE_X[0] + 0.6, SC.TERRACE_X[1] - 0.6
    y0, y1 = SC.TERRACE_Y[0], SC.TERRACE_Y[1] - 0.6
    walk_x0 = SC.PAV[0] - 2.0
    ok = rx - s1 >= x0 and rx + s1 <= min(x1, walk_x0) and ry - s1 >= y0 and ry + s1 <= y1
    log("rings: centre (%.2f, %.2f), scale %.3f, bands %.2f..%.2f and %.2f..%.2f m; reach x %.2f..%.2f y %.2f..%.2f "
        "(terrace inside the rails x %.1f..%.1f y %.1f..%.1f, axis walk from x %.1f)" % (
            rx, ry, SC.RING_K, t0, t1, s0, s1, rx - s1, rx + s1, ry - s1, ry + s1, x0, x1, y0, y1, walk_x0),
        "ok" if ok else "OFF THE TERRACE / ON THE WALK")
    if not ok:
        fails.append("rings off the terrace or under the walk")
    skip = {SCROLL, SC.FRAME, MOTES, SC.K + ".terrace", SC.K + ".walk", SC.K + ".approach"} | set(RINGS)
    Mi = np.array(root.matrix_world.inverted())
    on = {}
    for top, P in area_points(root, n=3000).items():
        if top in skip:
            continue
        L = P @ Mi[:3, :3].T + Mi[:3, 3]
        L = L[L[:, 2] <= 0.5]               # what stands on the paving: its vertices within 0.5 m of it
        if not len(L):
            continue
        r = np.hypot(L[:, 0] - rx, L[:, 1] - ry)
        for a, b in ((t0, t1), (s0, s1)):
            m = (r > a - 0.05) & (r < b + 0.05)
            if m.any():
                on[top] = round(float(r[m].min()), 2)
    log("rings: pieces standing on a band:", sorted(on.items()) if on else "none, ok")
    if on:
        fails.append("pieces stand on the ring bands: %s" % sorted(on))


def clash_check(display, fails):
    """No scene mesh cuts into the display (BVH overlap), apart from the paving under the plinths; logs every piece
    within NEAR m."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = {o.name for o in display}
    found, cut = [], []
    data = []
    for ob in display:
        P = world_pts(ob)
        bvh = BVHTree.FromPolygons([Vector(p) for p in P], [tuple(p.vertices) for p in ob.data.polygons])
        data.append((ob, P, bvh, P.min(0) - NEAR, P.max(0) + NEAR))
    for inst in dg.object_instances:
        o2 = inst.object
        if o2.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent is not None else o2.original
        if o2.original.name in names or src.name in names or src.name == MOTES:
            continue
        M = inst.matrix_world
        cs = np.array([tuple(M @ Vector(c)) for c in o2.bound_box])
        lo2, hi2 = cs.min(0), cs.max(0)
        hits = [d for d in data if (lo2 <= d[4]).all() and (hi2 >= d[3]).all()]
        if not hits:
            continue
        me = o2.data
        if not len(me.polygons):
            continue
        P2 = [M @ v.co for v in me.vertices]
        bvh2 = BVHTree.FromPolygons(P2, [tuple(p.vertices) for p in me.polygons])
        label = o2.original.name + ("" if not inst.is_instance else " (in %s)" % src.name)
        for ob, P, bvh, lo, hi in hits:
            if bvh.overlap(bvh2):
                if not any(label.startswith(k) for k in CLASH_OK):
                    cut.append((ob.name, label))
                continue
            ds = [h[3] for h in (bvh2.find_nearest(Vector(p), NEAR) for p in P[::3]) if h[0] is not None]
            if ds:
                found.append((round(min(ds), 3), ob.name, label))
    for d, a, b in sorted(set(found)):
        log("near %.3f m: %s - %s" % (d, a, b))
    if not found:
        log("near: nothing within %.1f m of the display" % NEAR)
    log("clash: display pieces cut by scene pieces:", sorted(set(cut)) if cut else "none (the paving under the "
        "plinths is by design), ok")
    if cut:
        fails.append("scene pieces cut into the display: %s" % sorted(set(cut))[:6])


def flight_check(display, fails):
    sc = bpy.context.scene
    cam = bpy.data.objects[CAM]
    P = np.concatenate([world_pts(o) for o in display])
    lo, hi = P.min(0), P.max(0)
    best = (1e9, None)
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        c = np.array(cam.matrix_world.translation)
        d = float(np.linalg.norm(np.maximum(np.maximum(lo - c, c - hi), 0.0)))
        if d < best[0]:
            best = (d, f)
    log("flight: closest %.1f m from the display's box (frame %d)" % best, "ok" if best[0] >= FLIGHT_CLEAR else
        "TOO CLOSE (< %.1f)" % FLIGHT_CLEAR)
    if best[0] < FLIGHT_CLEAR:
        fails.append("the flight passes %.1f m from the scroll" % best[0])


def scroll_dims():
    """props.bamboo_slip_scroll's slip count, characters per slip, cell and arc (patch_r8_scrolltext)."""
    W, H = SC.SCROLL_W, SC.SCROLL_H
    N = max(8, int(round(W / (H * 0.075))))
    pitch = W / N
    cell = pitch * 0.88 * 0.80
    rows = int(H * 0.84 / cell)
    d = max(1e-4, SC.SCROLL_CURVE * W)
    R = (W * W / 4 + d * d) / (2 * d)
    return N, rows, cell, R, math.asin(min(1.0, W / 2 / R))


def cells_at(view, js):
    """(slips wholly in frame, [cell height px of each]) on the view (patch_r8_scrolltext's measure)."""
    N, rows, cell, R, half = scroll_dims()
    M = np.array(js.matrix_world)
    top = rows * cell / 2.0
    W, H = view["res"]
    seen, px = [], []
    for i in range(N):
        a = -half + 2 * half * (i + 0.5) / N
        x, y = R * math.sin(a), -R + R * math.cos(a)
        P = np.array([[x, y, top - 0.5 * cell, 1.0], [x, y, top - 1.5 * cell, 1.0], [x, y, -top + 0.5 * cell, 1.0]])
        q = project(view, (P @ M.T)[:, :3])
        if (q[:, 2] > 0).all() and all(0 <= q[k, 0] <= W and 0 <= q[k, 1] <= H for k in (0, 2)):
            seen.append(i)
            px.append(abs(q[0, 1] - q[1, 1]))
    return seen, px


def facing(view, js):
    """The scroll's front normal (its -Y at the middle of the arc) against the view: (plan, 3D) angles in deg to the
    view's axis reversed (0 = its face parallel to the picture), and the 3D angle to the line from it to the camera."""
    M = js.matrix_world
    n = (M.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    back = Vector(view["R"][:, 2].tolist()).normalized()         # the camera's +Z: the view's axis reversed
    los = (Vector(view["loc"].tolist()) - M.translation).normalized()
    n2, b2 = Vector((n.x, n.y, 0.0)).normalized(), Vector((back.x, back.y, 0.0)).normalized()
    return math.degrees(n2.angle(b2)), math.degrees(n.angle(back)), math.degrees(n.angle(los))


def silhouette_gap(q_disp, q_pav):
    """Smallest (pavilion's leftmost x - display's rightmost x) over the 10 px screen rows both cover (a row's
    pavilion edge is the leftmost of it and its two neighbours); negative = they overlap on screen."""
    rows = {}
    for x, y, z in q_pav:
        if z <= 0:
            continue
        r = int(y // 10)
        rows[r] = min(rows.get(r, 1e9), x)
    best = 1e9
    for x, y, z in q_disp:
        if z <= 0:
            continue
        r = int(y // 10)
        lim = min(rows.get(r + k, 1e9) for k in (-1, 0, 1))
        if lim < 1e9:
            best = min(best, lim - x)
    return best


def in_frame(q, res):
    return (q[:, 0] >= 0) & (q[:, 0] <= res[0]) & (q[:, 1] >= 0) & (q[:, 1] <= res[1]) & (q[:, 2] > 0)


def hold_and_flight_view(root, display, fails):
    sc = bpy.context.scene
    cam = bpy.data.objects[CAM]
    js = bpy.data.objects[SCROLL]
    pav_tops = {SC.K + ".pavilion", SC.K + ".plaque", SC.K + ".lantern", SC.K + ".lantern.001"}
    whole = [o for o in display if not o.name.endswith((".posts", ".bases"))]
    legs = [o for o in display if o.name.endswith((".posts", ".bases"))]
    pav = np.concatenate(list(area_points(root, pav_tops).values()))   # the pavilion does not move: its points once
    Pw = np.concatenate([world_pts(o, 3) for o in whole])
    Pa = np.concatenate([world_pts(o, 3) for o in display])

    v = site_view(sc, cam, HOLD)
    Mi = np.array(root.matrix_world.inverted())
    cl = Mi[:3, :3] @ v["loc"] + Mi[:3, 3]
    fw = Mi[:3, :3] @ (-v["R"][:, 2])
    fw0 = Mi[:3, :3] @ (-np.array(cam.matrix_world.to_3x3().normalized())[:, 2])
    h, h0 = math.degrees(math.atan2(fw[1], fw[0])), math.degrees(math.atan2(fw0[1], fw0[0]))
    ok = math.dist(cl, SC.HOLD_CAM) < 0.05 and abs(h0 - math.degrees(SC.HOLD_HEADING)) < 0.05
    log("hold %d: chase.cam at (%.2f, %.2f, %.2f) heading %.2f deg in %s's frame (scroll.HOLD_CAM %s, HOLD_HEADING "
        "%.2f)" % (HOLD, cl[0], cl[1], cl[2], h0, AREA_ROOT, SC.HOLD_CAM, math.degrees(SC.HOLD_HEADING)),
        "agree" if ok else "DIFFER: the camera moved, update scroll.HOLD_CAM / HOLD_HEADING")
    if not ok:
        fails.append("chase.cam at the hold differs from scroll.HOLD_CAM / HOLD_HEADING")
    log("hold %d: the site turns the view %.1f deg left (scroll.HOLD_TURN, framing.ts): heading %.2f deg" % (
        HOLD, math.degrees(v["yaw"]), h))
    fp, f3, fl = facing(v, js)
    ok = fp <= FACE_PLAN_MAX and f3 <= FACE_3D_MAX
    log("hold %d: the scroll's face is %.2f deg off square to the turned view in plan, %.2f deg in 3D (the line of sight "
        "to its centre meets it %.1f deg off its normal: it stands left of the picture's centre); it was ~30 deg off "
        "square" % (HOLD, fp, f3, fl), "ok" if ok else "NOT FACING (max %.1f / %.1f)" % (FACE_PLAN_MAX, FACE_3D_MAX))
    if not ok:
        fails.append("the scroll is not square to the hold view")
    for res in (RES, RES_SMALL):
        v = site_view(sc, cam, HOLD, res)
        W, H = res
        k = W / RES[0]
        qw, qa = project(v, Pw), project(v, Pa)
        x0, x1, y0, y1 = qw[:, 0].min(), qw[:, 0].max(), qw[:, 1].min(), qw[:, 1].max()
        ok = x0 >= MARGIN_PX and x1 <= W - MARGIN_PX and y0 >= MARGIN_PX and y1 <= H - MARGIN_PX and \
            (qw[:, 2] > 0).all()
        log("hold %d %dx%d: scroll + rails + emblems x %.0f .. %.0f, y %.0f .. %.0f" % (HOLD, W, H, x0, x1, y0, y1),
            "wholly in frame, ok" if ok else "CROSSES THE FRAME EDGE (margin %d px)" % MARGIN_PX)
        if not ok:
            fails.append("the scroll is not wholly in frame at the hold (%dx%d)" % res)
        for o in legs:
            q = project(v, world_pts(o, 2))
            log("hold %d %dx%d: %-26s x %.0f .. %.0f, y %.0f .. %.0f, %.0f %% of its vertices in frame" % (
                HOLD, W, H, o.name, q[:, 0].min(), q[:, 0].max(), q[:, 1].min(), q[:, 1].max(),
                100.0 * in_frame(q, res).mean()))
        seen, px = cells_at(v, js)
        N = scroll_dims()[0]
        ok = len(seen) == N and px and min(px) >= MIN_CELL_PX * k
        log("hold %d %dx%d: %d of %d slips wholly in frame; a character cell is %.1f .. %.1f px tall (13.3 .. 16.5 at "
            "1600 x 900 before r10, turned away)" % (HOLD, W, H, len(seen), N, min(px) if px else 0,
                                                     max(px) if px else 0),
            "ok" if ok else "TOO SMALL / CUT (min %.1f px, all slips)" % (MIN_CELL_PX * k))
        if not ok:
            fails.append("the verses are cut or too small at the hold (%dx%d)" % res)
        qp = project(v, pav)
        gap = silhouette_gap(qa, qp)
        ok = gap >= PAV_GAP_PX * k
        log("hold %d %dx%d: the display keeps %.0f px left of the pavilion's silhouette (pavilion x %.0f .. %.0f)" % (
            HOLD, W, H, gap, qp[:, 0].min(), qp[:, 0].max()),
            "ok" if ok else "OVERLAPS / CROWDS IT (< %.0f px)" % (PAV_GAP_PX * k))
        if not ok:
            fails.append("the scroll crowds the pavilion at the hold (%dx%d)" % res)
    worst = (1e9, None)
    Ps = np.concatenate([world_pts(o, 6) for o in display])
    for f in APPROACH + DEPART:
        v = site_view(sc, cam, f)
        q = project(v, Ps)
        g = silhouette_gap(q, project(v, pav)) if f in APPROACH else float("nan")
        fp, f3, fl = facing(v, js)
        sn, spx = cells_at(v, js)
        log("%s %d (turn %.1f deg): display x %6.0f .. %6.0f y %5.0f .. %5.0f, %3.0f %% in frame, %2d slips whole "
            "(cells %s px), face %.1f deg off square%s" % (
                "approach" if f in APPROACH else "depart", f, math.degrees(v["yaw"]), q[:, 0].min(), q[:, 0].max(),
                q[:, 1].min(), q[:, 1].max(), 100 * in_frame(q, RES).mean(), len(sn),
                "%.1f .. %.1f" % (min(spx), max(spx)) if spx else "-", f3,
                ", %.0f px left of the pavilion" % g if f in APPROACH else ""))
        if f in APPROACH and g < worst[0]:
            worst = (g, f)
    ok = worst[0] >= 0
    log("approach: closest the display comes to the pavilion on screen %.0f px (frame %s)" % worst,
        "never overlapping, ok" if ok else "OVERLAPS")
    if not ok:
        fails.append("the scroll overlaps the pavilion on the approach")


def main():
    dry = options()
    sc = bpy.context.scene
    keep = (sc.frame_current, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    root = bpy.data.objects.get(AREA_ROOT)
    js = bpy.data.objects.get(SCROLL)
    fr = bpy.data.objects.get(SC.FRAME)
    if root is None or js is None or fr is None or bpy.data.objects.get(CAM) is None:
        raise RuntimeError("no %s / %s / %s / %s: is this out/sect_chase.blend after patch_r5_scroll?" % (
            AREA_ROOT, SCROLL, SC.FRAME, CAM))
    rings = [bpy.data.objects.get(n) for n in RINGS]
    motes = bpy.data.objects.get(MOTES)
    for nm, ob in [(SCROLL, js), (SC.FRAME, fr), (MOTES, motes)] + list(zip(RINGS, rings)):
        if ob is None or ob.parent != root:
            raise RuntimeError("%s missing or not under %s" % (nm, AREA_ROOT))
    coll = fr.users_collection[0]
    states = dict(old=OLD, new=new_state())
    st = {SCROLL: which(js, "scroll", states), SC.FRAME: which(fr, "scroll", states), MOTES: which(motes, "motes", states)}
    for nm, ob in zip(RINGS, rings):
        st[nm] = which(ob, "ring", states)
    log("state:", st, "| new placement: centre %s, turn %.2f deg, scale %.3f; rings at (%.2f, %.2f) x %.3f" % (
        tuple(round(v, 3) for v in SC.SCROLL_C), math.degrees(SC.SCROLL_YAW), SC.SCROLL_SCALE, SC.RING_C[0],
        SC.RING_C[1], SC.RING_K))
    if any(v is None for v in st.values()):
        bad = {k: (tuple(round(c, 3) for c in bpy.data.objects[k].location),
                   round(math.degrees(bpy.data.objects[k].rotation_euler.z), 2),
                   round(bpy.data.objects[k].scale.x, 4)) for k, v in st.items() if v is None}
        raise RuntimeError("neither the r5/r8 placement nor this one (location, turn deg, scale): %s" % bad)

    sc.frame_set(keep[0])
    display_old = [c for c in js.children_recursive if c.type == 'MESH'] + \
        [c for c in fr.children_recursive if c.type == 'MESH']
    before = {o.name: world_box(o) for o in display_old}
    before.update({o.name: inst_box(o) for o in rings + [motes]})
    n_obj = len(bpy.data.objects)

    # 1. the scroll
    js.location = SC.SCROLL_C
    js.rotation_euler = (0.0, 0.0, SC.SCROLL_YAW)
    js.scale = (SC.SCROLL_SCALE,) * 3
    # 2. its frame, rebuilt
    gone = remove_frame()
    log("removed the frame:", gone)
    grp = SC.scroll_frame(coll, root)
    # 3. the rings
    for ob in rings:
        ob.location = (SC.RING_C[0], SC.RING_C[1], 0.0)
        ob.scale = (SC.RING_K, SC.RING_K, 1.0)
    # 4. the motes
    motes.location = (SC.SCROLL_C[0] - MOTES_BUILT_C[0], SC.SCROLL_C[1] - MOTES_BUILT_C[1], 0.0)
    bpy.context.view_layer.update()

    fails = []
    got = sorted([grp.name] + [o.name for o in grp.children])
    if got != sorted(frame_names()) or len(bpy.data.objects) != n_obj:
        raise RuntimeError("frame names %s (wanted %s), objects %d -> %d: a name was taken" % (
            got, sorted(frame_names()), n_obj, len(bpy.data.objects)))
    frame_obs = [bpy.data.objects[n] for n in frame_names()[1:]]
    display = [c for c in js.children_recursive if c.type == 'MESH'] + frame_obs
    for ob in frame_obs:
        oe = open_edges(ob.data)
        log("mesh", ob.name, "tris", tris(ob.data), "slots", [s.material.name if s.material else None
                                                             for s in ob.material_slots],
            "closed" if oe == 0 else "OPEN (%d edges)" % oe)
        if oe:
            fails.append("%s is open" % ob.name)
    frame_fit_check(fails)
    post_plinth_check(fails)
    ground_check(root, fails)
    ring_check(root, fails)
    clash_check(display, fails)
    flight_check(display, fails)
    hold_and_flight_view(root, display, fails)

    # the checks scrubbed the timeline: back to the file's own frame (the motes drift with time) and render size
    sc.frame_set(keep[0])
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = keep[1:]
    moved = []
    for o in display + rings + [motes]:
        nb = inst_box(o) if o in rings or o is motes else world_box(o)
        ob_ = before.get(o.name)
        ok = ob_ is not None and nb is not None and inside(nb, ob_)
        if not ok:
            moved.append(o.name)
        log("box", o.name, "before", ob_, "after", nb, "inside the old box" if ok else "LEAVES the old box")
    if moved:
        log("CACHES needs audit: %d objects left their old boxes %s - run the export_web audit, then chunks,meta (the "
            "'resume' hotspot moved), then bakefull the scroll chunk and whatever else cmp_chunks reports (at least "
            "the backdrop), then the pack" % (len(moved), moved))
    else:
        log("CACHES ok: every box inside its old one (re-bake the scroll chunk for the rebuilt frame meshes)")
    if fails:
        raise RuntimeError("checks failed, NOT saved: %s" % fails)
    if dry:
        log("DRY_RUN: checks passed, not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
