"""Denser Huangshan pines in out/sect_chase.blend: crowns packed on the floating islands and islets with pines
leaning out over their rims, cliff pines down to the near-vertical column walls, a crown band under every peak's
top and pines all over the Cave Abode's cliff. The same changes scenery.py (build_density, build_forest),
areas/abode.py (dense_pines) and nature.floating_rock now make on a full rebuild, added to the finished scene
without moving anything in it. Run on the cloud box:

    blender --background out/sect_chase.blend --python sect/patch_density.py -- [KEY=value ...]

Parts (all by default; PARTS=islands,range,... runs some):
- islands, islets: scenery.island_crowns on scenery.island* / world.islet*: rim pines and packed crown pines,
  children of their rock, far-LOD Huangshan prototypes the scene already has.
- range: scenery.range_density: FACE masks scenery_cliff_dense / scenery_cliff_wall / scenery_crown on world.range
  (attributes only, its geometry is untouched) and the scatters scenery.cliffpines.dense / .walls and scenery.crowns.
- abode: abode.dense_pines under abode.root (cliff pines out of the face, Huangshan pines on the top rows).
- forest: scenery.forest instances pines only (its two shrub prototypes dropped; same points, turns and scales).
- masks: nature.fix_inside_out_plants on inside-out scenery.island* / world.islet* / arena.islet* rocks (their
  'nature_veg' mask and plant-scatter inputs). Not arena.island: arena.py cleared its mask under the paving.

Idempotent: every object the patch makes carries the custom property scenery.DENSITY_TAG (its part); a re-run
deletes those of the parts it runs and makes them again, and the forest / masks steps set values. It never deletes,
moves or reshapes an object it did not make. It stops without saving when a tree prototype would be built anew
(a builder changed under the scene) or the scatter node group has another version.

Overrides after "--": KEY=value for an upper-case constant of sect/scenery.py (CROWN_DENSITY=0.015 CARD_CLEAR=80),
abode.KEY=value for sect/areas/abode.py (abode.DENSE_FACE_PINES=12), PARTS=a,b and DRY_RUN=1 (report, no save).

It prints the pines added per part and, for each new pine, its nearest distance to chase.cam less 0.8 x its height
(about the distance to its box): under CARD_CLEAR the web would draw a 3D mesh, up to NM_BAND a card in the
nearest frame's area file plus a stand-in in backdrop_trees, beyond NM_BAND a backdrop_trees card only.

New objects are invisible to the web build until the audit has seen them. After saving: export_web audit --profile
full, chunks,meta (compare chunks.npz with the old one), bake_web for the areas whose trees changed + backdrop,
bake_trees plan,build, then tools/sect_pack.py.
"""
import ast
import collections
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Vector, kdtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import chase as CH  # noqa: E402
from sect import scenery as S  # noqa: E402
from sect import world as W  # noqa: E402
from sect.areas import abode as AB  # noqa: E402
from sect.lib import nature as N  # noqa: E402
from sect.lib import util as U  # noqa: E402

PARTS = ("islands", "islets", "range", "abode", "forest", "masks")
TAGGED = {"islands": "island", "islets": "islet", "range": "range", "abode": "abode"}   # part -> DENSITY_TAG value
INSIDE_OUT = ("scenery.island", "world.islet", "arena.islet")
NM_BAND = 400.0              # export_web.NM_BAND: seen only beyond this, a piece goes to the backdrop
CARD_B = 58                  # bytes per card in a .glb.gz (u5: 37-60 B after deflate)
NEAR_B = 40000               # bytes per extra near (3D) pine merged into trees.near (mirror: ~1.6 MB / 40)


def log(*a):
    print("DENSITY", *a, flush=True)


def options():
    """KEY=value arguments after '--' (module docstring). Unknown keys stop the run."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(parts=PARTS, dry=False)
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("patch_density: not KEY=value: %r" % a)
        if k == "PARTS":
            opt["parts"] = tuple(p.strip() for p in v.split(",") if p.strip())
            bad = [p for p in opt["parts"] if p not in PARTS]
            if bad:
                raise SystemExit("patch_density: unknown parts %s (known: %s)" % (bad, ",".join(PARTS)))
        elif k == "DRY_RUN":
            opt["dry"] = bool(ast.literal_eval(v))
        else:
            mod, key = (AB, k[len("abode."):]) if k.startswith("abode.") else (S, k)
            if not key.isupper() or not hasattr(mod, key):
                raise SystemExit("patch_density: %s has no constant %s" % (mod.__name__, key))
            setattr(mod, key, ast.literal_eval(v))
            log("override", mod.__name__ + "." + key, "=", getattr(mod, key))
    return opt


# ---- guards -------------------------------------------------------------------------------------------------

def proto_names():
    """{prototype collection: its objects' session ids}. nature._proto rebuilds a collection it finds empty or
    untagged under the same name, so new objects in an old collection count as a change too."""
    return {c.name: tuple(sorted(o.session_uid for o in c.all_objects))
            for c in bpy.data.collections if c.name.startswith("nature.proto.")}


def check_scatter_group():
    """scatter_on rebuilds a 'nature.scatter.*' group of another version, which would cut it from every scatter
    in the scene: stop before touching anything."""
    for ng in bpy.data.node_groups:
        if ng.name.startswith("nature.scatter.") and ng.get("nature_scatter") != N._SCATTER_VERSION:
            raise SystemExit("patch_density: node group %s is version %r, nature.py builds %r; not patching"
                             % (ng.name, ng.get("nature_scatter"), N._SCATTER_VERSION))


# ---- parts --------------------------------------------------------------------------------------------------

def remove_owned(parts):
    """Delete the objects earlier runs made for these parts (DENSITY_TAG), and their empty scatter meshes."""
    tags = {TAGGED[p] for p in parts if p in TAGGED}
    gone = [o for o in bpy.data.objects if o.get(S.DENSITY_TAG) in tags]
    meshes = {o.data for o in gone if o.type == 'MESH'}
    for o in gone:
        bpy.data.objects.remove(o, do_unlink=True)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return len(gone)


def _scatter_ids(mod):
    return {s.name: s.identifier for s in mod.node_group.interface.items_tree
            if getattr(s, "in_out", None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry'}


def forest_pines_only():
    """scenery.forest picks among the forest set's 6 pines instead of 6 pines + 2 shrubs (scenery.build_forest)."""
    ob = bpy.data.objects.get("scenery.forest")
    mod = ob.modifiers.get("NatureScatter") if ob is not None else None
    if mod is None or mod.node_group is None:
        log("WARN scenery.forest or its NatureScatter missing; forest step skipped")
        return None
    ids = _scatter_ids(mod)
    want = N._proto_set(N.plant_prototypes("forest")[:6])
    cur = N._get_mod_input(mod, ids["Prototypes"])
    if cur is not None and cur.name == want.name:
        return "unchanged (%s)" % want.name
    N._set_mod_input(mod, ids["Prototypes"], want)
    return "%s -> %s" % (cur.name if cur is not None else None, want.name)


def fix_masks():
    return [rock.name for prefix in INSIDE_OUT for rock in S._rocks(prefix) if N.fix_inside_out_plants(rock)]


def abode_pines():
    if AB.DENSE_TAG != S.DENSITY_TAG:
        raise SystemExit("patch_density: abode.DENSE_TAG %r != scenery.DENSITY_TAG %r" % (AB.DENSE_TAG, S.DENSITY_TAG))
    root, coll = bpy.data.objects.get("abode.root"), bpy.data.collections.get("abode")
    if root is None or coll is None:
        log("WARN abode.root or collection abode missing; abode step skipped")
        return None
    return AB.dense_pines(coll, root)


# ---- report -------------------------------------------------------------------------------------------------

def chase_path(scene):
    """(KD tree of chase.cam positions per frame, frames, frame -> area) or None."""
    cam = bpy.data.objects.get(S.CHASE_CAM)
    if cam is None:
        return None
    frames = np.arange(scene.frame_start, scene.frame_end + 1)
    try:
        pts = CH.path_from_camera(cam, frames)
    except Exception as exc:
        log("WARN report without camera distances:", exc)
        return None
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(Vector(p), i)
    kd.balance()
    secs = []
    try:
        secs = [(s["area"], s["frame_start"], s["frame_end"])
                for s in json.loads(CH.route_camera(scene)["timeline"])["sections"]]
    except Exception as exc:
        log("WARN no timeline sections, areas unnamed:", exc)

    def area_of(f):
        for a, f0, f1 in secs:
            if f0 <= f <= f1:
                return a
        return min(secs, key=lambda s: min(abs(f - s[1]), abs(f - s[2])))[0] if secs else "?"
    return kd, frames, area_of


def new_pines(scatters):
    """(category, world position, height) of every pine the patch made: tagged empties and scatter instances."""
    out = []
    for o in bpy.data.objects:
        t = o.get(S.DENSITY_TAG)
        if t and o.instance_type == 'COLLECTION':
            m = U.world_matrix(o)
            out.append((t, m.translation.copy(), m.to_scale().z * N.PINE_HEIGHT))
    if scatters:
        dg = bpy.context.evaluated_depsgraph_get()
        for inst in dg.object_instances:
            par = inst.parent.original.name if inst.is_instance and inst.parent is not None else None
            if par in scatters:
                m = inst.matrix_world
                out.append((par, m.translation.copy(), m.to_scale().z * N.PINE_HEIGHT))
    return out


def forest_kinds():
    dg = bpy.context.evaluated_depsgraph_get()
    c = collections.Counter()
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.name == "scenery.forest":
            nm = inst.object.original.name
            c["pine" if ".pine." in nm else ("shrub" if ".shrub." in nm else nm)] += 1
    return dict(c)


def report(scene, pines):
    cp = chase_path(scene)
    by = collections.defaultdict(lambda: collections.Counter())
    areas = collections.defaultdict(lambda: collections.Counter())
    for cat, p, h in pines:
        by[cat]["pines"] += 1
        if cp is None:
            continue
        kd, frames, area_of = cp
        _, i, d = kd.find(p)
        d -= 0.8 * h
        band = "mesh<%d" % S.CARD_CLEAR if d < S.CARD_CLEAR else ("area_card" if d <= NM_BAND else "backdrop_card")
        by[cat][band] += 1
        areas[area_of(int(frames[i])) if band != "backdrop_card" else "backdrop"][band] += 1
    tot = collections.Counter()
    for cat, c in sorted(by.items()):
        log("added", cat, dict(c))
        tot.update(c)
    for a, c in sorted(areas.items()):
        log("by area (nearest frame)", a, dict(c))
    if cp is not None:
        b = (tot["area_card"] * 2 + tot["backdrop_card"]) * CARD_B
        nb = tot["mesh<%d" % S.CARD_CLEAR] * NEAR_B
        log("estimate: cards %d in area files (+ a backdrop stand-in each), %d backdrop only: ~%.2f MB gz; "
            "%d would be near 3D pines: ~%.2f MB more" % (tot["area_card"], tot["backdrop_card"], b / 1e6,
                                                          tot["mesh<%d" % S.CARD_CLEAR], nb / 1e6))
    log("total new pines", tot["pines"], "(visibility, the 1.5 px floor and the audit decide what ships)")
    return {k: dict(v) for k, v in by.items()}


# ---- main ---------------------------------------------------------------------------------------------------

def main():
    opt = options()
    scene = bpy.context.scene
    parts = opt["parts"]
    log("file", bpy.data.filepath, "parts", ",".join(parts), "dry run" if opt["dry"] else "")
    check_scatter_group()
    protos = proto_names()
    if "forest" in parts:
        log("scenery.forest before", forest_kinds())
    log("removed earlier patch objects", remove_owned(parts))
    res = {}
    anchors = {k: tuple(v)[:4] for k, v in W.ANCHORS.items()}
    dens = [p for p in ("range", "islands", "islets") if p in parts]
    if dens:
        res.update(S.build_density(scene, U.get_collection(S.KEY, scene=scene), anchors, parts=dens))
    if "abode" in parts:
        res["abode"] = abode_pines()
    if "forest" in parts:
        res["forest"] = forest_pines_only()
        log("scenery.forest", res["forest"], "after", forest_kinds())
    if "masks" in parts:
        res["masks"] = fix_masks()
        log("inside-out rocks fixed", len(res["masks"]), res["masks"])
    after = proto_names()
    new = sorted(k for k in after if after[k] != protos.get(k))
    if new:
        raise SystemExit("patch_density: would add or rebuild tree prototypes %s (a builder changed under the "
                         "scene); not saving" % new)
    scatters = set(res.get("range") or ())
    report(scene, new_pines(scatters))
    log("result", json.dumps(res, default=str))
    if opt["dry"]:
        log("dry run: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
