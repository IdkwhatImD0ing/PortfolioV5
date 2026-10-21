"""Round 5, lane float: ground the props the whole-scene floating scan found hovering in the library and mirror areas,
the way sect/areas/library.py and sect/areas/mirror.py now build them. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r5_float.py [-- DRY_RUN=1]

Object locations only (z, in the parent's frame); nothing is added, removed, renamed or reshaped:
- library.lantern_stone .000-.003   on the lawn beside the axis path, not at the path's top: they stood 0.17-0.30 m
                                     over the undulating lawn (library._settle, foot radius LANTERN_FOOT_R)
- library.blossom, .blossom.001      peach trees; .001 on the lawn's rim stood 0.32-0.43 m over the terrace
- library.boulder                    on the pond basin's slope it hovered 0.19-0.36 m; now bedded BOULDER_SINK deep
- library.study_east/west.roof.finial  the round roofs' finials floated 0.33 m (nearest) over the apex
                                     (library._seat_finial: foot FINIAL_SINK into the tiles)
- mirror.ting_lantern, .001          the ting's eave-corner silk lanterns hung 0.19 m under the soffit from nothing;
                                     the cord's top now sits LANTERN_HOOK_IN inside the soffit (mirror._soffit_z)
Each new height comes from the same functions the area build calls, on the objects in the file, so a fresh build and
the patched file agree. Idempotent: a re-run computes the same heights (moves of < 1 mm are left alone).

Checks (nothing is saved when one fails): every object exists with the expected parent; after the move each lantern /
tree / rock foot is no more than GAP_OK over the ground on every foot sample, each finial touches its roof, each
silk lantern's top is within HOOK_OK of the soffit; no move is larger than MOVE_MAX; object count unchanged.
Prints 'PATCH CACHES ok' when every changed object's world box stayed inside its old one, else 'PATCH CACHES STALE'
with the boxes: then run export_web.py -- chunks,meta --profile full (the boxes moved down by up to ~0.45 m) and
re-bake the library and mirror chunks.
"""
import ast
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import library as LB  # noqa: E402
from sect.areas import mirror as MR  # noqa: E402

LIB_ROOT = LB.KEY + ".root"
MIR_ROOT = "mirror.root"
LANTERNS = [LB.KEY + ".lantern_stone" + s for s in ("", ".001", ".002", ".003")]
BLOSSOMS = [LB.KEY + ".blossom", LB.KEY + ".blossom.001"]
BOULDER = LB.KEY + ".boulder"
PAVS = [LB.KEY + ".study_east", LB.KEY + ".study_west"]
TING = "mirror.ting"
TING_LANTERNS = ["mirror.ting_lantern", "mirror.ting_lantern.001"]
MOVE_MAX = 0.8            # no object moves further than this (m)
GAP_OK = 0.05             # foot samples over the ground after the move (m)
HOOK_OK = 0.05
EPS = 1e-3


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
            raise SystemExit("patch_r5_float: unknown argument %r (DRY_RUN=1)" % a)
    return opt


def need(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % name)
    return ob


def world_box(ob):
    """World box of everything the object draws (itself, its instances and its children), evaluated."""
    dg = bpy.context.evaluated_depsgraph_get()
    own = {ob.name} | {c.name for c in ob.children_recursive}
    lo, hi = None, None
    for di in dg.object_instances:
        o = di.object
        if o.type not in {"MESH", "CURVE", "FONT"}:
            continue
        owner = di.parent.original if di.is_instance and di.parent is not None else o.original
        if owner.name not in own:
            continue
        M = di.matrix_world
        pts = np.array([tuple(M @ Vector(c)) for c in o.bound_box])
        lo = pts.min(0) if lo is None else np.minimum(lo, pts.min(0))
        hi = pts.max(0) if hi is None else np.maximum(hi, pts.max(0))
    if lo is None:
        return None
    return tuple(round(float(c), 3) for c in lo), tuple(round(float(c), 3) for c in hi)


def foot_gap(ob, bvh, r):
    """largest gap (m) between the object's origin height and the ground (lawn / terrace) on its foot samples."""
    x, y, z = ob.location
    worst = -1e9
    for k in range(9):
        if k == 0:
            px, py = x, y
        else:
            a = 2 * np.pi * (k - 1) / 8
            px, py = x + r * np.cos(a), y + r * np.sin(a)
        g = LB._ground_z(bvh, px, py, 0.0)
        worst = max(worst, z - g)
    return worst


def main():
    opt = options()
    lroot, mroot = need(LIB_ROOT), need(MIR_ROOT)
    lawn = need(LB.KEY + ".lawn")
    if lawn.parent != lroot:
        raise RuntimeError("library.lawn is not a child of %s" % LIB_ROOT)
    bvh = LB._lawn_bvh(lawn)
    ting = need(TING)
    n_obj = len(bpy.data.objects)
    moved = []          # (object, old z, new z, kind)

    def plan(ob, new_z, kind):
        if ob.parent is None:
            raise RuntimeError("%s has no parent" % ob.name)
        old = ob.location.z
        if abs(new_z - old) > MOVE_MAX:
            raise RuntimeError("%s would move %.3f m (> %.2f): not the file this patch expects" % (ob.name, new_z - old,
                                                                                                    MOVE_MAX))
        moved.append((ob, old, new_z, kind))

    for nm, r, sink in ([(n, LB.LANTERN_FOOT_R, LB.SETTLE_SINK) for n in LANTERNS] +
                        [(n, LB.TRUNK_FOOT_R, LB.SETTLE_SINK) for n in BLOSSOMS] +
                        [(BOULDER, LB.BOULDER_FOOT_R, LB.BOULDER_SINK)]):
        ob = need(nm)
        if ob.parent != lroot:
            raise RuntimeError("%s parent %s != %s" % (nm, ob.parent.name if ob.parent else None, LIB_ROOT))
        plan(ob, LB._ground_z(bvh, ob.location.x, ob.location.y, r) - sink, "settle r=%.2f sink=%.2f" % (r, sink))
    fins = []
    for pn in PAVS:
        pav = need(pn)
        fin = need(pn + ".roof.finial")
        z0 = fin.location.z
        gap = LB._seat_finial(pav)           # moves it; record and undo, so the plan applies it once below
        if gap is None:
            raise RuntimeError("%s: no roof tiles under the finial" % pn)
        z1 = fin.location.z
        fin.location.z = z0
        fins.append(fin)
        log(fin.name, "foot was %.3f m over the apex" % gap)
        plan(fin, z1, "seat finial (gap %.3f)" % gap)
    for nm in TING_LANTERNS:
        ob = need(nm)
        if ob.parent != mroot:
            raise RuntimeError("%s parent %s != %s" % (nm, ob.parent.name if ob.parent else None, MIR_ROOT))
        zc = MR.DECK_Z + 0.45 + 3.6
        soff = MR._soffit_z(ting, mroot, ob.location.x, ob.location.y, zc, None)
        if soff is None:
            raise RuntimeError("%s: no soffit above it" % nm)
        plan(ob, soff + MR.LANTERN_HOOK_IN, "hang from soffit at %.3f" % soff)

    before = {ob.name: world_box(ob) for ob, *_ in moved}
    changed = 0
    for ob, old, new, kind in moved:
        d = new - old
        if abs(d) < EPS:
            log("ok", ob.name, "already at z %.3f (%s)" % (old, kind))
            continue
        log("move", ob.name, "z %.3f -> %.3f (%+.3f m) %s" % (old, new, d, kind))
        ob.location.z = new
        changed += 1
    bpy.context.view_layer.update()

    # checks
    if len(bpy.data.objects) != n_obj:
        raise RuntimeError("object count changed: %d -> %d" % (n_obj, len(bpy.data.objects)))
    for nm, r in [(n, LB.LANTERN_FOOT_R) for n in LANTERNS] + [(n, LB.TRUNK_FOOT_R) for n in BLOSSOMS] + \
            [(BOULDER, LB.BOULDER_FOOT_R)]:
        g = foot_gap(need(nm), bvh, r)
        log("check", nm, "largest foot gap %.3f m" % g)
        if g > GAP_OK:
            raise RuntimeError("%s still %.3f m over the ground" % (nm, g))
    for pn in PAVS:
        pav = need(pn)
        fin = need(pn + ".roof.finial")
        z = fin.location.z
        g = LB._seat_finial(pav)             # measuring call: moves by g + sink, undone
        fin.location.z = z
        log("check", fin.name, "foot %.3f m over the apex (want %.2f)" % (g, -LB.FINIAL_SINK))
        if g is None or abs(g + LB.FINIAL_SINK) > 0.02:
            raise RuntimeError("%s not seated (gap %s)" % (fin.name, g))
    for nm in TING_LANTERNS:
        ob = need(nm)
        soff = MR._soffit_z(ting, mroot, ob.location.x, ob.location.y, MR.DECK_Z + 0.45 + 3.6, None)
        log("check", nm, "suspension %.3f, soffit %.3f" % (ob.location.z, soff))
        if soff is None or abs(ob.location.z - (soff + MR.LANTERN_HOOK_IN)) > HOOK_OK:
            raise RuntimeError("%s not at the soffit" % nm)
    bpy.context.view_layer.update()
    stale = []
    for ob, old, new, kind in moved:
        b0, b1 = before[ob.name], world_box(ob)
        inside = all(b1[0][i] >= b0[0][i] - 2e-3 and b1[1][i] <= b0[1][i] + 2e-3 for i in range(3))
        log("box", ob.name, "before", b0, "after", b1, "inside" if inside else "OUTSIDE")
        if not inside:
            stale.append(ob.name)
    log("moved %d of %d objects" % (changed, len(moved)))
    if stale:
        log("CACHES STALE (needs audit): world boxes moved out of their old ones", stale,
            "- run export_web.py -- chunks,meta --profile full, then re-bake the library and mirror chunks")
    else:
        log("CACHES ok: names unchanged and every world box inside its old one")
    if opt["dry"]:
        log("DRY_RUN: not saved")
        return
    if changed == 0:
        log("nothing to do; not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
