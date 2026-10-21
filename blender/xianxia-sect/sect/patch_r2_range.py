"""Phase 3 (2026-10-21): world.range in out/sect_chase.blend rebuilt on world.GRID's 2.5 m heightfield in place
(sect/world.py build_terrain), with the face masks its tree scatters read. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r2_range.py [-- DRY_RUN=1]

Why: on the 5 m grid the steep walls were 17-33 m slivers with zigzag folds (the stepped slabs of the mission
terrace's cliff at the arena hold 516 and of the abode's skirt at 1208; facet3/diag_blender.md cause 3).

What changes (object names stay; no object is added or removed):
- world.range keeps its object, material slots and children; its mesh is replaced by the 2.5 m build (about 4x the
  vertices). The fields are world.py's (Range), so every old 5 m node is a node of the new mesh at the same height.
- FACE masks on the new mesh: world_veg (build_terrain, cleared near the links), scenery_forest / _grove / _cliff
  (scenery.forest_masks) and scenery_cliff_dense / _wall / scenery_crown (scenery.density_masks), each from the
  paths and rules that made them. The scatters that read them (world.range.forest, scenery.forest, .grove,
  .cliffpines, .cliffpines.dense, .cliffpines.walls, .crowns) are geometry nodes on world.range, so they re-seed on
  the new faces by themselves: same densities, new points. The masks read normals averaged over 5 m cells
  (scenery.cell_nz, the scale they were tuned on), and the three cliff scatters accept faces up to 100 deg from
  flat (scenery.CLIFF_SCATTER_SLOPE): face by face, the finer walls' flutes failed both tests and a column wall at
  830 kept 15 of its 54 wall pines.
- The range falls (scenery.fall* sheets that pour off its top, origin 0.2 m over the lip) move up or down by however
  much the range under their origin moved, so they stay on their lips (up to about 4 m; most under 5 cm).
Not changed here: the life pass's ledge trees and shrines (sect.life) stand on the old faces. Run
sect/patch_life.py PARTS=ledges right after this, so they snap to the new walls.

Guards (nothing is saved when one fails): world.range's mesh must be world.py's own range, vertex for vertex (1 cm),
on the 5 m grid (or already on world.GRID: then only the masks are made again, the same way: idempotent); it has no
attributes but the known ones; every mask comes out non-empty.

Report: vertices and faces before / after; steep-wall folds (share of edges between top faces folding more than
45 deg; mean longest edge of steep faces) over the whole range and near the mission and abode terraces; how far the
range moved under each scenery.fall* sheet's lip; masked areas before / after.

Afterwards: patch_life PARTS=ledges, then export_web audit --profile full (the scatters' instance keys change),
chunks,meta, bakefull for every area plus backdrop (every chunk carries range faces), bake_web water, bake_trees
plan,build, and the pack. Size: the bake's weighted decimation keeps BIG_RATIO_FULL (0.6) of the range's faces, so
the shipped range triangles grow with the source; see the run report.
"""
import ast
import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect import world as W  # noqa: E402
from sect.lib import nature as N  # noqa: E402

RANGE = "world.range"
TOL = 0.01
OLD_GRID = 5.0
KNOWN = {"position", "material_index", "sharp_edge", "sharp_face", "world_veg", "scenery_forest", "scenery_grove",
         "scenery_cliff"} | set(S.DENSITY_MASKS)
FOREST = ("scenery_forest", "scenery_grove", "scenery_cliff")
LIP_UP = 0.2                   # scenery.build_range_falls: a fall's origin stands this far over its lip
NEAR = {"mission": 140.0, "abode": 140.0}
CLIFF_SCATTERS = ("scenery.cliffpines", "scenery.cliffpines.dense", "scenery.cliffpines.walls")   # fold stats near these terraces (the 516 cliff, the 1208 skirt)


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
            raise SystemExit("patch_r2_range: unknown argument %r (DRY_RUN=1)" % a)
    return opt


def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def face_ints(me, name):
    a = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get(name, a)
    return a


def grid_of(me):
    k = (coords(me)[:, 0] - W.EXTENT[0]) / 2.5
    kr = np.round(k)
    odd = (np.abs(k - kr) < 1e-4) & (kr % 2 == 1)
    return 2.5 if int(odd.sum()) > 1000 else OLD_GRID


def masks_m2(me):
    area = np.empty(len(me.polygons))
    me.polygons.foreach_get("area", area)
    out = {}
    for a in me.attributes:
        if a.domain == 'FACE' and a.data_type == 'FLOAT' and not a.name.startswith("."):
            v = np.empty(len(me.polygons), np.float32)
            a.data.foreach_get("value", v)
            out[a.name] = round(float(area[v > 0.5].sum()))
    return out


def fold_stats(me, centre=None, radius=None):
    """Top faces (material 0 / 1): share of their shared edges folding > 45 deg, and the mean longest edge (m) of
    steep ones (normal z < 0.5); within ``radius`` m (XY) of ``centre`` when given."""
    n = len(me.polygons)
    mi = face_ints(me, "material_index")
    nrm = np.empty(n * 3)
    me.polygons.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    cen = np.empty(n * 3)
    me.polygons.foreach_get("center", cen)
    cen = cen.reshape(-1, 3)
    sel = mi != 2
    if centre is not None:
        sel &= np.hypot(cen[:, 0] - centre[0], cen[:, 1] - centre[1]) < radius
    ls, lt = face_ints(me, "loop_start"), face_ints(me, "loop_total")
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", le)
    order = np.argsort(ls)
    fpl = np.repeat(order, lt[order])            # face of each loop (loops are contiguous per face)
    keep = sel[fpl]
    e, f = le[keep], fpl[keep]
    o = np.argsort(e, kind="stable")
    e, f = e[o], f[o]
    pair = np.nonzero(e[1:] == e[:-1])[0]
    fa, fb = f[pair], f[pair + 1]
    cos = np.clip((nrm[fa] * nrm[fb]).sum(1), -1.0, 1.0)
    fold45 = float((cos < np.cos(np.radians(45.0))).mean()) if len(cos) else 0.0
    co = coords(me)
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    elen = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
    longest = np.zeros(n)
    np.maximum.at(longest, fpl, elen[le])
    steep = sel & (nrm[:, 2] < 0.5)
    return dict(faces=int(sel.sum()), edges=int(len(cos)), fold45=round(100.0 * fold45, 1),
                steep_faces=int(steep.sum()), steep_longest_edge=round(float(longest[steep].mean()), 1) if steep.any() else 0)


RANGE_FALL = re.compile(r"^scenery\.fall(\.\d{3})?$")    # build_range_falls' sheets (islands': scenery.island.fall)


def range_falls_z(ob):
    """{range fall: height of world.range under its origin}, on the evaluated range as scenery.build_range_falls cast
    it (BVHTree.FromObject: the same triangulation; a lip 3 m from a 13 m drop moves 0.6 m with the other one)."""
    bpy.context.view_layer.update()
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    mi = ob.matrix_world.inverted()
    out = {}
    for o in bpy.data.objects:
        if o.parent is None and RANGE_FALL.match(o.name):
            p = o.matrix_world.translation
            hit = bvh.ray_cast(mi @ Vector((p.x, p.y, p.z + 300.0)), Vector((0.0, 0.0, -1.0)), 2000.0)[0]
            out[o.name] = None if hit is None else (ob.matrix_world @ hit).z
    return out


def main():
    opt = options()
    sc = bpy.context.scene
    ob = bpy.data.objects.get(RANGE)
    if ob is None or ob.type != 'MESH':
        raise SystemExit("patch_r2_range: no %s mesh; is this out/sect_chase.blend?" % RANGE)
    me0 = ob.data
    extra = sorted(a.name for a in me0.attributes if not a.name.startswith(".") and a.name not in KNOWN)
    if extra:
        raise RuntimeError("%s carries attributes this patch would drop: %s" % (RANGE, extra))
    if me0.users != 1 or any(s.link != 'DATA' for s in ob.material_slots):
        raise RuntimeError("%s: mesh users %d / object-linked slots" % (RANGE, me0.users))
    rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
    g0 = grid_of(me0)
    log("%s: %d vertices, %d faces, on the %g m grid (world.GRID %g)" % (RANGE, len(me0.vertices), len(me0.polygons),
                                                                         g0, W.GRID))
    if g0 not in (OLD_GRID, W.GRID):
        raise RuntimeError("unexpected grid %g" % g0)
    tmp = bpy.data.collections.new("patch_r2_range.tmp")       # not in the scene
    swapped = False
    m2_before = masks_m2(me0)
    stats_before = dict(all=fold_stats(me0), **{k: fold_stats(me0, W.ANCHORS[k], r) for k, r in NEAR.items()})
    try:
        ref, _ = W.build_terrain(rng_, tmp, grid=g0, name="patch_r2.range.ref")
        c0, c1 = coords(me0), coords(ref.data)
        if c0.shape != c1.shape or float(np.abs(c0 - c1).max()) > TOL:
            raise RuntimeError("%s is not world.py's %g m range: %s" % (
                RANGE, g0, ("%d vs %d vertices" % (len(c0), len(c1))) if c0.shape != c1.shape
                else "max vertex offset %.3f m" % float(np.abs(c0 - c1).max())))
        if not np.array_equal(face_ints(me0, "material_index"), face_ints(ref.data, "material_index")):
            raise RuntimeError("%s's face materials differ from world.py's" % RANGE)
        log("guard: the scene's range is world.py's %g m build (max vertex offset %.4f m)"
            % (g0, float(np.abs(c0 - c1).max())))
        if g0 != W.GRID:
            new, _ = W.build_terrain(rng_, tmp, grid=W.GRID, name="patch_r2.range.new")
            z_old = range_falls_z(ob)
            name = me0.name
            me1 = new.data
            bpy.data.objects.remove(new, do_unlink=True)
            ob.data = me1
            bpy.data.meshes.remove(me0)
            me1.name = name
            swapped = True
            z_new = range_falls_z(ob)
            # a range fall stands LIP_UP over the top it pours from (scenery.build_range_falls): keep it there
            shifted, skipped = [], []
            for nm, z0_ in sorted(z_old.items()):
                o = bpy.data.objects[nm]
                z1_ = z_new.get(nm)
                if z0_ is None or z1_ is None or abs(o.matrix_world.translation.z - LIP_UP - z0_) > 0.3:
                    skipped.append(nm)
                    continue
                if abs(z1_ - z0_) >= 0.01:
                    o.location.z += z1_ - z0_
                    shifted.append((nm, round(z1_ - z0_, 2)))
            dz = np.array([s_[1] for s_ in shifted]) if shifted else np.zeros(1)
            log("range falls: %d on their lips, %d moved with the range under them (median |dz| %.2f m, max %.2f m), "
                "%d not on a lip left alone" % (len(z_old) - len(skipped), len(shifted), float(np.median(np.abs(dz))),
                                                float(np.abs(dz).max()), len(skipped)))
            for nm, d_ in sorted(shifted, key=lambda s_: -abs(s_[1]))[:6]:
                log("  fall", nm, "dz %+.2f m" % d_)
        else:
            log("already on the %g m grid: masks only" % W.GRID)
    finally:
        for o in list(tmp.objects):
            m = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)
        bpy.data.collections.remove(tmp)
    me = ob.data
    # masks: world_veg comes with the build; clear it near the links as world.build does
    log("world_veg faces cleared near links:", W.clear_mask_near(ob, ["world_veg"], W.link_points()))
    # the cliff scatters' own per-face slope test (scenery.CLIFF_SCATTER_SLOPE): the masks now pick 5 m cells
    # (scenery.cell_nz), and on the fluted walls inside them faces stand past the old 80-86 deg
    want = math.cos(math.radians(S.CLIFF_SCATTER_SLOPE))
    for nm in CLIFF_SCATTERS:
        so = bpy.data.objects.get(nm)
        mod = so.modifiers.get("NatureScatter") if so is not None else None
        if mod is None or mod.node_group is None:
            raise RuntimeError("%s or its NatureScatter is missing" % nm)
        ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree
               if getattr(s, "in_out", None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry'}
        old = N._get_mod_input(mod, ids["Min Normal Z"])
        N._set_mod_input(mod, ids["Min Normal Z"], want)
        log("scatter", nm, "Min Normal Z %.3f -> %.3f" % (old, want))
    anchors = {k: tuple(v)[:4] for k, v in W.ANCHORS.items()}
    kd, _ = S.flight_paths(sc)
    S.forest_masks(ob, kd, anchors)
    S.density_masks(ob, S.density_paths(sc), anchors)
    m2_after = masks_m2(me)
    for k in sorted(set(m2_before) | set(m2_after)):
        log("mask", k, "m2 %s -> %s" % (m2_before.get(k), m2_after.get(k)))
        if not m2_after.get(k):
            raise RuntimeError("mask %s came out empty" % k)
    stats_after = dict(all=fold_stats(me), **{k: fold_stats(me, W.ANCHORS[k], r) for k, r in NEAR.items()})
    for k in stats_before:
        log("folds", k, stats_before[k], "->", stats_after[k])
    log("%s: %d vertices, %d faces (%s)" % (RANGE, len(me.vertices), len(me.polygons),
                                           "replaced" if swapped else "unchanged"))
    log("NEXT: patch_life PARTS=ledges; then audit, chunks,meta, bakefull all + backdrop, water, bake_trees, pack")
    if opt["dry"]:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
