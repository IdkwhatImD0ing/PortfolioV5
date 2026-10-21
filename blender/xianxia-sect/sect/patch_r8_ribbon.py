"""Round 8, lane ribbon: Xiaolongnü's golden-bell silk ribbon 金铃索 (Return of the Condor Heroes) on the Cave Abode's
tea pavilion, over the Smiling, Proud Wanderer duet, in a finished out/sect_chase.blend (sect/areas/abode.py makes the
same on a full rebuild), and save it. Run on the cloud box (on a copy first), after the round-5 patches
(patch_r5_duet.py puts the duet's qin table under it):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r8_ribbon.py [-- DRY_RUN=1]

What it adds (abode._ribbon; nothing else in the file changes): a long white silk ribbon tied round the upturned tip
of the tea pavilion's front-left hip ridge (just outboard of the immortal rider), knotted under it, its two tails
hanging past the balcony's front in the breeze off the falls, a gold cap and a golden bell ball at each end. The loop
is fitted to the file's own ridge mesh (abode.ribbon_section / ribbon_loop). Objects, all tagged
obj['sect_item'] = 'golden_bell_ribbon', in collection 'abode':
    abode.ribbon          Empty under abode.root at the knot (no rotation, scale 1)
    abode.ribbon_silk     the loop, the knot and both tails (abode_ribbon_silk, a cloth_white variant)
    abode.ribbon_bells    caps, rings and bell balls (gold) with their slots (lacquer_black)

Checks before saving (it stops without saving when one fails): the names exactly (no '.001') and the object count;
each mesh within abode.RIBBON_TRI_CAP triangles and closed (bake_web's closed-piece rule); the ridge's section round
the loop a sane size; the built meshes equal to abode.ribbon_geo's lists; no ribbon piece intersecting any scene piece
(instances included), the ridge it is tied round at least MIN_GAP_RIDGE off and everything else at least MIN_GAP
(nearest distances logged); the two tails clear of each other below the knot; each bell at least BELL_LAWN m over the
lawn (abode._lawn_sampler); the ribbon at least MIST_GAP from every mist_volume box; and from the 1380 hold camera
(chase.cam) most of the long tail and both bells inside the frame and not hidden behind anything (ray casts; mist and
haze volumes and the flyer count as clear), with their place and size on a 1280x720 frame logged.

Caches: the three objects are new names, so the web caches do not know them yet: it prints 'PATCH CACHES NEED AUDIT'
(run the export audit, then chunks,meta, then re-bake the abode, or the bake drops them); 'PATCH CACHES ok' only on a
re-run that rebuilt the same names inside their old world boxes. Idempotent: a re-run removes its own previous ribbon
(by tag and name) and builds it again, same names and geometry. Options after '--': DRY_RUN=1 (report, no save).
"""
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.areas import abode as AB  # noqa: E402

AREA_ROOT = "abode.root"
COLL = "abode"
GROUND = "abode.ground"
HOLD = 1380
RES = (1280, 720)
NEAR = 1.0             # m: scene pieces whose box comes this close to a ribbon mesh's box are tested
MIN_GAP_RIDGE = 0.005  # m: the loop's inner face off the ridge it is tied round (built at abode.RIBBON_LOOP_GAP)
MIN_GAP = 0.02         # m: off every other scene piece
TAIL_GAP = 0.004       # m: the two tails' surfaces apart, below their first 0.25 m (they leave the knot side by side)
BELL_LAWN = 0.3        # m: each bell's lowest point over the lawn
MIST_GAP = 2.0
LONG_SEEN = 0.6        # share of the long tail's samples the hold camera must see
TOL = 2e-3


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
            raise SystemExit("patch_r8_ribbon: unknown option %r (DRY_RUN=1)" % a)
    return dry


def names():
    return [AB.RIBBON] + [nm for nm, _roles in AB.RIBBON_PARTS]


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def open_edges(me):
    """Edges in fewer than two faces (bake_web._closed_faces: a piece with any is open)."""
    use = {}
    for p in me.polygons:
        for k in p.edge_keys:
            use[k] = use.get(k, 0) + 1
    return sum(1 for e in me.edges if use.get(e.key, 0) < 2)


def box_of(pts):
    return (Vector(tuple(min(p[k] for p in pts) for k in range(3))),
            Vector(tuple(max(p[k] for p in pts) for k in range(3))))


def box_gap(a, b):
    return math.sqrt(sum(max(a[0][k] - b[1][k], 0.0, b[0][k] - a[1][k]) ** 2 for k in range(3)))


def inside(inner, outer, tol=TOL):
    return all(inner[0][k] >= outer[0][k] - tol and inner[1][k] <= outer[1][k] + tol for k in range(3))


def rb(b):
    return tuple(round(x, 3) for x in b[0]), tuple(round(x, 3) for x in b[1])


def r3(p):
    return tuple(round(float(x), 3) for x in p)


def world_box(ob):
    pts = []
    for o in [ob] + list(ob.children_recursive):
        if o.type == 'EMPTY':
            pts.append(o.matrix_world.translation.copy())
        else:
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    return box_of(pts)


def world_verts(ob):
    M = ob.matrix_world
    return [M @ v.co for v in ob.data.vertices]


# --- build -------------------------------------------------------------------------------------------------------

def remove_previous():
    want = set(names())
    obs = [o for o in bpy.data.objects if o.get("sect_item") == AB.RIBBON_ITEM or o.name in want]
    for o in list(obs):
        obs.extend(c for c in o.children_recursive if c not in obs)
    gone, meshes, boxes = [], set(), {}
    for o in obs:
        if o.type == 'MESH':
            boxes[o.name] = world_box(o)
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
    return sorted(gone), boxes


def build(root, coll):
    gone, old_boxes = remove_previous()
    if gone:
        log("removed the previous ribbon:", gone)
    n_obj = len(bpy.data.objects)
    mats_before = {m.name for m in bpy.data.materials}
    em = AB._ribbon(coll, root)
    bpy.context.view_layer.update()
    group = [em] + list(em.children_recursive)
    got = sorted(o.name for o in group)
    if got != sorted(names()):
        raise RuntimeError("unexpected object names %s (wanted %s): a name was taken" % (got, sorted(names())))
    if len(bpy.data.objects) != n_obj + len(names()):
        raise RuntimeError("object count %d -> %d, expected +%d" % (n_obj, len(bpy.data.objects), len(names())))
    log("BUILT %d objects in collection '%s': %s" % (len(names()), COLL, ", ".join(names())))
    log("  %s under %s at %s (abode.root), rotation %s, scale %s" % (
        AB.RIBBON, em.parent.name, r3(em.location), r3(em.rotation_euler), r3(em.scale)))
    W = root.matrix_world.inverted()
    total = 0
    for ob in group:
        if ob.type != 'MESH':
            continue
        t, oe = tris(ob.data), open_edges(ob.data)
        total += t
        lo, hi = box_of([W @ p for p in world_verts(ob)])
        log("  %-20s tris %5d  open edges %d  materials %s  box in abode.root %s .. %s"
            % (ob.name, t, oe, [s.material.name if s.material else None for s in ob.material_slots], r3(lo), r3(hi)))
        if t > AB.RIBBON_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, AB.RIBBON_TRI_CAP))
        if oe:
            raise RuntimeError("%s has %d open edges: not closed" % (ob.name, oe))
        if ob.hide_render or ob.hide_get():
            raise RuntimeError("%s is hidden" % ob.name)
    log("  triangles in all: %d" % total)
    log("  materials created (were not in the file yet):", sorted({m.name for m in bpy.data.materials} - mats_before)
        or "none")
    return em, group, old_boxes


# --- checks ------------------------------------------------------------------------------------------------------

def check_geo(root, em, group):
    """The loop's fit and the built meshes against abode.ribbon_geo's lists (abode.root frame)."""
    pav_loc, verts, edges, ridge = AB.ribbon_ridge(root)
    silk, bells, info = AB.ribbon_geo(pav_loc, verts, edges)
    c, n, u, v, dn = info["plane"]
    sec = info["section"]
    us, vs = [p[0] for p in sec], [p[1] for p in sec]
    log("ridge %s: section round the loop %d points, %.3f m across x %.3f m (in the loop's plane at %s, axis %s)"
        % (ridge.name, len(sec), max(us) - min(us), max(vs) - min(vs), r3(c), r3(n)))
    if not (0.12 <= max(us) - min(us) <= 0.45 and 0.12 <= max(vs) - min(vs) <= 0.45):
        raise RuntimeError("the ridge's section round the loop is not the tip's (%.3f x %.3f m)"
                           % (max(us) - min(us), max(vs) - min(vs)))
    log("  knot (the Empty) at %s, the loop's apex at %s" % (r3(info["knot"]), r3(info["apex"])))
    k = Vector(info["knot"])
    if (em.location - k).length > 1e-5 or em.parent != root:
        raise RuntimeError("%s is not at the knot %s under %s" % (em.name, r3(k), AREA_ROOT))
    for (name, _roles), g in zip(AB.RIBBON_PARTS, (silk, bells)):
        ob = bpy.data.objects[name]
        if ob.parent != em or any(abs(ob.matrix_basis[i][j] - (i == j)) > 1e-9 for i in range(4) for j in range(4)):
            raise RuntimeError("%s is not at identity under %s" % (name, em.name))
        got = [v.co for v in ob.data.vertices]          # the Empty's frame (float32 world coordinates lose 0.1 mm)
        if len(got) != len(g.verts):
            raise RuntimeError("%s has %d vertices, abode.ribbon_geo makes %d" % (name, len(got), len(g.verts)))
        worst = max((a - (Vector(b) - k)).length for a, b in zip(got, g.verts))
        log("  %s matches abode.ribbon_geo: %d vertices, worst %.2e m" % (name, len(got), worst))
        if worst > 1e-4:
            raise RuntimeError("%s is %.4f m off abode.ribbon_geo" % (name, worst))
    for name, secs, low in info["tails"]:
        L = sum((Vector(a[0]) - Vector(b[0])).length for a, b in zip(secs[:-1], secs[1:]))
        top, end = secs[0][0], secs[-1][0]
        log("  tail %-5s %.2f m of silk, %d sections, from %s to %s (drops %.2f m, %.2f m along the wind); bell's "
            "lowest point %s" % (name, L, len(secs), r3(top), r3(end), top[2] - end[2],
                                 math.hypot(end[0] - top[0], end[1] - top[1]), r3(low)))
    return info, silk


def tails_apart(info, silk):
    """The two tails' surfaces (closed solids of abode.ribbon_geo's silk) must not meet below their first 0.25 m."""
    parts = {nm: (f0, f1) for nm, f0, f1 in silk.parts}
    trees, pts = {}, {}
    for name, secs, _low in info["tails"]:
        f0, f1 = parts["tail." + name]
        faces = silk.faces[f0:f1]
        ids = sorted({i for f in faces for i in f})
        trees[name] = BVHTree.FromPolygons([Vector(p) for p in silk.verts], faces)
        top = Vector(secs[0][0])
        pts[name] = [Vector(silk.verts[i]) for i in ids if (Vector(silk.verts[i]) - top).length > 0.25]
    a, b = [nm for nm, _s, _l in info["tails"]]
    best = min(h[3] for h in (trees[b].find_nearest(p) for p in pts[a]) if h[0] is not None)
    best = min(best, min(h[3] for h in (trees[a].find_nearest(p) for p in pts[b]) if h[0] is not None))
    log("tails %s and %s: nearest %.3f m apart below their first 0.25 m" % (a, b, best))
    if best < TAIL_GAP:
        raise RuntimeError("the two tails come %.4f m close (< %.3f)" % (best, TAIL_GAP))


def bvh_world(ob, M=None):
    me = ob.to_mesh()
    try:
        M = M or ob.matrix_world
        return BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    finally:
        ob.to_mesh_clear()


def neighbours(group, ridge_name):
    """[(name, ribbon mesh, nearest distance, intersects)] for every scene piece (evaluated instances included) whose
    world box comes within NEAR m of a ribbon mesh's."""
    dg = bpy.context.evaluated_depsgraph_get()
    gnames = {o.name for o in group}
    parts = []
    for o in group:
        if o.type == 'MESH':
            vs = world_verts(o)
            parts.append((o, box_of(vs), BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons]), vs))
    gbox = box_of([p for _o, _b, _t, vs in parts for p in vs])
    found = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH' or ob.original.name in gnames:
            continue
        M = inst.matrix_world.copy()
        nb = box_of([M @ Vector(c) for c in ob.bound_box])
        if box_gap(nb, gbox) > NEAR:
            continue
        tree = bvh_world(ob, M)
        label = ob.original.name + ("" if not inst.is_instance else " (instance under %s)" %
                                    (inst.parent.original.name if inst.parent else "?"))
        for o, b, t, vs in parts:
            if box_gap(nb, b) > NEAR:
                continue
            hit = bool(t.overlap(tree))
            d = min((h[3] for h in (tree.find_nearest(p) for p in vs) if h[0] is not None), default=9e9)
            found.append((label, o.name, d, hit, ob.original.name == ridge_name))
    return found


def check_clear(root, group):
    _pav, _v, _e, ridge = AB.ribbon_ridge(root)
    bad = []
    rows = sorted(neighbours(group, ridge.name), key=lambda r: r[2])
    for label, part, d, hit, is_ridge in rows:
        need = MIN_GAP_RIDGE if is_ridge else MIN_GAP
        ok = not hit and d >= need
        log("neighbour %-66s ~ %-19s nearest %.3f m  %s%s" % (label[:66], part, d, "INTERSECTS" if hit else "clear",
                                                              "" if ok else "  <- TOO CLOSE (want %.3f)" % need))
        if not ok:
            bad.append((label, part, round(d, 4)))
    if not any(r[4] for r in rows):
        raise RuntimeError("the ridge %s is not near the ribbon: the loop is not round its tip" % ridge.name)
    if bad:
        raise RuntimeError("ribbon pieces intersect or touch scene pieces: %s" % bad)


def check_lawn(root, info):
    gz = AB._lawn_sampler(bpy.data.objects[GROUND])
    for name, _secs, low in info["tails"]:
        dz = low[2] - gz(low[0], low[1], 0.0)
        log("bell %-5s lowest point %s, %.2f m over the lawn" % (name, r3(low), dz))
        if dz < BELL_LAWN:
            raise RuntimeError("the %s tail's bell is %.2f m over the lawn (< %.1f)" % (name, dz, BELL_LAWN))


def check_mist(group):
    pts = [p for o in group if o.type == 'MESH' for p in world_verts(o)[::5]]
    out = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not any(s.material is not None and "mist_volume" in s.material.name
                                        for s in ob.material_slots):
            continue
        M = ob.matrix_world
        Mi = M.inverted()
        lo = Vector(tuple(min(c[k] for c in ob.bound_box) for k in range(3)))
        hi = Vector(tuple(max(c[k] for c in ob.bound_box) for k in range(3)))
        best = 1e9
        for p in pts:
            q = Mi @ p
            c = Vector(tuple(min(max(q[k], lo[k]), hi[k]) for k in range(3)))
            best = min(best, (M @ c - p).length)
        out.append((best, ob.name))
    out.sort()
    for d, nm in out[:2]:
        log("mist box %-28s nearest ribbon vertex %.2f m" % (nm, d))
    if out and out[0][0] < MIST_GAP:
        raise RuntimeError("the ribbon is %.2f m from %s (< %.1f m)" % (out[0][0], out[0][1], MIST_GAP))


def _clear_objects():
    """Objects a sight line passes through: volume-shaded ones (mist, haze, cloud banks) and the flyer."""
    vol = {m.name for m in bpy.data.materials
           if m.node_tree is not None and any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    out = {o.name for o in bpy.data.objects
           if o.type == 'MESH' and any(s.material is not None and s.material.name in vol for s in o.material_slots)}
    fc = bpy.data.collections.get(EW.FLYER_COLL)
    if fc is not None:
        out |= {o.name for o in fc.all_objects}
    return out


def check_hold(root, info, group):
    """From chase.cam at HOLD: where the tails and bells land on a RES frame and how much of them is in sight."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get(EW.CAMERA)
    if cam is None:
        raise RuntimeError("no %s" % EW.CAMERA)
    f0 = sc.frame_current
    sc.frame_set(HOLD)
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        from bpy_extras.object_utils import world_to_camera_view
        M = root.matrix_world
        eye = cam.matrix_world.translation.copy()
        clear = _clear_objects()
        mine = {o.name for o in group}
        log("hold camera %s at frame %d: %s (abode.root), lens %.1f" % (cam.name, HOLD, r3(root.matrix_world.inverted()
                                                                                         @ eye), cam.data.lens))

        def seen(p):
            d = p - eye
            dist = d.length
            d.normalize()
            o = eye.copy()
            for _ in range(12):
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d, distance=dist - (o - eye).length - 0.02)
                if not hit:
                    return True
                nm = ob.original.name if ob is not None else ""
                if nm in mine:
                    return True
                if nm not in clear:
                    return False
                o = loc + d * 0.01
            return False

        def px(p):
            q = world_to_camera_view(sc, cam, p)
            return q.x * RES[0], (1.0 - q.y) * RES[1], q.z

        for name, secs, low in info["tails"]:
            pts = [M @ Vector(s[0]) for s in secs[::4]]
            scr = [px(p) for p in pts]
            infr = [0 <= x <= RES[0] and 0 <= y <= RES[1] and z > 0 for x, y, z in scr]
            vis = [i and seen(p) for i, p in zip(infr, pts)]
            share = sum(vis) / len(vis)
            xs, ys = [s[0] for s in scr], [s[1] for s in scr]
            mid = secs[len(secs) // 2]
            a, b = M @ Vector(_off(mid, 1.0)), M @ Vector(_off(mid, -1.0))
            wpx = math.hypot(px(a)[0] - px(b)[0], px(a)[1] - px(b)[1])
            bell = M @ Vector(low)
            bx, by, _bz = px(bell)
            log("hold: tail %-5s spans x %.0f..%.0f, y %.0f..%.0f px of %dx%d; %.0f%% of it in frame and in sight; "
                "%.1f px wide at its middle; %.0f m off" % (name, min(xs), max(xs), min(ys), max(ys), RES[0], RES[1],
                                                          100.0 * share, wpx, (pts[len(pts) // 2] - eye).length))
            bv = 0 <= bx <= RES[0] and 0 <= by <= RES[1] and seen(bell + Vector((0.0, 0.0, 0.12)))
            log("hold: bell  %-5s at (%.0f, %.0f) px, %s" % (name, bx, by,
                                                            "in sight" if bv else "HIDDEN or out of frame"))
            if not bv:
                raise RuntimeError("the %s tail's bell is not in sight from the hold camera" % name)
            if name == "long" and share < LONG_SEEN:
                raise RuntimeError("only %.0f%% of the long tail is in sight from the hold (< %.0f%%)"
                                   % (100 * share, 100 * LONG_SEEN))
        k = M @ Vector(info["knot"])
        kx, ky, _kz = px(k)
        log("hold: knot at (%.0f, %.0f) px, %s" % (kx, ky, "in sight" if seen(k) else "behind the eave"))
        tbl = bpy.data.objects.get(AB.DUET + "_table")
        if tbl is not None:
            tx, ty, _tz = px(tbl.matrix_world.translation)
            log("hold: the duet's qin table at (%.0f, %.0f) px" % (tx, ty))
    finally:
        sc.frame_set(f0)


def _off(sec, side):
    p, _t, e, _n, hw, _c = sec
    return tuple(p[k] + e[k] * hw * side for k in range(3))


# --- main --------------------------------------------------------------------------------------------------------

def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    coll = bpy.data.collections.get(COLL)
    if root is None or coll is None:
        raise RuntimeError("no %s / collection %s: is this out/sect_chase.blend?" % (AREA_ROOT, COLL))
    if bpy.data.objects.get(AB.DUET + "_table") is None:
        log("WARN no %s_table: run sect/patch_r5_duet.py first (the ribbon hangs over the duet's qin table)" % AB.DUET)
    n0 = len(bpy.data.objects)
    em, group, old_boxes = build(root, coll)
    info, silk = check_geo(root, em, group)
    tails_apart(info, silk)
    check_clear(root, group)
    check_lawn(root, info)
    check_mist(group)
    check_hold(root, info, group)
    log("objects %d -> %d" % (n0, len(bpy.data.objects)))

    stale = []
    for o in group:
        if o.type != 'MESH':
            continue
        b = world_box(o)
        ob0 = old_boxes.get(o.name)
        if ob0 is None or not inside(b, ob0):
            stale.append(("new or moved: %s" % o.name, rb(ob0) if ob0 else None, rb(b)))
    if stale:
        log("CACHES NEED AUDIT: %d ribbon meshes new or moved (run the export audit, then chunks,meta, then the abode "
            "re-bake, or the bake drops them):" % len(stale))
        for s in stale:
            log("  ", *s)
    else:
        log("CACHES ok: names kept and every world box inside the old one (a re-run)")
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
