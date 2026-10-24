"""Round 48, C: islands and islets culled to each view's intent, canopy caps on the ones that stay, falls that arc and
break into mist (and none in the five no-fall holds), and a horizon of pillar families and level mesas, in an
existing out/sect_chase.blend; the same as scenery.build_r48 makes on a fresh build. Run on the cloud box, on a COPY
first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_isles.py -- [PARTS=isles,caps,falls,horizon]
        [DRY_RUN=1]

PARTS (default isles,caps,falls,horizon; *_undo puts a part back):
  isles    lib/compose.cull_islands over the eleven holds (holds_intent islets: max, zone, none near the star, none in
           quiet sky), the listed flights and chase.cam every 6 frames (at most 7 in a frame), then the totals (about
           40 islands, 12 islets). Culled rocks, their plants, falls and companions are HIDDEN (hide_render: the
           export and the bake skip them), tagged r48_hidden 'isles'. Ice-Fire Island always stays. Every run also
           hides the top pines of any culled rock (world.islet.pine*, scenery.island.*) and island pines with no rock
           under them (phase C: they stood in the sky).
  caps     every visible island: the packed pine crowns hidden, a broadleaf cap and a few spires on its top.
  falls    lib/compose.cull_falls, then every fall that stays rebuilt (nature.waterfall: at most world.FALL_MAX_H m,
           exit 2.5-4 m/s, spread 40-60 %, island falls 0.3-0.5 x the island) with a spray chain of puffs
           (world.cloud.fallmist, exported by export_web clouds). Ice-Fire Island's fall stays as it is.
  horizon  the 14 backdrop massifs hidden, world.BACKDROP_R48 built (3 pillar families, 2 mesas).
Checks: Ice-Fire Island and the arena island visible; at most 7 islands in any sampled frame; each hold within its
max; no fall in the no-fall holds. Prints counts, 'PATCH DIGEST <md5>' (the hidden and the new objects), writes
out/tmp/r48/isles.json. Idempotent (it re-reads what is visible; the undo parts put back what it hid).
"""
import hashlib
import json
import os
import sys
import time

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect import world as W  # noqa: E402
from sect.lib import compose as C  # noqa: E402
from sect.lib import r48 as R  # noqa: E402

PARTS = ("isles", "caps", "falls", "horizon", "isles_undo", "caps_undo", "falls_undo", "horizon_undo")
DEFAULT_PARTS = ("isles", "caps", "falls", "horizon")


def main():
    t0 = time.time()
    opt = R.options(PARTS, {}, modules=(S, W, C))
    if not any(a.startswith("PARTS=") for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])):
        opt["parts"] = DEFAULT_PARTS
    parts = opt["parts"]
    fail = R.Fail()
    if bpy.data.objects.get("world.range") is None or bpy.data.objects.get(R.CAMERA) is None:
        R.log("NOT SAVED: no world.range or chase.cam: is this out/sect_chase.blend?")
        raise SystemExit(1)
    intent = C.load_intent()
    an = R.anchors()
    hv = R.views(intent, flights=False)
    star = R.star_boxes(hv, an)
    scene = bpy.context.scene
    res = {}
    for p, tag in (("isles_undo", "isles"), ("falls_undo", "falls"), ("horizon_undo", "horizon")):
        if p in parts:
            res[p] = dict(shown=S.r48_unhide(tag), removed=S.r48_remove((tag,)))
    if "caps_undo" in parts:
        res["caps_undo"] = dict(removed=S.r48_remove(("isles",)))
    if "isles" in parts:
        res["isles"] = S.r48_isles(intent, hv, star, log=R.log)
    kept = {r["name"] for r in S.r48_isle_records()[1]}
    if "caps" in parts:
        S.r48_remove(("isles",))
        res["caps"] = S.r48_island_caps(S.density_paths(scene), keep=kept)
    if "falls" in parts:
        S.r48_unhide("falls")          # a re-run starts from the falls as they were (rebuilt ones are replaced)
        S.r48_remove(("falls",))
        res["falls"] = S.r48_falls(intent, hv, kept, log=R.log)
    if "horizon" in parts:
        res["horizon"] = S.r48_horizon(scene, log=R.log)
    # checks on what is visible now
    for nm in (S.ICEFIRE_ISLAND, "arena.island"):
        ob = bpy.data.objects.get(nm)
        if ob is not None and ob.hide_render:
            fail.add("%s is hidden" % nm)
    rocks, recs = S.r48_isle_records()
    sample = R.flight_sample(int(intent.get("flight_default", {}).get("every", 6)))
    vis = C.island_visibility(recs, list(hv) + sample, intent["flight_default"]["max_dist"],
                              intent["flight_default"]["min_px"])
    worst = max(((len(v), k) for k, v in vis.items()), default=(0, None))
    per_hold = {v.name: len(vis.get(v.name, [])) for v in hv}
    R.log("visible islands now: %d (islands %d, islets %d); most in one frame %d (%s); per hold %s" % (
        len(recs), sum(r["kind"] == "island" for r in recs), sum(r["kind"] == "islet" for r in recs), worst[0],
        worst[1], json.dumps(per_hold)))
    fd = intent["flight_default"]
    if worst[0] > fd.get("islets_max", 7) + 1:          # +1: Ice-Fire Island is a location and may be the 8th
        fail.add("%d islands in frame %s" % worst)
    for name, h in intent["holds"].items():
        mx = h.get("islets", {}).get("max", 7)
        n = per_hold.get(name, 0) - sum(1 for x in vis.get(name, []) if recs[x[0]]["protected"])
        if n > mx:
            fail.add("%s shows %d islands (max %d)" % (name, n, mx))
    res["visible"] = dict(total=len(recs), worst=list(worst), per_hold=per_hold)
    h = hashlib.md5()
    for o in sorted((o for o in bpy.data.objects if o.get(S.R48_HIDDEN) in ("isles", "falls", "horizon")
                     or o.get(S.R48_TAG) in ("isles", "falls", "horizon")), key=lambda o: o.name):
        h.update(("%s|%s|%s|%s" % (o.name, o.get(S.R48_TAG), o.get(S.R48_HIDDEN), R.matrix_key(o, 3))).encode())
    res["seconds"] = round(time.time() - t0, 1)
    R.report("isles.json", res)
    R.log("CACHES needs audit: hidden islands and falls, new caps, falls, puffs and horizon - run export_web audit "
          "--profile full, chunks,meta, bake_web bakefull (all chunks and the backdrop), water, bake_trees plan,build, "
          "export_web clouds")
    R.save_or_dry(opt["dry"], fail, h.hexdigest())
    R.log("done in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
