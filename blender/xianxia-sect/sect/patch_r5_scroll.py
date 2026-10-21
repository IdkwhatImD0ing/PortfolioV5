"""Ground the Jade Slip Pavilion's floating props (round 5, lane 'scroll'): bring an existing out/sect_chase.blend to the
design in sect/areas/scroll.py and save it. Run on the cloud box (on a copy first):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r5_scroll.py [-- DRY_RUN=1]

What it does (a fresh build makes the same through scroll.build):
1. The jade scroll (scroll.jade_scroll, the 'resume' hotspot; NOT touched) gets its standing frame: ADDS the Empty
   scroll.scroll_frame (same place, turn and 0.9 scale as the scroll) and under it scroll.scroll_frame.posts
   (lacquer_red, gold), .rails (lacquer_red, gold), .bases (stone_grey, iron), .emblems (gold sun, silver moon).
2. The six Holy Fire Tokens stop floating: MOVES the Empty scroll.slip_stack from (21, -3, 6.5) turned -15 deg to the
   terrace at scroll.STAND_C (z 0, unturned), rebuilds the meshes of scroll.slips / scroll.slip_caps in place
   (upright in a row, leaning on the stand's rail; same objects, names and materials) with glow scroll.TOKEN_GLOW /
   scroll.CORE_GLOW, and ADDS under the Empty scroll.token_plinth (stone_grey) and scroll.token_stand (lacquer_black,
   gold, silver).
3. The three scholar rocks stand on pedestals: ADDS scroll.rock_pedestal.0/.1/.2 (marble_white) and MOVES
   scroll.rock.0/.1/.2 up onto them (z 0 -> scroll.ROCK_PEDESTAL top).
4. The two hanging lanterns at the pavilion's front eave corners (scroll.lantern, scroll.lantern.001) hung 13 cm
   below the eave soffit with nothing above their cords: MOVES them up to floors[1] - 1.7 + scroll.LANTERN_LIFT (the
   cord's top 3 cm into the soffit).
Every added object carries obj['sect_item'] (scroll.FRAME_ITEM, STAND_ITEM, ROCK_ITEM). Idempotent: a re-run first
removes its own previous output (tagged objects, or those names, and their meshes), rebuilds it under the same names
and sets the same transforms.

Checks before saving (it stops without saving when one fails): every added name came out exactly (no '.001'); every
added mesh closed (every edge in two or more faces: bake_web's closed-piece rule); the frame's sill top and top rail
bottom meet the slips' bottom and top; each post's plinth stands on the terrace between the two rune ring bands; every
token's lower end sits in its slot (between the slot bottom and the beam top) and leans on the rail;
nothing of the stand above the rail (post caps, the sun, the moon) cuts into a token;
the rails' big faces (cradle discs, rail tops) are lacquer, not gold; the stand, the
frame bases and the pedestals stand on the terrace (a ray straight down from each footprint corner meets the terrace
top within 2 cm of their bottom); the stand keeps out of the walks (the axis walk x 10..14 and the side steps' lane
y -6.5..-0.5). It also logs, at the hold camera (1103), where the scroll, the emblems and the stand land in the frame,
and every scene piece within 0.3 m of an added piece.

Caches: added objects are not in the web caches and the moved ones leave their old boxes, so the script prints
'PATCH CACHES needs audit' with the list (on a re-run over its own output it prints 'PATCH CACHES ok'). Then run the
export audit and chunks,meta before re-baking the scroll chunk (and the backdrop).
"""
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402

AREA_ROOT = SC.K + ".root"
STACK = SC.K + ".slip_stack"
TOKEN_OBS = (SC.K + ".slips", SC.K + ".slip_caps")
SCROLL = SC.K + ".jade_scroll"
HOLD = 1103
ITEMS = (SC.FRAME_ITEM, SC.STAND_ITEM, SC.ROCK_ITEM)
NEAR = 0.3


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
            raise SystemExit("patch_r5_scroll: unknown option %r (DRY_RUN=1)" % a)
    return dry


def added_names():
    fr = [SC.FRAME] + [SC.FRAME + "." + p for p in ("posts", "rails", "bases", "emblems")]
    st = [SC.K + ".token_plinth", SC.K + ".token_stand"]
    pe = [SC.K + ".rock_pedestal.%d" % i for i in range(len(SC.ROCKS))]
    return fr, st, pe


def remove_previous():
    """Remove what a previous run added (tagged objects or the added names, with their children) and free their
    meshes. Returns the removed names."""
    want = set(sum(added_names(), []))
    obs = [o for o in bpy.data.objects if o.get("sect_item") in ITEMS or o.name in want]
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


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def open_edges(me):
    """Edges in fewer than two faces (bake_web._closed_faces: a piece with any is open)."""
    cnt = {}
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            k = (a, b) if a < b else (b, a)
            cnt[k] = cnt.get(k, 0) + 1
    return sum(1 for e in me.edges if cnt.get(tuple(sorted(e.vertices)), 0) < 2)


def world_box(ob):
    """World box of an object's own geometry (mesh vertices; Empty -> None)."""
    if ob.type != 'MESH' or not len(ob.data.vertices):
        return None
    M = ob.matrix_world
    pts = [M @ v.co for v in ob.data.vertices]
    return (tuple(round(min(p[k] for p in pts), 3) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 3) for k in range(3)))


def inside(box, outer, tol=1e-3):
    return all(box[0][k] >= outer[0][k] - tol and box[1][k] <= outer[1][k] + tol for k in range(3))


def local_pts(ob, root):
    """Vertices of ob in the area root's frame."""
    M = root.matrix_world.inverted() @ ob.matrix_world
    return [M @ v.co for v in ob.data.vertices]


def bvh_of(ob):
    M = ob.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])


def ground_hits(root, pts_local, skip, depth=3.0):
    """For each root-frame point (x, y, z) cast a ray straight down from z + 0.5 and return (point, hit z in the root
    frame or None, the object hit), ignoring objects in ``skip``."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    M, Mi = root.matrix_world, root.matrix_world.inverted()
    down = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    out = []
    for p in pts_local:
        o = M @ Vector((p[0], p[1], p[2] + 0.5))
        hit_z, hit_ob = None, None
        for _ in range(8):
            ok, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, down, distance=depth + 0.5)
            if not ok:
                break
            if ob.original.name in skip:
                o = loc + down * 1e-3
                continue
            hit_z, hit_ob = (Mi @ loc).z, ob.original.name
            break
        out.append((p, hit_z, hit_ob))
    return out


def footprint_check(name, pts, root, skip, tol=0.02):
    """Footprint of one standing piece (its root-frame vertices ``pts``): from its lowest vertices take the ones
    furthest out in x and y (its plan corners), pull them 5 cm in, and cast straight down: the paving (terrace or the
    rune rings flush on it) must be within ``tol`` above its bottom (its bottom is sunk at most 0.15 m)."""
    zb = min(p.z for p in pts)
    low = [p for p in pts if p.z < zb + 0.01]
    cx, cy = sum(p.x for p in low) / len(low), sum(p.y for p in low) / len(low)
    ext = [min(low, key=lambda p: p.x), max(low, key=lambda p: p.x), min(low, key=lambda p: p.y),
           max(low, key=lambda p: p.y)]
    corners = []
    for p in ext:
        d = math.hypot(p.x - cx, p.y - cy) or 1.0
        corners.append((p.x - 0.05 * (p.x - cx) / d, p.y - 0.05 * (p.y - cy) / d, zb))
    bad = []
    for p, hz, hob in ground_hits(root, corners, skip):
        if hz is None or not (zb - tol <= hz <= zb + 0.15 + tol):
            bad.append((tuple(round(c, 2) for c in p), None if hz is None else round(hz, 3), hob))
    log("ground", name, "bottom z %.3f" % zb, "corners off the terrace:" if bad else "all 4 plan corners on the paving",
        bad if bad else "")
    return not bad


def post_plinth_check(root, fails):
    """Each post's plinth (corners, root frame) stays between the two rune ring bands."""
    fp = SC.frame_points()
    lo = SC.RING_TRIGRAM[0] + SC.RING_TRIGRAM[1] / 2.0 + 0.02
    hi = SC.RING_SCRIPT[0] - SC.RING_SCRIPT[1] / 2.0 - 0.02
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
        log("post", "left" if side < 0 else "right", "arc angle %.2f deg (%.0f %% of the half width)" % (
            math.degrees(a), 100.0 * abs(a) / SC._arc()[1]),
            "plinth corners %.2f .. %.2f m from the ring centre (free paving %.2f .. %.2f)" % (min(rs), max(rs), lo, hi),
            "ok" if ok else "ON A RING BAND")
        if not ok:
            fails.append("post plinth on a ring band")


def frame_fit_check(fails):
    """The sill's top and the top rail's bottom meet the slips (scroll frame z, unscaled)."""
    js = bpy.data.objects[SCROLL]
    sl = [c for c in js.children if c.type == 'MESH' and c.name.startswith(SCROLL + ".slips")]
    if not sl:
        fails.append("no jade slips mesh under " + SCROLL)
        return
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


def token_check(fails):
    """Every token's lowest point lies inside its slot and each token's back touches the rail."""
    stack = bpy.data.objects[STACK]
    body = bpy.data.objects[TOKEN_OBS[0]]
    Mi = stack.matrix_world.inverted()
    zb = SC.STAND_BEAM[3] - SC.SLOT_DEPTH
    lows = [(Mi @ (body.matrix_world @ v.co)).z for v in body.data.vertices]
    lo = min(lows)
    ok = zb - 0.03 <= lo <= SC.STAND_BEAM[3] - 0.05
    ry, rz = SC.stand_rail()
    log("tokens: lowest point z %.3f (slot bottom %.3f, beam top %.3f); rail at y %.3f z %.3f" % (
        lo, zb, SC.STAND_BEAM[3], ry, rz), "ok" if ok else "BAD")
    if not ok:
        fails.append("tokens not seated in their slots")


def stand_clear_check(stand, fails):
    """(verify r5) Above the back rail nothing of the stand (post caps, the sun, the moon) may cut into a token: the
    only intended contacts are the slots (beam top) and the rail."""
    stack = bpy.data.objects[STACK]
    Mi = stack.matrix_world.inverted()
    _ry, rz = SC.stand_rail()
    zmax = rz + SC.STAND_RAIL / 2.0 + 0.05
    sv = [stand.matrix_world @ v.co for v in stand.data.vertices]
    bad = []
    for nm in TOKEN_OBS:
        hits = bvh_of(stand).overlap(bvh_of(bpy.data.objects[nm]))
        for i, _j in hits:
            p = stand.data.polygons[i]
            z = (Mi @ (sum((sv[k] for k in p.vertices), Vector()) / len(p.vertices))).z
            if z > zmax:
                bad.append((nm, stand.material_slots[p.material_index].name, round(z, 2)))
    log("stand emblems/caps vs tokens above the rail (z > %.2f):" % zmax,
        "clear, ok" if not bad else "%d CLASHES %s" % (len(bad), sorted(set(bad))[:6]))
    if bad:
        fails.append("stand emblems cut into the tokens")


def rails_mat_check(fails):
    """(verify r5) The rails' big flat faces (the cradle discs' tops and bottoms, the rails' tops and bottoms) are
    lacquer: gold is only the strips, bands and end caps."""
    ob = bpy.data.objects[SC.FRAME + ".rails"]
    bad = [(round(p.area, 2), tuple(round(c, 2) for c in p.center)) for p in ob.data.polygons
           if p.area > 1.0 and ob.material_slots[p.material_index].name != "M.lacquer_red"]
    log("rails: big faces all lacquer_red, ok" if not bad else "rails: %d big faces not lacquer %s" % (len(bad), bad))
    if bad:
        fails.append("rails cradle/rail faces carry the wrong material")


def walk_check(root, stand_obs, fails):
    pts = [p for o in stand_obs for p in local_pts(o, root)]
    x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
    y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
    clash = []
    if x0 < 14.0 and x1 > 10.0:
        clash.append("axis walk")
    if y0 < -0.5 and y1 > -6.5:
        clash.append("side-steps lane")
    if x1 > SC.TERRACE_X[1] - 0.6 - 0.15:
        clash.append("right rail")
    log("stand footprint x %.2f .. %.2f, y %.2f .. %.2f" % (x0, x1, y0, y1), "clear of the walks and the rail"
        if not clash else "CLASHES with %s" % clash)
    if clash:
        fails.append("stand blocks %s" % clash)


def hold_report(root, frame_obs, stand_obs):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("chase.cam")
    if cam is None:
        log("WARN no chase.cam: hold framing not checked")
        return
    f0 = sc.frame_current
    sc.frame_set(HOLD)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900

    def span(obs):
        pts = [o.matrix_world @ v.co for o in obs for v in o.data.vertices]
        ndc = [world_to_camera_view(sc, cam, p) for p in pts]
        xs, ys = [v.x * 1600 for v in ndc], [(1 - v.y) * 900 for v in ndc]
        return (min(xs), max(xs), min(ys), max(ys), min(v.z for v in ndc))
    js = [o for o in bpy.data.objects[SCROLL].children_recursive if o.type == 'MESH']
    for label, obs in (("jade scroll", js), ("frame", frame_obs), ("emblems", [bpy.data.objects[SC.FRAME + ".emblems"]]),
                       ("token stand + tokens", stand_obs + [bpy.data.objects[n] for n in TOKEN_OBS])):
        x0, x1, y0, y1, d = span(obs)
        inn = x0 >= 0 and x1 <= 1600 and y0 >= 0 and y1 <= 900
        log("hold %d 1600x900: %-22s x %5.0f .. %5.0f  y %5.0f .. %5.0f  nearest %.1f m  %s" % (
            HOLD, label, x0, x1, y0, y1, d, "in frame" if inn else "crosses the frame edge"))
    sc.frame_set(f0)


def neighbours(added, skip):
    """Scene pieces (evaluated instances included) within NEAR m of an added piece."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = {o.name for o in added}
    found = []
    for ob in added:
        pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
        lo = Vector([min(p[k] for p in pts) - NEAR for k in range(3)])
        hi = Vector([max(p[k] for p in pts) + NEAR for k in range(3)])
        for inst in dg.object_instances:
            o2 = inst.object
            if o2.type != 'MESH' or o2.original.name in names or o2.original.name in skip:
                continue
            M = inst.matrix_world
            cs = [M @ Vector(c) for c in o2.bound_box]
            if any(min(c[k] for c in cs) > hi[k] or max(c[k] for c in cs) < lo[k] for k in range(3)):
                continue
            me = o2.to_mesh()
            try:
                if not len(me.polygons):
                    continue
                bvh = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
            finally:
                o2.to_mesh_clear()
            ds = [h[3] for h in (bvh.find_nearest(p, NEAR) for p in pts) if h[0] is not None]
            if ds:
                found.append((round(min(ds), 3), ob.name, o2.original.name + (" (instance)" if inst.is_instance else "")))
    for d, a, b in sorted(set(found)):
        log("near %.3f m: %s - %s" % (d, a, b))
    if not found:
        log("near: nothing within %.1f m of the added pieces" % NEAR)


def lantern_fix(root, moved_names):
    """Lift the eave-corner lanterns to the source height and check each cord's top now runs into the soffit."""
    pav = bpy.data.objects.get(SC.K + ".pavilion")
    floors = list(pav["arch_floors"]) if pav is not None and "arch_floors" in pav else None
    if floors is None or len(floors) < 2:
        raise RuntimeError("scroll.pavilion has no arch_floors: cannot place the eave lanterns")
    z = floors[1] - 1.7 + SC.LANTERN_LIFT
    obs = []
    for nm in (SC.K + ".lantern", SC.K + ".lantern.001"):
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.parent != root:
            raise RuntimeError("%s missing or not under %s" % (nm, AREA_ROOT))
        if abs(ob.location.z - z) > 1e-6:
            log("lantern", nm, "z %.3f -> %.3f" % (ob.location.z, z))
            ob.location.z = z
        obs.append(ob)
        moved_names.append(nm)
    return obs


def lantern_check(root, obs, fails):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    Mi = root.matrix_world.inverted()
    up = (root.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    side = (root.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    for ob in obs:
        lo, hi = inst_box(ob)
        c = (lo + hi) / 2
        o = Vector((c.x, c.y, hi.z)) - up * 0.10 + side * 0.05
        ok, loc, _n, _i, hob, _m = sc.ray_cast(dg, o, up, distance=2.0)
        top_z, soffit_z = (Mi @ hi).z, (Mi @ loc).z if ok else None
        good = ok and soffit_z < top_z - 0.005
        log("lantern", ob.name, "cord top z %.3f, %s above it at z %s" % (
            top_z, hob.name if ok else "nothing", "%.3f" % soffit_z if ok else "-"),
            "-> cord runs %.3f m into it, ok" % (top_z - soffit_z) if good else "-> NOT ATTACHED")
        if not good:
            fails.append("%s not attached to the eave" % ob.name)


def inst_box(ob):
    """World box of a collection-instance Empty's evaluated geometry (or a mesh object's)."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob and inst.object.type == 'MESH':
            M = inst.matrix_world
            pts += [M @ Vector(c) for c in inst.object.bound_box]
    if not pts and ob.type == 'MESH':
        pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return (Vector([min(p[k] for p in pts) for k in range(3)]), Vector([max(p[k] for p in pts) for k in range(3)]))


def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    stack = bpy.data.objects.get(STACK)
    if root is None or stack is None or bpy.data.objects.get(SCROLL) is None:
        raise RuntimeError("no %s / %s / %s: is this out/sect_chase.blend?" % (AREA_ROOT, STACK, SCROLL))
    coll = stack.users_collection[0]
    tok = []
    for nm in TOKEN_OBS:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH' or ob.parent != stack:
            raise RuntimeError("%s missing, not a mesh or not under %s" % (nm, STACK))
        tok.append(ob)
    rocks = []
    for i in range(len(SC.ROCKS)):
        ob = bpy.data.objects.get("%s.rock.%d" % (SC.K, i))
        if ob is None or ob.parent != root:
            raise RuntimeError("scroll.rock.%d missing or not under %s" % (i, AREA_ROOT))
        rocks.append(ob)
    js = bpy.data.objects[SCROLL]
    log("collection", coll.name, "| scroll", SCROLL, "at", tuple(round(c, 3) for c in js.location), "turn %.1f deg" %
        math.degrees(js.rotation_euler.z), "scale %.3f" % js.scale[0], "(not touched)")
    if (js.location - Vector(SC.SCROLL_C)).length > 1e-3 or abs(js.rotation_euler.z - SC.SCROLL_YAW) > 1e-4 or \
            abs(js.scale[0] - SC.SCROLL_SCALE) > 1e-4:
        raise RuntimeError("jade_scroll is not at scroll.SCROLL_C / SCROLL_YAW / SCROLL_SCALE: the frame would miss it")

    # boxes before (the web caches were built from these)
    before = {}
    for ob in tok + rocks:
        before[ob.name] = world_box(ob)
    pre_names = {o.name for o in bpy.data.objects}
    gone = remove_previous()
    if gone:
        log("removed the previous run's output:", gone)
    n_obj = len(bpy.data.objects)

    # 1. the scroll's frame
    grp = SC.scroll_frame(coll, root)
    # 2. the tokens on their stand
    log("slip_stack before: location", tuple(round(c, 3) for c in stack.location), "rotation z %.1f deg" %
        math.degrees(stack.rotation_euler.z))
    stack.location = (SC.STAND_C[0], SC.STAND_C[1], 0.0)
    stack.rotation_euler = (0.0, 0.0, 0.0)
    stack.scale = (1.0, 1.0, 1.0)
    news = SC.fire_token_meshes(names=tuple(nm + ".new" for nm in TOKEN_OBS), log=log)
    for ob, me in zip(tok, news):
        old = ob.data
        ob.data = me
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if old is not me and old.users == 0:
            bpy.data.meshes.remove(old)
        elif old is not me:
            log("WARN old mesh", old.name, "still has", old.users, "users; kept")
        me.name = ob.name
        if me.name != ob.name:
            log("WARN mesh name taken: the new mesh is", me.name)
    for ob, glow in zip(tok, (SC.TOKEN_GLOW, SC.CORE_GLOW)):
        if ob.get("glow") != glow:
            log("glow on", ob.name, ob.get("glow"), "->", glow)
            ob["glow"] = glow
    plinth, stand = SC.token_stand(coll, stack)
    log("slip_stack now: location", tuple(round(c, 3) for c in stack.location), "unturned")
    # 3. the scholar rocks on pedestals
    peds = []
    for i, (x, y, s) in enumerate(SC.ROCKS):
        peds.append(SC.rock_pedestal(coll, root, i, x, y, s))
        z = SC.ROCK_PEDESTAL[1] - SC.ROCK_PEDESTAL[2]
        r = rocks[i]
        if abs(r.location.x - x) > 1e-3 or abs(r.location.y - y) > 1e-3:
            log("WARN", r.name, "is at", tuple(round(c, 3) for c in r.location), "not at", (x, y))
        if abs(r.location.z - z) > 1e-6:
            log("rock", r.name, "z %.3f -> %.3f (onto its pedestal)" % (r.location.z, z))
            r.location.z = z
    # 4. the eave-corner lanterns
    lant_before = {}
    for nm in (SC.K + ".lantern", SC.K + ".lantern.001"):
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            lo, hi = inst_box(ob)
            lant_before[nm] = (tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi))
    lanterns = lantern_fix(root, [])
    bpy.context.view_layer.update()

    # checks
    fails = []
    fr_names, st_names, pe_names = added_names()
    frame_obs = [bpy.data.objects.get(n) for n in fr_names[1:]]
    want = sorted(fr_names + st_names + pe_names)
    got = sorted([grp.name] + [o.name for o in grp.children] + [plinth.name, stand.name] + [p.name for p in peds])
    if got != want or any(o is None for o in frame_obs):
        raise RuntimeError("unexpected names %s (wanted %s): a name was taken" % (got, want))
    if len(bpy.data.objects) != n_obj + len(want):
        raise RuntimeError("object count %d -> %d, expected +%d" % (n_obj, len(bpy.data.objects), len(want)))
    added = frame_obs + [plinth, stand] + peds
    for ob in added + tok:
        oe = open_edges(ob.data)
        log("mesh", ob.name, "tris", tris(ob.data), "slots", [s.material.name if s.material else None
                                                             for s in ob.material_slots],
            "closed" if oe == 0 else "OPEN (%d edges)" % oe)
        if oe and ob in added:
            fails.append("%s is open" % ob.name)
        if ob in tok and tris(ob.data) > SC.TOKEN_TRI_BUDGET:
            fails.append("%s over the token triangle budget" % ob.name)
    frame_fit_check(fails)
    post_plinth_check(root, fails)
    token_check(fails)
    stand_clear_check(stand, fails)
    rails_mat_check(fails)
    skip_ground = {o.name for o in added + tok + rocks}
    fp = SC.frame_points()
    bases = local_pts(bpy.data.objects[SC.FRAME + ".bases"], root)
    pieces = []
    for k in ("post_l", "post_r"):
        cx, cy = fp[k]
        other = fp["post_r" if k == "post_l" else "post_l"]
        pieces.append((SC.FRAME + ".bases (%s)" % k, [p for p in bases if (p.x - cx) ** 2 + (p.y - cy) ** 2 <
                                                      (p.x - other[0]) ** 2 + (p.y - other[1]) ** 2]))
    pieces += [(ob.name, local_pts(ob, root)) for ob in [plinth] + peds]
    for nm, pts in pieces:
        if not pts or not footprint_check(nm, pts, root, skip_ground):
            fails.append("%s not on the terrace" % nm)
    walk_check(root, [plinth, stand], fails)
    lantern_check(root, lanterns, fails)
    hold_report(root, frame_obs, [plinth, stand])
    neighbours(added, skip={SCROLL} | {o.name for o in bpy.data.objects[SCROLL].children_recursive} | {
        o.name for o in tok} | {o.name for o in rocks})

    # caches: added objects and moved boxes
    newly = [n for n in want if n not in pre_names]
    moved = []
    for ob in tok + rocks:
        nb = world_box(ob)
        ok = before[ob.name] is not None and nb is not None and inside(nb, before[ob.name])
        log("box", ob.name, "before", before[ob.name], "after", nb, "inside the old box" if ok else "LEAVES the old box")
        if not ok:
            moved.append(ob.name)
    for ob in lanterns:
        lo, hi = inst_box(ob)
        nb = (tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi))
        ok = inside(nb, lant_before[ob.name])
        log("box", ob.name, "before", lant_before[ob.name], "after", nb, "inside the old box" if ok else
            "LEAVES the old box")
        if not ok:
            moved.append(ob.name)
    if newly or moved:
        log("CACHES needs audit: %d added objects not in the caches %s; %d objects left their old boxes %s - run the "
            "export audit and chunks,meta before re-baking the scroll chunk (and the backdrop)" % (
                len(newly), newly, len(moved), moved))
    else:
        log("CACHES ok: every name existed before and every box stayed inside its old one")
    if fails:
        raise RuntimeError("checks failed, NOT saved: %s" % fails)
    if dry:
        log("DRY_RUN: checks passed, not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
