"""Round 48, P-0: the keep-list (plan rule 13: every hall, prop, stair, bridge, shrine, plaque and inscription, and
every tree and plant within 60 m of a hold camera in its frame, stays exactly as it is). Read-only: never saves.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<file>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r48_keep.py -- MODE=dump LABEL=before
    ... -- MODE=compare LABEL=after REF=out/tmp/r48/keep_before.json [ALLOW=abode.dense_cliff_pine,abode.cliff_pine]

MODE=dump writes out/tmp/r48/keep_<LABEL>.json:
- locations: every object of the eleven area collections and of world.links / life (shrines, bridge), except the
  vegetation instances (collection-instance Empties of nature.proto.*): name, type, parent, world matrix (4 dp) and
  a mesh signature (vertices to the mm, face sizes, material slots);
- framing: per hold, every shown object origin (hide_render off) and every scatter instance within 60 m of the hold
  camera inside its frame (widened 12 %): object name or '<scatter>|<prototype>#<n>', world matrix (3 dp); an object
  a round-48 part hides shows up as 'gone';
- cameras: chase.cam's matrix at the eleven hold frames.
MODE=compare also dumps (as keep_<LABEL>.json) and prints 'PATCH KEEP diff <n>' with the first changes; exit code 1
when n > 0. ALLOW=prefix,prefix lists object-name prefixes whose changes are intended (the abode PART: its face pines
go and its round-48 dressing comes in); they are listed but not counted.
"""
import json
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.lib import compose as C  # noqa: E402
from sect.lib import r48 as R  # noqa: E402

AREAS = ("gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll", "formation", "abode", "summit")
LOCATION_COLLS = AREAS + ("world.links", "scenery.life")
FRAMING_DEC = 3


def is_veg_instance(ob):
    return ob.instance_type == 'COLLECTION' and ob.instance_collection is not None and \
        ob.instance_collection.name.startswith("nature.proto.")


def locations():
    out = {}
    for cn in LOCATION_COLLS:
        col = bpy.data.collections.get(cn)
        if col is None:
            continue
        for ob in col.all_objects:
            if is_veg_instance(ob) or ob.name in out:
                continue
            if cn == "scenery.life" and not ob.name.startswith(("life.shrine", "life.span", "landmark.life")):
                continue
            rec = dict(type=ob.type, parent=ob.parent.name if ob.parent else None, m=R.matrix_key(ob),
                       hidden=bool(ob.hide_render))
            if ob.type == 'MESH' and ob.data is not None:
                rec["mesh"] = R.mesh_sig(ob)
                rec["nv"] = len(ob.data.vertices)
            out[ob.name] = rec
    return out


def framing(hold_views):
    """{hold: {key: matrix}} of objects and scatter instances within KEEP_R of the hold camera, in frame."""
    out = {v.name: {} for v in hold_views}
    obs = [o for o in bpy.data.objects if o.type in ('MESH', 'EMPTY', 'CURVE', 'FONT') and not o.hide_render]
    pos = np.array([list(o.matrix_world.translation) for o in obs], float)
    for v in hold_views:
        m = R.keep_zone_mask(pos, [v])
        for i in np.nonzero(m)[0]:
            o = obs[i]
            out[v.name][o.name] = [round(float(x), FRAMING_DEC) for row in o.matrix_world for x in row]
    dg = bpy.context.evaluated_depsgraph_get()
    seen = {}
    rows = []
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        par = inst.parent.original
        if not par.modifiers.get("NatureScatter"):
            continue
        rows.append((par.name, inst.object.original.name, np.array(inst.matrix_world)))
    if rows:
        P = np.array([r[2][:3, 3] for r in rows])
        for v in hold_views:
            m = R.keep_zone_mask(P, [v])
            for i in np.nonzero(m)[0]:
                par, proto, M = rows[i]
                key = "%s|%s" % (par, proto)
                n = seen.get((v.name, key), 0)
                seen[(v.name, key)] = n + 1
                out[v.name]["%s#%d" % (key, n)] = [round(float(x), FRAMING_DEC) for x in M.ravel()]
    return out


def dump(label):
    intent = C.load_intent()
    hv = R.views(intent, flights=False)
    t0 = time.time()
    data = dict(file=bpy.data.filepath, label=label, locations=locations(), framing=framing(hv),
                cameras={v.name: [round(float(x), 4) for x in np.r_[v.pos, v.fwd, v.up]] for v in hv})
    n_fr = sum(len(x) for x in data["framing"].values())
    R.log("KEEP dump: %d location objects, %d framing items over %d holds (%.1f s)"
          % (len(data["locations"]), n_fr, len(hv), time.time() - t0))
    for h, x in data["framing"].items():
        R.log("KEEP framing", h, len(x))
    R.report("keep_%s.json" % label, data)
    return data


def compare(cur, ref_path, allow):
    with open(ref_path, encoding="utf-8") as f:
        ref = json.load(f)
    diffs, allowed = [], []

    def note(kind, name, what):
        (allowed if any(name.startswith(a) for a in allow) else diffs).append("%s %s: %s" % (kind, name, what))
    a, b = ref["locations"], cur["locations"]
    for n in sorted(set(a) | set(b)):
        if n not in b:
            note("location", n, "gone")
        elif n not in a:
            note("location", n, "new")
        elif a[n] != b[n]:
            what = [k for k in a[n] if a[n].get(k) != b[n].get(k)]
            note("location", n, "changed " + ",".join(what))
    for h in sorted(set(ref["framing"]) | set(cur["framing"])):
        fa, fb = ref["framing"].get(h, {}), cur["framing"].get(h, {})
        for n in sorted(set(fa) | set(fb)):
            if n not in fb:
                note("framing " + h, n, "gone")
            elif n not in fa:
                note("framing " + h, n, "new")
            elif np.abs(np.array(fa[n]) - np.array(fb[n])).max() > 2e-3:
                note("framing " + h, n, "moved")
    for h in sorted(set(ref["cameras"]) | set(cur["cameras"])):
        if ref["cameras"].get(h) != cur["cameras"].get(h):
            diffs.append("camera %s changed" % h)
    R.log("KEEP diff %d (allowed and listed: %d)" % (len(diffs), len(allowed)))
    for d in diffs[:40]:
        R.log("  KEEP -", d)
    for d in allowed[:20]:
        R.log("  KEEP allowed -", d)
    R.report("keep_diff_%s.json" % cur["label"], dict(ref=ref_path, diffs=diffs, allowed=allowed))
    return diffs


def main():
    opt = R.options((), dict(mode="dump", label="now", ref="", allow=""))
    cur = dump(opt["label"])
    if opt["mode"] == "compare":
        ref = opt["ref"] if os.path.isabs(opt["ref"]) else os.path.join(ROOT, opt["ref"])
        allow = tuple(a for a in opt["allow"].split(",") if a)
        diffs = compare(cur, ref, allow)
        if diffs:
            raise SystemExit(1)
    R.log("KEEP done (read-only, nothing saved)")


if __name__ == "__main__":
    main()
