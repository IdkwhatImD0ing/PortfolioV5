"""Round 5, lane duet: ground the Smiling, Proud Wanderer duet and take the moss shelf off the cliff over the moon gate,
in a finished out/sect_chase.blend (sect/areas/abode.py makes the same on a full rebuild), and save it. Run on the
cloud box (on a copy first):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r5_duet.py [-- DRY_RUN=1]

1. THE DUET. The floating group (abode.duet: qin, xiao and huqin over a glowing moon-silver ring, 10 m up by the
   waterfall) is replaced by a scene just left (abode._duet): a stone qin table on the lawn at the koi pool's west rim
   with the qin resting on it and the xiao laid across its strings, two stone drum stools, Mo Da's huqin leaning on
   the table's front edge with its bow hanging to the lawn, and a gold sun / white-jade crescent emblem (日月) on the
   table's apron. The ring (abode.duet_ring) is gone. Objects, all tagged obj['sect_item'] = 'wanderer_duet':
       abode.duet             Empty under abode.root at abode.DUET_LOC (z 0), turned DUET_YAW, scale DUET_SCALE
       abode.duet_table       stone_grey, gold, props_jade_white
       abode.duet_seat_qin    stone_grey
       abode.duet_seat_xiao   stone_grey
       abode.duet_qin         (as before)
       abode.duet_xiao        (as before)
       abode.duet_huqin       (as before, bow hanging)
2. THE GARDEN MASK. abode.ground's 'garden_mask' is cleared round the set (abode.duet_keep_clear, 0.8 m like
   abode._garden_mask), so abode.garden_scatter drops the plants that stood there (listed); no other instance moves.
3. THE CLIFF. abode.cliff's vertices move onto abode._cliff_verts(): the slope cap (abode.CAP_*) over the dressed rock
   pulls the rock above the gate forward where it stood far behind it, so the shelf the rock moss painted as a green
   smear (z 17-22 m, normal z up to 0.84) becomes a face leaning back 14 deg. Same vertex count and faces; only
   front-face vertices over the dressed zone move (checked); sharp edges are recomputed as abode._cliff does.
   The face pines whose roots sat on the moved rock (abode._face_point + 0.6 m in y) move with it.

Checks before saving (it stops without saving when one fails): the cliff's vertex count and the moved vertices'
region; every face pine either unmoved or inside the cap's reach; the duet's names exactly (no '.001'), each mesh
within abode.DUET_TRI_CAP triangles and closed (bake_web's closed-piece rule); the set at least 2 m outside every
mist_volume box; no duet piece intersecting any scene piece other than abode.ground (instances included: plants, the
koi ledge, flagstones, the pool), with the nearest distances logged; every base on the lawn (stools, legs, plinths and
the huqin's foot sunk 1-6 cm, the bow's tip resting on it); no scatter instance added or moved by the mask.

Caches: the duet objects are new or moved and the face pines moved, so it prints 'PATCH CACHES STALE' with the list
(run the export audit, then chunks,meta, then re-bake the abode); 'PATCH CACHES ok' only when nothing moved (a re-run).
Idempotent: a re-run removes its own previous duet and builds it again (same names, same geometry), finds the cliff,
the pines and the mask already in place and changes nothing else. Options after '--': DRY_RUN=1 (report, no save).
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

from sect.areas import abode as AB  # noqa: E402
from sect.lib import util as U  # noqa: E402

AREA_ROOT = "abode.root"
COLL = "abode"
GROUND = "abode.ground"
CLIFF = "abode.cliff"
SCATTER = "abode.garden_scatter"
MIST_GAP = 2.0
NEAR = 1.0
OLD_EXTRA = ("abode.duet_ring",)     # the round-1 group's ring: removed with the group
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
            raise SystemExit("patch_r5_duet: unknown option %r (DRY_RUN=1)" % a)
    return dry


def names():
    return [AB.DUET] + [nm for _k, nm, _g, _r in AB.DUET_PARTS]


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


def world_box(ob):
    """World box of an object and everything under it (bound boxes of meshes; empties by location)."""
    pts = []
    for o in [ob] + list(ob.children_recursive):
        if o.type == 'EMPTY':
            pts.append(o.matrix_world.translation.copy())
        else:
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    return box_of(pts)


# --- 1. cliff ----------------------------------------------------------------------------------------------------

def patch_cliff(root):
    ob = bpy.data.objects.get(CLIFF)
    if ob is None or ob.type != 'MESH':
        raise RuntimeError("%s not found" % CLIFF)
    me = ob.data
    if me.users != 1:
        raise RuntimeError("%s mesh has %d users" % (CLIFF, me.users))
    ident = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    if any(abs(a - b) > 1e-9 for ra, rb_ in zip(ob.matrix_local, ident) for a, b in zip(ra, rb_)) or ob.parent != root:
        raise RuntimeError("%s is not at identity under %s" % (CLIFF, AREA_ROOT))
    new = AB._cliff_verts()
    nv = len(me.vertices)
    if nv != len(new) + 2:                     # + the two end-cap fan centres
        raise RuntimeError("%s has %d vertices, abode._cliff_verts makes %d (+2 cap centres)" % (CLIFF, nv, len(new)))
    old = [0.0] * (3 * nv)
    me.vertices.foreach_get("co", old)
    box0 = box_of([ob.matrix_world @ Vector(c) for c in ob.bound_box])
    ncol = AB.NZ + 1 + AB.NT + AB.NB
    moved, worst, outside = 0, 0.0, []
    flat = list(old)
    for i, p in enumerate(new):
        o = Vector(old[3 * i:3 * i + 3])
        d = (p - o).length
        if d > 1e-5:
            moved += 1
            worst = max(worst, d)
            col, row = divmod(i, ncol)
            if row > AB.NZ or AB._cap_w(p.x, p.z) <= 0.0 or abs(p.x - o.x) > 1e-5 or abs(p.z - o.z) > 1e-5:
                outside.append((i, col, row, tuple(round(v, 3) for v in o), tuple(round(v, 3) for v in p)))
        flat[3 * i:3 * i + 3] = (p.x, p.y, p.z)
    # the two end-cap fan centres: the mean of their column profile (abode._cliff)
    for k, col in enumerate((0, AB.NX)):
        c = sum((new[col * ncol + j] for j in range(ncol)), Vector()) / ncol
        ci = len(new) + k
        o = Vector(old[3 * ci:3 * ci + 3])
        if (c - o).length > 1e-3:
            outside.append((ci, "cap", col, tuple(round(v, 3) for v in o), tuple(round(v, 3) for v in c)))
        flat[3 * ci:3 * ci + 3] = (c.x, c.y, c.z)
    if outside:
        for r in outside[:20]:
            log("  unexpected cliff vertex change", r)
        raise RuntimeError("%d cliff vertices would move outside the slope cap's front-face region" % len(outside))
    if moved:
        me.vertices.foreach_set("co", flat)
        me.update()
        U.auto_smooth(ob, math.radians(50))
    box1 = box_of([ob.matrix_world @ Vector(c) for c in ob.bound_box])
    log("cliff %s: %d of %d vertices moved onto abode._cliff_verts (most %.2f m, all front face over the dressed zone, "
        "toward the camera)" % (CLIFF, moved, nv, worst))
    log("  world box before %s after %s" % (rb(box0), rb(box1)))
    return moved, box0, box1


def face_pines(root, dry_moves):
    """Face pines (abode.cliff_pine*, abode.dense_cliff_pine*) back on the face: y = abode._face_y(x, z) + 0.6."""
    out = []
    for ob in bpy.data.objects:
        if ob.parent != root or not (ob.name.startswith(AB.K + ".cliff_pine") or
                                     ob.name.startswith(AB.K + ".dense_cliff_pine")):
            continue
        x, y, z = ob.location
        want = AB._face_y(x, z) + 0.6
        if abs(want - y) <= 1e-4:
            continue
        if AB._cap_w(x, z) <= 0.0:
            raise RuntimeError("%s at (%.2f, %.2f, %.2f) is %.3f m off the face outside the slope cap: the face "
                               "formula does not reproduce it" % (ob.name, x, y, z, y - want))
        b0 = world_box(ob)
        ob.location.y = want
        out.append((ob.name, (round(x, 2), round(y, 3), round(z, 2)), round(want, 3), b0))
    bpy.context.view_layer.update()
    for nm, old, new_y, b0 in out:
        log("face pine %s at %s: y -> %.3f (moves %.2f m with the rock), world box %s -> %s"
            % (nm, old, new_y, new_y - old[1], rb(b0), rb(world_box(bpy.data.objects[nm]))))
    if not out:
        log("face pines: none needed to move")
    return out


# --- 2. garden mask ----------------------------------------------------------------------------------------------

def scatter_instances():
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.name == SCATTER:
            t = inst.matrix_world.translation
            key = (inst.object.original.name, round(t.x, 3), round(t.y, 3), round(t.z, 3))
            out[key] = out.get(key, 0) + 1
    return out


def patch_mask(root):
    g = bpy.data.objects.get(GROUND)
    if g is None:
        raise RuntimeError("%s not found" % GROUND)
    if g.parent != root:
        raise RuntimeError("%s is not under %s" % (GROUND, AREA_ROOT))
    log("ground %s: modifiers %s (the lawn sampler reads its mesh)" % (GROUND, [m.type for m in g.modifiers]))
    att = g.data.attributes.get("garden_mask")
    if att is None or att.domain != 'POINT':
        raise RuntimeError("%s has no POINT attribute garden_mask" % GROUND)
    M = g.matrix_local                   # ground frame -> abode.root frame
    rects = AB.duet_keep_clear()
    vals = [0.0] * len(g.data.vertices)
    att.data.foreach_get("value", vals)
    co = [0.0] * (3 * len(g.data.vertices))
    g.data.vertices.foreach_get("co", co)
    cleared = 0
    for i in range(len(vals)):
        if vals[i] <= 0.5:
            continue
        p = M @ Vector(co[3 * i:3 * i + 3])
        if any(AB._rect_d(p.x, p.y, r) < 0.8 for r in rects):
            vals[i] = 0.0
            cleared += 1
    before = scatter_instances()
    if cleared:
        att.data.foreach_set("value", vals)
        g.data.update()
        bpy.context.view_layer.update()
    after = scatter_instances()
    gone = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    W = root.matrix_world.inverted()
    log("garden mask: %d lawn vertices cleared round the set (rect in abode.root %s); scatter instances %d -> %d"
        % (cleared, tuple(round(v, 2) for v in rects[0][:4]), sum(before.values()), sum(after.values())))
    for k in gone:
        p = W @ Vector(k[1:])
        log("  plant removed: %s at abode.root (%.2f, %.2f, %.2f)" % (k[0], p.x, p.y, p.z))
    if added:
        raise RuntimeError("the mask change added or moved %d scatter instances: %s" % (len(added), added[:5]))
    return cleared, gone


# --- 3. duet -----------------------------------------------------------------------------------------------------

def remove_previous():
    want = set(names()) | set(OLD_EXTRA)
    obs = [o for o in bpy.data.objects if o.get("sect_item") == AB.DUET_ITEM or o.name in want]
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


def world_verts(ob):
    M = ob.matrix_world
    return [M @ v.co for v in ob.data.vertices]


def mist_report(group_pts):
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
        for p in group_pts[::7]:
            q = Mi @ p
            c = Vector(tuple(min(max(q[k], lo[k]), hi[k]) for k in range(3)))
            best = min(best, (M @ c - p).length)
        out.append((best, ob.name))
    return sorted(out)


def bvh_world(ob, M=None):
    me = ob.to_mesh()
    try:
        M = M or ob.matrix_world
        return BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    finally:
        ob.to_mesh_clear()


def neighbours(group):
    """[(name, nearest distance, intersects)] for every scene piece (evaluated instances included) whose world box comes
    within NEAR m of a group mesh's."""
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
        corners = [M @ Vector(c) for c in ob.bound_box]
        nb = box_of(corners)
        if box_gap(nb, gbox) > NEAR:
            continue
        tree = bvh_world(ob, M)
        label = ob.original.name + ("" if not inst.is_instance else " (instance under %s)" %
                                    (inst.parent.original.name if inst.parent else "?"))
        for o, b, t, vs in parts:
            if box_gap(nb, b) > NEAR:
                continue
            hit = bool(t.overlap(tree))
            d = min((h[3] for h in (tree.find_nearest(p) for p in vs[::3]) if h[0] is not None), default=9e9)
            found.append((label, o.name, d, hit))
    return found


def lawn_contacts(root, group):
    """Lowest point of each duet mesh against the lawn under it (abode.ground's mesh, abode._lawn_sampler)."""
    gz = AB._lawn_sampler(bpy.data.objects[GROUND])
    W = root.matrix_world.inverted()
    out = {}
    for o in group:
        if o.type != 'MESH':
            continue
        vs = [W @ p for p in world_verts(o)]
        low = min(vs, key=lambda p: p.z - gz(p.x, p.y, 0.0))
        out[o.name] = (low.z - gz(low.x, low.y, 0.0), tuple(round(v, 2) for v in low))
    return out


def build_duet(root, coll):
    gone, old_boxes = remove_previous()
    if gone:
        log("removed the previous duet:", gone)
    n_obj = len(bpy.data.objects)
    mats_before = {m.name for m in bpy.data.materials}
    em = AB._duet(coll, root, gz=AB._lawn_sampler(bpy.data.objects[GROUND]))
    bpy.context.view_layer.update()
    group = [em] + list(em.children_recursive)
    got = sorted(o.name for o in group)
    if got != sorted(names()):
        raise RuntimeError("unexpected object names %s (wanted %s): a name was taken" % (got, sorted(names())))
    if len(bpy.data.objects) != n_obj + len(names()):
        raise RuntimeError("object count %d -> %d, expected +%d" % (n_obj, len(bpy.data.objects), len(names())))
    log("BUILT %d objects in collection '%s': %s" % (len(names()), COLL, ", ".join(names())))
    log("  %s under %s at %s, rotation deg %s, scale %s" % (AB.DUET, em.parent.name,
                                                          tuple(round(x, 3) for x in em.location),
                                                          tuple(round(math.degrees(x), 2) for x in em.rotation_euler),
                                                          tuple(round(x, 3) for x in em.scale)))
    W = root.matrix_world.inverted()
    pts, total = [], 0
    for ob in group:
        if ob.type != 'MESH':
            continue
        t, oe = tris(ob.data), open_edges(ob.data)
        total += t
        vs = world_verts(ob)
        pts.extend(vs)
        lo, hi = box_of([W @ p for p in vs])
        log("  %-22s tris %5d  open edges %d  materials %s  box in abode.root %s .. %s"
            % (ob.name, t, oe, [s.material.name if s.material else None for s in ob.material_slots],
               tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi)))
        if t > AB.DUET_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, AB.DUET_TRI_CAP))
        if oe:
            raise RuntimeError("%s has %d open edges: not closed" % (ob.name, oe))
    log("  triangles in all: %d (the old group with its ring: %d objects)" % (total, len(old_boxes)))
    new_mats = sorted({m.name for m in bpy.data.materials} - mats_before)
    log("  materials created (were not in the file yet):", new_mats or "none")
    lay = AB.duet_layout(AB.duet_lawn(AB._lawn_sampler(bpy.data.objects[GROUND])))
    log("  xiao axis %.4f m over the qin's back (resting on its highest string), bow droop %.1f deg, huqin at %s"
        % (AB.xiao_rest_z(), math.degrees(AB.huqin_bow_droop(AB.duet_lawn(AB._lawn_sampler(
            bpy.data.objects[GROUND])))), tuple(round(v, 3) for v in lay["huqin"][0])))
    return em, group, pts, old_boxes


def check_duet(root, group, pts):
    mists = mist_report(pts)
    for d, nm in mists[:3]:
        log("mist box %-28s nearest duet vertex %.2f m" % (nm, d))
    if mists and mists[0][0] < MIST_GAP:
        raise RuntimeError("the set is %.2f m from %s (< %.1f m)" % (mists[0][0], mists[0][1], MIST_GAP))
    bad = []
    for label, part, d, hit in sorted(neighbours(group), key=lambda r: r[2]):
        tag = "INTERSECTS" if hit else "clear"
        log("neighbour %-62s ~ %-22s nearest %.3f m  %s" % (label[:62], part, d, tag))
        if hit and not label.startswith(GROUND):
            bad.append((label, part))
    if bad:
        raise RuntimeError("duet pieces intersect scene pieces: %s" % bad)
    contacts = lawn_contacts(root, group)
    S = AB.DUET_SCALE                    # sinks are in the duet frame; the lawn under a base varies by up to 4 cm
    want = {AB.K + ".duet_table": (-AB.TABLE_SINK * S - 0.04, -0.03),
            AB.K + ".duet_seat_qin": (-AB.SEAT_SINK * S - 0.04, -0.02),
            AB.K + ".duet_seat_xiao": (-AB.SEAT_SINK * S - 0.04, -0.02),
            AB.K + ".duet_huqin": (-AB.HQ_FOOT_SINK * S - 0.02, 0.0)}
    for nm, (dz, p) in sorted(contacts.items()):
        rng = want.get(nm)
        ok = rng is None or rng[0] <= dz <= rng[1]
        log("lowest point of %-22s %+.3f m against the lawn at %s %s" % (nm, dz, p, "" if ok else "<- OUT OF RANGE"))
        if not ok:
            raise RuntimeError("%s base %.3f m against the lawn (want %s)" % (nm, dz, rng))


# --- main --------------------------------------------------------------------------------------------------------

def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    coll = bpy.data.collections.get(COLL)
    if root is None or coll is None:
        raise RuntimeError("no %s / collection %s: is this out/sect_chase.blend?" % (AREA_ROOT, COLL))
    n0 = len(bpy.data.objects)
    moved, cb0, cb1 = patch_cliff(root)
    pines = face_pines(root, dry)
    cleared, plants = patch_mask(root)
    em, group, pts, old_boxes = build_duet(root, coll)
    check_duet(root, group, pts)
    log("objects %d -> %d" % (n0, len(bpy.data.objects)))

    stale = []
    if moved and not inside(cb1, cb0):
        stale.append(("%s world box grew" % CLIFF, rb(cb0), rb(cb1)))
    for nm, _old, _new, b0 in pines:
        stale.append(("face pine moved: %s" % nm, rb(b0), rb(world_box(bpy.data.objects[nm]))))
    if plants:
        stale.append(("%s lost %d instances" % (SCATTER, len(plants)),))
    for o in group:
        if o.type != 'MESH':
            continue
        b = world_box(o)
        ob0 = old_boxes.get(o.name)
        if ob0 is None or not inside(b, ob0):
            stale.append(("duet piece new or moved: %s" % o.name, rb(ob0) if ob0 else None, rb(b)))
    for nm in sorted(set(old_boxes) - {o.name for o in group}):
        stale.append(("removed: %s" % nm,))
    if stale:
        log("CACHES STALE: %d changes need the export audit (new/moved objects), then chunks,meta, then the abode "
            "re-bake:" % len(stale))
        for s in stale:
            log("  ", *s)
    else:
        log("CACHES ok: names kept and every world box inside the old one (nothing moved: a re-run)")
    if moved:
        log("the cliff moved %d vertices inside its own box (%s)" % (moved, "box unchanged" if inside(cb1, cb0) else
                                                                     "BOX GREW"))
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
