"""Round 7, lane swordtomb: add Dugu Qiubai's Sword Tomb 剑冢 (sect/areas/forge.py _sword_tomb) to the forge in
out/sect_chase.blend, the way a fresh build makes it, and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r7_swordtomb.py [-- DRY_RUN=1]

What it does:
- deletes this patch's previous output (the Empty forge.sword_tomb and everything under it, and its orphaned meshes);
- calls forge._sword_tomb at forge.ST_LOC under forge.root, in the 'forge' collection: the Empty forge.sword_tomb and
  five meshes, .rock (the outcrop), .cairn (the heap of stones), .slab (the bluestone and its four socket stones),
  .sharp_sword and .wood_sword (planted in the outer sockets); nothing else in the file is touched;
- rebuilds the five materials forge.py registers for it (forge_tomb_rock, forge_cairn_rock, forge_bluestone,
  forge_qing_steel, forge_old_wood), so a re-run picks up colour edits.

Checks (nothing is saved when one fails):
- every mesh closed (each edge shared by two faces, bake_web's rule) and consistently wound, at most forge.ST_TRI_CAP
  triangles, existing materials only, nothing ember or molten (the page's forge fire FX), only in the 'forge'
  collection, under forge.root;
- grounded: the outcrop's foot is under the paving; under every sample of the slab's footprint the rock's top is at
  or above the slab's bottom (no gap); each sword's lowest point is its foot, on its mortise floor, inside the
  mortise; a sword's faces meet the slab's only on that floor (the blade clears the mortise walls); the cairn's
  foot is bedded in the ledge; each loose stone set down round the heap (forge.ST_LOOSE) has the rock top above its
  lowest point (bedded, not hovering);
- clear of the yard: the outcrop stays outside the rune ring's band and its box meets no other forge object's box;
- reads at the hold: at the forge hold frame (352) the tomb's box is inside the 1600 x 900 frame, and the camera sees
  both swords' guards and pommels, the cairn and all four sockets.

Caches: the tomb is NEW object names, so the web caches (vis_cache.npz, chunks.npz) do not know them: the patch prints
'PATCH CACHES needs audit' (run export_web.py audit, then chunks,meta, or a cache_add step for these names, before
re-baking the forge chunk and the backdrop). A re-run over its own output rebuilds the same geometry under the same
names and prints 'PATCH CACHES ok' when every box is the same as before.
Idempotent: every run deletes its own previous output and builds it again (same seeds, same geometry, same names).
"""
import math
import os
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import forge as F  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

ROOT_EMPTY = "forge.root"
COLL = "forge"
PARTS = ("rock", "cairn", "slab", "sharp_sword", "wood_sword")
NEW_MATS = ("forge_tomb_rock", "forge_cairn_rock", "forge_bluestone", "forge_qing_steel", "forge_old_wood")
BANNED = ("ember", "molten")
HOLD = 352
CAMERA = "chase.cam"
RES = (1600, 900)
RUNE_RING = "forge.rune_ring"
# forge objects whose boxes may contain the tomb's (the whole yard): the paving, the balustrade arcs, the rune ring
# (checked by radius instead), the root and the artifact ring (9.5 m up)
BOX_SKIP = ("forge.root", "forge.paving", "forge.balustrade", "forge.rune_ring", "forge.ring_tilt", "forge.artifact",
            "forge.orbit_hoop")
TOL = 2e-3


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {k: v for k, _, v in (s.partition("=") for s in argv)}


def ours(ob):
    return ob.name == F.ST_NAME or ob.name.startswith(F.ST_NAME + ".")


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def world_box(obs, frame=None):
    """Axis-aligned box of the objects' mesh bound boxes (or origins, for Empties only), in world space or, with
    ``frame`` (a matrix_world), in that frame (forge.root is turned in the world, so yard clearances use its frame)."""
    T = frame.inverted() if frame is not None else None
    pts = [o.matrix_world @ Vector(c) for o in obs if o.type == 'MESH' for c in o.bound_box]
    if not pts:
        pts = [o.matrix_world.translation for o in obs]
    if T is not None:
        pts = [T @ p for p in pts]
    return (tuple(min(p[k] for p in pts) for k in range(3)), tuple(max(p[k] for p in pts) for k in range(3)))


def fmt_box(b):
    return "(%s)..(%s)" % (", ".join("%.2f" % v for v in b[0]), ", ".join("%.2f" % v for v in b[1]))


def mesh_checks(ob):
    """(open edges, inconsistently wound edges) of the object's mesh: both must be 0."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    open_e = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bad = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    bm.free()
    return open_e, bad


def bvh_world(ob):
    mw = ob.matrix_world
    vs = [mw @ v.co for v in ob.data.vertices]
    return BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons]), vs


def delete_previous():
    """Delete this patch's previous output; returns {name: world box} of its meshes (for the cache verdict)."""
    prev = [o for o in bpy.data.objects if ours(o)]
    boxes = {o.name: world_box([o]) for o in prev if o.type == 'MESH'}
    if prev:
        names = sorted(o.name for o in prev)
        for o in [o for o in prev if o.parent is None or not ours(o.parent)]:
            if bpy.data.objects.get(o.name) is not None:
                U.delete_hierarchy(o)
        for nm in names:
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        log("removed the previous run's", len(names), "objects", names)
    for m in list(bpy.data.meshes):
        if ours(m) and m.users == 0:
            bpy.data.meshes.remove(m)
    return boxes


def check_meshes(emp):
    total = 0
    parts = {}
    for ob in sorted(emp.children, key=lambda o: o.name):
        if ob.type != 'MESH':
            raise RuntimeError("%s is not a mesh" % ob.name)
        parts[ob.name[len(F.ST_NAME) + 1:]] = ob
        t = tris(ob.data)
        total += t
        mats = [s.material.name if s.material else None for s in ob.material_slots]
        open_e, bad = mesh_checks(ob)
        log("added", ob.name, "tris", t, "verts", len(ob.data.vertices), "materials", mats, "open edges", open_e,
            "flipped edges", bad, "world box", fmt_box(world_box([ob])))
        if open_e or bad:
            raise RuntimeError("%s is not closed / consistently wound (%d open, %d flipped)" % (ob.name, open_e, bad))
        if t > F.ST_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, F.ST_TRI_CAP))
        for m in mats:
            if m is None or any(b in m for b in BANNED):
                raise RuntimeError("%s uses material %r" % (ob.name, m))
        if [c.name for c in ob.users_collection] != [COLL]:
            raise RuntimeError("%s collections %s" % (ob.name, [c.name for c in ob.users_collection]))
    if sorted(parts) != sorted(PARTS):
        raise RuntimeError("parts %s, expected %s" % (sorted(parts), sorted(PARTS)))
    return parts, total


def check_ground(emp, parts, root):
    """Every piece rests on something: see the module docstring."""
    lay = F._st_layout()
    E = emp.matrix_world
    up = (E.to_3x3() @ Vector((0, 0, 1))).normalized()
    if up.z < 0.999:
        raise RuntimeError("forge.sword_tomb is not upright (%s)" % tuple(up))
    rock = parts["rock"]
    rock_bvh, rock_vs = bvh_world(rock)
    paving_z = (root.matrix_world @ Vector((0, 0, 0))).z
    foot = min(v.z for v in rock_vs)
    log("ground: rock foot %.3f, paving top %.3f (foot %.2f under it)" % (foot, paving_z, paving_z - foot))
    if foot > paving_z - 0.1:
        raise RuntimeError("the outcrop's foot %.3f is not under the paving %.3f" % (foot, paving_z))
    # slab: rock top at or above the slab's bottom under its whole footprint
    sx, sy, L, D, H, ch = F.ST_SLAB
    zb = lay["slab_z"]
    worst = None
    for i in range(13):
        for j in range(5):
            p = Vector((sx + (L - 0.02) * (i / 12.0 - 0.5), sy + (D - 0.02) * (j / 4.0 - 0.5), zb))
            w = E @ p
            hit = rock_bvh.ray_cast(w + Vector((0, 0, 1.5)), Vector((0, 0, -1)), 3.0)
            m = (hit[0].z - w.z) if hit[0] is not None else -9.0
            if worst is None or m < worst[0]:
                worst = (m, tuple(round(c, 2) for c in p))
    log("ground: slab bottom %.3f (tomb frame); rock top above it by >= %.3f m (worst at %s)" % (zb, worst[0], worst[1]))
    if worst[0] < -TOL:
        raise RuntimeError("the slab hangs %.3f m over the rock at %s" % (-worst[0], worst[1]))
    # swords: foot on the mortise floor, inside the mortise, faces meeting the slab only there
    slab = parts["slab"]
    slab_bvh, slab_vs = bvh_world(slab)
    slots = {k: (x, ml, mw, md) for k, x, ml, mw, md in F.ST_SLOTS}
    for key, nm in (("sharp", "sharp_sword"), ("wood", "wood_sword")):
        ob = parts[nm]
        fx, fy, fz = lay["floors"][key]
        floor = E @ Vector((fx, fy, fz))
        vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
        low = min(vs, key=lambda v: v.z)
        org = ob.matrix_world.translation
        x, ml, mw, md = slots[key]
        loc = E.inverted() @ low
        inside = abs(loc.x - fx) <= ml / 2 and abs(loc.y - fy) <= mw / 2
        log("ground: %s foot %.4f, mortise floor %.4f, lowest point %.4f (%s the mortise)" % (
            ob.name, org.z, floor.z, low.z, "inside" if inside else "OUTSIDE"))
        if abs(org.z - floor.z) > 1e-4 or low.z < floor.z - 1e-4 or not inside:
            raise RuntimeError("%s is not standing on its mortise floor" % ob.name)
        bvh, _ = bvh_world(ob)
        pairs = bvh.overlap(slab_bvh)
        walls = [b for a, b in pairs if abs(sum(slab_vs[i].z for i in slab.data.polygons[b].vertices)
                                            / len(slab.data.polygons[b].vertices) - floor.z) > 1e-3]
        log("ground: %s meets the slab in %d face pairs, %d of them off the floor" % (ob.name, len(pairs), len(walls)))
        if walls:
            raise RuntimeError("%s cuts the socket's walls (%d face pairs)" % (ob.name, len(walls)))
    # cairn: its foot bedded in the ledge
    cairn = parts["cairn"]
    cx, cy, R0, Hc = F.ST_CAIRN
    c_low = min((cairn.matrix_world @ v.co).z for v in cairn.data.vertices)
    hit = rock_bvh.ray_cast(E @ Vector((cx, cy, 5.0)), Vector((0, 0, -1)), 10.0)
    top = hit[0].z if hit[0] is not None else None
    log("ground: cairn foot %.3f, ledge top under its centre %s, base %.3f" % (
        c_low, "%.3f" % top if top is not None else None, (E @ Vector((0, 0, lay["cairn_z"]))).z))
    if top is None or c_low > top - 0.1 or (E @ Vector((0, 0, lay["cairn_z"]))).z > top:
        raise RuntimeError("the cairn is not bedded in the ledge")
    # loose stones: the cairn mesh's pieces whose centre is past the heap's foot; under each one's lowest point (and
    # four points round it, a third of the way in) the rock's top must be at or above the stone (bedded)
    bm = bmesh.new()
    bm.from_mesh(cairn.data)
    bm.verts.ensure_lookup_table()
    seen, loose = set(), []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        part, stack = [], [v0]
        seen.add(v0.index)
        while stack:
            a = stack.pop()
            part.append(a.index)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        c = sum((bm.verts[i].co for i in part), Vector()) / len(part)
        if (Vector((c.x, c.y)) - Vector((cx, cy))).length > R0 + 0.35:
            loose.append(part)
    vco = [cairn.matrix_world @ v.co for v in cairn.data.vertices]
    bm.free()
    if len(loose) != len(F.ST_LOOSE):
        raise RuntimeError("found %d loose stones, expected %d" % (len(loose), len(F.ST_LOOSE)))
    for part in loose:
        pts = [vco[i] for i in part]
        low = min(pts, key=lambda p: p.z)
        ctr = sum(pts, Vector()) / len(pts)
        gaps = []
        for p in [low] + [low.lerp(Vector((q.x, q.y, low.z)), 0.33) for q in sorted(pts, key=lambda p: p.z)[1:5]]:
            hit = rock_bvh.ray_cast(Vector((p.x, p.y, p.z + 2.0)), Vector((0, 0, -1)), 4.0)
            gaps.append(p.z - hit[0].z if hit[0] is not None else 9.0)
        log("ground: loose stone at (%.2f, %.2f): lowest point %.3f, rock top over it by %.3f m (worst of 5)" % (
            ctr.x, ctr.y, low.z, -max(gaps)))
        if max(gaps) > TOL:
            raise RuntimeError("a loose stone hovers %.3f m over the rock at (%.2f, %.2f)" % (max(gaps), ctr.x, ctr.y))
    # the front stones stay off the slab: the cairn's nearest point to the slab's back edge (tomb frame)
    near = min(((E.inverted() @ (cairn.matrix_world @ v.co)).y for v in cairn.data.vertices))
    log("ground: cairn front y %.3f, slab back y %.3f (gap %.3f, tomb frame)" % (near, sy + D / 2, near - (sy + D / 2)))
    if near < sy + D / 2:
        raise RuntimeError("the cairn's front stones reach over the slab")


def check_clear(emp, root):
    """The outcrop outside the rune ring's band; its box meets no other forge object's box."""
    rock = bpy.data.objects[F.ST_NAME + ".rock"]
    ring = bpy.data.objects.get(RUNE_RING)
    Ri = root.matrix_world.inverted()
    if ring is not None:
        c = Ri @ ring.matrix_world.translation
        r_out = max(abs(v) for v in ring.dimensions[:2]) * 0.5
        d = min(math.hypot((Ri @ (rock.matrix_world @ v.co)).x - c.x, (Ri @ (rock.matrix_world @ v.co)).y - c.y)
                for v in rock.data.vertices)
        log("clear: rune ring outer radius %.2f, outcrop's nearest point %.2f from its centre (%.2f m clear)"
            % (r_out, d, d - r_out))
        if d - r_out < 0.5:
            raise RuntimeError("the outcrop is within 0.5 m of the rune ring")
    R = root.matrix_world
    tb = world_box([o for o in emp.children_recursive], R)
    lo, hi = Vector(tb[0]) - Vector((0.3, 0.3, 0)), Vector(tb[1]) + Vector((0.3, 0.3, 0))
    hits, near = [], []
    for top in root.children:
        if ours(top) or any(top.name == s or top.name.startswith(s + ".") for s in BOX_SKIP):
            continue
        obs = [top] + list(top.children_recursive)
        b = world_box(obs, R)
        if all(b[0][k] <= hi[k] and b[1][k] >= lo[k] for k in range(3)):
            hits.append((top.name, fmt_box(b)))
        gap = max(max(b[0][k] - tb[1][k], tb[0][k] - b[1][k]) for k in range(2))
        near.append((round(gap, 2), top.name))
    log("clear: tomb box %s (forge frame); nearest other forge objects (box gap m): %s" % (
        fmt_box(tb), sorted(near)[:5]))
    log("clear: other forge objects in the tomb's box: %s" % (hits or "none"))
    if hits:
        raise RuntimeError("the tomb's box meets %s" % hits)


def check_view(emp, parts):
    """At the hold the tomb is in frame and the key points are seen (the first thing a ray from the camera hits)."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get(CAMERA)
    if cam is None:
        log("WARN", CAMERA, "not found: view check skipped")
        return
    f0 = sc.frame_current
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    sc.render.resolution_x, sc.render.resolution_y = RES
    try:
        sc.frame_set(HOLD)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = [o.matrix_world @ Vector(c) for o in emp.children for c in o.bound_box]
        ndc = [world_to_camera_view(sc, cam, p) for p in pts]
        x0, x1 = min(p.x for p in ndc) * RES[0], max(p.x for p in ndc) * RES[0]
        y0, y1 = (1 - max(p.y for p in ndc)) * RES[1], (1 - min(p.y for p in ndc)) * RES[1]
        log("view: at frame %d the tomb spans x %.0f..%.0f, y %.0f..%.0f of %dx%d (%.0f x %.0f px)" % (
            HOLD, x0, x1, y0, y1, RES[0], RES[1], x1 - x0, y1 - y0))
        if x0 < 0 or y0 < 0 or x1 > RES[0] or y1 > RES[1] or min(p.z for p in ndc) <= 0:
            raise RuntimeError("the tomb leaves the hold frame")
        E = emp.matrix_world
        lay = F._st_layout()
        targets = []
        # points just inside each sword's pommel and guard (the sword's own frame: guard bottom at gz)
        for nm, gz, pz in (("sharp_sword", 1.9, 0.6), ("wood_sword", 1.8, 0.47)):
            ob = parts[nm]
            targets.append((nm + " pommel", ob.matrix_world @ Vector((0.0, -0.015, gz + pz)), ob))
            targets.append((nm + " guard", ob.matrix_world @ Vector((0.0, -0.03, gz + 0.03)), ob))
        cx, cy, R0, Hc = F.ST_CAIRN
        targets.append(("cairn top", E @ Vector((cx, cy, lay["cairn_z"] + Hc - 0.15)), parts["cairn"]))
        for key, x, ml, mw, md in F.ST_SLOTS:
            targets.append(("socket " + key, E @ Vector((F.ST_SLAB[0] + x, F.ST_SLAB[1] - 0.12, lay["socket_top"] - 0.03)),
                            parts["slab"]))
        cpos = cam.matrix_world.translation
        unseen = []
        for label, p, ob in targets:
            d = p - cpos
            hit, loc, nrm, idx, hob, _ = sc.ray_cast(dg, cpos, d.normalized(), distance=d.length + 0.05)
            seen = bool(hit and hob is not None and hob.original == ob)
            log("view: %-20s %s (first hit %s, %.2f m from the target)" % (
                label, "seen" if seen else "HIDDEN", hob.name if hit and hob else None, (p - loc).length if hit else -1))
            if not seen:
                unseen.append(label)
        if unseen:
            raise RuntimeError("not seen from the hold: %s" % unseen)
    finally:
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.frame_set(f0)


def main():
    opts = options()
    root = bpy.data.objects.get(ROOT_EMPTY)
    if root is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % ROOT_EMPTY)
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        raise RuntimeError("collection %r not found" % COLL)
    n0 = len(bpy.data.objects)
    old_boxes = delete_previous()
    n_mid = len(bpy.data.objects)
    emp = F._sword_tomb(coll, root, F.ST_LOC[0], F.ST_LOC[1])
    if emp.name != F.ST_NAME:
        raise RuntimeError("the tomb's Empty came out as %s (another %s exists?)" % (emp.name, F.ST_NAME))
    for nm in NEW_MATS:
        M.rebuild(nm)
        log("material", nm, "rebuilt")
    bpy.context.view_layer.update()
    log("added", emp.name, "Empty, parent", emp.parent.name, "location", tuple(round(c, 3) for c in emp.location),
        "rot z %.3f" % emp.rotation_euler[2], "world", tuple(round(c, 2) for c in emp.matrix_world.translation))
    parts, total = check_meshes(emp)
    check_ground(emp, parts, root)
    check_clear(emp, root)
    check_view(emp, parts)
    n1 = len(bpy.data.objects)
    added = [emp] + sorted(emp.children, key=lambda o: o.name)
    log("SUMMARY objects %d -> %d (removed %d, added %d) | tris %d | %s" % (
        n0, n1, n0 - n_mid, len(added), total, [o.name for o in added]))
    if n1 - n_mid != 1 + len(PARTS):
        raise RuntimeError("object count %d -> %d after the build, expected +%d" % (n_mid, n1, 1 + len(PARTS)))
    grew = []
    for o in added[1:]:
        b = world_box([o])
        ob_ = old_boxes.get(o.name)
        if ob_ is None or not all(b[0][k] >= ob_[0][k] - 1e-3 and b[1][k] <= ob_[1][k] + 1e-3 for k in range(3)):
            grew.append(o.name)
    if grew:
        log("CACHES needs audit: %d new objects the web caches do not know (or boxes that grew): %s - run export_web.py "
            "audit, then chunks,meta (or cache_add for these names), before re-baking the forge chunk and the backdrop"
            % (len(grew) + 1, [F.ST_NAME] + grew))
    else:
        log("CACHES ok: same names and every world box the same as the previous run's (a re-run)")
    if opts.get("DRY_RUN") == "1":
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
