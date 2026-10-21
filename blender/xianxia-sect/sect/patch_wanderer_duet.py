"""Add the Smiling, Proud Wanderer duet 笑傲江湖 (sect/areas/abode.py _duet) to out/sect_chase.blend and save it. Run on
the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_wanderer_duet.py [-- DRY_RUN=1]

Wanderer ch. 7 授谱: Qu Yang's seven-string qin, Liu Zhengfeng's xiao and Mo Da's huqin (a sword hilt where its neck
enters the box), floating as relics beside the abode's waterfall pool on a thin moon-silver qi ring. A full rebuild
makes the same group (abode.build calls abode._duet); this script runs that builder on the finished file.

ADDS five objects to the 'abode' collection, nothing else changes (no existing object is renamed, moved or removed):
    abode.duet          Empty under abode.root at abode.DUET_LOC, turned DUET_YAW, tilted DUET_TILT, scaled DUET_SCALE
    abode.duet_qin      guqin (lacquer_black, cloth_white, props_jade_white, wood_dark, cloth_red)
    abode.duet_xiao     aged-bamboo xiao (abode_xiao_bamboo: a bamboo_stalk variant registered by abode.py, cloth_red)
    abode.duet_huqin    Mo Da's huqin (wood_dark, props_drum_skin, wood_light, props_feather_white, steel, cloth_black)
    abode.duet_ring     qi ring (rune_silver), shadow off
Every one carries obj['sect_item'] = 'wanderer_duet'. Idempotent: a re-run first removes its own previous output
(objects tagged so, or with those names, and their meshes), then builds the group again under the same names.

Checks before saving (it stops without saving when one fails): the five names came out exactly (no '.001'), each mesh
within abode.DUET_TRI_CAP triangles and closed (every edge in two or more faces: bake_web's closed-piece rule), the
group at least 2 m outside every mist_volume box (it prints the distance), and it logs every scene piece (instances
included) whose box comes within 1 m of the group's, with the true nearest distance.

New objects are not in the web caches: after saving, run the export audit, then chunks,meta, before the bake (see
the report build_wanderer_duet.md). Options after '--': DRY_RUN=1 (build, report, no save).
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

AREA_ROOT = "abode.root"
COLL = "abode"
MIST_GAP = 2.0
NEAR = 1.0


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
            raise SystemExit("patch_wanderer_duet: unknown option %r (DRY_RUN=1)" % a)
    return dry


def names():
    return [AB.DUET] + [nm for _k, nm, _g, _r in AB.DUET_PARTS]


def remove_previous():
    """Remove the group a previous run made (tagged objects, the group's names, their children) and free their
    meshes. Returns the removed names."""
    want = set(names())
    obs = [o for o in bpy.data.objects if o.get("sect_item") == AB.DUET_ITEM or o.name in want]
    for o in list(obs):
        obs.extend(c for c in o.children_recursive if c not in obs)
    gone = []
    meshes = set()
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


def world_verts(ob):
    M = ob.matrix_world
    return [M @ v.co for v in ob.data.vertices]


def box_of(pts):
    return (Vector(tuple(min(p[k] for p in pts) for k in range(3))),
            Vector(tuple(max(p[k] for p in pts) for k in range(3))))


def box_gap(a, b):
    return math.sqrt(sum(max(a[0][k] - b[1][k], 0.0, b[0][k] - a[1][k]) ** 2 for k in range(3)))


def mist_report(group_pts):
    """Nearest distance (m) from the group's vertices to every box whose material is mist_volume (exact for a rotated,
    axis-scaled box: clamp in the box's own space, measure in the world)."""
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
        for p in group_pts:
            q = Mi @ p
            c = Vector(tuple(min(max(q[k], lo[k]), hi[k]) for k in range(3)))
            best = min(best, (M @ c - p).length)
        out.append((best, ob.name))
    return sorted(out)


def neighbours(group, group_pts):
    """Scene pieces (evaluated instances included) whose world box is within NEAR m of the group's, with the nearest
    distance from a group vertex to their surface."""
    gbox = box_of(group_pts)
    dg = bpy.context.evaluated_depsgraph_get()
    gnames = {o.name for o in group}
    found = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH' or ob.original.name in gnames:
            continue
        M = inst.matrix_world
        corners = [M @ Vector(c) for c in ob.bound_box]
        if box_gap(box_of(corners), gbox) > NEAR:
            continue
        me = ob.to_mesh()
        try:
            bvh = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        finally:
            ob.to_mesh_clear()
        hits = (bvh.find_nearest(p) for p in group_pts)
        d = min((h[3] for h in hits if h[0] is not None), default=None)
        label = ob.original.name + ("" if not inst.is_instance else " (instance of %s)" %
                                    (inst.parent.original.name if inst.parent else "?"))
        found.append((d if d is not None else 9e9, label))
    return sorted(found)


def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    coll = bpy.data.collections.get(COLL)
    if root is None or coll is None:
        raise RuntimeError("no %s / collection %s: is this out/sect_chase.blend?" % (AREA_ROOT, COLL))
    gone = remove_previous()
    if gone:
        log("removed the previous run's output:", gone)
    n_obj, n_mat = len(bpy.data.objects), len(bpy.data.materials)
    mats_before = {m.name for m in bpy.data.materials}
    em = AB._duet(coll, root)
    bpy.context.view_layer.update()
    group = [em] + list(em.children_recursive)
    got = sorted(o.name for o in group)
    if got != sorted(names()):
        raise RuntimeError("unexpected object names %s (wanted %s): a name was taken" % (got, sorted(names())))
    if len(bpy.data.objects) != n_obj + len(names()):
        raise RuntimeError("object count %d -> %d, expected +%d" % (n_obj, len(bpy.data.objects), len(names())))
    log("ADDED %d objects to collection '%s' (nothing else changed): %s" % (len(names()), COLL, ", ".join(names())))
    W = root.matrix_world.inverted()
    log(AB.DUET, "under", em.parent.name, "location", tuple(round(x, 3) for x in em.location),
        "rotation deg", tuple(round(math.degrees(x), 2) for x in em.rotation_euler))
    pts = []
    total = 0
    for ob in group:
        if ob.type != 'MESH':
            continue
        t, oe = tris(ob.data), open_edges(ob.data)
        total += t
        vs = world_verts(ob)
        pts.extend(vs)
        lo, hi = box_of([W @ p for p in vs])
        log("  %-18s tris %5d  open edges %d  materials %s  shadow %s  box in abode.root %s .. %s"
            % (ob.name, t, oe, [s.material.name if s.material else None for s in ob.material_slots],
               ob.visible_shadow, tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi)))
        if t > AB.DUET_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, AB.DUET_TRI_CAP))
        if oe:
            raise RuntimeError("%s has %d open edges: not closed" % (ob.name, oe))
    log("triangles in all: %d" % total)
    new_mats = sorted({m.name for m in bpy.data.materials} - mats_before)
    log("materials created (were not in the file yet):", new_mats or "none", "(%d -> %d)" % (n_mat,
                                                                                           len(bpy.data.materials)))
    lo, hi = box_of([W @ p for p in pts])
    log("group box in abode.root: %s .. %s" % (tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi)))
    mists = mist_report(pts)
    for d, nm in mists[:4]:
        log("mist box %-28s nearest group vertex %.2f m" % (nm, d))
    if not mists:
        log("WARN no mist_volume object found")
    elif mists[0][0] < MIST_GAP:
        raise RuntimeError("the group is %.2f m from %s (< %.1f m)" % (mists[0][0], mists[0][1], MIST_GAP))
    near = neighbours(group, pts)
    for d, label in near:
        log("neighbour within %.0f m (box): %-60s nearest surface %.2f m" % (NEAR, label, d))
    if not near:
        log("no scene piece within %.0f m of the group's box" % NEAR)
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
