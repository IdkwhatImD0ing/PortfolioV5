"""The Divine Condor 神雕 (The Return of the Condor Heroes): a real-looking bird for the summit, from a downloaded model.

The procedural condor (metaball body, feather slabs) read as fake, so the bird is now a prepared copy of
"Dark Vulture - Scarred Bald-Headed Horror Bird" by Pigcraft (https://sketchfab.com/3d-models/
09cb4ac72a7c4eab95355eef28808310, CC-BY 4.0; credit in assets/CREDITS.md): a bald, hook-beaked, ragged black
vulture standing with folded wings, the closest downloadable match to the novel's huge, ugly, proud condor. The raw
download (glTF, ~2 M triangles) stays in assets/dl_condor/dark_vulture/ with its info.json.

prep (once, on the cloud box; the wrapper copies out/ back to the PC, then move the three files to assets/web/):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background --factory-startup \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/condor_props.py -- prep \
        [--src assets/dl_condor/dark_vulture/model.glb --out out/tmp/condor_prep]

    joins and welds the model, scales it to BIRD_HEIGHT with the feet on the origin and the beak toward -Y,
    collapse-decimates a copy to BIRD_TRIS triangles, unwraps it (Smart UV) and bakes the full model onto it with
    Cycles (selected to active): base colour -> condor_diff.jpg, tangent normals -> condor_nrm.png. The low mesh is
    written to condor_mesh.npz (co: vertices, tri: triangles, uv: one (u, v) per triangle corner), smooth shaded,
    the normals the bake used. assets/web is uploaded to the box by tools/rblender.py (files under 5 MB).

build: bird(collection, name, ...) makes the mesh object with the 'props_condor' material (UV image textures, the
shape the web bake keeps: it bakes the mesh's active-render UV map as 'UVMap'). Missing files raise, so a build
never silently ships the wrong bird.
"""

import math
import os
import sys

import bpy
import numpy as np

if __package__ in (None, ""):                       # run as a script (prep): make 'sect' importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from sect.lib import materials as M  # noqa: E402
    from sect.lib import util as U  # noqa: E402
else:
    from . import materials as M
    from . import util as U

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MESH_FILE = "condor_mesh.npz"        # in materials.SCAN_DIR (assets/web)
DIFF_FILE = "condor_diff.jpg"
NRM_FILE = "condor_nrm.png"
BIRD_HEIGHT = 1.7      # m, feet to crown: about 1.6 x a perched Andean condor, "taller than a man" (ch. 23)
BIRD_TRIS = 24000      # one object: within the bake's full-detail size near a hold (bake_web.HOLD_FULL_TRIS 30000)
TEX = 2048             # baked colour map
NRM_TEX = 1024         # baked normal map (PNG; 2048 is 5.8 MB, over rblender's 5 MB upload limit)
MAT = "props_condor"


def log(*a):
    print("CONDOR", *a, flush=True)


# --------------------------------------------------------------------------------------------------------------
# material
# --------------------------------------------------------------------------------------------------------------

def _mat_condor(g):
    """The prepared colour and normal maps on the mesh's UV map; matte, a faint sheen on the feathers. Without the
    files (a PC without assets/web) it falls back to flat condor black, and bird() refuses to build."""
    uv = g.coord("uv")
    img = M.scan_image(DIFF_FILE)
    nimg = M.scan_image(NRM_FILE, data=True)
    col = g.image(img, uv) if img is not None else "#1f1c1b"
    nrm = None
    if nimg is not None:
        nm = g.node("ShaderNodeNormalMap", {"Color": g.image(nimg, uv), "Strength": 1.0}, space='TANGENT')
        nrm = nm.outputs[0]
    kw = dict(base_color=col, roughness=0.78, sheen_weight=0.25, sheen_roughness=0.6)
    if nrm is not None:
        kw["normal"] = nrm
    g.output(g.principled(**kw))
    g.viewport("#2a2523", roughness=0.8)


M.register(MAT, _mat_condor)


# --------------------------------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------------------------------

def asset_paths():
    return [os.path.join(M.SCAN_DIR, f) for f in (MESH_FILE, DIFF_FILE, NRM_FILE)]


def missing_assets():
    return [p for p in asset_paths() if not os.path.isfile(p)]


def _load():
    miss = missing_assets()
    if miss:
        raise RuntimeError("condor assets missing (run sect/lib/condor_props.py -- prep, then copy to assets/web): %s"
                           % miss)
    with np.load(os.path.join(M.SCAN_DIR, MESH_FILE), allow_pickle=False) as d:
        return d["co"].astype(np.float32), d["tri"].astype(np.int64), d["uv"].astype(np.float32)


def toe_points(below=0.04):
    """(x, y) of the model's sole vertices (z < ``below`` m, model frame): where the toes meet the perch."""
    co = _load()[0]
    return [(float(x), float(y)) for x, y, z in co if z < below]


def bird_mesh(name):
    """New mesh ``name`` from condor_mesh.npz: model frame (feet centre on the origin, beak toward -Y, z up,
    BIRD_HEIGHT tall), UV map 'UVMap', smooth shaded, material props_condor."""
    co, tri, uv = _load()
    me = bpy.data.meshes.new(name)
    me.from_pydata(co.tolist(), [], tri.tolist())
    lay = me.uv_layers.new(name="UVMap")
    if len(lay.data) != len(uv):
        raise RuntimeError("condor mesh: %d corners but %d UVs" % (len(lay.data), len(uv)))
    lay.data.foreach_set("uv", uv.ravel())
    lay.active_render = True
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.validate(verbose=False)
    me.update()
    if len(me.polygons) != len(tri):
        raise RuntimeError("condor mesh: validate dropped faces (%d -> %d)" % (len(tri), len(me.polygons)))
    U.set_materials(me, [MAT])
    return me


def bird(collection, name, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), parent=None):
    """The condor object (see bird_mesh). Returns it."""
    me = bird_mesh(name)
    return U.object_from_mesh(name, me, collection, location=location, rotation=rotation, parent=parent)


# --------------------------------------------------------------------------------------------------------------
# prep (run on the box, factory startup)
# --------------------------------------------------------------------------------------------------------------

def _select(objs, active):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _bake_image(name, size, data):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False, is_data=data)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    img.generated_color = (0.5, 0.5, 1.0, 1.0) if data else (0.1, 0.1, 0.1, 1.0)
    return img


def prep(src, out_dir, height=BIRD_HEIGHT, tris=BIRD_TRIS):
    import bmesh
    from mathutils import Matrix
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=src)
    hi = [o for o in sc.objects if o.type == 'MESH']
    if not hi:
        raise RuntimeError("no meshes in " + src)
    bpy.context.view_layer.update()
    pts = np.array([tuple(o.matrix_world @ v.co) for o in hi for v in o.data.vertices], np.float64)
    lo_, hi_ = pts.min(0), pts.max(0)
    s = height / (hi_[2] - lo_[2])
    feet = pts[pts[:, 2] < lo_[2] + 0.03 * (hi_[2] - lo_[2])]
    fx, fy = feet[:, 0].mean(), feet[:, 1].mean()
    T = Matrix.Scale(s, 4) @ Matrix.Translation((-fx, -fy, -lo_[2]))
    log("source", src, "meshes", len(hi), "verts", len(pts), "box", lo_.round(3).tolist(), hi_.round(3).tolist(),
        "scale %.4f" % s, "feet centre", round(fx, 4), round(fy, 4))
    # the high model: world transform baked into its meshes (each keeps its own UVs and material)
    for o in hi:
        o.data.transform(T @ o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in [o for o in sc.objects if o.type != 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)
    # the low model: welded copy of everything, collapse-decimated, smooth, new UVs
    bm = bmesh.new()
    for o in hi:
        bm.from_mesh(o.data)
    n_hi = sum(len(f.verts) - 2 for f in bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    for lay in list(bm.loops.layers.uv.values()):
        bm.loops.layers.uv.remove(lay)
    me = bpy.data.meshes.new("condor_low")
    bm.to_mesh(me)
    bm.free()
    low = bpy.data.objects.new("condor_low", me)
    sc.collection.objects.link(low)
    mod = low.modifiers.new("dec", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = tris / float(n_hi)
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(low.evaluated_get(dg))
    low.modifiers.clear()
    low.data = me2
    bpy.data.meshes.remove(me)
    me2.name = "condor_low"
    bm = bmesh.new()
    bm.from_mesh(me2)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(me2)
    bm.free()
    me2.validate(verbose=False)                # drops the odd duplicate face, so the build's validate keeps all
    me2.polygons.foreach_set("use_smooth", [True] * len(me2.polygons))
    me2.update()
    log("high triangles", n_hi, "low triangles", len(me2.polygons), "low verts", len(me2.vertices))
    _select([low], low)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    me2.uv_layers[0].name = "UVMap"
    # bake the high model's colour and normals onto it
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = 'GPU'
                break
    except Exception as e:  # noqa: BLE001
        log("WARN GPU setup", e)
    sc.cycles.samples = 16
    mat = bpy.data.materials.new("condor_bake_target")
    mat.use_nodes = True
    tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
    mat.node_tree.nodes.active = tn
    me2.materials.clear()
    me2.materials.append(mat)
    diff = _bake_image("condor_diff", TEX, False)
    nrm = _bake_image("condor_nrm", NRM_TEX, True)
    _select(hi + [low], low)
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = 0.03 * height / 1.7
    bk.max_ray_distance = 0.12 * height / 1.7
    bk.margin = 16
    bk.use_clear = True
    tn.image = diff
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_selected_to_active=True,
                        cage_extrusion=bk.cage_extrusion, max_ray_distance=bk.max_ray_distance, margin=16)
    log("baked colour")
    tn.image = nrm
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', use_selected_to_active=True,
                        cage_extrusion=bk.cage_extrusion, max_ray_distance=bk.max_ray_distance, margin=16)
    log("baked normals")
    p_diff = os.path.join(out_dir, DIFF_FILE)
    diff.file_format = 'JPEG'
    diff.save(filepath=p_diff, quality=90)
    p_nrm = os.path.join(out_dir, NRM_FILE)
    nrm.filepath_raw = p_nrm
    nrm.file_format = 'PNG'
    nrm.save()
    # the mesh file: vertices, triangles, per-corner UVs
    if any(len(p.vertices) != 3 for p in me2.polygons):
        raise RuntimeError("low mesh is not all triangles")
    co = np.empty(len(me2.vertices) * 3, np.float32)
    me2.vertices.foreach_get("co", co)
    tri = np.empty(len(me2.loops), np.int32)              # every face is a triangle: loops in face order
    me2.loops.foreach_get("vertex_index", tri)
    uv = np.empty(len(me2.loops) * 2, np.float32)
    me2.uv_layers["UVMap"].data.foreach_get("uv", uv)
    p_mesh = os.path.join(out_dir, MESH_FILE)
    np.savez_compressed(p_mesh, co=co.reshape(-1, 3), tri=tri.reshape(-1, 3), uv=uv.reshape(-1, 2))
    box = co.reshape(-1, 3)
    log("wrote", p_mesh, os.path.getsize(p_mesh), p_diff, os.path.getsize(p_diff), p_nrm, os.path.getsize(p_nrm))
    log("low box", box.min(0).round(3).tolist(), box.max(0).round(3).tolist(), "triangles", len(tri) // 3)


if __name__ == "__main__":
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep"])
    ap.add_argument("--src", default="assets/dl_condor/dark_vulture/model.glb")
    ap.add_argument("--out", default="out/tmp/condor_prep")
    ap.add_argument("--tris", type=int, default=BIRD_TRIS)
    a = ap.parse_args(argv)
    if a.cmd == "prep":
        prep(os.path.join(PROJECT, a.src), os.path.join(PROJECT, a.out), tris=a.tris)
