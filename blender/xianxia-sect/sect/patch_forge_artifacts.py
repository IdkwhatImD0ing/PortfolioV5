"""Swap the forge ring's artifacts in out/sect_chase.blend for the winning projects' artifacts (areas/forge.py
FORGE_RING) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_forge_artifacts.py

Removes the artifact instances on forge.artifact_ring, places FORGE_ARTIFACTS with forge.place_artifacts and saves
the .blend. Idempotent: does nothing when the ring already holds the project artifacts.

The web caches are no longer patched here. This script used to give every piece of the ring (and of each crane
pair) the union of the group's visibility and chunk by hand. export_web's audit and chunk plan now do that for
every turning object (export_web.TURNING_GROUPS), so after a swap run the usual pipeline from the audit:
export_web.py -- audit, then -- chunks,meta (and the bakes).
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import forge  # noqa: E402

PREFIX = "forge.artifact."
RING = "forge.artifact_ring"


def log(*a):
    print("PATCH", *a, flush=True)


def swap_artifacts():
    spin = bpy.data.objects[RING]
    old = [o for o in spin.children if o.name.startswith(PREFIX)]
    if not old:
        raise RuntimeError("no artifacts under " + RING)
    coll = old[0].users_collection[0]
    log("removing", len(old), "artifacts:", sorted(o.name for o in old))
    for o in old:
        bpy.data.objects.remove(o, do_unlink=True)
    forge.place_artifacts(coll, spin)
    new = sorted(o.name for o in spin.children if o.name.startswith(PREFIX))
    log("placed", len(new), new)
    want = sorted(PREFIX + k for k in forge.FORGE_ARTIFACTS)
    if new != want:
        raise RuntimeError("unexpected artifact names %s" % new)


def main():
    have = {o.name for o in bpy.data.objects if o.name.startswith(PREFIX)}
    if have == {PREFIX + k for k in forge.FORGE_ARTIFACTS}:
        log("artifacts already swapped; nothing to do")
        return
    swap_artifacts()
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
