"""Round 48, P-2 .. P-5 and the abode PART: wall plants out, shelf plants in, a broadleaf canopy, hero pines, the far
canopy mass, the rock material, the abode cliff, in an existing out/sect_chase.blend; the same as scenery.build_r48,
areas/abode.py (ABODE_R48) and lib/materials.py now make on a fresh build. Run on the cloud box, on a COPY first,
AFTER patch_r48_range.py (the pillars must exist for 'shelves' and 'hero'):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_green.py -- \
        PARTS=walls,canopy,shelves,hero,forest SCOPE=b0 FOREST=hull [DRY_RUN=1]

PARTS (default walls,canopy,rim,shelves,hero,forest,rock,abode):
  walls       P-2: the old range scatters' masks (scenery.forest, .cliffpines, .cliffpines.dense, .walls, .crowns,
              world.range.forest) zeroed outside the keep zones (60 m of a hold camera, in frame): their trees there
              stay exactly; the life.ledge trees elsewhere hidden. walls_undo puts both back.
  canopy      P-3: masks r48_* on world.range (exclusion: areas, links, shrines, bridge, keep zones, sight cones,
              思過崖, corridor) and the range-only scatters scenery.r48.broadleaf / .spire / .pine / .scrub / .accent
              (group nature.rscatter.random; the shared nature.scatter.* groups are not touched).
  rim         phase C (slice critic F7): the area cakes' lip shrubs and small crowns (clear of the terraces' built
              things) and small crowns on their 49 deg aprons (scenery.r48.rim_lip / .rim_crown / .apron_crown);
              the apron's dense scrub comes with the canopy masks. Tagged 'rim'; PARTS without it leaves them out.
  shelves     P-2 on the pillars: cap canopy + rim spires, shelf shrubs, crack ferns (scatters under each pillar).
  hero        rule 7: hero pines on the rims of the pillars each hold shows (holds_intent hero_pines).
  forest      P-4 by FOREST (scenery.FOREST_MODE): cards | shell150 | shell250 | hull. Shell / hull objects
              world.canopy_shell / world.canopy_hull per 320 m tile, material nature_canopy_mass.
  rock        P-5: every _rock material rebuilt from lib/materials.py's round-48 constants.
  abode       the abode cliff variant (owner opt-in, applied by the main session): the face pines hidden, the
              round-48 dressing built (areas/abode.r48_dress). abode_undo takes it back.
SCOPE b0 | slice | all (default all): the canopy masks and the walls step stay inside it; shelves and hero only on
the pillars inside it.
Overrides: KEY=value for an upper-case constant of sect/scenery.py, lib/nature.py, sect/world.py or lib/materials.py
(CANOPY_DENSITY=0.03, CANOPY_NEAR_K=0.25, ROCK_SCAN_HUE=0.8 ...), FOREST=..., PARTS=..., DRY_RUN=1. A materials
override only lasts for that run's PARTS=rock rebuild; put the value in lib/materials.py to keep it.

Checks (any failure stops before saving): the shared scatter groups are version 3 (else nothing is touched); no
existing tree prototype is rebuilt (new ones, broadleaf / masson / scrub, are allowed); the keep zones keep every
old instance (counted before and after inside them); the near band (instances within 70 m of the camera path, the
bake's 3D trees) stays under NEAR_MAX. Prints counts per scatter, a near-tree estimate, 'PATCH CACHES needs audit',
'PATCH DIGEST <md5>' and writes out/tmp/r48/green_<SCOPE>.json. Idempotent (every part removes what it made first).
"""
import collections
import hashlib
import json
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect import world as W  # noqa: E402
from sect.areas import abode as AB  # noqa: E402
from sect.lib import compose as C  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import nature as N  # noqa: E402
from sect.lib import r48 as R  # noqa: E402

PARTS = ("walls", "canopy", "rim", "shelves", "hero", "forest", "rock", "abode", "abode_undo", "walls_undo")
DEFAULT_PARTS = ("walls", "canopy", "rim", "shelves", "hero", "forest", "rock", "abode")
NEAR_D = 70.0                  # bake_trees --tree-near
NEAR_MAX = 4000                # stop when more round-48 trees than this stand within NEAR_D of the path


def check_scatter_group():
    for ng in bpy.data.node_groups:
        if ng.name.startswith("nature.scatter.") and ng.get("nature_scatter") != N._SCATTER_VERSION:
            raise SystemExit("patch_r48_green: node group %s is version %r, nature.py builds %r; not patching"
                             % (ng.name, ng.get("nature_scatter"), N._SCATTER_VERSION))


def proto_ids():
    return {c.name: tuple(sorted(o.session_uid for o in c.all_objects))
            for c in bpy.data.collections if c.name.startswith("nature.proto.")}


def instances(names=None, prefix=None):
    """scatter -> [world xyz] of its instances (depsgraph)."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    out = collections.defaultdict(list)
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        par = inst.parent.original.name
        if (names is not None and par in names) or (prefix is not None and par.startswith(prefix)):
            out[par].append(tuple(inst.matrix_world.translation))
    return out


def keep_counts(hv):
    """Instances of every scatter inside the keep zones (they must not change)."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    pts = collections.defaultdict(list)
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.modifiers.get("NatureScatter"):
            pts[inst.parent.original.name].append(np.round(np.array(inst.matrix_world, dtype=np.float64), 3).tobytes())
    out = {}
    for k, v in pts.items():
        if k.startswith("scenery.r48") or ".r48_" in k or k.startswith("world.peak"):
            continue
        out[k] = v
    # only the instances inside the zones: positions from the matrices
    res = {}
    for k, mats in out.items():
        P = np.array([np.frombuffer(m, np.float64).reshape(4, 4)[:3, 3] for m in mats]) if mats else np.zeros((0, 3))
        if not len(P):
            continue
        m = R.keep_zone_mask(P, hv)
        if m.any():
            res[k] = hashlib.md5(b"".join(sorted(mats[i] for i in np.nonzero(m)[0]))).hexdigest()
    return res


def part_rock():
    from sect import world  # noqa: F401  (registers world_rock_under, world_pier_stone)
    tags = sorted({m.get(M.TAG) for m in bpy.data.materials if m.get(M.TAG) and m.library is None}
                  & {t for t, (b, _p) in M._REGISTRY.items() if b is M._rock})
    for name in tags:
        builder, params = M._REGISTRY[name]
        M.register(name, builder, overwrite=True, **params)
    R.log("rock materials rebuilt:", tags)
    return tags


def part_abode(undo=False):
    root = bpy.data.objects.get(AB.K + ".root")
    coll = bpy.data.collections.get(AB.K)
    if root is None or coll is None:
        R.log("WARN abode.root or collection abode missing; abode part skipped")
        return None
    gone = R.remove_objects([o for o in bpy.data.objects if o.get(S.R48_TAG) == "abode"])
    if undo:
        return dict(removed=gone, shown=S.r48_unhide("abode"))
    hid = S.r48_hide(AB.r48_old_face_pines(), "abode")
    made = AB.r48_dress(coll, root)
    return dict(removed_earlier=gone, hidden=hid, made=len(made), names=sorted({o.name.split(".")[1] for o in made}))


def main():
    t0 = time.time()
    opt = R.options(PARTS, dict(forest=""), modules=(S, N, W, M))
    if not any(a.startswith("PARTS=") for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])):
        opt["parts"] = DEFAULT_PARTS
    if opt["forest"]:
        if opt["forest"] not in ("cards", "shell150", "shell250", "hull"):
            raise SystemExit("patch_r48_green: FOREST must be cards, shell150, shell250 or hull")
        S.FOREST_MODE = opt["forest"]
    parts = opt["parts"]
    fail = R.Fail()
    rng_obj = bpy.data.objects.get("world.range")
    if rng_obj is None or bpy.data.objects.get(R.CAMERA) is None:
        R.log("NOT SAVED: no world.range or chase.cam: is this out/sect_chase.blend?")
        raise SystemExit(1)
    check_scatter_group()
    protos0 = proto_ids()
    intent = C.load_intent()
    an = R.anchors()
    hv = R.views(intent, flights=False)
    star = R.star_boxes(hv, an)
    discs = R.scope(opt["scope"])
    scene = bpy.context.scene
    coll = S.r48_collection(scene)
    R.log("parts", ",".join(parts), "scope", opt["scope"], "forest", S.FOREST_MODE, "pillars", len(S._pillars(discs)))
    keep0 = keep_counts(hv)
    res = {}
    if "walls_undo" in parts:
        res["walls_undo"] = S.r48_walls_undo(rng_obj)
    if "walls" in parts:
        res["walls"] = S.r48_walls_out(rng_obj, hv, discs)
    masks = None
    if "canopy" in parts or "forest" in parts or "rim" in parts:
        masks = S.r48_canopy_masks(rng_obj, scene, an, hv, star, discs)
        res["mask_m2"] = masks["area_m2"]
    if "canopy" in parts:
        S.r48_remove(("canopy",))
        res["canopy"] = S.r48_range_canopy(rng_obj, coll)
    if "rim" in parts:
        S.r48_remove(("rim",))
        res["rim"] = S.r48_rim_plants(rng_obj, coll)
    if "shelves" in parts:
        S.r48_remove(("shelves",))
        res["shelves"] = S.r48_pillar_plants(coll, discs)
    if "hero" in parts:
        S.r48_remove(("hero",))
        res["hero"] = S.r48_hero_pines(coll, hv, intent, discs, log=R.log)
    if "forest" in parts:
        S.r48_remove(("forest",))
        wc = rng_obj.users_collection[0]
        sh = S.r48_shell(rng_obj, wc, masks)
        hu = S.r48_hulls(rng_obj, wc, masks)
        res["forest"] = dict(mode=S.FOREST_MODE, shell_objects=len(sh), hull_objects=len(hu),
                             shell_tris=sum(2 * len(o.data.polygons) for o in sh),
                             hull_tris=sum(len(p.vertices) - 2 for o in hu for p in o.data.polygons))
    if "rock" in parts:
        res["rock"] = part_rock()
    if "abode_undo" in parts:
        res["abode_undo"] = part_abode(undo=True)
    if "abode" in parts:
        res["abode"] = part_abode()
    # checks
    after = proto_ids()
    rebuilt = sorted(k for k in protos0 if after.get(k) != protos0[k])
    if rebuilt:
        fail.add("existing tree prototypes rebuilt: %s" % rebuilt[:8])
    R.log("new prototypes:", sorted(k for k in after if k not in protos0))
    keep1 = keep_counts(hv)
    moved = sorted(k for k in set(keep0) | set(keep1) if keep0.get(k) != keep1.get(k))
    allow = ("abode.",) if ("abode" in parts or "abode_undo" in parts) else ()
    bad = [k for k in moved if not k.startswith(allow)] if allow else moved
    if bad:
        fail.add("instances inside the keep zones changed on %s" % bad[:8])
    shelf_names = {c.name for o in S._pillars(discs) for c in o.children if c.get(S.R48_TAG) == "shelves"}
    ins = instances(prefix="scenery.r48")
    ins.update(instances(names=shelf_names))
    path = R.path_points(2)
    from mathutils import kdtree
    kd = kdtree.KDTree(len(path))
    for i, p in enumerate(path):
        kd.insert(tuple(p), i)
    kd.balance()
    counts, near = {}, collections.Counter()
    for k, pts in ins.items():
        counts[k] = len(pts)
        for p in pts:
            if kd.find(p)[2] < NEAR_D:
                near[k.split(".")[0] if not k.startswith("scenery.r48") else k] += 1
    n_near = sum(near.values())
    R.log("round-48 instances:", json.dumps(dict(sorted((k, v) for k, v in counts.items() if v)), default=str))
    R.log("within %d m of the camera path (3D in the bake): %d %s" % (NEAR_D, n_near, dict(near)))
    if n_near > NEAR_MAX:
        fail.add("%d round-48 trees within %d m of the path (> %d): lower CANOPY_NEAR_K" % (n_near, NEAR_D, NEAR_MAX))
    res["instances"] = counts
    res["near"] = dict(near)
    # digest: the masks, the round-48 objects and their instance counts
    h = hashlib.md5()
    for a in sorted(at.name for at in rng_obj.data.attributes if at.name.startswith(("r48_", "scenery_", "world_veg"))):
        v = R.face_attr(rng_obj, a)
        if v is not None:
            h.update(a.encode())
            h.update(np.round(v, 4).tobytes())
    for o in sorted((o for o in bpy.data.objects if o.get(S.R48_TAG) or o.get(S.R48_HIDDEN)), key=lambda o: o.name):
        h.update(("%s|%s|%s|%s" % (o.name, o.get(S.R48_TAG), o.get(S.R48_HIDDEN), R.matrix_key(o, 3))).encode())
    h.update(json.dumps(sorted(counts.items())).encode())
    res["seconds"] = round(time.time() - t0, 1)
    R.report("green_%s.json" % opt["scope"], res)
    R.log("CACHES needs audit: new plants, shells, hulls, materials and hidden objects - run export_web audit "
          "--profile full, chunks,meta, bake_web bakefull (the chunks that see them and the backdrop), bake_trees "
          "plan,build")
    R.save_or_dry(opt["dry"], fail, h.hexdigest())
    R.log("done in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
