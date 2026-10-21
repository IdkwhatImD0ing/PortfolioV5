"""Give the rock and ground materials in out/sect_chase.blend their photo-scan layer (sect.lib.materials:
ROCK_SCANS, LAWN_SCANS, GROUND_SCANS) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_nature_look.py

Rebuilds in place every material tagged rock_cliff, world_rock_under, nature_rock_small, grass or nature_soil_moss
(materials.register(..., overwrite=True)), each with its own registered parameters, so objects keep their slots and
nothing else changes. register() rebuilds only materials with that exact tag, hence every variant is listed. Stops
before touching the file when a scan is missing from assets/web (materials.SCAN_DIR). Idempotent.

Tuning: upper-case constants of sect.lib.materials can be overridden after "--" (Python literals), e.g.

    ... --python .../sect/patch_nature_look.py -- ROCK_SCAN_MIX=0.5 LAWN_SCAN_MIX=0.7 ROCK_SCAN_SHARP=6

Then re-bake the area from the saved .blend (bake_web.py -- bakefull --profile full --chunks mirror).

The rock rebuild also carries the rock life layer (materials.ROCK_LIFE, on by default): moss, ledge streaks, lichen,
and the lip moss under grass rims (ROCK_LIP_MOSS). grass and nature_soil_moss carry the ground life layer
(GROUND_LIFE: GROUND_MACRO patches, GROUND_CLUMP clumps, GROUND_FLOWERS, GROUND_RIM band). A dict constant may be
overridden in part and keeps its other keys, e.g. "GROUND_FLOWERS={'amount':0}". The look before them:

    ... -- GROUND_LIFE=False "ROCK_LIP_MOSS={'amount':0}" "ROCK_MOSS_UP=(0.27,0.45)"

sect/patch_rock_life.py rebuilds only the rock materials (every _rock variant) and takes the ROCK_* overrides.
"""
import ast
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world  # noqa: E402,F401  (registers world_rock_under)
from sect.lib import materials as M  # noqa: E402
from sect.lib import nature  # noqa: E402,F401  (registers nature_rock_small, nature_soil_moss)

NAMES = ("rock_cliff", "world_rock_under", "nature_rock_small", "grass", "nature_soil_moss")


def log(*a):
    print("PATCH", *a, flush=True)


def apply_overrides():
    """KEY=value arguments after '--' naming an upper-case constant of sect.lib.materials; others are skipped
    with a warning."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq or not k.isupper() or not hasattr(M, k):
            log("WARN skipped argument (not KEY=value of a sect.lib.materials constant):", a)
            continue
        setattr(M, k, ast.literal_eval(v))
        log("override", k, "=", getattr(M, k))


def scan_nodes(mats):
    return sorted({n.image.name for m in mats if m.node_tree for n in m.node_tree.nodes
                   if n.bl_idname == "ShaderNodeTexImage" and n.image is not None})


def main():
    apply_overrides()
    missing = [f for f in M.scan_files() if not os.path.isfile(os.path.join(M.SCAN_DIR, f))]
    if missing:
        raise RuntimeError("scans missing in %s: %s" % (M.SCAN_DIR, missing))
    for name in NAMES:
        builder, params = M._REGISTRY[name]
        mats = [m for m in bpy.data.materials if m.get(M.TAG) == name and m.library is None]
        if not mats:
            log("WARN no material tagged", name)
            continue
        M.register(name, builder, overwrite=True, **params)
        imgs = scan_nodes(mats)
        log(name, "rebuilt", len(mats), [m.name for m in mats][:4], "params", params, "scans", imgs)
        if not imgs:
            raise RuntimeError("%s has no scan image after the rebuild" % name)
    bad = [im.name for im in bpy.data.images
           if os.path.normpath(bpy.path.abspath(im.filepath)).startswith(M.SCAN_DIR) and not im.size[0]]
    if bad:
        raise RuntimeError("scans failed to load: %s" % bad)
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
