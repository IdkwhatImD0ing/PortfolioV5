"""Bring out/sect_chase.blend to the round-5 sun-and-moon design (the Ming Sect: 明 = 日 sun + 月 moon) and save.
Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r5_sunmoon.py

1. Banner roundels, in place. Every sect banner cloth that carries the older crescent roundel (a shared mesh
   'props.banner_cloth.<style>.<W>.<L>.<seed>.<wind>.00000000.moon.v4': the arena ring, the gate plaza and stair
   landings, the forge approach and the mission plaza) gets the sun-and-moon roundel of props._sunmoon_flat, exactly
   as a fresh build with banner(emblem='sunmoon') makes it. Each old mesh's exact cloth length is recovered first
   (the key rounds it to 3 digits): a fresh 'moon' build must reproduce the file's mesh to 0.1 mm, or the script
   stops without saving. Same objects, names, parents, transforms and Wave modifiers; the cloth objects get the
   new shared mesh, their 'flutter' weights again, their four object-linked slots back and two more (4 moon, 5 sun:
   moon-white silk and gold thread on dark cloth, ink and vermilion on the gold / moon-white cloths). Banners with
   text (the formation flags) and plain ones are left alone.
2. Gate emblem, added (gate._sun_moon, from the paifang and plaque in the file): the gilt ridge finial
   'gate.sunmoon_finial' (.gold, .moon) on the top roof's main ridge, and the lacquered medallions
   'gate.sun_medallion' (.disc, .gold) and 'gate.moon_medallion' (.disc, .gold, .moon) on the plaque zone either
   side of the 明教 plaque = 3 Empties + 7 meshes in the 'gate' collection. Before building, ray casts check that
   the layout's ridge top and board face agree with the file's geometry (1 cm).

Caches. Banner cloths keep their names; every one's world box (base mesh, and evaluated at the current frame) is
compared with its old box: 'PATCH CACHES ok (banners)' or 'PATCH CACHES GREW'. The gate pieces are NEW names, so the
web caches do not know them yet: run export_web.py audit + chunks,meta (or the proposed cache_add.py) before
bakefull, or the bake drops them ('WARN cache misses'). The script prints 'PATCH CACHES NEED AUDIT (new gate
objects)' for that.

Idempotent: banners already on 'sunmoon' meshes are skipped (a re-run finds no crescent meshes left), and the gate
pieces from a previous run are removed and rebuilt, so names and counts come out the same.
"""
import os
import sys
import zlib

import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import gate as G  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import util as U  # noqa: E402

NO_TEXT = "%08x" % (zlib.crc32(b"") & 0xFFFFFFFF)
MATCH_TOL = 1e-4          # m: a fresh 'moon' build must reproduce the file's cloth this closely
BOX_TOL = 2e-3            # m: world-box growth that counts
GATE_COLL = "gate"
GATE_NAMES = tuple(G.K + "." + n for n in (G.FINIAL_NAME, G.SUN_NAME, G.MOON_NAME))
GATE_TRI_BUDGET = 6000    # all three gate pieces together


def log(*a):
    print("PATCH", *a, flush=True)


def unk(s):
    return float(s.replace("p", ".").replace("m", "-"))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def world_box(ob, evaluated=True):
    M = ob.matrix_world
    if evaluated:
        pts = [M @ Vector(c) for c in ob.bound_box]
    else:
        pts = [M @ v.co for v in ob.data.vertices]
    return (tuple(min(p[k] for p in pts) for k in range(3)), tuple(max(p[k] for p in pts) for k in range(3)))


def grew(a, b, tol=BOX_TOL):
    return any(y < x - tol for x, y in zip(a[0], b[0])) or any(y > x + tol for x, y in zip(a[1], b[1]))


def closed_and_out(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    nb = sum(1 for e in bm.edges if e.is_boundary)
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    flips = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0.0)
    bm.free()
    return nb, flips


# ---------------------------------------------------------------- 1. banners

def parse_key(me):
    key = me.get("sect_shared") or me.name
    p = key.split(".")
    if len(p) != 10 or p[0] != "props" or p[1] != "banner_cloth":
        return None
    return dict(key=key, style=p[2], W=unk(p[3]), Lk=unk(p[4]), seed=int(p[5]), wind=unk(p[6]), tkey=p[7],
                emblem=p[8])


def cloth_length(style, H, W):
    """banner()'s default cloth length for pole height H (every sect banner uses the default)."""
    za = H - 0.35
    if style == "qi":
        return max(0.3, min(0.8 * W, H - 1.2))
    L = max(0.8, min(H * 0.6, za - 0.06 - 0.4))
    return max(0.5 * W + 0.3, L)


def mesh_err(a, b, n=None):
    """Largest coordinate difference (m) between meshes a and b over their first n vertices (all: the counts must
    match)."""
    if n is None:
        if len(a.vertices) != len(b.vertices):
            return float("inf")
        n = len(a.vertices)
    if len(a.vertices) < n or len(b.vertices) < n:
        return float("inf")
    ca = [c for v in a.vertices[:n] for c in v.co]
    cb = [c for v in b.vertices[:n] for c in v.co]
    return max(abs(x - y) for x, y in zip(ca, cb)) if ca else 0.0


def fit_length(me, k, users):
    """The exact cloth length that built ``me``: candidates from each user's pole height (cloth object z), then a
    golden-section search round the key's rounded value. Returns (L, error)."""
    cands = {round(k["Lk"], 6)}
    for ob in users:
        H = ob.location.z + (0.32 if k["style"] == "qi" else 0.06 + 0.35)
        cands.add(cloth_length(k["style"], H, k["W"]))
    best = (None, float("inf"))

    def err(L):
        t = P._banner_cloth_mesh(k["W"], L, k["seed"], k["wind"], k["style"], None, "moon", fresh=True)
        e = mesh_err(me, t)
        bpy.data.meshes.remove(t)
        return e
    for L in sorted(cands):
        e = err(L)
        if e < best[1]:
            best = (L, e)
    if best[1] <= MATCH_TOL:
        return best
    lo, hi = k["Lk"] * (1 - 1e-3), k["Lk"] * (1 + 1e-3)
    g = 0.6180339887
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = err(a), err(b)
    for _ in range(40):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = err(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = err(b)
    L = 0.5 * (lo + hi)
    e = err(L)
    return (L, e) if e < best[1] else best


def patch_banners():
    users = {}
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.data is not None:
            k = parse_key(ob.data)
            if k is not None:
                users.setdefault(ob.data.name, []).append(ob)
    todo, done, other = [], 0, 0
    for mname, obs in sorted(users.items()):
        me = bpy.data.meshes[mname]
        k = parse_key(me)
        if k["emblem"] == "sunmoon":
            done += len(obs)
        elif k["emblem"] == "moon" and k["tkey"] == NO_TEXT:
            todo.append((me, k, obs))
        else:
            other += len(obs)
    log("banner cloths: %d to convert (%d meshes), %d already sun-and-moon, %d with text / plain left alone"
        % (sum(len(o) for _m, _k, o in todo), len(todo), done, other))
    changed, boxes = [], {}
    for me, k, obs in todo:
        L, e = fit_length(me, k, obs)
        if L is None or e > MATCH_TOL:
            raise RuntimeError("%s: no cloth length reproduces it (best L %s, error %.2e m)" % (me.name, L, e))
        bare = P._banner_cloth_mesh(k["W"], L, k["seed"], k["wind"], k["style"], None, None, fresh=True)
        n_cloth = len(bare.vertices)
        bpy.data.meshes.remove(bare)
        new = P._banner_cloth_mesh(k["W"], L, k["seed"], k["wind"], k["style"], None, "sunmoon")
        e2 = mesh_err(me, new, n_cloth)
        if e2 > MATCH_TOL:
            raise RuntimeError("%s: the new cloth's body differs from the old by %.2e m" % (me.name, e2))
        idx = [p.material_index for p in new.polygons]
        log("mesh", me.name, "-> L %.5f (fit error %.1e m)" % (L, e), "->", new.name, "verts", len(new.vertices),
            "tris", tris(new), "(was %d)" % tris(me), "emblem faces moon %d sun %d ring %d" %
            (idx.count(P.SM_MATS["moon"]), idx.count(P.SM_MATS["sun"]), idx.count(P.SM_MATS["ring"])))
        for ob in obs:
            boxes[ob.name] = (world_box(ob, False), world_box(ob, True))
            mats = [s.material for s in ob.material_slots][:4]
            links = [s.link for s in ob.material_slots][:4]
            if len(mats) != 4 or any(m is None for m in mats) or any(l_ != 'OBJECT' for l_ in links):
                raise RuntimeError("%s: expected 4 object-linked slots, found %s %s" % (ob.name, mats, links))
            ob.data = new
            for i, m in enumerate(mats):
                U.set_object_material(ob, m, i)
            moon_m, sun_m = P.sunmoon_materials(mats[0])
            U.set_object_material(ob, moon_m, P.SM_MATS["moon"])
            U.set_object_material(ob, sun_m, P.SM_MATS["sun"])
            if ob.vertex_groups.get("flutter") is None:
                vg = ob.vertex_groups.new(name="flutter")
                for i, w in enumerate(new.get("props_weights", [])):
                    if w > 0:
                        vg.add([i], float(w), 'REPLACE')
            wv = ob.modifiers.get("props_wind")
            if wv is None or wv.vertex_group != "flutter":
                raise RuntimeError("%s lost its props_wind modifier / flutter group" % ob.name)
            changed.append(ob)
            log("  ", ob.name, "slots", [s.material.name if s.material else None for s in ob.material_slots])
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return changed, boxes


# ---------------------------------------------------------------- 2. gate

def ours(name):
    return any(name == n or name.startswith(n + ".") for n in GATE_NAMES)


def remove_previous_gate():
    obs = [o for o in bpy.data.objects if ours(o.name)]
    datas = [o.data for o in obs if o.data is not None]
    if obs:
        log("removing the previous run's", len(obs), "gate objects:", sorted(o.name for o in obs))
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    for d in datas:
        if d.users == 0:
            bpy.data.meshes.remove(d)
    for d in list(bpy.data.meshes):
        if ours(d.name) and d.users == 0:
            bpy.data.meshes.remove(d)
    return len(obs)


def ray(o, d):
    sc = bpy.context.scene
    hit, loc, _n, _i, ob, _m = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector(o), Vector(d))
    return (ob.name, loc) if hit else (None, None)


def patch_gate():
    coll = bpy.data.collections.get(GATE_COLL)
    paifang = bpy.data.objects.get(G.K + ".paifang")
    plaque = bpy.data.objects.get(G.K + ".plaque")
    if coll is None or paifang is None or plaque is None:
        raise RuntimeError("gate collection / gate.paifang / gate.plaque not found; is this out/sect_chase.blend?")
    anchor = bpy.data.objects[paifang["plaque_anchor"]]
    removed = remove_previous_gate()
    bpy.context.view_layer.update()
    n0 = len(bpy.data.objects)
    lay = G.sun_moon_layout(paifang, anchor, plaque)
    # the layout against the file's geometry
    R, par, loc = lay["finial"]
    base = par.matrix_world @ Vector(loc)
    nm, hit = ray((base.x, base.y, base.z + 20.0), (0, 0, -1))
    log("finial base", tuple(round(c, 3) for c in base), "ridge ray hits", nm, tuple(round(c, 3) for c in hit) if hit else None)
    if hit is None or not nm.endswith(".ridges") or abs(hit.z - base.z) > 0.01:
        raise RuntimeError("the finial's base is not on the ridge top (%s %s)" % (nm, hit))
    for part, rm, par, loc, nmm in lay["medallions"]:
        c = par.matrix_world @ Vector(loc)
        nm, hit = ray((c.x, c.y - 30.0, c.z), (0, 1, 0))
        log("medallion", part, "radius %.3f" % rm, "centre", tuple(round(v, 3) for v in c), "board ray hits", nm,
            tuple(round(v, 3) for v in hit) if hit else None)
        if hit is None or abs(hit.y - c.y) > 0.01:
            raise RuntimeError("the %s medallion is not on the plaque zone board (%s %s)" % (part, nm, hit))
        # its whole disc must sit on the board: rim points
        for dx, dz in ((rm, 0), (-rm, 0), (0, rm), (0, -rm)):
            nm2, h2 = ray((c.x + dx * 0.98, c.y - 30.0, c.z + dz * 0.98), (0, 1, 0))
            if h2 is None or abs(h2.y - c.y) > 0.01:
                raise RuntimeError("the %s medallion's rim overhangs the board at (%.2f, %.2f): %s %s"
                                   % (part, dx, dz, nm2, h2))
    G._sun_moon(coll, paifang, anchor, plaque)
    bpy.context.view_layer.update()
    new = sorted((o for o in bpy.data.objects if ours(o.name)), key=lambda o: o.name)
    added = len(bpy.data.objects) - n0
    if added != 10 or len(new) != 10:
        raise RuntimeError("expected 10 new gate objects, got %d (%d named)" % (added, len(new)))
    total = 0
    for o in new:
        if [c.name for c in o.users_collection] != [GATE_COLL]:
            raise RuntimeError("%s is in %s" % (o.name, [c.name for c in o.users_collection]))
        if o.type == 'MESH':
            t = tris(o.data)
            total += t
            nb, flips = closed_and_out(o.data)
            if nb or flips:
                raise RuntimeError("%s is not closed / outward: %d boundary edges, %d faces flip" % (o.name, nb, flips))
            b = world_box(o)
            log("added", o.name, "tris", t, "slots", [s.material.name if s.material else None for s in o.material_slots],
                "box", tuple(round(v, 3) for v in b[0]), tuple(round(v, 3) for v in b[1]), "parent", o.parent.name)
        else:
            log("added", o.name, o.type, "world", tuple(round(c, 3) for c in o.matrix_world.translation),
                "parent", o.parent.name)
    if total > GATE_TRI_BUDGET:
        raise RuntimeError("gate emblem pieces have %d triangles > %d" % (total, GATE_TRI_BUDGET))
    log("gate emblem: %d objects (%d meshes), %d triangles (budget %d); removed %d from a previous run"
        % (len(new), sum(o.type == 'MESH' for o in new), total, GATE_TRI_BUDGET, removed))
    return new


def main():
    n_before = len(bpy.data.objects)
    sc = bpy.context.scene
    log("file", bpy.data.filepath, "objects", n_before, "frame", sc.frame_current)
    changed, boxes = patch_banners()
    bpy.context.view_layer.update()
    gate_new = patch_gate()
    bpy.context.view_layer.update()
    grown = []
    for ob in changed:
        (a0, a1) = boxes[ob.name]
        b0, b1 = world_box(ob, False), world_box(ob, True)
        if grew(a0, b0) or grew(a1, b1):
            grown.append((ob.name, a0, b0, a1, b1))
    log("banner cloths converted:", len(changed))
    if grown:
        for g in grown:
            log("GREW", g)
        log("CACHES GREW: %d banner boxes got bigger - run export_web.py -- chunks,meta --profile full before the bake"
            % len(grown))
    else:
        log("CACHES ok (banners): %d cloth objects, names unchanged, every world box the same or smaller" % len(changed))
    if gate_new:
        log("CACHES NEED AUDIT (new gate objects): %s - run export_web.py audit + chunks,meta (or cache_add) "
            "before bakefull" % ", ".join(o.name for o in gate_new if o.parent is None or not ours(o.parent.name)))
    log("objects", n_before, "->", len(bpy.data.objects))
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
