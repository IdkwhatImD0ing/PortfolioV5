"""Make scenery.island.009 Ice-Fire Island 冰火島 (Heaven Sword and Dragon Saber) in a finished out/sect_chase.blend and
save the .blend: sect/lib/icefire_props.py through scenery.build_icefire() (the same code a fresh scenery.py build
runs, scenery.ICEFIRE_ISLAND). Run on a cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r7_icefire.py

What changes (all on the one island; nothing else is touched):
- removed: the island's plants and roots: its 87 crown pines, ledge-plant scatter and hanging roots (children of the
  rock), and the 8 top pines, 1 blossom and 2 life-pass peaches standing on it (top-level). Logged by name.
- the rock 'scenery.island.009' keeps its mesh, name and transform; its two material slots become M.icefire_rock
  (cone) and M.icefire_ground (top): glacier ice on one half, black basalt on the other, split in object space
- added, as children of the rock (identity local transforms, obj['sect_icefire'] = part):
    scenery.island.009.icefire_glacier      glacier cap with ice shards (M.icefire_ice)
    scenery.island.009.icefire_icicles      icicles under the cap's overhang (M.icefire_ice)
    scenery.island.009.icefire_stalactites  ice stalactites under the ice half (M.icefire_ice)
    scenery.island.009.icefire_volcano      volcanic cone (M.icefire_basalt), molten crater pool (M.molten); glow
    scenery.island.009.icefire_lava_flow    two lava streams on the top (M.molten); glow
    scenery.island.009.icefire_lava_veins   the glowing crack network on the basalt underside (M.molten); glow
    world.cloud.icefire_steam(.001-.018)    19 cloud-puff domains: the steam plume where lava meets ice
- kept: the island's waterfall (scenery.island.fall.003): it now pours from under the glacier's edge (meltwater)

Checks (any failure: no save, exit 1 with --python-exit-code 1): the rock's geometry and transform are unchanged, the
waterfall is unmoved, no plant is left on the island, every part exists, is closed (bake_web.fix_normals needs closed
pieces) with consistent normals, stays under icefire_props.TRI_CAP triangles (bake_web's island LOD floor keeps at most
ISLAND_FLOOR_HI) and touches its support shell by shell (BVH overlap with the rock / cap / cone, or within 0.3 m: no
hovering icicle, shard, slab or cone), the lava pieces carry obj['glow'], the steam puffs carry 'density'.

Idempotent: every run removes the previous run's parts (by their tag) and builds them again from the same seed; a re-run
finds no plants left and logs the same part digests (vertex count + coordinate sum), names and object count.

CACHES: the parts are new names. The script reads out/web/full/vis_cache.npz (when present) and prints
'PATCH CACHES ok' only when every part is already a cached record; otherwise 'PATCH CACHES audit-needed' with the
missing names: run the export audit (export_web.py -- audit, then chunks,meta --profile full), then bakefull the chunk
that holds the island (logged from chunks.npz) and the backdrop, bake_trees for that chunk (the island's pines are
gone), export_web.py -- clouds --profile full (the steam puffs; it re-runs mist.py) and sect_pack.py. The rock's new
materials alone need only the rebake of its chunk.
"""
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect.lib import icefire_props as IF  # noqa: E402

TOUCH = 0.3                  # m: a shell that does not cut its support must come at least this close to it
VIS_CACHE = os.path.join(ROOT, "out", "web", "full", "vis_cache.npz")
CHUNKS = os.path.join(ROOT, "out", "web", "full", "chunks.npz")
FALL = "scenery.island.fall.003"
SUPPORT = dict(glacier=("rock",), icicles=("rock", "glacier"), stalactites=("rock", "glacier"),
               volcano=("rock",), lava_flow=("rock", "volcano"), lava_veins=("rock",))


def log(*a):
    print("PATCH", *a, flush=True)


def fail(msg):
    log("FAIL", msg)
    raise RuntimeError("patch_r7_icefire: " + msg)


def mesh_arrays(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def digest(me):
    co = mesh_arrays(me)
    return "%d v, %d f, sum %.3f" % (len(me.vertices), len(me.polygons), float(np.round(co, 4).sum()) if len(co) else 0)


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def closed_and_out(me):
    """(boundary edges, faces recalc would flip): both 0 for a closed, consistently wound mesh."""
    bm = bmesh.new()
    bm.from_mesh(me)
    nb = sum(1 for e in bm.edges if e.is_boundary)
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    flips = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0.0)
    bm.free()
    return nb, flips


def shells(me):
    """Connected components: list of polygon index lists."""
    nv = len(me.vertices)
    parent = list(range(nv))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    groups = {}
    for p in me.polygons:
        groups.setdefault(find(p.vertices[0]), []).append(p.index)
    return list(groups.values())


def bvh_of(mes, polys_sel=None):
    vs, ps = [], []
    for me in mes:
        off = len(vs)
        vs.extend(tuple(v.co) for v in me.vertices)
        ps.extend([[i + off for i in p.vertices] for p in me.polygons])
    return BVHTree.FromPolygons(vs, ps)


def grounded(me, support, on_main=False):
    """Shells of `me` that neither cut their support (BVH overlap) nor come within TOUCH m of it. on_main: the mesh's
    largest shell (the glacier's cap) also supports its other shells (the shards standing on it)."""
    bad = []
    co = [tuple(v.co) for v in me.vertices]
    sh_all = sorted(shells(me), key=len, reverse=True)
    main_b = BVHTree.FromPolygons(co, [list(me.polygons[i].vertices) for i in sh_all[0]]) if on_main else None
    for k, sh in enumerate(sh_all):
        polys = [list(me.polygons[i].vertices) for i in sh]
        b = BVHTree.FromPolygons(co, polys)
        sups = [support] + ([main_b] if on_main and k > 0 else [])
        if any(b.overlap(s) for s in sups):
            continue
        vids = {i for p in polys for i in p}
        dmin = min(s.find_nearest(co[i])[3] for s in sups for i in vids)
        if dmin > TOUCH:
            bad.append((len(sh), round(dmin, 2), tuple(round(c, 1) for c in co[next(iter(vids))])))
    return bad


def cache_keys(path):
    if not os.path.isfile(path):
        return None
    z = np.load(path, allow_pickle=False)
    return set(z["key"].tolist())


def chunk_of(name):
    if not os.path.isfile(CHUNKS):
        return None
    z = np.load(CHUNKS, allow_pickle=False)
    keys = z["key"].tolist()
    if name not in keys:
        return None
    c = int(z["chunk"][keys.index(name)])
    return str(z["ids"][c]) if c >= 0 else "-"


def main():
    rock = bpy.data.objects.get(S.ICEFIRE_ISLAND)
    if rock is None or rock.type != 'MESH':
        fail("%s not found (or not a mesh); is this out/sect_chase.blend?" % S.ICEFIRE_ISLAND)
    log("blend", bpy.data.filepath, "island", rock.name, "world location",
        tuple(round(v, 2) for v in rock.matrix_world.translation))
    names0 = {o.name for o in bpy.data.objects}
    m0 = [list(r) for r in rock.matrix_world]
    d0 = digest(rock.data)
    fall = bpy.data.objects.get(FALL)
    f0 = [list(r) for r in fall.matrix_world] if fall else None
    prev = IF.our_objects(rock)
    log("before: objects", len(names0), "rock mesh", d0, "slots",
        [s.material.name if s.material else None for s in rock.material_slots], "earlier icefire objects", len(prev))

    out = S.build_icefire()
    bpy.context.view_layer.update()

    # ---- checks
    if [list(r) for r in rock.matrix_world] != m0:
        fail("the rock moved")
    if digest(rock.data) != d0:
        fail("the rock's mesh changed: %s -> %s" % (d0, digest(rock.data)))
    if fall is None:
        log("WARN", FALL, "not found (no waterfall to keep)")
    elif [list(r) for r in fall.matrix_world] != f0:
        fail("the waterfall moved")
    left = IF._plant_children(rock) + IF._plant_companions(rock)
    if left:
        fail("plants left on the island: %s" % [o.name for o in left])
    slots = [s.material.name if s.material else None for s in rock.material_slots]
    if slots != ["M.icefire_rock", "M.icefire_ground"]:
        fail("rock slots %s" % slots)
    parts = {k: v for k, v in out.items() if k != "steam"}
    if sorted(parts) != sorted(IF.PARTS):
        fail("parts %s, expected %s" % (sorted(parts), sorted(IF.PARTS)))
    total = 0
    for k in IF.PARTS:
        ob = parts[k]
        me = ob.data
        if ob.parent != rock or any(abs(v) > 1e-9 for v in ob.location) or ob.get(IF.TAG) != k:
            fail("%s: parent %s, location %s, tag %s" % (ob.name, ob.parent, tuple(ob.location), ob.get(IF.TAG)))
        t = tris(me)
        total += t
        if t > IF.TRI_CAP:
            fail("%s has %d triangles > %d" % (ob.name, t, IF.TRI_CAP))
        nb, flips = closed_and_out(me)
        if nb or flips:
            fail("%s: %d boundary edges, %d faces wound against their neighbours" % (ob.name, nb, flips))
        mats = [s.material.name if s.material else None for s in ob.material_slots]
        if not mats or None in mats or not all(m.startswith(("M.icefire_", "M.molten")) for m in mats):
            fail("%s materials %s" % (ob.name, mats))
        if "M.molten" in mats and not ob.get("glow"):
            fail("%s has molten faces but no obj['glow']" % ob.name)
        sup = bvh_of([rock.data if s == "rock" else parts[s].data for s in SUPPORT[k]])
        bad = grounded(me, sup, on_main=(k == "glacier"))
        if bad:
            fail("%s: %d shells hover off %s: %s" % (ob.name, len(bad), SUPPORT[k], bad[:6]))
        log("part", ob.name, "tris", t, "shells", len(shells(me)), "slots", mats, "glow", ob.get("glow"),
            "digest", digest(me))
    steam = out["steam"]
    want = IF.STEAM["puffs"] + IF.STEAM["wisps"]
    if len(steam) != want or not all(o.name.startswith(IF.STEAM_PREFIX) and o.get("density") for o in steam):
        fail("steam puffs %d (want %d) %s" % (len(steam), want, [o.name for o in steam]))
    log("steam", len(steam), "puffs", steam[0].name, "...", steam[-1].name, "world z",
        round(min(o.matrix_world.translation.z for o in steam), 1), "-",
        round(max(o.matrix_world.translation.z for o in steam), 1))
    names1 = {o.name for o in bpy.data.objects}
    removed = sorted(names0 - names1)
    added = sorted(names1 - names0)
    ours = sorted(o.name for o in IF.our_objects(rock))
    log("objects", len(names0), "->", len(names1), "removed", len(removed), "added", len(added),
        "icefire objects", len(ours), "triangles (parts)", total)
    if removed:
        log("removed names", removed)
    if added:
        log("added names", added)

    # ---- caches
    keys = cache_keys(VIS_CACHE)
    meshes = [parts[k].name for k in IF.PARTS]
    chunk = chunk_of(rock.name)
    if keys is None:
        log("CACHES audit-needed: no", VIS_CACHE, "here to check the", len(meshes), "new pieces against")
    else:
        miss = [n for n in meshes if n not in keys]
        if miss:
            log("CACHES audit-needed: %d new pieces not in vis_cache.npz %s - run the export audit (export_web.py -- "
                "audit, then chunks,meta --profile full), then bakefull the island's chunk (%s) and the backdrop, "
                "bake_trees for it (the island's pines are gone), export_web.py -- clouds --profile full (the %d steam "
                "puffs) and sect_pack.py" % (len(miss), miss, chunk, len(steam)))
        else:
            log("CACHES ok: every icefire piece is a cached record; rebake the island's chunk (%s) for its new "
                "materials, bake_trees for it, export_web.py -- clouds for the steam" % chunk)
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
