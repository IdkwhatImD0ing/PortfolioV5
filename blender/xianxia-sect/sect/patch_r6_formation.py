"""Bring the formation in a .blend to the round-6 design (护宗大阵 as carved stone and cast bronze with the light inside
it: sect/areas/formation.py, sect/lib/array_props.py) and save. Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<file>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r6_formation.py [-- --no-save] [--once]

1. Removes the old array (light drawn on top of the world): the sky light pillar, the core feed beam, the floating
   octahedron and its rings and halo (the children of formation.core), the rune rings and their grooves, the dark
   floor, the network (spokes, satellite / cluster / cross links, satellites, pads, traces, flags), the motes, the
   dome's glowing base ring, and the old prototypes formation.p.pillar and formation.p.satellite. The eight
   'formation.pillar.k' instances (the page's arch:k hotspots) are kept: reparented to formation.root first.
2. Re-skins the plaza's outer wall and the dais sides in aged marble, and rebuilds the balustrade in it (same names).
3. Builds the new array with formation.build_array(): bluestone floor, ink-stone bands, the jade channel, bronze
   trigrams, radial channels, the chant ring, moss, the armillary (static frame 'formation.armillary', turning set
   under the kept 'formation.core', moved to z 10.5 with the driver frame*0.0025), the station prototype
   'formation.p.station' (every formation.pillar.k now instances it) with the trigram plaques, eight braziers with
   the area's eight point lights, the Five Element Banners, the Big Dipper star-stones, axis lanterns and a censer.

Checks (nothing is saved when one fails): the eight pillars and the core exist (instances of formation.p.station,
core at z 10.5 with the new driver); no object of the formation (or anything it instances) uses a light_beam /
props_beam / formation_beam material; 8 lights or fewer; evaluated triangles <= TRI_CAP; the axis walk (|x| <= 2), the
four dais flights and the cross walks over the dais top are clear of new geometry (vertex box test; the censer is the
one thing on the walk, which passes it); every flag cloth stays inside R_FLAG_MAX; and (unless --once) a second
build in the same session gives the same object names and triangle count.

Idempotent: every object (and own mesh) the new build makes carries the property 'formation_r6'; a re-run removes
them (and empties formation.p.station) before building again, so names and counts come out the same.

Caches: the new pieces have NEW names, so the web caches do not know them: 'PATCH CACHES NEED AUDIT (new formation
objects)' -> run export_web.py -- audit, then -- chunks,meta --profile full, then bake_web.py -- bakefull --profile
full --chunks formation before the page shows them.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import formation as F  # noqa: E402
from sect.lib import array_props as AP  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

K = F.KEY
COLL = K
TRI_CAP = 1_200_000
TRI_TARGET = 1_000_000
MAX_LIGHTS = 8
R_FLAG_MAX = 47.8
BEAM_WORDS = ("light_beam", "props_beam", "formation_beam")
OLD_SUBTREES = ("light_pillar", "core_feed", "motes", "floor_dark", "dome.ring", "ring_trigram", "ring_sigil",
                "ring_script", "ring_dais", "network", "balustrade.0", "balustrade.1")
OLD_PROTOS = (K + ".p.pillar", K + ".p.satellite")
RESKIN = ("plaza_edge", "dais_sides")
WALK_EXEMPT = (K + ".censer",)


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--once", action="store_true", help="skip the in-session second build")
    a, _rest = ap.parse_known_args(argv)
    return a


def need(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise RuntimeError("%s not found; is this a sect .blend with the formation?" % name)
    return ob


def tris_of(me):
    n = len(me.polygons)
    if not n:
        return 0
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def remove_objects(obs):
    obs = [o for o in obs if o is not None]
    datas = set()
    for o in obs:
        if o.data is not None:
            datas.add(o.data)
    n = 0
    for o in obs:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
        except ReferenceError:
            pass
    for d in datas:
        try:
            if d.users == 0:
                if isinstance(d, bpy.types.Mesh):
                    bpy.data.meshes.remove(d)
                elif isinstance(d, bpy.types.Light):
                    bpy.data.lights.remove(d)
        except ReferenceError:
            pass
    return n


def subtree(ob):
    return [ob] + list(ob.children_recursive)


def purge_tagged_data():
    n = 0
    for me in list(bpy.data.meshes):
        if me.get(AP.TAG) and me.users == 0:
            bpy.data.meshes.remove(me)
            n += 1
    for ld in list(bpy.data.lights):
        if ld.get(AP.TAG) and ld.users == 0:
            bpy.data.lights.remove(ld)
            n += 1
    return n


def remove_r6(coll):
    """Everything a previous round-6 build made (tagged objects and their meshes, the station prototype)."""
    obs = [o for o in bpy.data.objects if o.get(AP.TAG)]
    for o in obs:
        if o.users_collection and not any(c == coll or c.name.startswith(K) or c.name.startswith("_protos")
                                          for c in o.users_collection):
            raise RuntimeError("tagged object %s lives outside the formation: %s" % (o.name,
                                                                                      [c.name for c in o.users_collection]))
    n = remove_objects(obs)
    pc = bpy.data.collections.get(K + ".p.station")
    if pc is not None:
        n += remove_objects(list(pc.all_objects))
    return n, purge_tagged_data()


def remove_old(coll, root):
    """The pre-round-6 array (kept: the pillar instances, reparented to the root first)."""
    for k in range(8):
        p = need("%s.pillar.%d" % (K, k))
        if p.parent is not None and p.parent != root:
            U.parent(p, root, keep_transform=True)
    removed = []
    for nm in OLD_SUBTREES:
        ob = bpy.data.objects.get("%s.%s" % (K, nm))
        if ob is None:
            continue
        sub = [o for o in subtree(ob) if not o.name.startswith(K + ".pillar.")]
        removed += [o.name for o in sub]
        remove_objects(sub)
    core = need(K + ".core")
    kids = list(core.children_recursive)
    removed += [o.name for o in kids if not o.get(AP.TAG)]
    remove_objects([o for o in kids if not o.get(AP.TAG)])
    for cn in OLD_PROTOS:
        c = bpy.data.collections.get(cn)
        if c is not None:
            removed += [o.name for o in c.all_objects]
            remove_objects(list(c.all_objects))
            bpy.data.collections.remove(c)
            removed.append("collection " + cn)
    # leftovers of the old network that were not under formation.network (should be none)
    stray = [o for o in coll.all_objects if any(o.name.startswith("%s.%s" % (K, w)) for w in
                                                ("spoke", "sat_link", "cluster_link", "cross_link", "satellite",
                                                 "sat_pad", "pad.", "trace.", "flag.0", "flag.1", "flag.2", "flag.3",
                                                 "flag.4", "flag.5", "flag.6", "flag.7"))
             and not o.get(AP.TAG)]
    removed += [o.name for o in stray]
    remove_objects(stray)
    for me in list(bpy.data.meshes):
        if me.users == 0 and me.name.startswith(K + "."):
            bpy.data.meshes.remove(me)
    return removed


def reskin():
    done = []
    for nm in RESKIN:
        ob = need("%s.%s" % (K, nm))
        me = ob.data
        if me.users != 1:
            raise RuntimeError("%s's mesh %s has %d users; re-skinning it would change them all" % (ob.name, me.name,
                                                                                                    me.users))
        cur = [m.get(M.TAG) if m else None for m in me.materials]
        if cur != [AP.M_MARBLE]:
            U.set_materials(me, [AP.M_MARBLE])
            done.append((ob.name, cur))
    return done


def formation_objects(coll):
    return sorted(coll.all_objects, key=lambda o: o.name)


def evaluated_tris(coll):
    bpy.context.view_layer.update()
    return U.evaluated_triangle_count(coll)


def instanced_materials(ob, seen=None):
    out = set()
    if ob.type == 'MESH':
        out |= {s.material.name for s in ob.material_slots if s.material}
    if ob.instance_type == 'COLLECTION' and ob.instance_collection is not None:
        for o in ob.instance_collection.all_objects:
            out |= instanced_materials(o)
    return out


def walk_boxes():
    """(name, test(x, y, z)) regions that must stay free of new geometry (formation frame)."""
    def axis(x, y, z):
        return abs(x) <= 2.0 and 11.9 <= abs(y) <= 46.0 and 0.006 < z < 2.2

    def flights_ew(x, y, z):
        return 7.3 <= abs(x) <= 12.4 and abs(y) <= 1.7 and 0.006 < z < 3.6

    def flights_ns(x, y, z):
        return 7.3 <= abs(y) <= 12.4 and abs(x) <= 1.7 and 0.006 < z < 3.6

    def dais_cross(x, y, z):
        r = math.hypot(x, y)
        return (abs(x) <= 1.5 or abs(y) <= 1.5) and 2.5 <= r <= 8.4 and 1.51 < z < 3.6
    return [("axis walk", axis), ("E/W dais flights", flights_ew), ("N/S dais flights", flights_ns),
            ("dais top cross walks", dais_cross)]


def check_walk(coll, root):
    """Vertex box test of every tagged mesh (instances realised) against the walk boxes."""
    dg = bpy.context.evaluated_depsgraph_get()
    inv = root.matrix_world.inverted()
    tagged = {o.name for o in coll.all_objects if o.get(AP.TAG)}
    tagged |= {"%s.pillar.%d" % (K, k) for k in range(8)}
    tagged |= {o.name for o in need(K + ".core").children_recursive}
    exempt = set()
    for nm in WALK_EXEMPT:
        for o in coll.all_objects:
            if o.name == nm or o.name.startswith(nm + "."):
                exempt.add(o.name)
    bad = []
    boxes = walk_boxes()
    for di in dg.object_instances:
        o = di.object
        if o.type != 'MESH':
            continue
        owner = di.parent.original if di.is_instance and di.parent is not None else o.original
        oname = owner.name
        top = owner
        while top is not None and top.name not in tagged:
            top = top.parent
        if top is None or oname in exempt or (top.name in exempt):
            continue
        M_ = inv @ di.matrix_world
        me = o.data
        co = [0.0] * (3 * len(me.vertices))
        me.vertices.foreach_get("co", co)
        hits = {}
        for i in range(0, len(co), 3):
            p = M_ @ Vector((co[i], co[i + 1], co[i + 2]))
            for bn, test in boxes:
                if test(p.x, p.y, p.z):
                    hits.setdefault(bn, tuple(round(c, 2) for c in p))
        for bn, p in hits.items():
            bad.append((o.original.name, oname, bn, p))
    return bad


def flag_tips(root):
    dg = bpy.context.evaluated_depsgraph_get()
    inv = root.matrix_world.inverted()
    out = []
    for key, *_ in F.ELEMENT_FLAGS:
        cl = [o for o in bpy.data.objects if o.name.startswith("%s.flag.%s.cloth" % (K, key))]
        if not cl:
            raise RuntimeError("flag %s has no cloth" % key)
        for o in cl:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            M_ = inv @ o.matrix_world
            r = max(math.hypot(*(M_ @ v.co).xy) for v in me.vertices)
            ev.to_mesh_clear()
            out.append((o.name, r))
    return out


def build(coll, root):
    F._materials()
    for nm in F.R6_MATERIALS:
        if any(m.get(M.TAG) == nm for m in bpy.data.materials):
            M.rebuild(nm)
    dais = need(K + ".dais_top")
    top = max(v.co.z for v in dais.data.vertices)
    F._rim(coll, root)                                  # the balustrade, rebuilt in aged marble
    F.build_array(coll, root, top)
    bpy.context.view_layer.update()


def snapshot(coll):
    names = sorted(o.name for o in coll.all_objects)
    return names, evaluated_tris(coll)


def main():
    opt = options()
    sc = bpy.context.scene
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        raise SystemExit("PATCH no 'formation' collection in %s" % bpy.data.filepath)
    root = need(K + ".root")
    log("file", bpy.data.filepath, "objects", len(bpy.data.objects), "frame", sc.frame_current)
    t0 = evaluated_tris(coll)
    n0 = len(coll.all_objects)
    log("formation before: %d objects, %d evaluated triangles" % (n0, t0))

    F._materials()
    n_r6, n_data = remove_r6(coll)
    log("removed %d objects of a previous round-6 run (%d data blocks)" % (n_r6, n_data))
    removed = remove_old(coll, root)
    log("removed %d old objects/collections" % len(removed))
    for nm in removed[:400]:
        log("  old", nm)
    rs = reskin()
    log("re-skinned in aged marble:", rs or "nothing (already)")
    build(coll, root)
    names1, tris1 = snapshot(coll)
    log("built: %d objects, %d evaluated triangles" % (len(names1), tris1))

    fails = []
    if not opt.once:
        n_r6, n_data = remove_r6(coll)
        for nm in ("balustrade.0", "balustrade.1"):
            ob = bpy.data.objects.get("%s.%s" % (K, nm))
            if ob is not None:
                remove_objects(subtree(ob))
        build(coll, root)
        names2, tris2 = snapshot(coll)
        same = names1 == names2 and tris1 == tris2
        log("second build: removed %d, rebuilt %d objects, %d triangles: %s" % (n_r6, len(names2), tris2,
                                                                                "SAME" if same else "DIFFERENT"))
        if not same:
            a, b = set(names1), set(names2)
            fails.append("second build differs: -%s +%s tris %d vs %d" % (sorted(a - b)[:20], sorted(b - a)[:20],
                                                                          tris1, tris2))

    # ---- checks
    pc = bpy.data.collections.get(K + ".p.station")
    for k in range(8):
        p = bpy.data.objects.get("%s.pillar.%d" % (K, k))
        if p is None or p.instance_type != 'COLLECTION' or p.instance_collection != pc or p.parent != root:
            fails.append("formation.pillar.%d missing or not an instance of formation.p.station under the root" % k)
    core = bpy.data.objects.get(K + ".core")
    if core is None:
        fails.append("formation.core missing")
    else:
        exprs = [d.driver.expression for d in core.animation_data.drivers] if core.animation_data else []
        if abs(core.location.z - F.CORE_Z) > 1e-6 or exprs != ["frame*%s" % F.CORE_SPEED]:
            fails.append("formation.core at z %.3f with drivers %s" % (core.location.z, exprs))
        log("core", tuple(round(c, 3) for c in core.location), "drivers", exprs, "children",
            sorted(c.name for c in core.children))
    beams = []
    for o in coll.all_objects:
        for m in instanced_materials(o):
            if any(w in m for w in BEAM_WORDS):
                beams.append((o.name, m))
    if beams:
        fails.append("beam materials still in the formation: %s" % beams[:10])
    lights = [o for o in coll.all_objects if o.type == 'LIGHT']
    log("lights", len(lights), [(o.name, o.data.energy, o.data.use_shadow) for o in lights])
    if len(lights) > MAX_LIGHTS:
        fails.append("%d lights > %d" % (len(lights), MAX_LIGHTS))
    tris = evaluated_tris(coll)
    log("triangles: %d before -> %d after (target %d, cap %d)" % (t0, tris, TRI_TARGET, TRI_CAP))
    if tris > TRI_CAP:
        fails.append("%d triangles > %d" % (tris, TRI_CAP))
    # per-part triangle report
    parts = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for di in dg.object_instances:
        o = di.object
        if o.type != 'MESH':
            continue
        owner = di.parent.original if di.is_instance and di.parent is not None else o.original
        top = owner
        while top.parent is not None and top.parent.name != K + ".root":
            top = top.parent
        if not any(c == coll for c in top.users_collection) and top.name not in coll.all_objects:
            continue
        key = top.name.split(".")[1] if "." in top.name else top.name
        parts[key] = parts.get(key, 0) + tris_of(o.data)
    for key in sorted(parts, key=lambda k: -parts[k]):
        log("  tris %-22s %8d" % (key, parts[key]))
    bad = check_walk(coll, root)
    for b in bad[:30]:
        log("WALK BLOCKED", b)
    if bad:
        fails.append("%d pieces in the walk boxes" % len(bad))
    else:
        log("walk boxes clear:", ", ".join(n for n, _t in walk_boxes()))
    tips = flag_tips(root)
    for nm, r in tips:
        log("flag cloth", nm, "reaches R %.2f" % r)
        if r > R_FLAG_MAX:
            fails.append("%s reaches R %.2f > %.1f" % (nm, r, R_FLAG_MAX))

    if fails:
        for f in fails:
            log("FAIL", f)
        log("NOT SAVED: %d check(s) failed" % len(fails))
        if opt.no_save:                                 # a preview run in the same session may still look
            return
        raise SystemExit(1)
    new = sorted(o.name for o in coll.all_objects if o.get(AP.TAG) and (o.parent is None or not o.parent.get(AP.TAG)))
    log("CACHES NEED AUDIT (new formation objects): %d new top-level pieces (%s ...) - run export_web.py -- audit, "
        "then -- chunks,meta --profile full, then bake_web.py -- bakefull --profile full --chunks formation"
        % (len(new), ", ".join(new[:12])))
    log("objects in the formation:", n0, "->", len(coll.all_objects))
    if opt.no_save:
        log("--no-save: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
