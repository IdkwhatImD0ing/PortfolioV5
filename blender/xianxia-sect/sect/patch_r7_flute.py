"""Round 7, lane flute: add Huang Yaoshi's jade flute 玉簫 at the Heart-Mirror pond (sect/areas/mirror.py _flute,
builders in sect/lib/flute_props.py; a full rebuild makes the same set) to a finished out/sect_chase.blend and save
it. Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r7_flute.py [-- DRY_RUN=1]

ADDS six objects to the 'mirror' collection; nothing else changes (no existing object is renamed, moved or removed):
    mirror.flute          Empty under mirror.root at mirror.FLUTE_LOC (z 0), turned FLUTE_YAW
    mirror.flute_rock     flat dark slate, sunk into the lawn at the pond's east rim (flute_qingshi)
    mirror.flute_bag      the flute's empty red brocade bag lying flat in front of it (flute_silk, cloth_gold)
    mirror.flute_xiao     the jade xiao resting on the stone (flute_jade, lacquer_black in the holes and the bore)
    mirror.flute_tassel   gold cord from the front vent hole, knot, jade bead and tassel hanging against the stone
    mirror.flute_petals   fallen peach petals on the stone, the lawn, the bank, the rim stones and the water
Every one carries obj['sect_item'] = 'jade_flute'. Idempotent: a re-run first removes its own previous output (objects
tagged so or with those names, and their meshes), then builds the set again under the same names.

Checks before saving (it stops without saving when one fails): the six names exactly (no '.001'); each mesh within
mirror.FLUTE_TRI_CAP triangles and closed (every edge in two or more faces: bake_web's closed-piece rule); the set at
least 2 m outside every mist_volume box; no piece intersecting any scene piece but the lawn and the pond basin
(instances included), nearest distances logged; grounding: the stone's foot below the ground all round, the bag on
the stone (no overlap, touching), the flute on the stone (no overlap, touching at its two rest points, its ends within
1.5 cm), the cord and tassel against the stone and the bag, every petal within a few mm over a surface; the 217 hold:
the flute's ends in
frame, its length in pixels at 1600x900 and how much of it the hold camera sees (unblocked rays), and how much of it
the sun reaches (logged).

Caches: new objects, so the first run prints 'PATCH CACHES audit-needed' (run the export audit, then chunks,meta, then
re-bake the mirror chunk); a re-run that rebuilds the same names inside the same world boxes prints 'PATCH CACHES ok'.
Options after '--': DRY_RUN=1 (build, report, no save).
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

from sect.areas import mirror as MI  # noqa: E402
from sect.lib import flute_props as FP  # noqa: E402
from sect.lib import materials as M  # noqa: E402

AREA_ROOT = "mirror.root"
COLL = "mirror"
GROUND_OK = ("mirror.lawn", "mirror.pond.basin")    # the stone is sunk into these; petals lie on them
MIST_GAP = 2.0
NEAR = 1.0
TOL = 2e-3
HOLD = 217
CAMERA = "chase.cam"
MIN_VISIBLE = 0.6               # share of the flute's sample points the hold camera must see
MIN_PX = 40.0                   # flute length on screen at 1600 px


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
            raise SystemExit("patch_r7_flute: unknown option %r (DRY_RUN=1)" % a)
    return dry


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


def world_verts(ob):
    M = ob.matrix_world
    return [M @ v.co for v in ob.data.vertices]


def world_box(ob):
    pts = []
    for o in [ob] + list(ob.children_recursive):
        if o.type == 'EMPTY':
            pts.append(o.matrix_world.translation.copy())
        else:
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    return box_of(pts)


def bvh_obj(ob, M=None):
    M = M or ob.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])


# --- build -------------------------------------------------------------------------------------------------------

def remove_previous():
    want = set(MI.flute_names())
    obs = [o for o in bpy.data.objects if o.get("sect_item") == MI.FLUTE_ITEM or o.name in want]
    for o in list(obs):
        obs.extend(c for c in o.children_recursive if c not in obs)
    gone, meshes, boxes = [], set(), {}
    for o in obs:
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
        log("removed the previous run's output:", gone)
    n_obj = len(bpy.data.objects)
    mats_before = {m.name for m in bpy.data.materials}
    # this lane's own materials (only the set uses them): a re-run rebuilds them from the current parameters, so a
    # file patched by an earlier version gets the same look as a fresh build
    for name in (FP.JADE, FP.STONE, FP.SILK, FP.PETAL):
        if any(m.get(M.TAG) == name and m.library is None for m in bpy.data.materials):
            M.rebuild(name)
            log("material %s%s rebuilt from sect/lib/flute_props.py" % (M.PREFIX, name))
    for nm, kind, vs, ps in MI.flute_scene(root):
        ob = bpy.data.objects[nm]
        if ob.modifiers:
            log("WARN petal surface %s has modifiers %s (the sampler reads its base mesh)" % (nm, [m.type for m in ob.modifiers]))
    em = MI._flute(coll, root)
    bpy.context.view_layer.update()
    group = [em] + list(em.children_recursive)
    got = sorted(o.name for o in group)
    if got != sorted(MI.flute_names()):
        raise RuntimeError("unexpected object names %s (wanted %s): a name was taken" % (got, sorted(MI.flute_names())))
    if len(bpy.data.objects) != n_obj + len(MI.flute_names()):
        raise RuntimeError("object count %d -> %d, expected +%d" % (n_obj, len(bpy.data.objects), len(MI.flute_names())))
    log("BUILT %d objects in collection '%s': %s" % (len(group), COLL, ", ".join(MI.flute_names())))
    log("  %s under %s at %s, rotation deg %s; %d petals (%d dropped for clipping a rim stone, the paving or the set)"
        % (MI.FLUTE, em.parent.name, tuple(round(x, 3) for x in em.location),
           tuple(round(math.degrees(x), 2) for x in em.rotation_euler), em.get("petals", -1), em.get("petals_dropped", -1)))
    W = root.matrix_world.inverted()
    total = 0
    for ob in group:
        if ob.type != 'MESH':
            continue
        t, oe = tris(ob.data), open_edges(ob.data)
        total += t
        lo, hi = box_of([W @ p for p in world_verts(ob)])
        log("  %-22s tris %5d  open edges %d  materials %s  box in mirror.root %s .. %s"
            % (ob.name, t, oe, [s.material.name if s.material else None for s in ob.material_slots],
               tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi)))
        if t > MI.FLUTE_TRI_CAP:
            raise RuntimeError("%s has %d triangles > %d" % (ob.name, t, MI.FLUTE_TRI_CAP))
        if oe:
            raise RuntimeError("%s has %d open edges: not closed" % (ob.name, oe))
    log("  triangles in all: %d" % total)
    new_mats = sorted({m.name for m in bpy.data.materials} - mats_before)
    log("  materials created (were not in the file yet):", new_mats or "none")
    return em, group, old_boxes


# --- checks ------------------------------------------------------------------------------------------------------

def mist_report(pts):
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
        for p in pts[::5]:
            q = Mi @ p
            c = Vector(tuple(min(max(q[k], lo[k]), hi[k]) for k in range(3)))
            best = min(best, (M @ c - p).length)
        out.append((best, ob.name))
    return sorted(out)


def neighbours(group):
    """[(label, part, nearest distance, intersects)] for every scene piece (evaluated instances included) whose world
    box comes within NEAR m of a group mesh's."""
    dg = bpy.context.evaluated_depsgraph_get()
    gnames = {o.name for o in group}
    parts = []
    for o in group:
        if o.type != 'MESH':
            continue
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
        me = ob.to_mesh()
        try:
            tree = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        finally:
            ob.to_mesh_clear()
        label = ob.original.name + ("" if not inst.is_instance else " (instance under %s)" %
                                    (inst.parent.original.name if inst.parent else "?"))
        for o, b, t, vs in parts:
            if box_gap(nb, b) > NEAR:
                continue
            hit = bool(t.overlap(tree))
            d = min((h[3] for h in (tree.find_nearest(p) for p in vs[::3]) if h[0] is not None), default=9e9)
            found.append((label, o.name, d, hit))
    return found


def check_scene(group):
    pts = [p for o in group if o.type == 'MESH' for p in world_verts(o)]
    mists = mist_report(pts)
    for d, nm in mists[:3]:
        log("mist box %-30s nearest set vertex %.2f m" % (nm, d))
    if mists and mists[0][0] < MIST_GAP:
        raise RuntimeError("the set is %.2f m from %s (< %.1f m)" % (mists[0][0], mists[0][1], MIST_GAP))
    bad = []
    near = sorted(neighbours(group), key=lambda r: r[2])
    for label, part, d, hit in near:
        tag = "INTERSECTS" if hit else "clear"
        if hit or d < 0.3:
            log("neighbour %-56s ~ %-20s nearest %.3f m  %s" % (label[:56], part, d, tag))
        if hit and not any(label == g or label.startswith(g + " ") for g in GROUND_OK):
            bad.append((label, part))
    log("neighbours within %.0f m: %d pairs (%d listed above: touching or within 0.3 m)"
        % (NEAR, len(near), sum(1 for r in near if r[3] or r[2] < 0.3)))
    if bad:
        raise RuntimeError("set pieces intersect scene pieces: %s" % bad)


def check_grounding(root, em):
    """Every piece rests on what is under it (all in the set frame: the pieces' own coordinates)."""
    ob = {p: bpy.data.objects["%s_%s" % (MI.FLUTE, p)] for p in MI.FLUTE_PARTS}
    for p, o in ob.items():
        ml = o.matrix_parent_inverse @ o.matrix_basis
        if o.parent != em or any(abs(ml[i][j] - (1.0 if i == j else 0.0)) > 1e-6 for i in range(4) for j in range(4)):
            raise RuntimeError("%s is not at identity under %s" % (o.name, MI.FLUTE))

    def tree(o):
        return BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [tuple(p.vertices) for p in o.data.polygons])

    t = {p: tree(o) for p, o in ob.items()}
    # ground under the set (set frame), without the set itself
    verts, polys = [], []
    for _nm, _kind, vs, ps in MI.flute_scene(root):
        base = len(verts)
        verts.extend(vs)
        polys.extend(tuple(base + i for i in q) for q in ps)
    ground = BVHTree.FromPolygons(verts, polys)

    def gz(x, y):
        h = ground.ray_cast(Vector((x, y, 4.0)), Vector((0, 0, -1)), 12.0)
        return None if h[0] is None else h[0].z

    # 1. the stone's foot: its bottom ring is under the ground all round
    rv = [v.co for v in ob["rock"].data.vertices]
    zmin = min(v.z for v in rv)
    foot = [v for v in rv if v.z < zmin + 0.05]
    sink = [(gz(v.x, v.y) - v.z) for v in foot if gz(v.x, v.y) is not None]
    z_line = min(FP.ROCK_RINGS, key=lambda r: abs(r[1]))[1]              # the ring nearest the lawn line
    side = [v for v in rv if abs(v.z - z_line) < 1e-4]
    over = [(v.z - gz(v.x, v.y)) for v in side if gz(v.x, v.y) is not None]
    log("stone: foot ring %.2f .. %.2f m under the ground (%d points); the ring at z %.2f is %.2f .. %.2f m from the "
        "ground" % (min(sink), max(sink), len(sink), z_line, min(over), max(over)))
    if len(sink) < len(foot) or min(sink) < 0.08:
        raise RuntimeError("the stone's foot is not buried all round (min %.3f m)" % min(sink or [-1]))
    # 2. bag on the stone, flute on the stone, cord and tassel against them
    for a, b, touch in (("bag", "rock", 0.006), ("xiao", "rock", 0.002), ("tassel", "rock", 0.004)):
        ov = t[a].overlap(t[b])
        vs = [v.co for v in ob[a].data.vertices]
        d = min(h[3] for h in (t[b].find_nearest(v) for v in vs) if h[0] is not None)
        log("%s on %s: nearest %.4f m, %d overlapping face pairs" % (a, b, d, len(ov)))
        if ov:
            raise RuntimeError("%s intersects %s (%d pairs)" % (a, b, len(ov)))
        if d > touch:
            raise RuntimeError("%s does not touch %s (%.4f m > %.3f)" % (a, b, d, touch))
    for a, b in (("tassel", "bag"), ("xiao", "bag")):
        ov = t[a].overlap(t[b])
        if ov:
            raise RuntimeError("%s intersects the %s (%d pairs)" % (a, b, len(ov)))
    ov = t["tassel"].overlap(t["xiao"])
    log("tassel into the flute's vent hole: %d overlapping face pairs (the cord's tied end)" % len(ov))
    # the flute's rest: lowest gap to the stone along its length (two contacts), and its ends' gap
    xv = [v.co for v in ob["xiao"].data.vertices]
    gaps = sorted((t["rock"].find_nearest(v)[3], round(v.x, 2)) for v in xv)
    ends = [min(t["rock"].find_nearest(v)[3] for v in xv if (v.x < -0.85 if e == 0 else v.x > 0.85)) for e in (0, 1)]
    log("flute rests on the stone at x %s (gaps %s m); its ends %.4f / %.4f m over it"
        % ([g[1] for g in gaps[:6]], [round(g[0], 4) for g in gaps[:6]], ends[0], ends[1]))
    if max(ends) > 0.015:
        raise RuntimeError("the flute's ends stand %.3f m off the stone" % max(ends))
    # 3. petals: each one's lowest vertex within a few mm of a surface (ground, stones, paths, water, the set)
    pv = [v.co for v in ob["petals"].data.vertices]
    k = len(FP.petal_outline(1.0, 1.0)) * 2
    if len(pv) % k:
        raise RuntimeError("petal mesh has %d vertices, not a multiple of %d" % (len(pv), k))
    sets = [t[p] for p in ("rock", "bag", "xiao", "tassel")]
    worst, kinds = 0.0, {}
    for i in range(0, len(pv), k):
        bottom = pv[i:i + k:2]
        d = min(min([ground.find_nearest(v)[3]] + [s.find_nearest(v)[3] for s in sets]) for v in bottom)
        worst = max(worst, d)
    n_pet = len(pv) // k
    for p in ("rock", "bag", "xiao", "tassel"):
        if t["petals"].overlap(t[p]):
            raise RuntimeError("petals intersect the %s" % p)
    log("petals: %d, every one within %.4f m of the surface under it" % (n_pet, worst))
    if worst > 0.008:
        raise RuntimeError("a petal hovers %.4f m over everything" % worst)


def check_hold(group):
    """The flute in the 217 hold: on screen, its length in pixels, how much the camera sees, how much is in sun."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get(CAMERA)
    if cam is None:
        log("WARN no %s: hold check skipped" % CAMERA)
        return
    keep = sc.frame_current
    sc.frame_set(HOLD)
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        xiao = bpy.data.objects["%s_xiao" % MI.FLUTE]
        M = xiao.matrix_world
        vs = [M @ v.co for v in xiao.data.vertices]
        rw, rh = 1600, 900
        sx = [world_to_camera_view(sc, cam, p) for p in vs]
        if not all(0.0 <= c.x <= 1.0 and 0.0 <= c.y <= 1.0 and c.z > 0 for c in sx):
            raise RuntimeError("the flute is not wholly in the %d hold frame" % HOLD)
        px = [(c.x * rw, (1.0 - c.y) * rh) for c in sx]
        lo = (min(p[0] for p in px), min(p[1] for p in px))
        hi = (max(p[0] for p in px), max(p[1] for p in px))
        length = math.hypot(hi[0] - lo[0], hi[1] - lo[1])
        C = cam.matrix_world.translation
        sun = [o for o in bpy.data.objects if o.type == 'LIGHT' and o.data.type == 'SUN']
        Ls = (-(sun[0].matrix_world.to_3x3() @ Vector((0, 0, -1)))).normalized() if sun else None
        names = {o.name for o in group}
        seen = lit = n = 0
        top = sorted(vs, key=lambda p: -p.z)[:len(vs) // 3]
        for p in top[::max(1, len(top) // 60)]:
            n += 1
            d = C - p
            dist = d.length
            d.normalize()
            h = sc.ray_cast(dg, p + d * 0.004, d, distance=dist - 0.1)
            if not h[0] or h[4].name == xiao.name:
                seen += 1
            if Ls is not None:
                h = sc.ray_cast(dg, p + Ls * 0.004, Ls, distance=500.0)
                if not h[0] or h[4].name == xiao.name:
                    lit += 1
        dist = (C - M.translation).length
        log("217 hold: flute on screen (1600x900) x %.0f..%.0f y %.0f..%.0f, %.0f px long, %.1f m from the camera; "
            "camera sees %d/%d of its top points, sun reaches %d/%d" % (lo[0], hi[0], lo[1], hi[1], length, dist,
                                                                        seen, n, lit, n))
        rock = bpy.data.objects["%s_rock" % MI.FLUTE]
        cs = [world_to_camera_view(sc, cam, rock.matrix_world @ Vector(c)) for c in rock.bound_box]
        log("217 hold: stone box on screen x %.0f..%.0f y %.0f..%.0f" % (min(c.x for c in cs) * rw, max(c.x for c in cs) * rw,
                                                                       (1 - max(c.y for c in cs)) * rh,
                                                                       (1 - min(c.y for c in cs)) * rh))
        if length < MIN_PX:
            raise RuntimeError("the flute is only %.0f px long in the hold (< %.0f)" % (length, MIN_PX))
        if seen < MIN_VISIBLE * n:
            raise RuntimeError("the hold camera sees only %d/%d of the flute" % (seen, n))
    finally:
        sc.frame_set(keep)


# --- main --------------------------------------------------------------------------------------------------------

def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    coll = bpy.data.collections.get(COLL)
    if root is None or coll is None:
        raise RuntimeError("no %s / collection %s: is this out/sect_chase.blend?" % (AREA_ROOT, COLL))
    n0 = len(bpy.data.objects)
    em, group, old_boxes = build(root, coll)
    check_scene(group)
    check_grounding(root, em)
    check_hold(group)
    log("objects %d -> %d" % (n0, len(bpy.data.objects)))
    stale = []
    for o in group:
        b = world_box(o) if o.type == 'MESH' else (o.matrix_world.translation.copy(),) * 2
        ob0 = old_boxes.get(o.name)
        if ob0 is None or not inside(b, ob0):
            stale.append(("new or moved: %s" % o.name, rb(ob0) if ob0 else None, rb(b)))
    for nm in sorted(set(old_boxes) - {o.name for o in group}):
        stale.append(("removed: %s" % nm,))
    if stale:
        log("CACHES audit-needed: %d new/moved objects need the export audit, then chunks,meta, then the mirror "
            "re-bake:" % len(stale))
        for s in stale:
            log("  ", *s)
    else:
        log("CACHES ok: same names, every world box inside the old one (a re-run: nothing moved)")
    if dry:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
