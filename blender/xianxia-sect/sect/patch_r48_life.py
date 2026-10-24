"""Round 48, C: life in the range (life.build_paths): two plank walkways 栈道 round two round-48 pillars the holds see
200-650 m off, each from the forested plinth at the pillar's foot up about a third of it to a deck with a small
pavilion, and one more pavilion at the foot of a third pillar. Run on the cloud box AFTER patch_r48_range.py and
patch_r48_green.py (the walkways follow the final pillars), on a COPY first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_life.py [-- DRY_RUN=1]

Checks: each walkway's foot within 1.5 m of the ground under it and its top on its deck (life.build_paths builds
them so; this re-measures); nothing within 150 m of the camera path. Prints 'PATCH DIGEST <md5>', writes
out/tmp/r48/life.json. Idempotent (an earlier run's objects, tagged sect_life = 'r48path', are replaced).
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

from sect import life as LF  # noqa: E402
from sect.lib import compose as C  # noqa: E402
from sect.lib import r48 as R  # noqa: E402

PATH_MIN = 150.0


def main():
    t0 = time.time()
    opt = R.options(("paths",), {}, modules=(LF,))
    fail = R.Fail()
    if bpy.data.objects.get("world.range") is None or bpy.data.objects.get(R.CAMERA) is None:
        R.log("NOT SAVED: no world.range or chase.cam")
        raise SystemExit(1)
    intent = C.load_intent()
    hv = R.views(intent, flights=False)
    res = LF.build_paths(bpy.context.scene, hv, log=R.log)
    surf = LF.Surface(bpy.data.objects["world.range"])
    path = R.path_points(2)
    for f in res["paths"]:
        if f["kind"] != "walkway":
            continue
        x, y, z = f["foot"]
        hit = surf.down(x, y, z + 3.0, 60.0)
        gap = None if hit is None else z - hit[0].z
        f["foot_gap"] = None if gap is None else round(float(gap), 2)
        if gap is None or gap > 1.5:
            R.log("WARN walkway on %s: its foot stands %s m over the ground under it (it starts at the wall's foot; "
                  "check the still)" % (f["pillar"], f["foot_gap"]))
    for o in bpy.data.objects:
        if o.get(LF.TAG) != LF.PATH_TAG:
            continue
        p = np.array(o.matrix_world.translation) if o.name.find("walkway") < 0 else None
        if p is None:
            co = np.array([list(o.matrix_world @ v.co) for v in o.data.vertices[::25]])
        else:
            co = p[None]
        d = np.min(np.linalg.norm(path[None, :, :] - co[:, None, :], axis=2))
        if d < PATH_MIN:
            fail.add("%s stands %.0f m from the camera path" % (o.name, d))
    R.log("life paths", json.dumps(res))
    h = hashlib.md5()
    for o in sorted((o for o in bpy.data.objects if o.get(LF.TAG) == LF.PATH_TAG), key=lambda o: o.name):
        h.update(o.name.encode())
        h.update(R.mesh_sig(o).encode())
        h.update(json.dumps(R.matrix_key(o, 3)).encode())
    res["seconds"] = round(time.time() - t0, 1)
    R.report("life.json", res)
    R.log("CACHES needs audit: new walkways and pavilions - run export_web audit, chunks,meta, bake_web bakefull")
    R.save_or_dry(opt["dry"], fail, h.hexdigest())


if __name__ == "__main__":
    main()
