"""Round 48, phase D: the range critic's must-fixes that live outside the green patch, on an existing
out/sect_chase.blend; the same as the builders now make on a fresh build (life.build_islands skips culled rocks,
world.terrain_data sinks the range's chips, world.build_backdrop leaves BACKDROP_R48_CUT out). Run on the cloud box,
on a COPY first, AFTER patch_r48_isles.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_fixes.py -- [PARTS=blossoms,chips,backdrop,falls]
        [DRY_RUN=1]

PARTS (default all four):
  blossoms  M1: scenery._hide_culled_companions, which now takes the life pass's island blossoms and azaleas
            (life.island.*) with a culled rock, and any with no visible island under them. Hidden as 'isles'
            (patch_r48_isles PARTS=isles_undo shows them again with the rocks). The chain bridge stays.
  chips     M2: world.range's loose parts under world.RANGE_CHIP_FACES faces (slabs a few m across floating in the
            air: the 'crown over the cloud sea' at f1300 was one) go down whole under the cloud sea
            (scenery.r48_sink_range_chips). Vertices move; faces and their order stay.
  backdrop  M5: the round-48 horizon pillars of world.BACKDROP_R48_CUT (family1: from the summit its two front pillars
            read as stumps in the quiet sea) are removed, as r48_horizon now builds the horizon without them.
  falls     found in phase D's water bake: phase C's 34 rebuilt falls (and their 131 spray puffs) all stood in one
            pile at the world origin, under the gate, because the old fall roots sit there (their sheets carry the
            position). They are removed (scenery.R48_FALL_REBUILD is off: no range or island fall ships; the old ones
            stay hidden, Ice-Fire's stays), and scenery.r48_streams then hides the streams whose fall is gone.
The abode (M4) and the pillar shelves (M3, and M5's 思過崖 pads) are patch_r48_green.py PARTS=shelves,abode.
Checks: the chain bridges (life.span*) and Ice-Fire Island visible; no visible life.island plant without a visible
island under it. Prints counts, 'PATCH DIGEST <md5>', writes out/tmp/r48/fixes.json. Idempotent (a second run hides,
moves and removes nothing).
"""
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
from sect.lib import r48 as R  # noqa: E402

PARTS = ("blossoms", "chips", "backdrop", "falls")


def orphan_island_plants():
    """Visible life.island.* objects with no visible island or islet within max(15 m, 0.8 x its size) in plan."""
    _rk, recs = S.r48_isle_records()
    c = np.array([r["c"] for r in recs], float).reshape(-1, 3)
    sz = np.array([r["size"] for r in recs], float)
    out = []
    for o in bpy.data.objects:
        if o.parent is not None or o.hide_render or not o.name.startswith(S.LIFE_ISLAND):
            continue
        p = np.array(o.matrix_world.translation)
        if not len(c) or not (np.hypot(c[:, 0] - p[0], c[:, 1] - p[1]) < np.maximum(15.0, 0.8 * sz)).any():
            out.append(o.name)
    return out


def main():
    t0 = time.time()
    opt = R.options(PARTS, {}, modules=(S, W))
    parts = opt["parts"]
    fail = R.Fail()
    rng_obj = bpy.data.objects.get("world.range")
    if rng_obj is None or bpy.data.objects.get(R.CAMERA) is None:
        R.log("NOT SAVED: no world.range or chase.cam: is this out/sect_chase.blend?")
        raise SystemExit(1)
    res = {}
    if "blossoms" in parts:
        vis0 = sum(1 for o in bpy.data.objects if o.name.startswith(S.LIFE_ISLAND) and not o.hide_render)
        hid = S._hide_culled_companions()
        vis1 = sum(1 for o in bpy.data.objects if o.name.startswith(S.LIFE_ISLAND) and not o.hide_render)
        res["blossoms"] = dict(hidden=hid, island_plants_visible_before=vis0, after=vis1)
        R.log("island blossoms and azaleas: %d visible before, %d after (%d objects hidden)" % (vis0, vis1, hid))
    if "chips" in parts:
        if not np.allclose(np.array(rng_obj.matrix_world), np.eye(4), atol=1e-6):
            fail.add("world.range has a transform")
        else:
            res["chips"] = S.r48_sink_range_chips(rng_obj)
            R.log("range chips", json.dumps(res["chips"]))
    if "backdrop" in parts:
        cut = [o for o in bpy.data.objects if o.get(S.R48_TAG) == "horizon" and
               o.get("r48_backdrop") in W.BACKDROP_R48_CUT]
        names = sorted(o.name for o in cut)
        res["backdrop"] = dict(removed=R.remove_objects(cut + [c for o in cut for c in o.children_recursive]),
                               names=names)
        R.log("horizon pillars removed (BACKDROP_R48_CUT %s): %s" % (list(W.BACKDROP_R48_CUT), names))
    if "falls" in parts:
        made = [o for o in bpy.data.objects if o.get(S.R48_TAG) == "falls"]
        n_root = sum(1 for o in made if o.type == 'EMPTY' and o.parent is None)
        res["falls"] = dict(removed=R.remove_objects(made), roots=n_root, streams_hidden=S.r48_streams(log=R.log))
        R.log("round-48 falls removed: %d objects (%d falls); streams hidden: %s" % (
            res["falls"]["removed"], n_root, res["falls"]["streams_hidden"]))
    # checks
    for o in bpy.data.objects:
        if o.name.startswith("life.span") and o.hide_render:
            fail.add("%s (a chain bridge) is hidden" % o.name)
    ice = bpy.data.objects.get(S.ICEFIRE_ISLAND)
    if ice is not None and ice.hide_render:
        fail.add("Ice-Fire Island is hidden")
    orph = orphan_island_plants()
    if orph:
        fail.add("%d island plants with no island under them, e.g. %s" % (len(orph), orph[:6]))
    res["orphans"] = len(orph)
    h = hashlib.md5()
    for o in sorted((o for o in bpy.data.objects if o.name.startswith(S.LIFE_ISLAND)), key=lambda o: o.name):
        h.update(("%s|%s|%s" % (o.name, o.hide_render, o.get(S.R48_HIDDEN))).encode())
    h.update(R.mesh_sig(rng_obj, 3).encode())
    for o in sorted((o for o in bpy.data.objects if o.name.startswith(("world.backdrop", "world.stream")) or
                     o.get(S.R48_TAG) == "falls"), key=lambda o: o.name):
        h.update(("%s|%s|%s" % (o.name, o.hide_render, o.get(S.R48_TAG))).encode())
    res["seconds"] = round(time.time() - t0, 1)
    R.report("fixes.json", res)
    R.log("CACHES needs audit: hidden island plants, world.range's chips, the horizon - run export_web audit "
          "--profile full, chunks,meta, bake_web bakefull, water, bake_trees plan,build, export_web clouds")
    R.save_or_dry(opt["dry"], fail, h.hexdigest())
    R.log("done in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
