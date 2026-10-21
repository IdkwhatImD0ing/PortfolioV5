"""Audit D1 (2026-10-21): the link stairways' supports in out/sect_chase.blend rebuilt the way sect/world.py now
builds them (_stairway, _supports), and their stone retinted. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r2_links.py [-- DRY_RUN=1]

Why: the stairs read as a Roman aqueduct (audit visual #1, seen large in about 10 of 35 frames): a pale grey pier
every 4.8 m, a round-headed arcade between them and tie arches every 12 m down.

For each of the 8 stairway links (world.link.<a>_<b>; the chain bridge to the arena and the stepping stones from it
are not touched), same object names, new mesh data:
- <link>.piers: piers with stepped corbel heads, at most world.PIER_SPAN[1] (20 m) apart, where the treads stand more
  than world.PIER_GAP (4 m) over the ground, widening toward the ground; plus a footing from the soffit into the
  ground under the lower stretches, whose ends are the abutments of each run of piers (it was piers + arcades);
- <link>.stairs, <link>.rails: the same vertices; their bottom faces get world_pier_stone (a second material slot);
- <link>.rest_pier: its foot on the range as the scene's world.range meshes it.
M.world_pier_stone is rebuilt in place as world.py's cliff-rock variant (it was stone_grey). world.root['links']
gets the new link reports (piers, tallest_pier, pier_runs, longest_span, footing_m, tallest_footing, buried_mesh).

Guards (nothing is saved when one fails): each link's ports must be where the scene's report has them, and the
stairway they give must reproduce the scene's treads, parapets, landings and bridge arch vertex for vertex (1 mm);
every replaced object exists, keeps one user and has its material slots on its data; no span between supports over
PIER_SPAN[1] (+0.5 m) and no tread more than 0.5 m under the range.
Idempotent: a re-run rebuilds the same meshes (and still finds the same treads).

The supports stand on the range as the scene meshes it: world.GRID, or 5 m when the scene's world.range is still on
the 5 m grid (measured from its node spacing), so this runs before or after sect/patch_r2_range.py.

Afterwards: the names are the same, but the .piers meshes change shape and box. Run export_web audit (with the rest
of round 2), chunks,meta, then bakefull for every area a stairway passes plus backdrop, and the pack.
"""
import ast
import json
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world as W  # noqa: E402
from sect.lib import materials as M  # noqa: E402

TOL = 1e-3                     # m: rebuilt vertices must match the scene's this closely
PORT_TOL = 0.02                # m: the ports against world.root's report
REPLACE = ("stairs", "rails", "piers", "rest_pier")
SAME = ("foot_landing", "foot_rail", "rest_landing", "rest_rail", "arch")
PIER_MAT = "world_pier_stone"
BURIAL_MAX = 0.5


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
            raise SystemExit("patch_r2_links: unknown argument %r (DRY_RUN=1)" % a)
    return opt


def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def tris(me):
    n = len(me.polygons)
    lt = np.empty(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(lt.sum() - 2 * n)


def range_grid():
    """The scene's world.range node spacing: 2.5 when many nodes sit on odd multiples of 2.5 m from EXTENT, else 5."""
    r = bpy.data.objects.get("world.range")
    if r is None:
        raise SystemExit("patch_r2_links: no world.range; is this out/sect_chase.blend?")
    k = (coords(r.data)[:, 0] - W.EXTENT[0]) / 2.5
    kr = np.round(k)
    odd = (np.abs(k - kr) < 1e-4) & (kr % 2 == 1)
    return 2.5 if int(odd.sum()) > 1000 else 5.0


def part_of(name, nm):
    """'stairs' for 'world.link.gate_mirror.stairs' or '...stairs.001' (a rebuilt copy's name)."""
    return name[len(nm) + 1:].split(".")[0] if name.startswith(nm + ".") else None


def same_verts(a, b):
    ca, cb = coords(a.data), coords(b.data)
    if ca.shape != cb.shape:
        return False, "vertex count %d vs %d" % (len(ca), len(cb))
    d = float(np.abs(ca - cb).max()) if len(ca) else 0.0
    return d <= TOL, "max vertex offset %.4f m" % d


def swap(ob, new_ob):
    """Give ``ob`` the mesh of ``new_ob`` (its name, object, collections and props stay); drop both leftovers."""
    if any(s.link != 'DATA' for s in ob.material_slots):
        raise RuntimeError("%s has object-linked material slots" % ob.name)
    if ob.data.users != 1:
        raise RuntimeError("%s's mesh has %d users" % (ob.name, ob.data.users))
    old_me, me = ob.data, new_ob.data
    name = old_me.name
    bpy.data.objects.remove(new_ob, do_unlink=True)
    ob.data = me
    bpy.data.meshes.remove(old_me)
    me.name = name


def main():
    opt = options()
    root = bpy.data.objects.get("world.root")
    if root is None or "links" not in root or bpy.data.collections.get("world.links") is None:
        raise SystemExit("patch_r2_links: no world.root['links'] / collection world.links; is this out/sect_chase.blend?")
    g = range_grid()
    log("world.range node spacing %g m (world.GRID %g); stairs planned on %g m" % (g, W.GRID, W.PLAN_GRID))
    W.GRID = g
    rng_ = W.Range(W._norm_anchors(None), W._anchor_yaws(None))
    reports = json.loads(root["links"])
    by_link = {r["link"]: r for r in reports}
    tmp = bpy.data.collections.new("patch_r2_links.tmp")       # not in the scene: built, compared, swapped, dropped
    mat = M.get(PIER_MAT)
    users0 = mat.users
    tri0 = tri1 = 0
    done = []
    try:
        for seg in rng_.segs:
            if not seg["mass"]:
                continue
            ka, kb = seg["ka"], seg["kb"]
            nm = "world.link.%s_%s" % (ka, kb)
            key = "%s-%s" % (ka, kb)
            pa, pb = W.port(rng_, ka, "depart"), W.port(rng_, kb, "arrival")
            old = by_link.get(key)
            if old is None or pa is None or pb is None:
                raise RuntimeError("%s: no report or no ports" % nm)
            for end, p in (("depart", pa), ("arrival", pb)):
                off = float(np.abs(np.asarray(old[end]["world"], float) - p["p"]).max())
                if off > PORT_TOL:
                    raise RuntimeError("%s %s moved %.3f m since the build: %s vs %s"
                                       % (nm, end, off, old[end]["world"], p["p"].round(2).tolist()))
            objs, rep, _ = W._stairway(rng_, tmp, seg, nm, pa, pb, arch_extras=False)
            new = {part_of(o.name, nm): o for o in objs}
            for part in SAME + ("stairs", "rails"):
                o_old, o_new = bpy.data.objects.get(nm + "." + part), new.get(part)
                if (o_old is None) != (o_new is None):
                    raise RuntimeError("%s.%s: in the scene %s, rebuilt %s" % (nm, part, o_old is not None, o_new is not None))
                if o_old is None:
                    continue
                ok, why = same_verts(o_old, o_new)
                if not ok:
                    raise RuntimeError("%s.%s does not match the rebuilt plan: %s" % (nm, part, why))
            if (bpy.data.objects.get(nm + ".rest_pier") is None) != (new.get("rest_pier") is None):
                raise RuntimeError("%s.rest_pier: the rest terrace's pier came and went" % nm)
            if rep["longest_span"] > W.PIER_SPAN[1] + 0.5:
                raise RuntimeError("%s: a %.1f m span between supports" % (nm, rep["longest_span"]))
            if rep["burial_max"] > BURIAL_MAX:
                raise RuntimeError("%s: a tread %.2f m under the range" % (nm, rep["burial_max"]))
            for part in REPLACE:
                o_old, o_new = bpy.data.objects.get(nm + "." + part), new.get(part)
                if o_new is None:
                    if o_old is not None:
                        raise RuntimeError("%s.%s: the scene has it, the rebuild has none" % (nm, part))
                    continue
                if o_old is None:
                    raise RuntimeError("%s.%s: new object (would need new names); not patching" % (nm, part))
                t0, t1 = tris(o_old.data), tris(o_new.data)
                tri0, tri1 = tri0 + t0, tri1 + t1
                swap(o_old, o_new)
                log("replaced", o_old.name, "tris %d -> %d" % (t0, t1), "slots",
                    [s.material.name if s.material else None for s in o_old.material_slots])
            old_p, old_t = old.get("piers"), old.get("tallest_pier")
            upd = {k: v for k, v in rep.items() if k not in ("depart", "arrival", "link")}
            old.update(upd)
            done.append(key)
            log("LINK", key, "piers %s -> %d (tallest %s -> %.1f m) in %d runs, longest span %.1f m, footing %.1f m "
                "(tallest %.1f m), treads under the range: %d samples, at most %.2f m"
                % (old_p, rep["piers"], old_t, rep["tallest_pier"], rep["pier_runs"], rep["longest_span"],
                   rep["footing_m"], rep["tallest_footing"], rep["buried_mesh"], rep["burial_max"]))
    finally:
        for o in list(tmp.objects):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(tmp)
    if len(done) != sum(1 for s in rng_.segs if s["mass"]):
        raise RuntimeError("only %d stairways patched: %s" % (len(done), done))
    builder, params = M._REGISTRY[PIER_MAT]
    n0 = len(mat.node_tree.nodes)
    M.rebuild(PIER_MAT)
    log("rebuilt", mat.name, "as", builder.__name__, {k: v for k, v in params.items()}, "nodes %d -> %d"
        % (n0, len(mat.node_tree.nodes)), "users %d -> %d" % (users0, mat.users))
    root["links"] = json.dumps(reports)
    log("stairways", len(done), "triangles of the replaced meshes %d -> %d" % (tri0, tri1))
    log("SAME NAMES, NEW SHAPES: export_web audit + chunks,meta, then bakefull for the areas the stairs pass + backdrop")
    if opt["dry"]:
        log("DRY_RUN: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
