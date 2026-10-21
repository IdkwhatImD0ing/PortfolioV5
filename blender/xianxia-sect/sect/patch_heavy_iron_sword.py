"""Recast the arena's giant stone sword in out/sect_chase.blend as the Heavy Iron Sword 玄铁重剑 of sect/areas/arena.py
(heavy_sword_meshes) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_heavy_iron_sword.py

In place: the six objects arena.sword_blade / _glow / _guard / _grip / _pommel / _tassel keep their names, parent (the
Empty 'arena.sword', not touched: guard at (0, 40, 24) in the arena's frame, rotX -6, rotY 3) and transforms. Each
gets its new mesh 'arena.<part>' with its material slots linked to the data (iron, molten, cloth_black, props_rope);
the old meshes are freed. arena.sword_glow keeps shadow off and gets obj['glow'] = arena.HS_GLOW.
Removed: the inscription plaque on the blade, 'arena.plaque_sword' and everything under it (its pivot Empty, .board,
.frame, .relief, .text). The heavy sword is famously plain; the area's name stays on arena.plaque_gate and
arena.plaque. The object count drops by exactly the size of that subtree (logged; 0 on a re-run). Nothing is added.

Why only the bake re-runs: export_web keys every cache on the record key (the object name) and boxes the pieces by
their bound boxes. Every new part's local box sits inside the old part's (arena.HS_OLD_BOX), so the world boxes only
shrink: vis_cache.npz, chunks.npz and the 'arena' hotspot (the arena.sword subtree) stay valid, and load_cache simply
ignores the deleted plaque's rows. The script checks this and prints 'PATCH CACHES ok' (or 'PATCH CACHES STALE' with
what grew: then run export_web.py -- chunks,meta --profile full before the bake). Then:

    python .../tools/rblender.py --background .../out/sect_chase.blend \
        --python .../sect/bake_web.py -- bakefull --profile full --chunks arena,backdrop
    python .../tools/sect_pack.py --profile full --only arena,backdrop

Idempotent: every run builds the six meshes fresh (same seed, same geometry), swaps them in and frees the previous
ones; a second run finds no plaque and changes nothing else. Refuses to save if a part is missing, a new box leaves
the old one, a part goes over arena.HS_TRI_CAP triangles or a part is not closed.
"""
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import arena as A  # noqa: E402
from sect.lib import util as U  # noqa: E402

SWORD = A.K + ".sword"                 # the sword's Empty (kept as it is)
PLAQUE = A.K + ".plaque_sword"         # the blade's inscription plaque (deleted with its subtree)
TOL = 2e-3


def log(*a):
    print("PATCH", *a, flush=True)


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (tuple(round(min(p[k] for p in pts), 4) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 4) for k in range(3)))


def box_of_corners(M, lo, hi):
    pts = [M @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return (tuple(min(p[k] for p in pts) for k in range(3)), tuple(max(p[k] for p in pts) for k in range(3)))


def local_box(me):
    if not len(me.vertices):
        return None
    cs = [v.co for v in me.vertices]
    return (tuple(round(min(c[k] for c in cs), 4) for k in range(3)),
            tuple(round(max(c[k] for c in cs), 4) for k in range(3)))


def inside(inner, outer, tol=TOL):
    return all(inner[0][k] >= outer[0][k] - tol and inner[1][k] <= outer[1][k] + tol for k in range(3))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def open_edges(me):
    """Edges used by fewer than two faces (bake_web counts a piece as closed only when there are none)."""
    use = {}
    for p in me.polygons:
        for k in p.edge_keys:
            use[k] = use.get(k, 0) + 1
    return sum(1 for e in me.edges if use.get(e.key, 0) < 2)


def delete_plaque():
    """Delete PLAQUE and every object under it, then their meshes once unused. Returns the deleted names."""
    root = bpy.data.objects.get(PLAQUE)
    if root is None:
        log("plaque", PLAQUE, "not found: already removed")
        return []
    sub = [root] + list(root.children_recursive)
    names = [o.name for o in sub]
    stray = [n for n in names if not n.startswith(PLAQUE)]
    if stray:
        raise RuntimeError("objects under %s that are not plaque parts: %s" % (PLAQUE, stray))
    datas = [o.data for o in sub if o.data is not None]
    log("plaque subtree", len(names), names, "parent", root.parent.name if root.parent else None)
    for nm in reversed(names):                       # children first
        bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
    for d in datas:
        if isinstance(d, bpy.types.Mesh) and d.users == 0:
            bpy.data.meshes.remove(d)
    return names


def main():
    sroot = bpy.data.objects.get(SWORD)
    if sroot is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % SWORD)
    m0 = sroot.matrix_world.copy()
    log("sword empty", SWORD, "world location", tuple(round(v, 3) for v in m0.translation),
        "rotation deg", tuple(round(v * 57.29578, 2) for v in sroot.rotation_euler), "parent",
        sroot.parent.name if sroot.parent else None)
    targets = {}
    for part in A.HS_PARTS:
        nm = A.K + "." + part
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            raise RuntimeError("%s not found (or not a mesh)" % nm)
        if ob.parent != sroot:
            log("WARN", nm, "parent is", ob.parent.name if ob.parent else None, "not", SWORD)
        if ob.modifiers:
            log("WARN", nm, "has modifiers; they now act on the new mesh:", [m.type for m in ob.modifiers])
        targets[part] = ob
    n_obj = len(bpy.data.objects)
    before = {}
    for part, ob in targets.items():
        me = ob.data
        ours = me.get("sect_heavy_sword") == part
        before[part] = (local_box(me), world_box(ob), ours)
        log("before", ob.name, "mesh", me.name, "users", me.users, "tris", tris(me), "local box", before[part][0],
            "world box", before[part][1], "slots", [s.material.name if s.material else None for s in ob.material_slots],
            "(already the heavy sword)" if ours else "")
    meshes = A.heavy_sword_meshes(log=log)
    for part, ob in targets.items():
        old = ob.data
        ob.data = meshes[part]
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if old is not ob.data and old.users == 0:
            bpy.data.meshes.remove(old)
    glow = targets["sword_glow"]
    glow["glow"] = A.HS_GLOW
    U.set_visibility(glow, shadow=False)
    for me in list(bpy.data.meshes):
        if me.users == 0 and any(me.name.startswith(A.K + "." + p + ".old") for p in A.HS_PARTS):
            log("freed mesh", me.name)
            bpy.data.meshes.remove(me)
    removed = delete_plaque()
    bpy.context.view_layer.update()

    # checks: object count, boxes (local and world), budget, closed parts
    if len(bpy.data.objects) != n_obj - len(removed):
        raise RuntimeError("object count %d -> %d, expected -%d (the plaque subtree)"
                           % (n_obj, len(bpy.data.objects), len(removed)))
    if any(abs(a - b) > 1e-6 for ra, rb in zip(sroot.matrix_world, m0) for a, b in zip(ra, rb)):
        raise RuntimeError("the sword empty moved")
    stale, total = [], 0
    for part, ob in targets.items():
        me = ob.data
        lb = local_box(me)
        lb0, wb0, ours = before[part]
        old = A.HS_OLD_BOX[part]
        if lb is None or not inside(lb, old):
            raise RuntimeError("%s local box %s leaves the stone sword's %s" % (ob.name, lb, old))
        if not ours and not inside(lb, lb0):
            raise RuntimeError("%s local box %s leaves the old mesh's %s" % (ob.name, lb, lb0))
        t = tris(me)
        total += t
        if t > A.HS_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, A.HS_TRI_CAP))
        n_open = open_edges(me)
        if n_open:
            raise RuntimeError("%s has %d open edges (bake_web needs closed pieces)" % (ob.name, n_open))
        wb = world_box(ob)
        ref = wb0 if not ours else box_of_corners(ob.matrix_world, *old)
        if not inside(wb, ref):
            stale.append((ob.name, ref, wb))
        log("after", ob.name, "mesh", me.name, "tris", t, "local box", lb, "world box", wb, "slots",
            [(s.material.name if s.material else None, s.link) for s in ob.material_slots])
    log("glow", glow.name, "obj glow", glow.get("glow"), "visible_shadow", glow.visible_shadow)
    log("total triangles", total, "objects", n_obj, "->", len(bpy.data.objects), "(removed %d)" % len(removed))
    if stale:
        log("CACHES STALE: world boxes grew", stale, "- run export_web.py -- chunks,meta --profile full before the bake")
    else:
        log("CACHES ok: names kept and every world box inside the old one; vis_cache, chunks and the 'arena' hotspot "
            "stay valid (the deleted plaque's rows are ignored)")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
