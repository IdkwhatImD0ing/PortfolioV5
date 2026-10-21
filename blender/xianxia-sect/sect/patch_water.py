"""Waterfalls in out/sect_chase.blend (waterfall plan steps B1/B2): the changes nature.waterfall, world.build_waterfalls
and scenery.build_islands / build_range_falls now make on a full rebuild, applied to the finished scene. Run on the
cloud box, never locally:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_water.py -- [KEY=value ...]

Parts (all by default; PARTS=layers,extend runs some):
- layers: every waterfall sheet (a mesh with a 'waterfall' material under a fall root: a nature.waterfall root, which
  carries 'foot', or a world.waterfall* root) gets obj['water_layer'] (nature.sheet_roles of its place among its
  root's sheets; build order = name order) and obj['exit_speed'] (m/s over the lip, fitted to its arc when the scene
  has none). The side curtain and the front veil move to nature.SHEET_FRONT m in front of the core (location y in
  the root's frame, set absolutely; they sat 6 cm apart per sheet, the world falls' veil 0.3 m). The web export
  (bake_web.py water) writes the role to COLOR_0.b and the speed into the fall time (TEXCOORD_1).
- extend: island and range falls (roots EXTEND_PREFIXES) whose sheets end above the cloud sea (W.CLOUD_SEA_Z;
  scenery.py capped them at 260 / 320 m, so the high islands' falls ended 30-160 m up in the air) get rows added
  under their last row, down to W.CLOUD_SEA_Z - scenery.FALL_UNDER: the same columns, widening at the sheet's own
  rate (lip row to last row; never narrowing) and following its ballistic arc (exit speed), EXT_ROW_M apart. The rows above stay exactly as they
  are (a full rebuild draws the sheet at the new height instead: same lip, width and speed, its wobble stretched).
  root['foot'] follows. Their mist volumes (film only; the web skips 'mist') stay where they are.
- abode: under every nature.waterfall root that has them, the baked foam disc ('<root>.foam', nature_foam) and the
  splash blobs ('<root>.splash', nature_splash) are deleted (the web draws an animated foam ring and spray there;
  baked, they were a frozen white lump in abode.glb), and nature.plunge_stones puts half-sunk boulders around the
  landing line, children of the root (so the abode's 'fact:0' Waterfall hotspot keeps baked geometry: its node in
  abode.glb held only the foam and splash), tagged obj['sect_water'] = 'plunge'. In the sect: abode.waterfall only.

Idempotent: layers set absolute values, extend skips sheets already ending in the cloud sea, abode deletes the stones
it made before (sect_water = 'plunge') and makes them again from the same generator. It never moves an object that
is not a waterfall sheet, and reshapes only the sheets it extends (rows added under the old ones). Prints WATER lines
with the counts; DRY_RUN=1 reports without saving.

Overrides after "--": KEY=value for an upper-case constant of this script (EXT_ROW_M=2.0), nature.KEY=value for
sect/lib/nature.py (nature.SHEET_FRONT="{'core': 0.0, 'side': 0.2, 'veil': 0.5}"), scenery.FALL_UNDER=30,
PARTS=layers,extend and DRY_RUN=1.

Afterwards (box, in this order; the other patches first: patch_density, then patch_life (it must follow
patch_density), patch_rock_life / patch_nature_look in any order, then this one):
  1. export_web.py -- audit --profile full    the plunge stones are new objects (invisible to the bake until the
     audit has seen them). The water export alone does not need it: the sheets keep their names, so the old
     vis_cache.npz / chunks.npz still match them.
  2. export_web.py -- chunks,meta --profile full    meta.json's waterfall lips / feet / corners (the extended falls
     end in the cloud sea now, the layers moved; the page's foot effects read them).
  3. bake_web.py -- bakefull,water --profile full --chunks abode,<the other changed areas>,backdrop    abode: the
     foam and splash are gone and the stones are in. 'water' writes every <area>_water.glb (it always does all).
  4. bake_trees.py plan,build, then tools/sect_pack.py --profile full.
"""
import ast
import collections
import json
import math
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import scenery as S  # noqa: E402
from sect import world as W  # noqa: E402
from sect.lib import nature as N  # noqa: E402

PARTS = ("layers", "extend", "abode")
EXTEND_PREFIXES = ("scenery.island.fall", "scenery.fall")
EXT_ROW_M = 1.0             # m between the added rows (the old rows are 0.5 m; the export thins every sheet anyway)
EXT_MIN = 1.0               # m: shorter extensions are skipped
OLD_STEP = {"nature": 0.06, "world": 0.3}   # m per sheet index: the layer offsets the scene was built with
MOVE_SLACK = 0.02           # m: a sheet whose y is neither the old nor the new offset (hand-placed) is left alone
G_ACC = 9.81
FOAM_MATS = ("nature_foam", "nature_splash")


def log(*a):
    print("WATER", *a, flush=True)


def options():
    """KEY=value arguments after '--' (module docstring). Unknown keys stop the run."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(parts=PARTS, dry=False)
    mods = {"nature": N, "scenery": S}
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("patch_water: not KEY=value: %r" % a)
        if k == "PARTS":
            opt["parts"] = tuple(p.strip() for p in v.split(",") if p.strip())
            bad = [p for p in opt["parts"] if p not in PARTS]
            if bad:
                raise SystemExit("patch_water: unknown parts %s (known: %s)" % (bad, ",".join(PARTS)))
            continue
        if k == "DRY_RUN":
            opt["dry"] = bool(ast.literal_eval(v))
            continue
        mod_name, dot, key = k.partition(".")
        if dot:                                     # nature.KEY / scenery.KEY
            mod = mods.get(mod_name)
            if mod is None or not key.isupper() or not hasattr(mod, key):
                raise SystemExit("patch_water: no constant %s" % k)
            setattr(mod, key, ast.literal_eval(v))
            log("override", k, "=", getattr(mod, key))
        else:                                       # this script's own (blender --python runs it as __main__)
            if not k.isupper() or k not in globals() or k in ("PARTS",):
                raise SystemExit("patch_water: no constant %s" % k)
            globals()[k] = ast.literal_eval(v)
            log("override", k, "=", globals()[k])
    return opt


# ---- the scene's falls --------------------------------------------------------------------------------------

def is_sheet(ob):
    return ob.type == 'MESH' and any(s.material is not None and "waterfall" in s.material.name
                                     for s in ob.material_slots)


def builder_of(root):
    """'nature' (nature.waterfall roots carry 'foot'), 'world' (world.waterfall*) or None."""
    if "foot" in root:
        return "nature"
    if re.match(r"^world\.waterfall(\.\d{3})?$", root.name):
        return "world"
    return None


def fall_roots():
    """{root: [its waterfall sheets in build order]} for every fall root in the file (linked data left out)."""
    out = collections.defaultdict(list)
    for ob in bpy.data.objects:
        if ob.library is not None or ob.parent is None or not is_sheet(ob):
            continue
        if builder_of(ob.parent) is None:
            continue
        out[ob.parent].append(ob)
    for sheets in out.values():
        sheets.sort(key=lambda o: o.name)
    return dict(out)


def mesh_co(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def rows_of(co):
    """(row z values descending, row index per vertex) of a row-built sheet (each row has one local z)."""
    z = np.round(co[:, 2], 4)
    uz, inv = np.unique(z, return_inverse=True)
    order = np.argsort(-uz)
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    return uz[order], rank[inv]


def fit_exit_speed(co):
    """Exit speed (m/s) from the sheet's arc: the mean y of each falling row (local z <= 0, lip at the origin)
    against sqrt(2 d / g); the sheets were built as y = -v sqrt(2 d / g) + c. None when it cannot be fitted."""
    uz, rid = rows_of(co)
    d = -uz
    keep = d > 0.25
    if keep.sum() < 3:
        return None
    ym = np.array([co[rid == k, 1].mean() for k in range(len(uz))])
    slope = np.polyfit(np.sqrt(2.0 * d[keep] / G_ACC), ym[keep], 1)[0]
    v = -float(slope)
    return v if 0.05 < v < 20.0 else None


# ---- parts --------------------------------------------------------------------------------------------------

def set_layers(roots):
    n = collections.Counter()
    for root, sheets in sorted(roots.items(), key=lambda kv: kv[0].name):
        kind = builder_of(root)
        roles = N.sheet_roles(len(sheets))
        for k, (ob, role) in enumerate(zip(sheets, roles)):
            ob["water_layer"] = role
            n[role] += 1
            if "exit_speed" not in ob:
                v = fit_exit_speed(mesh_co(ob.data))
                if v is not None:
                    ob["exit_speed"] = v
                    n["exit_speed_fitted"] += 1
                else:
                    n["exit_speed_missing"] += 1
            y_new = -N.SHEET_FRONT[role]
            y_old = -OLD_STEP[kind] * k
            y = ob.location.y
            if abs(y - y_new) < 1e-6:
                n["already_placed"] += 1
                continue
            if abs(y - y_old) > MOVE_SLACK:
                log("WARN left in place (y %.3f is neither the built %.3f nor the new %.3f):" % (y, y_old, y_new),
                    ob.name)
                n["left_in_place"] += 1
                continue
            ob.location.y = y_new
            n["moved"] += 1
    return dict(n)


def extend_sheet(ob, target_z):
    """Rows added under the sheet's last row down to world z ``target_z`` (see the module docstring). Returns a
    report dict, or None when the sheet already ends there or is not a row-built grid."""
    me = ob.data
    M = ob.matrix_world
    if abs(M[2][0]) > 1e-4 or abs(M[2][1]) > 1e-4 or M[2][2] <= 0.0:
        log("WARN not upright, not extended:", ob.name)
        return None
    sz = M[2][2]
    co = mesh_co(me)
    nv = len(co)
    zmin = float(co[:, 2].min())
    bottom = np.nonzero(np.abs(co[:, 2] - zmin) < 1e-4)[0]
    foot_z = (M @ Vector((float(co[bottom, 0].mean()), float(co[bottom, 1].mean()), zmin))).z
    if foot_z <= W.CLOUD_SEA_Z + 1e-3:
        return None
    m = len(bottom)
    if m < 2 or not np.array_equal(bottom, np.arange(nv - m, nv)) or nv % m:
        log("WARN not a row-built grid (bottom row %d vertices, %d in all), not extended:" % (m, nv), ob.name)
        return None
    if me.users > 1:
        log("WARN mesh %s is shared (%d users), not extended:" % (me.name, me.users), ob.name)
        return None
    d_bot = -zmin
    d_new = d_bot + (foot_z - target_z) / sz
    if d_new - d_bot < EXT_MIN or d_bot <= 0.0:
        return None
    uz, rid = rows_of(co)
    top = co[rid == 0]
    w_lip = float(np.ptp(top[:, 0]))
    xb, yb = co[bottom, 0], co[bottom, 1]
    w_bot = float(np.ptp(xb))
    cx = float(xb.mean())
    rate = max(0.0, (w_bot - w_lip) / d_bot)      # widening per metre of drop (the wobble can hide it: never taper)
    v = ob.get("exit_speed") or fit_exit_speed(co) or 1.3
    nrow = int(math.ceil((d_new - d_bot) / EXT_ROW_M))
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    prev = [bm.verts[i] for i in range(nv - m, nv)]
    y0 = -v * math.sqrt(2.0 * d_bot / G_ACC)
    for j in range(1, nrow + 1):
        d = d_bot + (d_new - d_bot) * j / nrow
        k = (w_bot + rate * (d - d_bot)) / max(w_bot, 1e-6)
        dy = -v * math.sqrt(2.0 * d / G_ACC) - y0
        row = [bm.verts.new((cx + (float(x) - cx) * k, float(y) + dy, -d)) for x, y in zip(xb, yb)]
        for i in range(m - 1):
            f = bm.faces.new((prev[i], prev[i + 1], row[i + 1], row[i]))
            f.smooth = True
        prev = row
    bm.to_mesh(me)
    bm.free()
    me.update()
    return dict(name=ob.name, foot_z_old=round(foot_z, 2), foot_z_new=round(float(target_z), 2),
                drop_old=round(d_bot * sz, 2), drop_new=round(d_new * sz, 2), rows_added=nrow,
                verts_added=nrow * m, exit_speed=round(float(v), 3), widen_per_100m=round(rate * 100.0, 3))


def extend_falls(roots):
    target_z = W.CLOUD_SEA_Z - S.FALL_UNDER
    out, n = [], collections.Counter()
    for root, sheets in sorted(roots.items(), key=lambda kv: kv[0].name):
        if not root.name.startswith(EXTEND_PREFIXES):
            continue
        n["roots_checked"] += 1
        done = [r for r in (extend_sheet(ob, target_z) for ob in sheets) if r is not None]
        if not done:
            continue
        n["roots_extended"] += 1
        n["sheets_extended"] += len(done)
        n["verts_added"] += sum(r["verts_added"] for r in done)
        out += done
        if builder_of(root) == "nature":
            drop = max(r["drop_new"] for r in done)
            # the speeds the rows were drawn with (PARTS=extend alone: fitted, not yet stored on the sheet)
            fy = min(-r["exit_speed"] * math.sqrt(2.0 * drop / G_ACC) for r in done)
            root["foot"] = (0.0, fy, -drop)
    for r in out:
        log("extended", json.dumps(r))
    return dict(n), out


def _core_lip_width(ob):
    """Width (m) of the sheet's top row: the core's width at the lip, as nature.waterfall passes it to
    plunge_stones."""
    co = mesh_co(ob.data)
    uz, rid = rows_of(co)
    return float(np.ptp(co[rid == 0, 0])) * ob.matrix_world.to_scale().x


def abode_foot(roots):
    n = collections.Counter()
    for root, sheets in sorted(roots.items(), key=lambda kv: kv[0].name):
        if builder_of(root) != "nature":
            continue
        pat = re.compile(r"^%s\.(foam|splash)(\.\d{3})?$" % re.escape(root.name))
        foam = [c for c in root.children if c.type == 'MESH' and pat.match(c.name) and any(
            s.material is not None and any(f in s.material.name for f in FOAM_MATS) for s in c.material_slots)]
        stones = [c for c in root.children if c.get("sect_water") == "plunge"]
        if not foam and not stones:
            continue
        coll = root.users_collection[0] if root.users_collection else bpy.context.scene.collection
        for c in foam + stones:
            me = c.data
            n["deleted_" + ("stone" if c in stones else pat.match(c.name).group(1))] += 1
            bpy.data.objects.remove(c, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        width = _core_lip_width(sheets[0])
        made = N.plunge_stones(coll, root, tuple(root["foot"]), width, root.name)
        n["stones"] += len(made)
        log("plunge stones", root.name, "core width %.2f m" % width, [o.name for o in made])
    return dict(n)


# ---- main ---------------------------------------------------------------------------------------------------

def main():
    opt = options()
    parts = opt["parts"]
    log("file", bpy.data.filepath, "parts", ",".join(parts), "dry run" if opt["dry"] else "")
    roots = fall_roots()
    by = collections.Counter(builder_of(r) for r in roots)
    log("fall roots", len(roots), dict(by), "sheets", sum(len(s) for s in roots.values()))
    res = {}
    if "layers" in parts:
        res["layers"] = set_layers(roots)
        log("layers", json.dumps(res["layers"]))
    if "extend" in parts:
        res["extend"], _ = extend_falls(roots)
        log("extend: to z %.1f (cloud-sea top %.1f - %.1f)" % (W.CLOUD_SEA_Z - S.FALL_UNDER, W.CLOUD_SEA_Z,
                                                                S.FALL_UNDER), json.dumps(res["extend"]))
    if "abode" in parts:
        res["abode"] = abode_foot(roots)
        log("abode", json.dumps(res["abode"]))
    log("result", json.dumps(res))
    if opt["dry"]:
        log("dry run: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
