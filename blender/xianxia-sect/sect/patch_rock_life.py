"""Give every rock material in out/sect_chase.blend the "rock life" layer (sect.lib.materials._rock_life: moss on
up-facing rock and in cushions along the 11 m ledge lines, dark damp streaks hanging from the ledges, ochre and
grey-green lichen, damp undersides) and save the .blend. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_rock_life.py

Rebuilds in place every material whose tag (materials.TAG) is registered with the _rock builder: rock_cliff (range
faces, peaks, pillars, islands, the abode cliff, plinths), world_rock_under (the range's underside) and
nature_rock_small (boulders), each with its own registered parameters, so objects keep their slots and nothing else
changes. register() rebuilds only materials with that exact tag, hence every variant is found by its builder and
listed. No object is touched or moved. Stops before touching the file when a scan is missing from assets/web
(materials.SCAN_DIR). Idempotent: a re-run rebuilds the same node trees again; images load once (check_existing).

Tuning: upper-case constants of sect.lib.materials can be overridden after "--" (Python literals), e.g.

    ... --python .../sect/patch_rock_life.py -- ROCK_MOSS=0.7 ROCK_STREAK=0.5 "ROCK_MOSS_UP=(0.3,0.5)"

ROCK_LIFE=False rebuilds the rocks exactly as they were before this layer (the rollback). ROCK_DAMP_AO=(2.5,16) turns
on ray-traced recess dampness (slower bake). ROCK_MOSS_BUMP=0.3 / ROCK_MOSS_PHOTO_BUMP=0.25 add the moss bumps (off by
default: Cycles evaluates a Bump's whole Height graph three times, ~+70 % rock shading, for sub-texel relief). Then re-bake the areas and the backdrop from the saved .blend
(bake_web.py -- bakefull --profile full --chunks ...).
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
from sect.lib import nature  # noqa: E402,F401  (registers nature_rock_small)

EXPECTED = ("rock_cliff", "world_rock_under", "nature_rock_small")   # bake_web.DETAIL_CLASSES "rock"


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


def rock_tags():
    """Tags in this file whose registered builder is materials._rock, plus EXPECTED ones (warned when absent)."""
    present = {m.get(M.TAG) for m in bpy.data.materials if m.get(M.TAG) and m.library is None}
    tags = sorted(t for t in present if t in M._REGISTRY and M._REGISTRY[t][0] is M._rock)
    for t in EXPECTED:
        if t not in tags:
            log("WARN no material tagged", t)
    odd = sorted(t for t in present if t not in M._REGISTRY and "rock" in t)
    if odd:
        log("WARN rock-like tags with no registered builder (left alone):", odd)
    extra = [t for t in tags if t not in EXPECTED]
    if extra:
        log("WARN _rock variants not in bake_web.DETAIL_CLASSES (no web rock detail on them):", extra)
    return tags


def node_stats(mats):
    """(node count, scan file names, AO node count). Files by their path's basename, not the datablock name: an
    image that met a same-named one on load is called 'moss001_color.jpg.001'."""
    nodes = sum(len(m.node_tree.nodes) for m in mats if m.node_tree)
    imgs = sorted({os.path.basename(bpy.path.abspath(n.image.filepath)) or n.image.name
                   for m in mats if m.node_tree for n in m.node_tree.nodes
                   if n.bl_idname == "ShaderNodeTexImage" and n.image is not None})
    ao = sum(1 for m in mats if m.node_tree for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeAmbientOcclusion")
    return nodes, imgs, ao


def main():
    apply_overrides()
    missing = [f for f in M.scan_files() if not os.path.isfile(os.path.join(M.SCAN_DIR, f))]
    if missing:
        raise RuntimeError("scans missing in %s: %s" % (M.SCAN_DIR, missing))
    log("ROCK_LIFE", M.ROCK_LIFE, {k: getattr(M, k) for k in sorted(dir(M))
                                   if k.startswith("ROCK_") and k not in ("ROCK_SCANS",)})
    users = {}
    for ob in bpy.data.objects:
        for s in getattr(ob, "material_slots", ()):
            if s.material is not None:
                users.setdefault(s.material.name, set()).add(ob.name)
    total = 0
    moss = M.GROUND_SCANS["moss"]
    for name in rock_tags():
        builder, params = M._REGISTRY[name]
        mats = [m for m in bpy.data.materials if m.get(M.TAG) == name and m.library is None]
        before = node_stats(mats)[0]
        M.register(name, builder, overwrite=True, **params)
        nodes, imgs, ao = node_stats(mats)
        n_obj = len(set().union(*[users.get(m.name, set()) for m in mats])) if mats else 0
        total += len(mats)
        log(name, "rebuilt", len(mats), [m.name for m in mats][:4], "objects", n_obj, "nodes", before, "->", nodes,
            "ao_nodes", ao, "params", params, "scans", imgs)
        if not imgs:
            raise RuntimeError("%s has no scan image after the rebuild" % name)
        if M.ROCK_LIFE and M.ROCK_MOSS and moss not in imgs:
            raise RuntimeError("%s has no %s after the rebuild (rock life moss)" % (name, moss))
    if not total:
        raise RuntimeError("no rock material found; is this out/sect_chase.blend?")
    bad = [im.name for im in bpy.data.images
           if os.path.normpath(bpy.path.abspath(im.filepath)).startswith(M.SCAN_DIR) and not im.size[0]]
    if bad:
        raise RuntimeError("scans failed to load: %s" % bad)
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "materials rebuilt", total)


main()
