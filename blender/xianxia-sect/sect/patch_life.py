"""Life on the mountains (sect.life) on a finished out/sect_chase.blend, then save it. Run on the cloud box AFTER
sect/patch_density.py (pass 1), so the new trees keep clear of pass 1's:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_life.py

Adds, in collection 'scenery.life' (under 'scenery'), each object tagged sect_life = its part:
- ledges: Huangshan / cliff pines, peach-blossom clusters and big shrubs in tiers on the 11 m rock layers of every
  peak (up to LEDGE_TOP_CLEAR m under its top, where pass 1's crown band starts);
- islands: peach-blossom clusters (and azaleas) on about half the floating islands and islets;
- shrines: 10 low-poly pavilions / pagodas with two glowing lanterns each on distant peak tops seen from the holds,
  and a chain bridge between the two by the gate.
Idempotent: a re-run removes what the previous run made for the parts it runs (sect.life.clear) and builds them
again from the same seeds; nothing else in the file is touched, nothing existing moves. Prints LIFE lines with the
counts (and WARN lines for anything skipped).

Options after "--" (KEY=value, Python literals): an upper-case constant of sect.life (e.g. LEDGE_STEP=4.5
LEDGE_COVER=0.65 BLOSSOM_SHARE=0.15 SHRUB_P=0.4); PARTS=ledges,islands (or a tuple) rebuilds only those parts and
leaves the others as they are; DRY_RUN=1 (or DRY=True) builds and reports without saving.

Afterwards (new objects reach the web only through these): export_web audit --profile full, then chunks,meta;
bake_web bakefull for the areas whose chunks changed + backdrop (the shrines and the bridge are atlas geometry, and
the new trees cast baked shadows); bake_trees build; sect_pack.
"""
import ast
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import life as LF  # noqa: E402


def log(*a):
    print("LIFE", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = dict(PARTS=LF.PARTS, DRY=False)
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq or not k.isupper():
            log("WARN skipped argument (not KEY=value):", a)
            continue
        k = "DRY" if k == "DRY_RUN" else k
        try:
            val = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            if k != "PARTS":
                log("WARN skipped argument (value is not a Python literal):", a)
                continue
            val = tuple(x.strip() for x in v.split(",") if x.strip())
        if k in opts:
            opts[k] = val
        elif hasattr(LF, k):
            setattr(LF, k, val)
            log("override", k, "=", val)
        else:
            log("WARN skipped argument (no such constant in sect.life):", a)
    if isinstance(opts["PARTS"], str):
        opts["PARTS"] = (opts["PARTS"],)
    opts["DRY"] = bool(opts["DRY"])
    return opts


def main():
    opts = options()
    parts = tuple(p for p in opts["PARTS"] if p in LF.PARTS)
    bad = [p for p in opts["PARTS"] if p not in LF.PARTS]
    if bad or not parts:
        raise SystemExit("PARTS must name some of %s (got %s)" % (LF.PARTS, opts["PARTS"]))
    if bpy.data.objects.get("world.range") is None:
        raise SystemExit("no world.range in %s: run this on out/sect_chase.blend" % bpy.data.filepath)
    counts = LF.build(bpy.context.scene, parts=parts)
    log("parts", parts, "counts", counts)
    if opts["DRY"]:
        log("DRY: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
