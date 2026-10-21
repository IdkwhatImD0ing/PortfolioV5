"""Round 7, condor lane: replace the procedural Divine Condor 神雕 (it read as fake, and it stood on the terrace) with
the prepared real-looking bird on a rock crag beyond the summit's west rail (sect/areas/summit.py divine_condor,
sect/lib/condor_props.py), and save. Run on the cloud box, on a COPY of the chase file:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r7_condor.py [-- --dry]

Needs assets/web/condor_mesh.npz, condor_diff.jpg and condor_nrm.png (sect/lib/condor_props.py -- prep; the wrapper
uploads assets/web). Stops before touching the file when one is missing.

Removes (logged 'PATCH remove'): every object tagged sect_item = divine_condor or named summit.condor*, i.e. the
round-2 bird (summit.condor Empty, .body, .feathers, .head, .legs), its rock summit.condor_rock, and this patch's
own previous output; unshared meshes go with them (the shared boulder meshes stay).
Adds (logged 'PATCH add'), all children of summit.root, collection 'summit':
    summit.condor_crag          karst column (rock_cliff, nature_soil_moss), foot 45 m down in the summit cliff
    summit.condor_crag_rock(.001)  two small boulders on its dome (shared nature.boulder meshes)
    summit.condor_cap           the capstone boulder, the bird's perch
    summit.condor_bird          the bird: 24k triangles, material props_condor (new on the first run)
Nothing else is moved, renamed or changed.

Checks (any failure: no save, exit code 1): the five objects and nothing else new; only M.props_condor may be a new
material and its two images load; no empty material slots; bird <= 25k triangles; no toe more than 6 cm above the
capstone and no boulder edge hovering over its support; the crag's foot is inside the summit cliff; the crag stays
>= 3 m outside the balustrade and >= 12 m from the camera path (frames 1535-1729); at the contact hold (frame
1647) the bird is fully in frame and >= 50 px tall.

Idempotent: a second run removes the first run's objects and builds the same names and geometry again.

CACHES: the new names are not in the web caches (and the removed ones are stale there), so the summit chunk needs
the audit path before its bake (the patch prints 'PATCH CACHES audit-needed'):
    export_web.py -- audit --profile full   (or cache_add for these owners), then -- chunks,meta --profile full
    bake_web.py -- bakefull --profile full --chunks summit,backdrop
No vegetation instances are added (the trees bake is not affected).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import summit as S  # noqa: E402
from sect.lib import condor_props as CP  # noqa: E402
from sect.lib import materials as M  # noqa: E402

ROOT_EMPTY = "summit.root"
COLL = "summit"
CAMERA = "chase.cam"
HOLD_FRAME = 1647
PATH_FRAMES = (1535, 1729)
RAIL_R = S.TERRACE_R - 0.6
EXPECTED = ("summit.condor_crag", "summit.condor_crag_rock", "summit.condor_crag_rock.001", "summit.condor_cap",
            "summit.condor_bird")
BIRD_TRI_CAP = 25000
MAX_TOE_GAP = S.CONDOR_MAX_TOE_GAP
MAX_HOVER = 0.08          # m: a boulder's sole may not sit higher than this above its support
MIN_RAIL_GAP = 3.0        # m between the crag (at terrace height) and the balustrade
MIN_PATH_GAP = 12.0       # m between the camera path and the crag / bird boxes
MIN_HOLD_PX = 50


def log(*a):
    print("PATCH", *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="build and check, do not save")
    a, _rest = ap.parse_known_args(argv)
    return a


def ours(ob):
    return ob.get(S.CONDOR_TAG) == S.CONDOR_ITEM or ob.name.startswith("summit.condor")


def remove_previous():
    obs = [o for o in bpy.data.objects if ours(o)]
    meshes = set()
    for o in sorted(obs, key=lambda o: o.name):
        if o.type == 'MESH' and o.data is not None and o.data.get("sect_shared") is None:
            meshes.add(o.data.name)
        log("remove", o.name, o.type)
        bpy.data.objects.remove(o, do_unlink=True)
    gone = 0
    for m in list(bpy.data.meshes):
        if (m.name in meshes or m.name.startswith("summit.condor")) and m.users == 0:
            bpy.data.meshes.remove(m)
            gone += 1
    return len(obs), gone


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def world_box(ob):
    Mw = ob.matrix_world
    pts = [Mw @ Vector(c) for c in ob.bound_box]
    return (Vector(tuple(min(p[k] for p in pts) for k in range(3))),
            Vector(tuple(max(p[k] for p in pts) for k in range(3))))


def r3(v):
    return tuple(round(x, 2) for x in v)


def world_tree(ob):
    """BVH of ``ob``'s mesh in world space."""
    Mw = ob.matrix_world
    me = ob.data
    return BVHTree.FromPolygons([Mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def top_below(tree, p, above=3.0):
    """Height of the support's first surface below p + ``above`` (straight down), or None."""
    h = tree.ray_cast(Vector((p.x, p.y, p.z + above)), Vector((0.0, 0.0, -1.0)))
    return None if h[0] is None else h[0].z


def main():
    a = args()
    fails = []
    root = bpy.data.objects.get(ROOT_EMPTY)
    coll = bpy.data.collections.get(COLL)
    cam = bpy.data.objects.get(CAMERA)
    if root is None or coll is None or cam is None:
        raise RuntimeError("%s / collection %s / %s not found; is this the chase file?" % (ROOT_EMPTY, COLL, CAMERA))
    miss = CP.missing_assets()
    if miss:
        raise RuntimeError("condor assets missing, nothing changed: %s" % miss)
    sc = bpy.context.scene
    f0 = sc.frame_current
    removed, meshes_gone = remove_previous()
    n_obj = len(bpy.data.objects)
    mats0 = {m.name for m in bpy.data.materials}
    imgs0 = {i.name for i in bpy.data.images}
    bird = S.divine_condor(coll, root, log=lambda *x: log("condor", *x))
    bpy.context.view_layer.update()
    new = sorted((o for o in bpy.data.objects if ours(o)), key=lambda o: o.name)
    names = tuple(o.name for o in new)
    if len(bpy.data.objects) - n_obj != len(EXPECTED) or names != tuple(sorted(EXPECTED)):
        fails.append("objects: expected %s, got %s (+%d)" % (sorted(EXPECTED), names, len(bpy.data.objects) - n_obj))
    new_mats = sorted({m.name for m in bpy.data.materials} - mats0)
    if any(m != M.PREFIX + CP.MAT for m in new_mats):
        fails.append("unexpected new materials %s" % new_mats)
    new_imgs = sorted({i.name for i in bpy.data.images} - imgs0)
    log("new materials", new_mats, "new images", new_imgs)
    mat = bpy.data.materials.get(M.PREFIX + CP.MAT)
    imgs = [n.image for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"] if mat else []
    if len(imgs) != 2 or any(i is None or i.size[0] == 0 for i in imgs):
        fails.append("props_condor images missing or empty: %s" % [(i.name, tuple(i.size)) if i else None for i in imgs])
    else:
        log("props_condor images", [(i.name, tuple(i.size), i.filepath) for i in imgs])
    for o in new:
        slots = [s.material.name if s.material else None for s in o.material_slots]
        lo, hi = world_box(o)
        log("add", o.name, "mesh", o.data.name, "tris", tris(o.data), "slots", slots,
            "parent", o.parent.name if o.parent else None, "world box", r3(lo), r3(hi))
        if None in slots or not slots:
            fails.append("%s has an empty material slot" % o.name)
    if bird is None or bird.name != "summit.condor_bird":
        fails.append("divine_condor did not return the bird")
        bird = bpy.data.objects.get("summit.condor_bird")
    t = tris(bird.data)
    if t > BIRD_TRI_CAP:
        fails.append("bird has %d triangles > %d" % (t, BIRD_TRI_CAP))
    if [s.material.name if s.material else None for s in bird.material_slots] != [M.PREFIX + CP.MAT]:
        fails.append("bird material is not %s" % CP.MAT)
    if bird.data.uv_layers.get("UVMap") is None or not bird.data.uv_layers["UVMap"].active_render:
        fails.append("bird has no active-render 'UVMap'")
    dg = bpy.context.evaluated_depsgraph_get()
    ourn = set(names)
    # grounding: every toe of the bird on the capstone, the sole of every boulder on the crag (support-only BVHs, so
    # a toe's own sole lying on the rock cannot hide the rock from the ray)
    trees = {n: world_tree(bpy.data.objects[n]) for n in ("summit.condor_cap", "summit.condor_crag")}
    Mb = bird.matrix_world
    gaps = []
    for x, y in CP.toe_points():
        p = Mb @ Vector((x, y, 0.0))
        z = top_below(trees["summit.condor_cap"], p, above=1.0)
        gaps.append(99.0 if z is None else p.z - z)
    log("bird toes", len(gaps), "highest toe above the capstone %.3f m, deepest in it %.3f m" % (max(gaps), -min(gaps)))
    if max(gaps) > MAX_TOE_GAP:
        fails.append("a toe floats %.3f m above the capstone" % max(gaps))
    for nm in ("summit.condor_cap", "summit.condor_crag_rock", "summit.condor_crag_rock.001"):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        Mw = ob.matrix_world
        zs = [v.co.z for v in ob.data.vertices]
        z0, z1 = min(zs), max(zs)
        sole = [Mw @ v.co for v in ob.data.vertices if v.co.z < z0 + 0.06 * (z1 - z0)]
        hov = []
        for p in sole:
            z = top_below(trees["summit.condor_crag"], p)
            hov.append(99.0 if z is None else p.z - z)
        log("grounding", nm, "sole vertices", len(sole), "highest above the crag %.3f m (negative: sunk in)" % max(hov))
        if max(hov) > MAX_HOVER:
            fails.append("%s hovers %.3f m above the crag" % (nm, max(hov)))
    # the crag's foot is in the cliff: along its azimuth, the summit cliff face (seen from outside) lies inside the
    # crag's footprint at depth, and its top stands free of the rail
    crag = bpy.data.objects["summit.condor_crag"]
    R = root.matrix_world
    Mc = R.inverted() @ crag.matrix_world
    cv = [Mc @ v.co for v in crag.data.vertices]
    r0, a0 = S.CONDOR_SITE
    u = Vector((math.cos(a0), math.sin(a0), 0.0))
    for z in (-4.0, -10.0, -20.0, -30.0):
        band = [p.xy.length for p in cv if abs(p.z - z) < 1.5]
        c_in = min(band) if band else None
        o = R @ (u * 90.0 + Vector((0.0, 0.0, z)))
        d = R.to_3x3() @ -u
        rc = None
        oo = o.copy()
        for _ in range(8):
            hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, oo, d, distance=200.0)
            if not hit:
                break
            if ob.name not in ourn:
                rc = ((R.inverted() @ loc).xy.length, ob.name)
                break
            oo = loc + d * 0.002
        log("at local z %.0f: summit cliff face r %s (%s), crag inner side r %s (centre r %.1f)" % (
            z, None if rc is None else round(rc[0], 2), None if rc is None else rc[1],
            None if c_in is None else round(c_in, 2), r0))
        if z <= -20.0 and (rc is None or c_in is None or rc[0] < c_in + 0.5):
            fails.append("crag foot not inside the cliff at z %.0f (cliff %s, crag inner r %s)" % (z, rc, c_in))
    # rail clearance at terrace height (the crag's inner side, from its mesh)
    inner = min(p.xy.length for p in cv if -1.0 < p.z < S.CONDOR_CRAG["top"] + 1.5)
    log("crag inner side r %.2f, balustrade r %.2f: gap %.2f m" % (inner, RAIL_R, inner - RAIL_R))
    if inner - RAIL_R < MIN_RAIL_GAP:
        fails.append("crag within %.2f m of the balustrade" % (inner - RAIL_R))
    # camera path clearance (nearest surface point of the crag and the bird) and the hold read
    boxes = {o.name: world_box(o) for o in (crag, bird)}
    near = {"summit.condor_crag": trees["summit.condor_crag"], bird.name: world_tree(bird)}
    dmin = {k: (1e9, None) for k in near}
    for f in range(PATH_FRAMES[0], PATH_FRAMES[1] + 1):
        sc.frame_set(f)
        p = cam.matrix_world.translation.copy()
        for k, tr in near.items():
            hit = tr.find_nearest(p)
            if hit[0] is not None and hit[3] < dmin[k][0]:
                dmin[k] = (hit[3], f)
    log("closest camera approach (frames %d-%d):" % PATH_FRAMES,
        {k: "%.1f m at frame %d" % v for k, v in dmin.items()})
    if min(v[0] for v in dmin.values()) < MIN_PATH_GAP:
        fails.append("camera path passes %.1f m from the crag/bird" % min(v[0] for v in dmin.values()))
    sc.frame_set(HOLD_FRAME)
    bpy.context.view_layer.update()
    res = (sc.render.resolution_x, sc.render.resolution_y)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    lo, hi = boxes[bird.name]
    pts = [world_to_camera_view(sc, cam, Vector((x, y, z))) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    xs, ys = [p.x * 1600 for p in pts], [(1 - p.y) * 900 for p in pts]
    inside = all(0 <= x <= 1600 for x in xs) and all(0 <= y <= 900 for y in ys) and all(p.z > 0 for p in pts)
    dist = ((lo + hi) / 2 - cam.matrix_world.translation).length
    log("hold %d: bird box on screen x %.0f-%.0f y %.0f-%.0f (%.0f px tall), %.1f m from the camera, in frame %s" % (
        HOLD_FRAME, min(xs), max(xs), min(ys), max(ys), max(ys) - min(ys), dist, inside))
    if not inside or max(ys) - min(ys) < MIN_HOLD_PX:
        fails.append("the bird does not read at the hold (in frame %s, %.0f px)" % (inside, max(ys) - min(ys)))
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.frame_set(f0)
    log("removed", removed, "objects and", meshes_gone, "meshes; added", len(new), "objects:", list(names),
        "objects now", len(bpy.data.objects))
    log("CACHES audit-needed: new %s, removed the round-2 condor names; export_web.py -- audit --profile full, then "
        "-- chunks,meta --profile full; bake_web.py -- bakefull --profile full --chunks summit,backdrop" % list(names))
    if fails:
        for f in fails:
            log("FAIL", f)
        log("checks failed: not saved")
        sys.exit(1)
    log("all checks passed")
    if a.dry:
        log("dry run: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath)


main()
