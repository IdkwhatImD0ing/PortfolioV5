"""Round 28, lane 'lions': the gate's guardian lions become the photogrammetry pair (sect/lib/lion_props.py) in an
existing, patched out/sect_chase.blend, so it matches what a fresh build of sect/areas/gate.py makes once the pending
props.py change (props.LION_SCAN: guardian_lion places lion_props.lion_proto) is in. Run on the cloud box, on a copy
first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r28_lions.py [-- DRY_RUN=1]

Why (owner): "the guardian lions look really weird, can you find better assets online?" The procedural lion (metaball
body, stuck-on curls) read as a toy. The new pair is a real Qing white-marble lion scan, "Stone Big Lion 01" by Game
industry veteran (Sketchfab, CC-BY 4.0, assets/CREDITS.md), prepared by lion_props.py -- prep: the female as scanned
(cub under her left forepaw), the male her mirror image with the cub replaced by a carved embroidered ball under his
right forepaw; 28k triangles each, clean weathered-marble colour and a baked normal map.

Needs assets/web/lion_{f,m}_mesh.npz, lion_{f,m}_diff.jpg, lion_{f,m}_nrm.png (the wrapper uploads assets/web). Stops
before touching anything when one is missing.

What it does: every guardian-lion instance (an Empty instancing an old procedural prototype
'props.lion.<bucket>.<0|1>.<material>.<plinth material>.v<n>'; in the round-27 file only the gate's pair: 'gate.lion',
the male at x +10.6, and 'gate.lion.001', the female at x -10.6, both at y -30 under gate.root, size 2) is pointed at
the scan prototype lion_props.lion_proto builds for the same size bucket, sex and materials
('props.lion_scan.<bucket>.<m|f>.<material>.v<n>' under _protos, one object 'props.lion.scan.<m|f>', material
M.props_lion_<m|f>). Each instance keeps its name, parent, transform and collection. The old prototypes (objects
'props.lion.plinth' and 'props.lion.body', 113k triangles a lion) go with their meshes once nothing instances them.
A scan prototype whose mesh no longer equals the npz (the assets were prepped again) is rebuilt.

State: each lion instance must point at an old procedural prototype or a scan one; anything else stops the patch.
Idempotent: on a patched file it prints 'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure: NOT SAVED, exit code 1; DRY_RUN=1 runs everything and never saves):
- the pair and the custom (左雄右雌 seen coming out of the gate, zh.wikipedia 石狮子): gate.lion is the male and
  gate.lion.001 the female; in gate.root's frame both face -Y (out of the gate), the male at +X (the left hand of
  someone walking out), the female at -X;
- prototypes: one mesh object, <= TRI_CAP triangles, material M.props_lion_<sex> whose two images load, 'UVMap'
  active for render, the mesh equal to the npz at the bucket's size;
- grounding: the plinth's sole on the paving (gate.plaza / gate.forecourt): at FOOT_PTS points of the sole's footprint
  the paving's top lies between the sole's cut and the instance origin (within FOOT_TOL);
- clearance: no other geometry within CLEAR_MIN of the new lion or intersecting it (the paving and world-sized pieces
  aside), before (logged) and after;
- reading: chase.cam at the gate's hold (93), 1600 x 900: each lion's box and head on screen, before and after (logged;
  the head must not leave the frame);
- counts: instance names kept; objects change by exactly the prototype objects added and removed; new materials only
  M.props_lion_m / M.props_lion_f, new images only the six lion maps' two kinds; no scratch data or scenes left.
Prints 'PATCH CACHES needs audit' or 'PATCH CACHES ok' and 'PATCH DIGEST <md5>' (the instances, their prototypes'
meshes, materials and world matrices).
"""
import hashlib
import math
import os
import re
import sys
import time

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA)
from sect.lib import lion_props as LP  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import props as P  # noqa: E402

OLD_RX = re.compile(r"^props\.lion\.([^.]+)\.([01])\.([^.]+)\.([^.]+)\.v(\d+)$")
NEW_RX = re.compile(r"^props\.lion_scan\.([^.]+)\.([mf])\.(.+)\.v(\d+)$")
EXPECTED = (("gate.lion", "m", 1.0), ("gate.lion.001", "f", -1.0))   # instance, sex, side (sign of x in gate.root)
ROOT_EMPTY = "gate.root"
SUPPORT = ("gate.plaza", "gate.forecourt")
TRI_CAP = 30000            # bake_web.HOLD_FULL_TRIS: near the hold a piece up to this keeps every triangle
FOOT_TOL = 0.01            # m
FOOT_PTS = 9               # the sole's footprint: centre, edge midpoints and corners (inset 5 % of its size)
CLEAR_MIN = 0.10           # m between the lion and anything else (the stair-head balustrade, lanterns, weapons)
CLEAR_SKIP = SUPPORT + ("world.haze", "world.range", "world.roots")
FACE_TOL = math.radians(1.0)
HOLD_FRAME = 93
RES = (1600, 900)
HEAD_FRAC = 0.72           # the head: the top 28 % of the lion's height


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
            raise SystemExit("patch_r28_lions: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------ helpers

def bucket_of(kb):
    for k in range(-8, 9):
        b = math.sqrt(2.0) ** k
        if P._k(b) == kb:
            return b
    return None


def lion_instances():
    """{instance object: ('old' | 'new', proto collection)} of every guardian-lion instance."""
    out = {}
    for o in bpy.data.objects:
        pc = o.instance_collection if o.instance_type == 'COLLECTION' else None
        if pc is None:
            continue
        if OLD_RX.match(pc.name):
            out[o] = ("old", pc)
        elif NEW_RX.match(pc.name):
            out[o] = ("new", pc)
    return out


def params(state, pc):
    """(size bucket, mirror, material, plinth material) the instance was built with."""
    if state == "old":
        kb, mir, mat, pm, _v = OLD_RX.match(pc.name).groups()
        return bucket_of(kb), mir == "1", mat, pm
    kb, sex, lm, _v = NEW_RX.match(pc.name).groups()
    if lm == LP.MAT % sex:
        mat, pm = "marble_white", "marble_white"
    else:
        _lm, mat, pm = lm.split(".")
    return bucket_of(kb), sex == "f", mat, pm


def proto_mesh_obj(pc):
    obs = [o for o in pc.all_objects if o.type == 'MESH']
    return obs[0] if len(obs) == 1 else None


def tris(me):
    n = len(me.polygons)
    lt = np.zeros(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(lt.sum() - 2 * n)


def mesh_arrays(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    tri = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", tri)
    uvl = me.uv_layers.get("UVMap")
    uv = np.empty(len(me.loops) * 2, np.float32)
    if uvl is not None:
        uvl.data.foreach_get("uv", uv)
    return co.reshape(-1, 3), tri, uv.reshape(-1, 2)


def proto_current(pc, sex, b):
    """The scan prototype's mesh equals the npz at bucket ``b``."""
    ob = proto_mesh_obj(pc)
    if ob is None:
        return False
    co, tri, uv = mesh_arrays(ob.data)
    c0, t0, u0 = LP.load(sex)
    return (co.shape == c0.shape and tri.size == t0.size and np.allclose(co, c0 * b, atol=1e-5)
            and np.array_equal(tri, t0.ravel()) and np.allclose(uv, u0, atol=1e-6))


def lion_world(inst):
    """(world 4x4 of the lion mesh, its mesh) for a lion instance."""
    ob = proto_mesh_obj(inst.instance_collection)
    if ob is None:          # the old prototypes: plinth + body
        return None, None
    return inst.matrix_world @ ob.matrix_world, ob.data


def proto_parts(inst):
    """[(world 4x4, mesh)] of every mesh object an instance shows."""
    return [(inst.matrix_world @ o.matrix_world, o.data) for o in inst.instance_collection.all_objects
            if o.type == 'MESH']


def world_points(parts):
    pts = []
    for Mw, me in parts:
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        A = np.array(Mw)
        pts.append(co @ A[:3, :3].T + A[:3, 3])
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def bvh_of(parts):
    verts, polys, off = [], [], 0
    for Mw, me in parts:
        A = np.array(Mw)
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ A[:3, :3].T + A[:3, 3]
        verts.extend(map(tuple, co))
        polys.extend([tuple(v + off for v in p.vertices) for p in me.polygons])
        off += len(co)
    return BVHTree.FromPolygons(verts, polys)


def owner_of(inst):
    if inst.is_instance and inst.parent is not None:
        return inst.parent.original.name
    return inst.object.original.name


def neighbours(dg, lo, hi, skip_owners):
    """[(owner name, world BVH, sample points)] of evaluated geometry whose world box overlaps lo..hi."""
    out = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        own = owner_of(inst)
        if own in skip_owners or any(own == s or own.startswith(s + ".") for s in CLEAR_SKIP):
            continue
        Mw = inst.matrix_world
        bb = [Mw @ Vector(c) for c in ob.bound_box]
        blo = Vector([min(p[k] for p in bb) for k in range(3)])
        bhi = Vector([max(p[k] for p in bb) for k in range(3)])
        if any(blo[k] > hi[k] or bhi[k] < lo[k] for k in range(3)):
            continue
        me = ob.to_mesh()
        try:
            out.append((own, bvh_of([(Mw.copy(), me)])))
        finally:
            ob.to_mesh_clear()
    return out


def clearance(dg, inst, tag, fail=None):
    """Nearest approach of other geometry to the lion instance ``inst`` (and intersections)."""
    parts = proto_parts(inst)
    pts = world_points(parts)
    lo = Vector(pts.min(0) - CLEAR_MIN)
    hi = Vector(pts.max(0) + CLEAR_MIN)
    me_bvh = bvh_of(parts)
    sample = pts[:: max(1, len(pts) // 20000)]
    rows = []
    near = neighbours(dg, lo, hi, {inst.name})
    for own, tree in near:
        dmin = 1e9
        for p in sample:
            h = tree.find_nearest(Vector(p), CLEAR_MIN * 3)
            if h[0] is not None and h[3] < dmin:
                dmin = h[3]
        hit = bool(me_bvh.overlap(tree))
        if dmin < CLEAR_MIN * 3 or hit:
            rows.append((own, dmin, hit))
    rows.sort(key=lambda r: r[1])
    log("clearance %s %s (%d pieces in its box +%.2f m): %s" % (
        tag, inst.name, len(near), CLEAR_MIN, "; ".join("%s %.3f m%s" % (o, d, " INTERSECTS" if h else "")
                                                     for o, d, h in rows[:8]) or "nothing within %.2f m" % (CLEAR_MIN * 3)))
    if fail is not None:
        for own, d, h in rows:
            if h or d < CLEAR_MIN:
                fail.add("%s: %s %s (%.3f m)" % (inst.name, own, "intersects it" if h else "is too near", d))
    return rows


def support_tree(dg):
    """World BVH of the paving the lions stand on (evaluated: modifiers applied)."""
    parts, evs = [], []
    for nm in SUPPORT:
        o = bpy.data.objects.get(nm)
        if o is not None and o.type == 'MESH':
            ev = o.evaluated_get(dg)
            parts.append((o.matrix_world.copy(), ev.to_mesh()))
            evs.append(ev)
    try:
        return bvh_of(parts) if parts else None
    finally:
        for ev in evs:
            ev.to_mesh_clear()


def grounding(inst, sex, b, tree, fail):
    """The sole's footprint on the paving: FOOT_PTS points, paving top between the cut sole and the origin."""
    co = LP.load(sex)[0] * b
    z0 = float(co[:, 2].min())
    sole = co[co[:, 2] < z0 + 0.02 * b]
    x0, y0 = sole[:, :2].min(0)
    x1, y1 = sole[:, :2].max(0)
    ix, iy = 0.05 * (x1 - x0), 0.05 * (y1 - y0)
    Mw = inst.matrix_world
    oz = Mw.translation.z
    gaps = []
    for u in (0.0, 0.5, 1.0):
        for v in (0.0, 0.5, 1.0):
            p = Mw @ Vector((x0 + ix + u * (x1 - x0 - 2 * ix), y0 + iy + v * (y1 - y0 - 2 * iy), 0.0))
            h = tree.ray_cast(Vector((p.x, p.y, oz + 2.0)), Vector((0.0, 0.0, -1.0)), 6.0)
            gaps.append(None if h[0] is None else h[0].z - oz)
    ok = [g for g in gaps if g is not None]
    log("grounding %s: sole cut at %.3f m under the origin; paving top at the %d footprint points: %s m from the origin"
        % (inst.name, -z0, len(gaps), ["%.4f" % g if g is not None else None for g in gaps]))
    if len(ok) < FOOT_PTS:
        fail.add("%s: no paving under %d of the sole's %d points" % (inst.name, FOOT_PTS - len(ok), FOOT_PTS))
    elif min(ok) < z0 - FOOT_TOL or max(ok) > FOOT_TOL:
        fail.add("%s: the paving top (%.3f..%.3f m) is not between the sole (%.3f) and the origin" % (
            inst.name, min(ok), max(ok), z0))


def screen(sc, cam, pts):
    cs = [world_to_camera_view(sc, cam, Vector(p)) for p in pts]
    xs = [c.x * RES[0] for c in cs]
    ys = [(1.0 - c.y) * RES[1] for c in cs]
    front = all(c.z > 0 for c in cs)
    return min(xs), max(xs), min(ys), max(ys), front


def reading(sc, cam, inst, tag):
    """(box, head box) of the lion on screen at the hold, logged."""
    pts = world_points(proto_parts(inst))
    lo, hi = pts.min(0), pts.max(0)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    zh = lo[2] + HEAD_FRAC * (hi[2] - lo[2])
    head = pts[pts[:, 2] > zh]
    hl, hh = head.min(0), head.max(0)
    hc = [(x, y, z) for x in (hl[0], hh[0]) for y in (hl[1], hh[1]) for z in (hl[2], hh[2])]
    b = screen(sc, cam, corners)
    h = screen(sc, cam, hc)
    inside = max(0.0, min(h[1], RES[0]) - max(h[0], 0.0)) * max(0.0, min(h[3], RES[1]) - max(h[2], 0.0))
    area = max(1e-6, (h[1] - h[0]) * (h[3] - h[2]))
    log("reading %s %s at frame %d (%dx%d): box x %.0f..%.0f y %.0f..%.0f; head x %.0f..%.0f y %.0f..%.0f, %.0f%% of it "
        "in frame" % (tag, inst.name, HOLD_FRAME, RES[0], RES[1], b[0], b[1], b[2], b[3], h[0], h[1], h[2], h[3],
                      100.0 * inside / area))
    return b, h, inside / area


def digest(insts):
    h = hashlib.md5()
    for inst in sorted(insts, key=lambda o: o.name):
        pc = inst.instance_collection
        h.update(("%s|%s" % (inst.name, pc.name)).encode())
        h.update(np.round(np.array(inst.matrix_world), 5).tobytes())
        for o in sorted(pc.all_objects, key=lambda o: o.name):
            h.update(o.name.encode())
            if o.type == 'MESH':
                co, tri, uv = mesh_arrays(o.data)
                h.update(np.round(co, 5).tobytes())
                h.update(tri.tobytes())
                h.update(np.round(uv, 6).tobytes())
                h.update(",".join(s.material.name if s.material else "-" for s in o.material_slots).encode())
    return h.hexdigest()


def remove_proto(pc):
    n = 0
    for o in list(pc.all_objects):
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        n += 1
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(pc)
    return n


# ------------------------------------------------------------------------------------------------------ main

def main():
    t0 = time.time()
    dry = options()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    root = bpy.data.objects.get(ROOT_EMPTY)
    cam = bpy.data.objects.get(EW.CAMERA)
    if root is None or cam is None:
        raise SystemExit("PATCH %s / %s not found: is this the chase file?" % (ROOT_EMPTY, EW.CAMERA))
    miss = LP.missing_assets()
    if miss:
        raise SystemExit("PATCH lion assets missing, nothing changed: %s" % miss)
    insts = lion_instances()
    log("lion instances:", {o.name: (s, pc.name) for o, (s, pc) in sorted(insts.items(), key=lambda r: r[0].name)})
    names = {o.name: o for o in insts}
    for nm, sex, side in EXPECTED:
        if nm not in names:
            fail.add("%s is not a guardian-lion instance" % nm)
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    mats0 = {m.name for m in bpy.data.materials}
    imgs0 = {i.name for i in bpy.data.images}
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    dg = bpy.context.evaluated_depsgraph_get()
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    sc.frame_set(HOLD_FRAME)
    read0 = {}
    for o in sorted(insts, key=lambda o: o.name):
        state, pc = insts[o]
        b, mirror, mat, pm = params(state, pc)
        log("%s: %s prototype %s (size bucket %s, %s, %s / %s), %d objects, %d triangles, at %s" % (
            o.name, state, pc.name, b, "female" if mirror else "male", mat, pm, len(pc.all_objects),
            sum(tris(x.data) for x in pc.all_objects if x.type == 'MESH'),
            tuple(round(v, 3) for v in (root.matrix_world.inverted() @ o.matrix_world.translation))))
        if b is None:
            fail.add("%s: unknown size bucket in %s" % (o.name, pc.name))
        read0[o.name] = reading(sc, cam, o, "before")
        clearance(dg, o, "before")
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    # apply
    added, removed, changed = 0, 0, []
    old_protos = set()
    for o in sorted(insts, key=lambda o: o.name):
        state, pc = insts[o]
        b, mirror, mat, pm = params(state, pc)
        key, b2, _res, sex, lm = LP.proto_key(b, mirror, mat, pm)
        cname = "%s.%s.v%d" % (P.PREFIX, key, P._VERSION)
        new = bpy.data.collections.get(cname)
        if new is not None and not proto_current(new, sex, b2):
            log("%s: %s is stale (the npz changed): rebuilding it" % (o.name, cname))
            for x in list(new.all_objects):
                me = x.data if x.type == 'MESH' else None
                bpy.data.objects.remove(x, do_unlink=True)
                removed += 1
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            changed.append(o.name)
        n_before = len(bpy.data.objects)
        new, res = LP.lion_proto(b, mirror, mat, pm)
        added += len(bpy.data.objects) - n_before
        if abs(res - 1.0) > 1e-9 or new.name != cname:
            fail.add("%s: lion_proto gave %s (residual %s), expected %s" % (o.name, new.name, res, cname))
        if o.instance_collection != new:
            if state == "old":
                old_protos.add(pc)
            o.instance_collection = new
            changed.append(o.name)
            log("%s -> %s (%s)" % (o.name, new.name, [x.name for x in new.all_objects]))
        else:
            log("%s already on %s" % (o.name, new.name))
    for pc in sorted(old_protos, key=lambda c: c.name):
        if any(x.instance_type == 'COLLECTION' and x.instance_collection == pc for x in bpy.data.objects):
            log("old prototype %s still instanced: kept" % pc.name)
            continue
        log("old prototype %s removed (%s)" % (pc.name, [x.name for x in pc.all_objects]))
        removed += remove_proto(pc)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    insts1 = lion_instances()
    # checks: the pair and the custom
    rinv = root.matrix_world.inverted()
    for nm, sex, side in EXPECTED:
        o = bpy.data.objects.get(nm)
        state, pc = insts1.get(o, (None, None))
        if state != "new":
            fail.add("%s is not on a scan prototype" % nm)
            continue
        if NEW_RX.match(pc.name).group(2) != sex:
            fail.add("%s should be the %s" % (nm, "male" if sex == "m" else "female"))
        Ml = rinv @ o.matrix_world
        x = Ml.translation.x
        yaw = Ml.to_euler().z
        fwd = (Ml.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
        log("custom %s: %s at gate x %+.2f, facing %s (yaw %.2f deg)" % (
            nm, "male" if sex == "m" else "female", x, tuple(round(v, 3) for v in fwd), math.degrees(yaw)))
        if x * side <= 0:
            fail.add("%s (%s) is on the wrong side of the gate's axis (x %.2f)" % (nm, sex, x))
        if fwd.dot(Vector((0.0, -1.0, 0.0))) < math.cos(FACE_TOL):
            fail.add("%s does not face -Y (out of the gate)" % nm)
    # prototypes
    tree = support_tree(dg)
    for o in sorted(insts1, key=lambda o: o.name):
        state, pc = insts1[o]
        if state != "new":
            fail.add("%s still on %s" % (o.name, pc.name))
            continue
        b, mirror, mat, pm = params(state, pc)
        sex = "f" if mirror else "m"
        ob = proto_mesh_obj(pc)
        if ob is None or len(pc.all_objects) != 1:
            fail.add("%s: prototype %s holds %s" % (o.name, pc.name, [x.name for x in pc.all_objects]))
            continue
        me = ob.data
        t = tris(me)
        slots = [s.material.name if s.material else None for s in ob.material_slots]
        mt = bpy.data.materials.get(M.PREFIX + LP.MAT % sex) if mat == "marble_white" == pm else None
        imgs = [n.image for n in mt.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"] if mt else []
        uvl = me.uv_layers.get("UVMap")
        log("%s: %s -> %s, %d triangles, %d vertices, slots %s, images %s, box %s..%s" % (
            o.name, pc.name, ob.name, t, len(me.vertices), slots,
            [(i.name, tuple(i.size)) if i else None for i in imgs],
            tuple(round(min(c[k] for c in ob.bound_box), 3) for k in range(3)),
            tuple(round(max(c[k] for c in ob.bound_box), 3) for k in range(3))))
        if t > TRI_CAP:
            fail.add("%s: %d triangles > %d" % (ob.name, t, TRI_CAP))
        if mat == "marble_white" == pm and slots != [M.PREFIX + LP.MAT % sex]:
            fail.add("%s: material slots %s" % (ob.name, slots))
        if mt is not None and (len(imgs) != 2 or any(i is None or i.size[0] == 0 for i in imgs)):
            fail.add("%s: its two images do not load" % mt.name)
        if uvl is None or not uvl.active_render:
            fail.add("%s: no active-render 'UVMap'" % ob.name)
        if not proto_current(pc, sex, b):
            fail.add("%s: the mesh is not the npz at size %s" % (ob.name, b))
        if tree is None:
            fail.add("no paving (%s) to stand on" % (SUPPORT,))
        else:
            grounding(o, sex, b, tree, fail)
        clearance(dg, o, "after", fail)
    # reading at the hold
    sc.frame_set(HOLD_FRAME)
    for o in sorted(insts1, key=lambda o: o.name):
        _b, _h, frac = reading(sc, cam, o, "after")
        frac0 = read0.get(o.name, (None, None, 0.0))[2]
        if frac < min(frac0, 1.0) - 0.15:
            fail.add("%s: its head leaves the hold's frame (%.0f%% in frame, was %.0f%%)" % (
                o.name, 100 * frac, 100 * frac0))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
    sc.frame_set(keep_frame)
    # counts
    n_obj1 = len(bpy.data.objects)
    log("objects %d -> %d (prototype objects added %d, removed %d)" % (n_obj0, n_obj1, added, removed))
    if n_obj1 - n_obj0 != added - removed:
        fail.add("object count %d -> %d does not match +%d -%d" % (n_obj0, n_obj1, added, removed))
    if sorted(o.name for o in insts1) != sorted(o.name for o in insts):
        fail.add("lion instances %s -> %s" % (sorted(o.name for o in insts), sorted(o.name for o in insts1)))
    new_mats = sorted({m.name for m in bpy.data.materials} - mats0)
    new_imgs = sorted({i.name for i in bpy.data.images} - imgs0)
    log("new materials", new_mats, "new images", new_imgs)
    if any(not m.startswith(M.PREFIX + "props_lion_") for m in new_mats):
        fail.add("unexpected new materials %s" % new_mats)
    if any(not re.match(r"^lion_[mf]_(diff|nrm)\.", i) for i in new_imgs):
        fail.add("unexpected new images %s" % new_imgs)
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    log("DIGEST", digest(list(insts1)))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if changed:
        log("CACHES needs audit: the lions' instance names are kept, but what they instance is new (prototype objects "
            "'props.lion.scan.m' / 'props.lion.scan.f' replace 'props.lion.plinth' / 'props.lion.body': the "
            "visibility cache keys them by owner|object, so the old records miss) and their world boxes changed by up "
            "to ~0.2 m - run export_web.py -- audit --profile full, then -- chunks,meta --profile full, then "
            "bake_web.py -- bakefull --profile full --chunks gate,backdrop (both lions bake in the gate chunk; the "
            "backdrop's gate proxy), then pack. The trees bake and the water are not affected.")
    else:
        log("CACHES ok: nothing changed")
    if not changed:
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
