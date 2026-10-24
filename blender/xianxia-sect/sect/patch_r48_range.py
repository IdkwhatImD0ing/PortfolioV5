"""Round 48, P-1: the range's tall peaks become karst pillars (or, B0 variant a, benched cones) in an existing
out/sect_chase.blend, the same change world.py makes on a fresh build (Range peak_mode, build_peak_pillars). Run on
the cloud box, on a COPY first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_range.py -- VARIANT=b SCOPE=b0 [DRY_RUN=1]

VARIANT (plan section 6, B0):
  a     heightfield benches: each peak's 11 m strata become irregular benches 14-30 m apart from its own top
  b     peak_pillar 'sandstone' on every cut peak (mid level; hero within world.PILLAR_HERO_D m of a hold camera)
  c     peak_pillar 'granite' on every cut peak
  auto  columns sandstone, granite cones granite (the final choice unless B0 says otherwise; world.py's default)
SCOPE   b0 (the f870 wall's peak family and the scroll hillside), slice (the chunks of f870, f974, f1103) or all.
COMPOSE 1 (default) applies sect/holds_intent.json's rules to the pillar tops (lib/compose.peak_limits: the star's
        skyline, quiet sky, a clear moon at the gate, the poster, 1160 and the summit); 0 skips them.
PARTS   range (world.range's heights), pillars (the world.peak.<NNN> objects). Default both.

What it does: world.range keeps every vertex and face; only heights move (and, along the range's outline next to a
cut peak, the outline vertices slide along their edge): the old heights are the committed Range in peak_mode
'strata' (or the state an earlier run of this patch stored in world.range['r48_range']), the new ones the asked
mode. Each vertex at the old height moves to the new one; one already at the new height stays; any other vertex
(the links' sinks) must lie where nothing changes, else the patch stops. Faces whose vertices moved get the
material (rock / green) and 'world_veg' a fresh build gives them. The pillars (named world.peak.<NNN>, NNN the
peak's index in Range.peaks, tagged r48_peak) are deleted and built again on every run. The shrine peaks
(life.SHRINES, the objects life.shrine.* and their life_peak) stay cones.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves): world.range has the
committed topology (faces equal); no vertex in a changed region off both the old and the new surface; every pillar
fits inside its old cone (world.fit_pillar) and stands at least PATH_CLEAR m off the camera path below its top and
LINK_CLEAR m off every link; every pillar's foot ring is buried in the range; no pillar within an area's terrace.
Prints 'PATCH DIGEST <md5>' (world.range's vertices and the pillars' meshes) and writes
out/tmp/r48/range_<VARIANT>_<SCOPE>.json (the plan, the composition cuts and conflicts, triangles per pillar).
Idempotent: a second run with the same options prints the same digest and 'PATCH nothing changed: not saving'
(the pillars are rebuilt identically; no save when nothing differs).
After saving: export_web audit --profile full, chunks,meta, bake_web bakefull for every chunk that sees the changed
peaks (all of them in SCOPE=all) and the backdrop, bake_trees plan,build (trees on the old cones moved or went).
"""
import hashlib
import json
import math
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world as W  # noqa: E402
from sect.lib import compose as C  # noqa: E402
from sect.lib import look as L  # noqa: E402
from sect.lib import r48 as R  # noqa: E402

PARTS = ("range", "pillars")
TOL = 0.02                     # m: a vertex this near a reference surface is on it
PATH_CLEAR = 25.0              # m: no pillar this near the camera path (horizontally) under its top
LINK_CLEAR = 10.0              # m: no pillar foot this near a link part
PROP = "r48_range"             # world.range custom property: the options of the last run (JSON)
VARIANTS = dict(a=("benches", None), b=("pillars", "sandstone"), c=("pillars", "granite"),
                auto=("pillars", "auto"))


def shrine_skip(rng_):
    s = set(W.shrine_peaks(rng_.peaks))
    for ob in bpy.data.objects:
        if ob.name.startswith("life.shrine.") and "life_peak" in ob.keys():
            s.add(int(ob["life_peak"]))
    return s


def scope_peaks(rng_, discs):
    if discs is None:
        return None
    xy = np.array([p[:2] for p in rng_.peaks])
    return set(int(k) for k in np.nonzero(R.in_scope(discs, xy))[0])


def mesh_faces(me):
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    return lt, lv


def plan_json(plan):
    return {str(k): {q: v for q, v in s.items() if not callable(v)} for k, s in plan.items()}


def make_range(an, yaws, mode, preset, skip, only, holds, limits):
    opts = dict(skip=set(skip), only=None if only is None else set(only), holds=holds, preset=preset,
                limits={int(k): float(v) for k, v in (limits or {}).items()})
    return W.Range(an, yaws, peak_mode=mode, plan_opts=opts)


def main():
    t0 = time.time()
    opt = R.options(PARTS, dict(variant="auto", compose="1"), modules=(W,))
    if opt["variant"] not in VARIANTS:
        raise SystemExit("patch_r48_range: VARIANT must be one of %s" % sorted(VARIANTS))
    mode, preset = VARIANTS[opt["variant"]]
    fail = R.Fail()
    ob = bpy.data.objects.get("world.range")
    if ob is None or bpy.data.objects.get(R.CAMERA) is None:
        R.log("NOT SAVED: no world.range or chase.cam: is this out/sect_chase.blend?")
        raise SystemExit(1)
    mw = np.array(ob.matrix_world)
    if not np.allclose(mw, np.eye(4), atol=1e-6):
        R.log("NOT SAVED: world.range has a transform; this patch expects it at the origin")
        raise SystemExit(1)
    an = R.anchors()
    yaws = W._anchor_yaws(None)
    intent = C.load_intent()
    hv = R.views(intent, flights=True)
    holds_v = [v for v in hv if v.name in intent["holds"]]
    hold_pos = [v.pos.tolist() for v in holds_v]
    base = W.Range(an, yaws, peak_mode="strata")
    skip = shrine_skip(base)
    discs = R.scope(opt["scope"])
    only = scope_peaks(base, discs)
    R.log("variant", opt["variant"], "mode", mode, "preset", preset, "scope", opt["scope"],
          "peaks in scope", "all" if only is None else len(only), "shrine peaks kept", sorted(skip))
    # the new plan, then the composition's cuts on the pillar tops
    limits, crow = {}, []
    new = make_range(an, yaws, mode, preset, skip, only, hold_pos, None)
    if mode == "pillars" and opt["compose"] not in ("0", "false", "no"):
        plan0 = new.pillar_plan()
        star = R.star_boxes(holds_v, an)
        moon = C.moon_world(W.MOON_VIEW, list(L.MOON_DIR), W.MOON_DISTANCE)
        limits, crow = C.peak_limits(plan0, hv, intent, star=star, moon=moon, log=R.log)
        new = make_range(an, yaws, mode, preset, skip, only, hold_pos, limits)
    plan = new.pillar_plan() if mode == "pillars" else {}
    state = dict(variant=opt["variant"], mode=mode, preset=preset, skip=sorted(skip),
                 only=None if only is None else sorted(only), holds=hold_pos,
                 limits={str(k): round(v, 3) for k, v in limits.items()})
    # reference surfaces: committed (strata), the last run's (if any), the new one
    prev_state = json.loads(ob[PROP]) if PROP in ob.keys() else None
    me = ob.data
    n_v, n_f = len(me.vertices), len(me.polygons)
    if "range" in opt["parts"]:
        t1 = time.time()
        d_old = W.terrain_data(base)
        d_new = W.terrain_data(new)
        refs = [("strata", d_old)]
        if prev_state is not None and prev_state != state:
            prev = make_range(an, yaws, prev_state["mode"], prev_state["preset"], prev_state["skip"],
                              prev_state["only"], prev_state["holds"], prev_state["limits"])
            refs.append(("previous run (%s)" % prev_state["variant"], W.terrain_data(prev)))
        R.log("terrain data built in %.1f s: %d verts, %d faces" % (time.time() - t1, len(d_new["verts"]),
                                                                    len(d_new["faces"])))
        if len(d_new["verts"]) != n_v or len(d_new["faces"]) != n_f or \
                not np.array_equal(d_old["faces"], d_new["faces"]):
            fail.add("world.range is not the committed range (verts %d / %d, faces %d / %d) or the mode changed its "
                     "topology" % (n_v, len(d_new["verts"]), n_f, len(d_new["faces"])))
        else:
            lt, lv = mesh_faces(me)
            if not (lt == 4).all() or not np.array_equal(lv.reshape(-1, 4), d_new["faces"]):
                fail.add("world.range's faces differ from terrain_data's (another patch changed its topology)")
        if not fail:
            co = np.empty(n_v * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            target = d_new["verts"]
            changed_region = np.zeros(n_v, bool)
            at_ref = np.zeros(n_v, bool)
            for nm_, d_ in refs:
                changed_region |= np.abs(d_["verts"] - target).max(1) > 1e-4
                at_ref |= np.abs(co - d_["verts"]).max(1) < TOL
            at_new = np.abs(co - target).max(1) < TOL
            todo = changed_region & ~at_new & at_ref
            odd = changed_region & ~at_new & ~at_ref
            R.log("vertices: %d in changed regions, %d already at the new surface, %d to move, %d off every "
                  "reference" % (int(changed_region.sum()), int((changed_region & at_new).sum()), int(todo.sum()),
                                 int(odd.sum())))
            if odd.any():
                bad = np.nonzero(odd)[0][:8]
                fail.add("%d vertices in changed regions sit off both surfaces, e.g. %s" % (
                    int(odd.sum()), [[round(float(x), 2) for x in co[i]] for i in bad]))
            elif todo.any():
                co[todo] = target[todo]
                me.vertices.foreach_set("co", co.ravel())
                moved = np.zeros(n_v, bool)
                moved[todo] = True
                F = d_new["faces"]
                touch = moved[F].any(1)
                mi = np.empty(n_f, np.int32)
                me.polygons.foreach_get("material_index", mi)
                mi[touch] = d_new["mats"][touch]
                me.polygons.foreach_set("material_index", mi)
                veg = R.face_attr(ob, "world_veg")
                if veg is not None:
                    veg[touch] = d_new["veg"][touch].astype(np.float32)
                    R.face_attr(ob, "world_veg", veg)
                me.update()
                R.log("moved %d vertices; %d faces re-classed (rock / green)" % (int(todo.sum()), int(touch.sum())))
    ob[PROP] = json.dumps(state)
    # pillars
    built = []
    if "pillars" in opt["parts"]:
        old = [o for o in bpy.data.objects if "r48_peak" in o.keys()]
        old += [c for o in old for c in o.children_recursive if c not in old]   # fringes, cap / shelf scatters
        R.log("removed earlier pillars (with their fringes and plants)", R.remove_objects(old))
        if mode == "pillars":
            coll = ob.users_collection[0]
            built = W.build_peak_pillars(new, coll, plan, log=R.log)
            path = R.path_points(2)
            lp = W.link_points()
            for k, pob, info in built:
                s = plan[k]
                dxy = np.hypot(path[:, 0] - s["x"], path[:, 1] - s["y"])
                below = path[:, 2] < info["top_z"] + 10.0
                if below.any() and float(dxy[below].min()) < info["bot_r"] + PATH_CLEAR:
                    fail.add("pillar %d stands %.1f m from the camera path" % (k, float(dxy[below].min())))
                if len(lp):
                    dl = float(np.hypot(lp[:, 0] - s["x"], lp[:, 1] - s["y"]).min())
                    if dl < info["bot_r"] + LINK_CLEAR:
                        fail.add("pillar %d stands %.1f m from a link" % (k, dl))
                for key, a in an.items():
                    if math.hypot(a[0] - s["x"], a[1] - s["y"]) < a[3] + W.TERRACE_PAD + info["bot_r"]:
                        fail.add("pillar %d stands on the %s terrace" % (k, key))
            tris = sum(i["tris"] + i["fringe_tris"] for _k, _o, i in built)
            R.log("pillars built: %d (%s), %d triangles with fringes; hero %d, mid %d" % (
                len(built), {p: sum(1 for _k, _o, i in built if i["preset"] == p) for p in ("sandstone", "granite")},
                tris, sum(1 for _k, _o, i in built if i["lod"] == "hero"),
                sum(1 for _k, _o, i in built if i["lod"] == "mid")))
    # digest + report
    h = hashlib.md5()
    h.update(R.mesh_sig(ob, 3).encode())
    for o in sorted((o for o in bpy.data.objects if "r48_peak" in o.keys()), key=lambda o: o.name):
        h.update(o.name.encode())
        h.update(R.mesh_sig(o, 3).encode())
    R.report("range_%s_%s.json" % (opt["variant"], opt["scope"]), dict(
        state=state, plan=plan_json(plan), composition=crow,
        pillars=[dict(peak=k, name=o.name, **i) for k, o, i in built], seconds=round(time.time() - t0, 1)))
    digest = h.hexdigest()
    if not fail and prev_state == state and ob.get(PROP + "_digest") == digest:
        R.log("DIGEST", digest)
        R.log("nothing changed: not saving")
        return
    ob[PROP + "_digest"] = digest
    R.log("CACHES needs audit: world.range's heights at the cut peaks and %d pillar objects - run export_web audit "
          "--profile full, chunks,meta, bake_web bakefull (every chunk that sees them and the backdrop), bake_trees "
          "plan,build" % len(built))
    R.save_or_dry(opt["dry"], fail, digest)
    R.log("done in %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
