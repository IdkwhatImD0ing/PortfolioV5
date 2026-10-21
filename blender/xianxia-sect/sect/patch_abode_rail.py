"""Stand the Cave Abode's stone rim rail on the lawn in out/sect_chase.blend and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_abode_rail.py [-- DRY_RUN=1]

Why: areas/abode.py built the rail at r 53 m with its feet at z -0.4, outside the round lawn (r 50 m) on the terrace
rock where the cliff already falls away, so it read as detached from the grass (in the shipped web files 59 of its 94
posts stand more than 0.3 m over the ground under them, up to ~2.5 m over the cliff's first slope). It now stands on
the lawn: an arc at RIM_R (48.5 m) with every post on the lawn height less RIM_SINK, open where the arrival landing
crosses it (RIM_GAP), RIM_SEGS segments a span. abode._rim_spans lays it out; a full rebuild runs the same code.

What it does: for each rail span (the Empties abode.rim_rail and abode.rim_rail.001 under abode.root, west and east of
the arrival landing), lays the new rail out with sect.lib.arch.balustrade on the lawn of abode.ground (its evaluated
mesh, in abode.root's frame), with arch.scatter captured, so the instance matrices are exactly the ones a rebuild
makes, and writes them into the span's existing point clouds <span>.posts and <span>.panels (vertex positions and
the arch_xf matrix attribute). Nothing is created or removed in the saved file: same objects, names, parents,
modifiers, prototypes (arch.p.post.1220.stone_grey, arch.p.panel.860.stone_grey: material stone_grey) and instance
counts (41 posts / 40 panels and 53 / 52), so every export record key (owner|proto|0.0.<index>) stays valid.
Stops without saving when a span, a prototype or an instance count is not what it expects (a blend built
differently; after a full rebuild run the export audit instead). Idempotent: a re-run lays out the same rail on the
same lawn and writes the same values ("unchanged").

Options after "--": DRY_RUN=1 (report, no save); abode.KEY=value overrides an upper-case constant of
sect/areas/abode.py, e.g. abode.RIM_R=48.0 abode.RIM_SINK=0.03 (abode.RIM_SEGS must stay (20, 26)).

After saving, nothing of export_web has to re-run (record keys, chunk plan and hotspots are unchanged; the rail is
not a hotspot member and too small for the backdrop proxy). Re-bake the abode chunk and pack it:
    ... rblender.py --background .../out/sect_chase.blend --python .../sect/bake_web.py -- bakefull --profile full --chunks abode
    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/sect_pack.py --profile full --only abode
Close-ups first if wanted: sect/preview_abode_rail.py.
"""
import ast
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import abode as AB  # noqa: E402
from sect.lib import arch as A  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

AREA_ROOT = "abode.root"
GROUND = "abode.ground"
SPANS = ("abode.rim_rail", "abode.rim_rail.001")          # build order: west span, east span
RAIL_HEIGHT = 1.0                                         # = abode._rim_rail's balustrade call
RAIL_MAT = "stone_grey"
PROTOS = {"posts": "arch.p.post.1220.stone_grey", "panels": "arch.p.panel.860.stone_grey"}
COUNTS = {"abode.rim_rail": (41, 40), "abode.rim_rail.001": (53, 52)}   # (posts, panels) the export's records hold
TMP = "abode.rim_rail_patchtmp"


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("patch_abode_rail: not KEY=value: %r" % a)
        if k == "DRY_RUN":
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k.startswith("abode.") and k[6:].isupper() and hasattr(AB, k[6:]):
            setattr(AB, k[6:], ast.literal_eval(v))
            log("override", k, "=", getattr(AB, k[6:]))
        else:
            raise SystemExit("patch_abode_rail: unknown option %r (DRY_RUN=1 or abode.KEY=value)" % a)
    return dry


def lawn_sampler(ground, root):
    """gz(x, y, default) in abode.root's frame, as abode._lawn_sampler: the top of abode.ground's evaluated mesh
    (what the bake exports). Also returns the list of points that missed the lawn."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ground.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        m = U.world_matrix(root).inverted() @ U.world_matrix(ground)
        verts = [m @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        ev.to_mesh_clear()
    bvh = BVHTree.FromPolygons(verts, polys)
    down = Vector((0.0, 0.0, -1.0))
    misses = []

    def gz(x, y, default=-0.4):
        hit = bvh.ray_cast(Vector((x, y, 20.0)), down)
        if hit[0] is None:
            misses.append((round(x, 2), round(y, 2)))
            return default
        return hit[0].z
    log("lawn", ground.name, len(verts), "verts", len(polys), "faces")
    return gz, misses


def layout(pts, coll):
    """{'posts' | 'panels': (prototype collection, [4x4 matrices])} for one span, from arch.balustrade itself
    (its scatter call captured: no point cloud is made). The matrices are in the span root's space = the points'."""
    got = {}
    real = A.scatter

    def capture(name, collection, proto, matrices, parent=None):
        got[name.rsplit(".", 1)[-1]] = (proto, [Matrix(m) for m in matrices])
        return None
    A.scatter = capture
    try:
        root = A.balustrade(TMP, coll, pts, height=RAIL_HEIGHT, mat=RAIL_MAT)
    finally:
        A.scatter = real
    bpy.data.objects.remove(root, do_unlink=True)
    return got


def scatter_proto(ob):
    """The prototype collection an arch.scatter point cloud instances (its 'arch_scatter' node group)."""
    mod = ob.modifiers.get("arch_scatter")
    ng = mod.node_group if mod is not None else None
    ci = ng.nodes.get("arch_ci") if ng is not None else None
    return ci.inputs["Collection"].default_value if ci is not None else None


def read_points(ob):
    me = ob.data
    co = [0.0] * (3 * len(me.vertices))
    me.vertices.foreach_get("co", co)
    return [Vector(co[i:i + 3]) for i in range(0, len(co), 3)]


def write_points(ob, mats, rel):
    """Write instance matrices (span-root space) into an arch.scatter point cloud in place, as arch.scatter stores
    them (vertex = translation, 'arch_xf' column-major). Returns the largest move of a point (m)."""
    me = ob.data
    at = me.attributes.get("arch_xf")
    co, flat = [], []
    for m in mats:
        m = rel @ m
        t = m.translation
        co.extend((t.x, t.y, t.z))
        for c in range(4):
            for r in range(4):
                flat.append(m[r][c])
    old = read_points(ob)
    me.vertices.foreach_set("co", co)
    at.data.foreach_set("value", flat)
    me.update()
    return max((Vector(co[3 * i:3 * i + 3]) - p).length for i, p in enumerate(old)) if old else 0.0


def angle_of(points):
    s = Vector((0.0, 0.0, 0.0))
    for p in points:
        s += Vector((p.x, p.y, 0.0)).normalized()
    return math.degrees(math.atan2(s.y, s.x)) % 360.0


def main():
    dry = options()
    root = bpy.data.objects.get(AREA_ROOT)
    ground = bpy.data.objects.get(GROUND)
    if root is None or ground is None or ground.type != "MESH":
        raise RuntimeError("no %s / %s mesh: is this out/sect_chase.blend?" % (AREA_ROOT, GROUND))
    for part, cname in PROTOS.items():
        col = bpy.data.collections.get(cname)
        if col is None or not col.get("arch_ok") or not len(col.objects):
            raise RuntimeError("prototype collection %s missing or not built (arch_ok); nothing saved" % cname)
        for o in col.objects:
            mats = [s.material for s in getattr(o, "material_slots", ())]
            tags = [m.get(M.TAG) if m is not None else None for m in mats]
            log("prototype", cname, o.name, "materials", [m.name if m else None for m in mats], "tags", tags)
            if o.type == "MESH" and (not mats or mats[0] is None):
                U.set_materials(o.data, [RAIL_MAT])
                log("WARN", o.name, "had no material; set", RAIL_MAT)
            elif RAIL_MAT not in tags:
                log("WARN", o.name, "material is not tagged", RAIL_MAT)
    spans = []
    for nm in SPANS:
        rr = bpy.data.objects.get(nm)
        if rr is None or rr.type != "EMPTY" or rr.parent != root:
            raise RuntimeError("rail span %s missing or not under %s; nothing saved" % (nm, AREA_ROOT))
        parts = {}
        for part in ("posts", "panels"):
            ob = bpy.data.objects.get(nm + "." + part)
            if ob is None or ob.type != "MESH" or ob.parent != rr or ob.data.attributes.get("arch_xf") is None:
                raise RuntimeError("%s.%s missing or not an arch.scatter point cloud; nothing saved" % (nm, part))
            if ob.data.users > 1:
                raise RuntimeError("%s.%s shares its mesh; nothing saved" % (nm, part))
            pc = scatter_proto(ob)
            if pc is None or pc.name != PROTOS[part]:
                raise RuntimeError("%s.%s instances %s, not %s; nothing saved"
                                   % (nm, part, pc.name if pc else None, PROTOS[part]))
            parts[part] = ob
        spans.append((nm, rr, parts))
    gz, misses = lawn_sampler(ground, root)
    new = AB._rim_spans(gz)
    if misses:
        raise RuntimeError("rail points off the lawn %s: RIM_R %.2f too large? nothing saved" % (misses[:6], AB.RIM_R))
    if len(new) != len(spans):
        raise RuntimeError("abode._rim_spans made %d spans, the blend has %d; nothing saved" % (len(new), len(spans)))
    coll = bpy.data.collections.new(TMP)
    try:
        laid = [layout(pts, coll) for pts in new]
    finally:
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(coll)
    # pair the new spans with the blend's by where they lie (west / east of the gap), then check the counts
    old_ang = [angle_of(read_points(p["posts"])) for _, _, p in spans]
    new_ang = [angle_of([m.translation for m in L["posts"][1]]) for L in laid]
    order = sorted(range(len(spans)), key=lambda i: old_ang[i])
    order_new = sorted(range(len(laid)), key=lambda i: new_ang[i])
    work = []
    for i, j in zip(order, order_new):
        nm, rr, parts = spans[i]
        L = laid[j]
        want = COUNTS[nm]
        have = (len(parts["posts"].data.vertices), len(parts["panels"].data.vertices))
        got = (len(L["posts"][1]), len(L["panels"][1]))
        log(nm, "at %.0f deg, new span at %.0f deg; posts/panels: blend %s, new %s, export records %s"
            % (old_ang[i], new_ang[j], have, got, want))
        if not (have == got == want):
            raise RuntimeError("%s: instance counts differ (blend %s, new %s, records %s): this would drop or orphan "
                               "export records; nothing saved" % (nm, have, got, want))
        for part in ("posts", "panels"):
            if L[part][0].name != PROTOS[part]:
                raise RuntimeError("new %s use %s, not %s; nothing saved" % (part, L[part][0].name, PROTOS[part]))
        work.append((nm, parts, L, new[j]))
    # check every post against the lawn before anything is written: the lawn height under it less its foot
    # (main points: RIM_SINK by construction; the mid-segment posts sit on the straight line between two of them)
    W_root = U.world_matrix(root)
    plan = []
    for nm, parts, L, pts in work:
        before = read_points(parts["posts"])
        after = [m.translation for m in L["posts"][1]]
        dev = [gz(p.x, p.y) - p.z for p in after]
        rel = {part: U.world_matrix(ob).inverted() @ W_root for part, ob in parts.items()}
        off = max(max(abs(rel[p][r][c] - (1.0 if r == c else 0.0)) for r in range(4) for c in range(4)) for p in rel)
        log(nm, "posts r %.2f -> %.2f m, feet z %.2f..%.2f -> %.3f..%.3f; lawn over the feet %.3f..%.3f m "
            "(RIM_SINK %.3f); span-root offset %.1e"
            % (sum(math.hypot(p.x, p.y) for p in before) / len(before),
               sum(math.hypot(p.x, p.y) for p in after) / len(after), min(p.z for p in before),
               max(p.z for p in before), min(p.z for p in after), max(p.z for p in after), min(dev), max(dev),
               AB.RIM_SINK, off))
        if min(dev) < -0.04 or max(dev) > 0.12:
            raise RuntimeError("%s: a post foot is %.3f / %.3f m off the lawn; nothing saved" % (nm, min(dev), max(dev)))
        plan.append((nm, parts, L, rel))
    if misses:
        raise RuntimeError("posts off the lawn: %s; nothing saved" % misses[:6])
    end_w, end_e = new[0][-1], new[1][0]
    log("arrival gap: rail ends at (%.2f, %.2f) and (%.2f, %.2f); landing x %.1f..%.1f"
        % (end_w[0], end_w[1], end_e[0], end_e[1], AB.GATE_X - 4.0, AB.GATE_X + 4.0))
    if dry:
        log("DRY_RUN: nothing written or saved")
        return
    for nm, parts, L, rel in plan:
        moved = {part: round(write_points(parts[part], L[part][1], rel[part]), 3) for part in ("posts", "panels")}
        log(nm, "written: largest move per part (m)", moved, "(unchanged)" if max(moved.values()) < 1e-3 else "")
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
