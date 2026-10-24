"""The guardian lions 石狮 (round 28): a real stone-lion scan instead of the procedural metaball lion.

The owner: "the guardian lions look really weird, can you find better assets online?" The procedural lion
(props._build_lion: metaball body, stuck-on curls) read as a toy, so props.guardian_lion now places a prepared copy
of "Stone Big Lion 01" by Game industry veteran (https://sketchfab.com/3d-models/68e7b4db10214d12bf4ae6ec53bf1e4f,
CC-BY 4.0; credit in assets/CREDITS.md): a photogrammetry scan (RealityCapture) of a Qing imperial-style white
marble lion on a xumizuo plinth with a draped brocade, 400k triangles, 8192 px colour. The raw download stays in
assets/sketchfab/lion_stone_big_01_gltf/ (git-ignored, with its info.json); the scan is the female, a cub under her
left forepaw.

The pair (the real custom, zh.wikipedia 石狮子 and the Palace Museum's bronze lions: 左雄右雌 as you come OUT of
the gate, so from outside, facing the entrance, the male is on the right; at the Forbidden City the male stands east,
his right forepaw on the embroidered ball 绣球, the female west, her left forepaw on a cub; both paws toward the axis):
    'f'  the scan as it is: the female, cub under her left forepaw (+X side of the model frame);
    'm'  the male: the scan mirrored (x -> -x), the cub cut away (the paw's sole and the brocade capped flat) and an
         embroidered ball under his right forepaw (-X side), 22 cm across at size 1, the paw gripping its top: a
         sphere carved with a geodesic lattice of ribbon bands (grooved both sides), a ring and a boss in every cell.
props.guardian_lion(mirror=False) is the male, mirror=True the female, exactly as before, so sect/areas/gate.py
(male at +X, female at -X, the lions facing -Y, out of the gate) already follows the custom.

Model frame (both): z up, the front (the face) toward -Y, the plinth's footprint centred on the origin, its sole at
z = -SINK (sunk a little into the ground, so no light line shows under the base), crown at MODEL_HEIGHT - SINK
(2.27 m at size 1, the procedural lion's height). The plinth's top (the brocade) is at about 0.85 m.

prep (once, on the cloud box; the wrapper copies out/ back to the PC, then copy the six files to assets/web/, which
the wrapper uploads; each is under its 5 MB limit):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background --factory-startup \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/lib/lion_props.py -- prep [--out out/tmp/lion_prep]

    The source is not uploaded by the wrapper (assets/sketchfab is raw downloads, and the zip is 28 MB): copy
    model_gltf.zip to the same path on the box (ssh, as tools/rblender.py connects) and unzip it there into a new
    folder 'extracted/' with an isolated Python (python3 -I, zipfile, member paths checked); nothing in it is run.
    Takes about 3 minutes on one RTX 5090 (both lions, previews included). Options: --sexes f,m, --tris, --no-ball
    (the male as the plain mirror, a cub under his paw), --no-previews.

    imports the glTF (assets/sketchfab/lion_stone_big_01_gltf/extracted/scene.gltf: the 8192 px texture; the GLB
    download has only 1024 px), joins and welds it, measures its frame (the plinth's min-area rectangle, the head's
    side), cuts the scanned ground fringe off (everything below CUT_FRAC of the height), scales it to MODEL_HEIGHT,
    builds the male from it, collapse-decimates a copy of each to LION_TRIS triangles, unwraps it (Smart UV) and
    bakes the full scan onto it with Cycles on the GPU (selected to active): colour (emission), tangent normals.
    The male's scan part and his ball bake apart (each low part takes rays only from its own high model). The colour
    is then re-textured as clean weathered white marble (re_texture): the scan's photographed lighting (its broad
    light and dark sides, the shade under the chin and the belly) is divided out (a Gaussian of DELIGHT_SIGMA = 10 cm
    at size 1 over vertices whose normals agree), its fine stone detail (grain, veins, crevice grime, carving edges)
    is kept and laid on the scene's marble palette (ALBEDO), with a little rising damp at the foot; a museum sign on
    the base's front is painted out. prep also renders preview_<sex>_<view>.png stills of the result.
    Writes lion_<f|m>_mesh.npz (co, tri, uv per corner), lion_<f|m>_diff.jpg, lion_<f|m>_nrm.png.

build: lion_mesh(sex, name, size) makes the mesh (model frame x size, UV map 'UVMap' active for render, smooth),
material 'props_lion_<sex>' (or a tinted variant for another stone, see lion_material). Missing files raise, so a
build never silently ships the old lion.
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
SRC = "assets/sketchfab/lion_stone_big_01_gltf/extracted/scene.gltf"
SEXES = ("f", "m")
MESH_FILE = "lion_%s_mesh.npz"       # in materials.SCAN_DIR (assets/web)
DIFF_FILE = "lion_%s_diff.jpg"
NRM_FILE = "lion_%s_nrm.png"
MAT = "props_lion_%s"
MODEL_HEIGHT = 2.28    # m at size 1, ground to crown: the procedural lion's height (docs/api_props.md 2.28 x size)
SINK = 0.012           # m at size 1: the plinth's cut sole sits this far below z = 0
LION_TRIS = 28000      # per lion, plinth included: within the web bake's full-detail size near a hold
#                        (bake_web.HOLD_FULL_TRIS 30000), so the gate pair keeps every triangle at its hold
TEX = 2048             # baked colour map
NRM_TEX = 2048         # baked normal map
# measured on the scan (raw glTF frame after the import: z up, 33.1 units tall)
CUT_FRAC = 0.062       # the scanned ground fringe lies below 6 % of the height (the base's lowest tier starts at 5 %)
BODY_BAND = (0.20, 0.38)   # height fractions of the plinth's straight middle (its min-area rectangle gives the frame)
HEAD_BAND = 0.85       # above this fraction: the head (its centroid lies toward the front)


def log(*a):
    print("LION", *a, flush=True)


# --------------------------------------------------------------------------------------------------------------
# material
# --------------------------------------------------------------------------------------------------------------

def _mat_lion(g, sex="f", tint=None, plinth_tint=None, top=None, rough=(0.42, 0.62)):
    """The prepared colour and normal maps on the mesh's UV map (the colour is already the clean marble albedo).
    ``tint`` / ``plinth_tint``: linear RGB factors for another stone (lion_material), the plinth's below ``top``
    (model z x size, object coordinates: bake_web carries them per vertex, so the bake keeps the split)."""
    uv = g.coord("uv")
    img = M.scan_image(DIFF_FILE % sex)
    nimg = M.scan_image(NRM_FILE % sex, data=True)
    col = g.image(img, uv) if img is not None else "#d8d3c8"
    if tint is not None or plinth_tint is not None:
        t1 = tuple(tint or (1.0, 1.0, 1.0)) + (1.0,)
        t0 = tuple(plinth_tint or tint or (1.0, 1.0, 1.0)) + (1.0,)
        if t0 != t1 and top is not None:
            z = g.sep(g.coord("object_raw"))[2]
            t = g.mix(t0, t1, g.smooth(z, top - 0.01, top + 0.01))
        else:
            t = t1
        col = g.vmath('MULTIPLY', col, t)
    # a hair rougher in the carving's hollows (dark texels), polished a little on the worn high points
    r = rough[1]
    if img is not None:
        lum = g.node("ShaderNodeRGBToBW", {"Color": col}).outputs[0]
        r = g.maprange(lum, 0.25, 0.7, rough[1], rough[0])
    kw = dict(base_color=col, roughness=r, subsurface_weight=0.06, subsurface_radius=(1.0, 0.85, 0.7),
              subsurface_scale=0.02, specular_ior_level=0.45)
    if nimg is not None:
        nm = g.node("ShaderNodeNormalMap", {"Color": g.image(nimg, uv), "Strength": 1.0}, space='TANGENT')
        kw["normal"] = nm.outputs[0]
    g.output(g.principled(**kw))
    g.viewport("#d8d3c8", roughness=rough[0])


for _s in SEXES:
    M.register(MAT % _s, _mat_lion, overwrite=True, sex=_s)   # overwrite: a patched file gets the current material


def _viewport_rgb(name):
    m = M.get(name)
    return np.array(m.diffuse_color[:3], float)


def lion_material(sex, material="marble_white", plinth_material=None, size=1.0):
    """Material name for a lion of ``sex`` asked for in ``material`` (and ``plinth_material`` for the plinth). The
    scan is white marble: 'marble_white' (the default) is the prepared map itself; any other registered stone
    multiplies it by that material's solid-view colour relative to marble_white's (a variant registered once per
    combination, e.g. 'props_lion_m.stone_grey'), the plinth below the brocade by its own."""
    pm = plinth_material or material
    if material == "marble_white" and pm == "marble_white":
        return MAT % sex
    name = "%s.%s.%s" % (MAT % sex, material, pm)
    if not M.has(name):
        ref = _viewport_rgb("marble_white")
        t1 = tuple(np.clip(_viewport_rgb(material) / np.maximum(ref, 1e-3), 0.0, 1.5).tolist())
        t0 = tuple(np.clip(_viewport_rgb(pm) / np.maximum(ref, 1e-3), 0.0, 1.5).tolist())
        M.register(name, _mat_lion, sex=sex, tint=t1, plinth_tint=t0, top=PLINTH_TOP * size)
    return name


# --------------------------------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------------------------------

PLINTH_TOP = 0.85      # m at size 1: the brocade's top (model frame), measured by prep and checked by the patch


def asset_paths(sexes=SEXES):
    return [os.path.join(M.SCAN_DIR, f % s) for s in sexes for f in (MESH_FILE, DIFF_FILE, NRM_FILE)]


def missing_assets(sexes=SEXES):
    return [p for p in asset_paths(sexes) if not os.path.isfile(p)]


_LOADED = {}


def load(sex):
    """(co, tri, uv) of the prepared lion ``sex`` (model frame at size 1)."""
    miss = missing_assets((sex,))
    if miss:
        raise RuntimeError("lion assets missing (run sect/lib/lion_props.py -- prep, then copy to assets/web): %s"
                           % miss)
    p = os.path.join(M.SCAN_DIR, MESH_FILE % sex)
    key = (p, os.path.getmtime(p))
    if key not in _LOADED:
        with np.load(p, allow_pickle=False) as d:
            _LOADED[key] = (d["co"].astype(np.float32), d["tri"].astype(np.int64), d["uv"].astype(np.float32))
    return _LOADED[key]


def lion_mesh(sex, name, size=1.0, material=None):
    """New mesh ``name``: the prepared lion ``sex`` ('f' or 'm') at ``size`` (model frame x size), UV map 'UVMap'
    (active for render), smooth shaded, one material (``material`` or 'props_lion_<sex>')."""
    co, tri, uv = load(sex)
    me = bpy.data.meshes.new(name)
    me.from_pydata((co * float(size)).tolist(), [], tri.tolist())
    lay = me.uv_layers.new(name="UVMap")
    if len(lay.data) != len(uv):
        raise RuntimeError("lion mesh: %d corners but %d UVs" % (len(lay.data), len(uv)))
    lay.data.foreach_set("uv", uv.ravel())
    lay.active_render = True
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.validate(verbose=False)
    me.update()
    if len(me.polygons) != len(tri):
        raise RuntimeError("lion mesh: validate dropped faces (%d -> %d)" % (len(tri), len(me.polygons)))
    U.set_materials(me, [material or MAT % sex])
    return me


def lion(collection, sex, name, size=1.0, material=None, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
         parent=None):
    """The lion object (see lion_mesh). Returns it."""
    me = lion_mesh(sex, name, size, material)
    return U.object_from_mesh(name, me, collection, location=location, rotation=rotation, parent=parent)


def _props():
    if __package__ in (None, ""):
        from sect.lib import props as P
    else:
        from . import props as P
    return P


def proto_key(size=1.0, mirror=False, material="marble_white", plinth_material=None):
    """(prototype key, size bucket, residual scale, sex, material name) of a guardian lion: the key of
    'props.lion_scan.<bucket>.<sex>.<material>.v<n>' (props._proto adds the prefix and version)."""
    P = _props()
    b, res = P._bucket(size, 1.0)
    sex = "f" if mirror else "m"
    mat = lion_material(sex, material, plinth_material, b)
    return "lion_scan.%s.%s.%s" % (P._k(b), sex, mat), b, res, sex, mat


def lion_proto(size=1.0, mirror=False, material="marble_white", plinth_material=None):
    """(prototype collection, residual scale) for props.guardian_lion: built once per size bucket, sex and material
    under the excluded _protos (props._proto), one object 'props.lion.scan.<sex>' (lion() at the bucket's size).
    mirror False: the male; True: the female (props.guardian_lion's meaning)."""
    P = _props()
    key, b, _res, sex, mat = proto_key(size, mirror, material, plinth_material)
    pc = P._proto(key, lambda pc: lion(pc, sex, P._nm("lion", "scan", sex), b, mat))
    return pc, _res


# --------------------------------------------------------------------------------------------------------------
# prep (run on the box, factory startup)
# --------------------------------------------------------------------------------------------------------------

def _select(objs, active):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _verts(me):
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def import_scan(src):
    """The scan as one welded mesh object 'lion_scan' (world transform applied) and its colour image."""
    import bmesh
    from mathutils import Matrix
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=src)
    meshes = [o for o in sc.objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError("no meshes in " + src)
    bpy.context.view_layer.update()
    for o in meshes:
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in [o for o in sc.objects if o.type != 'MESH']:
        bpy.data.objects.remove(o, do_unlink=True)
    _select(meshes, meshes[0])
    bpy.ops.object.join()
    hi = bpy.context.view_layer.objects.active
    hi.name = hi.data.name = "lion_scan"
    bm = bmesh.new()
    bm.from_mesh(hi.data)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bm.to_mesh(hi.data)
    bm.free()
    imgs = [n.image for m in hi.data.materials if m and m.node_tree for n in m.node_tree.nodes
            if n.bl_idname == "ShaderNodeTexImage" and n.image is not None]
    if not imgs:
        raise RuntimeError("the scan has no colour image")
    log("scan", src, "faces", len(hi.data.polygons), "verts %d (welded from %d)" % (len(hi.data.vertices), n0),
        "image", imgs[0].name, tuple(imgs[0].size))
    return hi, imgs[0]


def frame_transform(co):
    """4x4 Matrix from the scan's import frame to the model frame, measured on vertices ``co`` (n, 3): the plinth's
    straight middle (BODY_BAND) gives the axes (min-area rectangle) and the centre, the head's centroid the front,
    CUT_FRAC the ground, MODEL_HEIGHT the scale. Returns (matrix, info dict)."""
    from mathutils import Matrix
    z0, z1 = float(co[:, 2].min()), float(co[:, 2].max())
    H = z1 - z0
    zr = (co[:, 2] - z0) / H
    band = co[(zr > BODY_BAND[0]) & (zr < BODY_BAND[1])][:, :2]
    c0 = band.mean(0)
    best = None
    for a in np.radians(np.arange(-12.0, 12.0, 0.05)):
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        q = (band - c0) @ R                      # points turned by -a
        lo, hi = q.min(0), q.max(0)
        area = float((hi - lo).prod())
        if best is None or area < best[0]:
            best = (area, a, hi - lo, ((lo + hi) / 2) @ R.T + c0)
    _area, a, ext, c = best
    # front: the head's centroid relative to the plinth centre, in the turned frame
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    hd = (co[zr > HEAD_BAND][:, :2].mean(0) - c) @ R
    f = np.array([1.0, 0.0]) * np.sign(hd[0]) if abs(hd[0]) > abs(hd[1]) else np.array([0.0, 1.0]) * np.sign(hd[1])
    rot = -math.pi / 2 - math.atan2(f[1], f[0])          # turn the front to -Y
    z_cut = z0 + CUT_FRAC * H
    s = MODEL_HEIGHT / (z1 - z_cut)
    T = (Matrix.Translation((0.0, 0.0, -SINK)) @ Matrix.Scale(s, 4) @ Matrix.Rotation(rot - a, 4, 'Z')
         @ Matrix.Translation((-c[0], -c[1], -z_cut)))
    info = dict(height=H, axis_deg=math.degrees(a), plinth_ext=(ext * s).round(4).tolist(), centre=c.round(4).tolist(),
                head=hd.round(3).tolist(), front=f.tolist(), turn_deg=math.degrees(rot - a), z_cut=z_cut, scale=s)
    return T, info


def to_model_frame(hi):
    """Transform the scan into the model frame and cut its ground fringe off (everything below z = -SINK)."""
    import bmesh
    T, info = frame_transform(_verts(hi.data))
    hi.data.transform(T)
    bm = bmesh.new()
    bm.from_mesh(hi.data)
    n0 = len(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7,
                           plane_co=(0.0, 0.0, -SINK), plane_no=(0.0, 0.0, 1.0), clear_inner=True)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(hi.data)
    bm.free()
    hi.data.update()
    co = _verts(hi.data)
    info["faces_cut"] = n0 - len(hi.data.polygons)
    info["box"] = (co.min(0).round(4).tolist(), co.max(0).round(4).tolist())
    log("model frame:", info)
    return info


def plinth_top(me):
    """Model z of the brocade (the plinth's top): the area-weighted median of the up-facing faces between 30 and
    50 % of the height."""
    zs, ws = [], []
    for p in me.polygons:
        if p.normal.z > 0.95 and 0.30 * MODEL_HEIGHT < p.center.z < 0.50 * MODEL_HEIGHT:
            zs.append(p.center.z)
            ws.append(p.area)
    zs, ws = np.array(zs), np.array(ws)
    o = np.argsort(zs)
    cw = np.cumsum(ws[o])
    return float(zs[o][np.searchsorted(cw, cw[-1] / 2)])


# ---- the male: the scan mirrored, the cub replaced by an embroidered ball (all sizes in the female's model frame at
# size 1; the male is built here, then mirrored x -> -x, so his ball lies under his right forepaw)
BALL = True              # False: the male is the plain mirror (a cub under his paw)
CUB_BOX = (0.13, 0.44, -0.665, -0.285)   # x0, x1, y0, y1: the cub under her left forepaw (ortho views and z sections)
CUB_Z = (0.8505, 0.985)  # deleted between these heights: just above the brocade (0.8496; the cut leaves a 1 mm pad,
#                          capped) and just below the paw (its toes rest at ~1.0; the cut caps the paw's sole flat)
BALL_C = (0.272, -0.468)  # the ball's centre x, y: under the paw's middle, 2 cm in from the plinth's side
BALL_R = 0.108           # 22 cm across at size 1 (43 cm at the gate): about the paw's width, the paw grips its top
BALL_SINK = 0.006        # into the brocade (no light line under it)
BALL_GROOVE = 0.0045     # depth of the carved lattice (the normal map carries it; the low ball is smooth)
BALL_CELLS = 2           # icosphere subdivisions of the lattice's cell centres (42 cells: 12 pentagons, 30 hexagons)
BALL_HI_SUBDIV = 8       # the carved ball's icosphere (328k triangles, ~1 mm edges)
BALL_LO_SUBDIV = 4       # the ball in the web mesh (1280 triangles)


def _cut_cub(bm):
    """Delete the cub from the female scan ``bm`` (everything between CUB_Z inside CUB_BOX), cap the paw above the cut
    and the pad below it. Returns the new cap faces."""
    import bmesh
    x0, x1, y0, y1 = CUB_BOX

    def inbox(co, m=0.0):
        return x0 - m < co.x < x1 + m and y0 - m < co.y < y1 + m

    for zc in CUB_Z:
        faces = [f for f in bm.faces if any(inbox(v.co, 0.02) for v in f.verts)
                 and min(v.co.z for v in f.verts) < zc < max(v.co.z for v in f.verts)]
        edges = list({e for f in faces for e in f.edges})
        verts = list({v for f in faces for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=verts + edges + faces, dist=1e-7, plane_co=(0.0, 0.0, zc),
                               plane_no=(0.0, 0.0, 1.0))
    dead = []
    for f in bm.faces:
        c = f.calc_center_median()
        if inbox(c) and CUB_Z[0] < c.z < CUB_Z[1]:
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.edges.ensure_lookup_table()
    bnd = [e for e in bm.edges if e.is_boundary and all(inbox(v.co, 0.03) and CUB_Z[0] - 0.02 < v.co.z < CUB_Z[1] + 0.02
                                                        for v in e.verts)]
    res = bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
    caps = list(res["faces"])
    tri = bmesh.ops.triangulate(bm, faces=caps, quad_method='BEAUTY', ngon_method='BEAUTY')
    caps = list(tri["faces"])
    left = [e for e in bm.edges if e.is_boundary and inbox(e.verts[0].co, 0.03) and e.verts[0].co.z > 0.5]
    log("male: cub cut: %d faces deleted, %d boundary edges capped with %d triangles, %d boundary edges left in the box"
        % (len(dead), len(bnd), len(caps), len(left)))
    return caps


def _ball_dirs(subdiv):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    d = np.array([tuple(v.co.normalized()) for v in bm.verts])
    f = [[v.index for v in fc.verts] for fc in bm.faces]
    bm.free()
    return d, f


def ball_height(d):
    """Carved relief (m, 0 = BALL_R) of the embroidered ball at unit directions ``d`` (n, 3): a geodesic lattice of
    grooved ribbon bands (the Voronoi borders of BALL_CELLS cell centres), a ring and a boss in every cell."""
    cells, _f = _ball_dirs(BALL_CELLS)
    ang = np.arccos(np.clip(d @ cells.T, -1.0, 1.0))
    ang.sort(axis=1)
    a1, a2 = ang[:, 0], ang[:, 1]
    border = (a2 - a1) / 2.0                     # angular distance to the cell's border
    cell_r = math.sqrt(4.0 * math.pi / len(cells) / math.pi)

    def bump(x, w):                              # 1 at 0, 0 beyond w (smooth)
        t = np.clip(1.0 - np.abs(x) / w, 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    G = BALL_GROOVE
    band = 0.11 * cell_r                         # half width of a ribbon band (raised between two grooves)
    h = np.zeros(len(d))
    h -= G * bump(border - band, 0.06 * cell_r)           # the groove along each side of a band
    h -= G * bump(border + band, 0.06 * cell_r) * (border > band)
    h += 0.35 * G * bump(border, band)                    # the band itself stands proud
    h -= 0.8 * G * bump(a1 - 0.52 * cell_r, 0.06 * cell_r)  # the ring in each cell
    h += 0.6 * G * bump(a1, 0.22 * cell_r)               # the boss
    return h


def ball_mesh(name, centre, subdiv, carved):
    """The embroidered ball as a mesh at ``centre`` (female frame); carved or a smooth sphere of radius BALL_R minus
    half the groove (the web mesh's ball, which the normal map carves)."""
    d, faces = _ball_dirs(subdiv)
    r = BALL_R + (ball_height(d) if carved else -0.5 * BALL_GROOVE)
    co = d * (r[:, None] if carved else r) + np.array(centre)
    me = bpy.data.meshes.new(name)
    me.from_pydata(co.tolist(), [], faces)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    return me


def ball_centre():
    """The ball's centre (female frame): resting on the brocade (PLINTH_TOP), sunk BALL_SINK into it."""
    return (BALL_C[0], BALL_C[1], PLINTH_TOP + BALL_R - BALL_SINK)


def make_male(hi, sc):
    """The male's high model: a copy of the female scan ``hi`` with the cub cut out and capped (BALL) and the carved
    ball (object 'lion_ball_hi'), mirrored x -> -x. Returns (scan object, [extra high objects], low ball mesh or None).
    """
    import bmesh
    from mathutils import Matrix
    me = hi.data.copy()
    me.name = "lion_scan_m"
    m = bpy.data.objects.new("lion_scan_m", me)
    sc.collection.objects.link(m)
    extra, low_ball = [], None
    mirror = Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
    if BALL:
        bm = bmesh.new()
        bm.from_mesh(me)
        caps = _cut_cub(bm)
        if len(me.materials) < 2:
            me.materials.append(None)
        for f in caps:
            f.material_index = 1
        bm.to_mesh(me)
        bm.free()
        c = ball_centre()
        bme = ball_mesh("lion_ball_hi", c, BALL_HI_SUBDIV, True)
        ball = bpy.data.objects.new("lion_ball_hi", bme)
        sc.collection.objects.link(ball)
        extra.append(ball)
        low_ball = ball_mesh("lion_ball_lo", c, BALL_LO_SUBDIV, False)
        log("male: ball centre %s r %.3f (top %.3f), high %d faces, low %d faces" % (
            tuple(round(v, 3) for v in c), BALL_R, c[2] + BALL_R, len(bme.polygons), len(low_ball.polygons)))
    for mm in [me] + [o.data for o in extra] + ([low_ball] if low_ball is not None else []):
        mm.transform(mirror)
        mm.flip_normals()
        mm.update()
    return m, extra, low_ball


# ---- low mesh, bakes, re-texture
DELIGHT_SIGMA = 0.10     # m at size 1: the scale over which the scan's own lighting is divided out
DELIGHT_NORMAL = 2.0     # exponent of the normal agreement in that average (the lit and the shaded side stay apart)
DETAIL_GAMMA = 0.9       # contrast of the kept fine detail (1 = the scan's)
DETAIL_CLAMP = (0.42, 1.55)
LARGE_KEEP = 0.2         # share (exponent) of the scan's broad tones kept (weathering stains; its lighting is gone)
LARGE_CLAMP = (0.82, 1.12)
HUE_KEEP = 0.35          # share of the scan's own hue (blue-grey veins, warm stains); the rest is ALBEDO's
ALBEDO = "#dad4c8"       # the marble's mean albedo (sRGB): the scene's marble_white, a shade greyer for weathering
GROUND_DAMP = (0.0, 0.16, 0.86)   # rising damp: albedo x the third value at z = first, back to 1 at the second (m)
SIGN_BOX = ((-0.085, 0.105), (-0.72, -0.58), (0.07, 0.165))   # a museum sign on the base's front: painted out
SIGN_SOFT = 0.012        # m: its feathered edge
CAGE = 0.022             # bake cage extrusion (m at size 1)
RAY = 0.07               # bake max ray distance


def _gpu(sc, samples):
    sc.render.engine = 'CYCLES'
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
            sc.cycles.samples = samples
            log("cycles device", kind, [d.name for d in prefs.devices if d.use])
            return kind
    raise RuntimeError("no OptiX or CUDA device: refusing to bake on the CPU")


def _image(name, size, data=False, float_buffer=False, alpha=True, fill=(0.0, 0.0, 0.0, 0.0)):
    """Bake target. Float buffers are always Non-Color (raw linear values: emission bakes store the scene-linear
    colour as it is); alpha 0 where nothing was baked when ``alpha``."""
    img = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=float_buffer, is_data=data or float_buffer)
    img.colorspace_settings.name = "Non-Color" if (data or float_buffer) else "sRGB"
    img.generated_color = fill
    return img


def _px(img):
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def _emit_material(name, colour_socket_fn):
    """Material whose surface is an emission of whatever colour_socket_fn(nodes, links) returns."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(colour_socket_fn(nt.nodes, nt.links), em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _target_material(name, img):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = img
    mat.node_tree.nodes.active = tn
    return mat, tn


def make_low(name, hi, tris, low_ball=None):
    """Collapse-decimated, triangulated, Smart-UV-unwrapped copy of ``hi`` (plus the smooth ``low_ball``)."""
    import bmesh
    sc = bpy.context.scene
    bm = bmesh.new()
    bm.from_mesh(hi.data)
    n_hi = sum(len(f.verts) - 2 for f in bm.faces)
    for lay in list(bm.loops.layers.uv.values()):
        bm.loops.layers.uv.remove(lay)
    me = bpy.data.meshes.new(name + "_tmp")
    bm.to_mesh(me)
    bm.free()
    low = bpy.data.objects.new(name, me)
    sc.collection.objects.link(low)
    n_ball = len(low_ball.polygons) if low_ball is not None else 0
    mod = low.modifiers.new("dec", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = (tris - n_ball) / float(n_hi)
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(low.evaluated_get(dg))
    low.modifiers.clear()
    low.data = me2
    bpy.data.meshes.remove(me)
    me2.name = name
    bm = bmesh.new()
    bm.from_mesh(me2)
    for f in bm.faces:
        f.material_index = 0
    if low_ball is not None:                      # the ball's faces: material index 1 (bake_lion bakes them apart)
        n0 = len(bm.faces)
        bm.from_mesh(low_ball)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]:
            f.material_index = 1
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(me2)
    bm.free()
    me2.validate(verbose=False)
    me2.polygons.foreach_set("use_smooth", [True] * len(me2.polygons))
    me2.update()
    log(name, "high triangles", n_hi, "low triangles", len(me2.polygons), "verts", len(me2.vertices))
    _select([low], low)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.003, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    try:                                          # tighter packing: small islands go into the big ones' holes
        bpy.ops.uv.pack_islands(rotate=True, margin=0.003, shape_method='CONCAVE')
    except TypeError as e:
        log("WARN pack_islands", e)
        bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    me2.uv_layers[0].name = "UVMap"
    return low


def _bake(kind, objs, low, img, selected_to_active, margin=16, **kw):
    """Bake ``kind`` into ``img`` (the low's target node shows it)."""
    for s in low.material_slots:
        if s.material is not None:
            for n in s.material.node_tree.nodes:
                if n.bl_idname == "ShaderNodeTexImage" and n.name == "bake_target":
                    n.image = img
                    s.material.node_tree.nodes.active = n
    _select(objs + [low], low)
    args = dict(type=kind, use_selected_to_active=selected_to_active, margin=margin, use_clear=True)
    if selected_to_active:
        args.update(cage_extrusion=CAGE, max_ray_distance=RAY)
    args.update(kw)
    bpy.ops.object.bake(**args)


def vertex_luminance(low, colour):
    """(n,) mean linear luminance of the baked ``colour`` (H, W, 4) around each vertex of ``low``."""
    me = low.data
    H, W = colour.shape[:2]
    L = colour[..., :3] @ np.array(M.LUMA, np.float32)
    k = 2                                         # 5 x 5 box blur (summed-area table)
    S = np.pad(L, ((k + 1, k), (k + 1, k)), mode='edge').cumsum(0).cumsum(1)
    n = 2 * k + 1
    Lb = (S[n:, n:] - S[:-n, n:] - S[n:, :-n] + S[:-n, :-n]) / (n * n)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    vi = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", vi)
    tx = np.clip((uv[:, 0] * W).astype(int), 0, W - 1)
    ty = np.clip((uv[:, 1] * H).astype(int), 0, H - 1)
    s = np.bincount(vi, weights=Lb[ty, tx], minlength=len(me.vertices))
    c = np.bincount(vi, minlength=len(me.vertices))
    return s / np.maximum(c, 1)


def delight_field(low, lum):
    """Per-vertex low-frequency luminance: a Gaussian (DELIGHT_SIGMA) average over nearby vertices whose normals
    agree (so the two sides of a leg stay apart): the scan's lighting at the scale of the body's forms."""
    me = low.data
    co = _verts(me).astype(np.float32)
    nrm = np.empty(len(me.vertices) * 3, np.float32)
    me.vertex_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(-1, 3)
    out = np.empty(len(co), np.float64)
    inv = 1.0 / (2.0 * DELIGHT_SIGMA ** 2)
    for i in range(0, len(co), 1024):
        a, na = co[i:i + 1024], nrm[i:i + 1024]
        d2 = ((a[:, None, :] - co[None, :, :]) ** 2).sum(-1)
        w = np.exp(-d2 * inv) * np.clip(na @ nrm.T, 0.0, 1.0) ** DELIGHT_NORMAL
        out[i:i + 1024] = (w @ lum) / np.maximum(w.sum(1), 1e-9)
    return out


def _srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def _soft_box(P, box, soft):
    """1 inside the axis box ((x0, x1), (y0, y1), (z0, z1)) at positions P (..., 3), feathered by ``soft``."""
    m = np.ones(P.shape[:-1], np.float32)
    for k, (a, b) in enumerate(box):
        m *= np.clip((P[..., k] - a) / soft, 0, 1) * np.clip((b - P[..., k]) / soft, 0, 1)
    return m


def re_texture(colour, pos, llow, covered):
    """The clean albedo (H, W, 3 linear) from the baked scan colour, the texel positions (model frame) and the
    per-texel low-frequency luminance (delight_field baked)."""
    luma = np.array(M.LUMA, np.float32)
    C = colour[..., :3].astype(np.float64)
    L = C @ luma
    Lo = np.maximum(llow, 1e-4)
    med = float(np.median(Lo[covered]))
    ratio = L / Lo
    ratio = ratio / float(np.median(ratio[covered]))     # the median texel gets ALBEDO
    detail = np.clip(ratio, *DETAIL_CLAMP) ** DETAIL_GAMMA
    large = np.clip((Lo / med) ** LARGE_KEEP, *LARGE_CLAMP)
    hue = C / np.maximum(L, 1e-4)[..., None]
    hue = 1.0 + HUE_KEEP * (hue - 1.0)
    sign = _soft_box(pos[..., :3], SIGN_BOX, SIGN_SOFT)
    detail = detail * (1.0 - sign) + sign * 1.0
    hue = hue * (1.0 - sign[..., None]) + sign[..., None]
    z = pos[..., 2]
    damp = GROUND_DAMP[2] + (1.0 - GROUND_DAMP[2]) * np.clip((z - GROUND_DAMP[0]) / (GROUND_DAMP[1] - GROUND_DAMP[0]),
                                                             0.0, 1.0)
    base = np.array(M.rgb(ALBEDO)[:3], np.float64)
    out = base * (detail * large * damp)[..., None] * hue
    log("re-texture: scan median low-frequency luminance %.4f, detail p5/p50/p95 %s, sign texels %d" % (
        med, np.percentile(detail[covered], [5, 50, 95]).round(3).tolist(), int((sign > 0.5).sum())))
    return np.clip(out, 0.0, 0.92)


def _save_rgb(name, rgb_lin, path, quality=92, srgb=True):
    H, W = rgb_lin.shape[:2]
    img = bpy.data.images.new(name, W, H, alpha=False, float_buffer=False)
    a = np.ones((H, W, 4), np.float32)
    a[..., :3] = _srgb(rgb_lin) if srgb else np.clip(rgb_lin, 0, 1)
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw = path
    img.file_format = 'JPEG' if path.lower().endswith(".jpg") else 'PNG'
    if img.file_format == 'JPEG':
        bpy.context.scene.render.image_settings.quality = quality
        img.save(filepath=path, quality=quality)
    else:
        img.save()
    return img


def _dilate(m, n):
    m = m.copy()
    for _ in range(n):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    return m


def _rgb_node(nodes, rgb):
    n = nodes.new("ShaderNodeRGB")
    n.outputs[0].default_value = tuple(rgb) + (1.0,)
    return n


def _split_bake(sex, low, ball_faces, hi_objs, tmat, colour, nrm):
    """Colour and normals for a low mesh with the male's ball: its scan part takes rays only from the high scan, its
    ball only from the carved ball (one bake of both let the brocade round the ball take the ball's underside: a dark
    ring), composited by the ball islands' coverage."""
    import bmesh
    sc = bpy.context.scene
    parts = []
    for nm, keep in (("scan", ~ball_faces), ("ball", ball_faces)):
        me = low.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f, k in zip(bm.faces, keep) if not k], context='FACES')
        bm.to_mesh(me)
        bm.free()
        me.materials.clear()
        me.materials.append(tmat)
        o = bpy.data.objects.new("%s.%s" % (low.name, nm), me)
        sc.collection.objects.link(o)
        parts.append(o)
    low.hide_render = True
    white = _emit_material("bake_white", lambda nodes, links: _rgb_node(nodes, (1.0, 1.0, 1.0)).outputs[0])
    white.node_tree.nodes.new("ShaderNodeTexImage").name = "bake_target"
    out = {}
    try:
        for (o, src), key in zip(((parts[0], hi_objs[:1]), (parts[1], hi_objs[1:])), ("scan", "ball")):
            c = _image("split_%s_colour" % key, TEX, float_buffer=True)
            n = _image("split_%s_nrm" % key, NRM_TEX, data=True, alpha=False, fill=(0.5, 0.5, 1.0, 1.0))
            _bake('EMIT', src, o, c, True)
            _bake('NORMAL', src, o, n, True, normal_space='TANGENT')
            cov = _image("split_%s_cov" % key, TEX, data=True, float_buffer=True)
            o.data.materials.clear()
            o.data.materials.append(white)
            _bake('EMIT', [], o, cov, False, margin=0)
            o.data.materials.clear()
            o.data.materials.append(tmat)
            out[key] = (_px(c), _px(n), _px(cov)[..., 0] > 0.5)
    finally:
        for o in parts:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
        low.hide_render = False
    (cs, ns, ms), (cb, nb, mb) = out["scan"], out["ball"]
    take_b = mb | (_dilate(mb, 8) & ~ms)
    c = np.where(take_b[..., None], cb, cs)
    n = np.where(take_b[..., None], nb, ns)
    c[..., 3] = 1.0
    n[..., 3] = 1.0
    colour.pixels.foreach_set(c.ravel())
    nrm.pixels.foreach_set(n.ravel())
    colour.update()
    nrm.update()
    log(sex, "split bake: ball texels %d, scan texels %d" % (int(mb.sum()), int(ms.sum())))


def bake_lion(sex, hi_objs, scan_img, low_ball, out_dir, tris=LION_TRIS):
    """Low mesh, bakes and re-texture for one lion; writes the three files. ``hi_objs``: the scan (first) and the
    extra high objects (the male's carved ball)."""
    sc = bpy.context.scene
    hi = hi_objs[0]
    # high materials: the scan's colour as emission; caps and the ball plain marble, darkened in the carving
    med = np.array([0.42, 0.41, 0.39])
    scan_mat = _emit_material("bake_scan", lambda nodes, links: _img_node(nodes, scan_img).outputs["Color"])

    def plain(nodes, links):
        ao = nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 16
        ao.only_local = True                      # the carving's own hollows, not the low meshes or the paw
        ao.inputs["Distance"].default_value = 0.012
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.inputs["A"].default_value = tuple(med * 0.6) + (1.0,)
        mix.inputs["B"].default_value = tuple(med) + (1.0,)
        links.new(ao.outputs["AO"], mix.inputs["Factor"])
        return mix.outputs["Result"]
    plain_mat = _emit_material("bake_plain", plain)
    idx = np.zeros(len(hi.data.polygons), np.int32)
    hi.data.polygons.foreach_get("material_index", idx)
    hi.data.materials.clear()                    # (resets every face's material index: restored below)
    hi.data.materials.append(scan_mat)
    hi.data.materials.append(plain_mat)
    hi.data.polygons.foreach_set("material_index", np.minimum(idx, 1))
    log(sex, "high model: %d scan faces, %d plain (caps)" % (int((idx == 0).sum()), int((idx > 0).sum())))
    for o in hi_objs[1:]:
        o.data.materials.clear()
        o.data.materials.append(plain_mat)
    low = make_low("lion_%s_low" % sex, hi, tris, low_ball)
    ball_faces = np.zeros(len(low.data.polygons), np.int32)
    low.data.polygons.foreach_get("material_index", ball_faces)
    ball_faces = ball_faces == 1
    for o in sc.objects:                         # nothing else in the bake
        o.hide_render = not (o in hi_objs or o is low)
    tmat, tnode = _target_material("bake_target_mat", None)
    tnode.name = "bake_target"
    low.data.materials.clear()
    low.data.materials.append(tmat)
    # 1. colour and normals from the high model
    colour = _image("lion_%s_colour" % sex, TEX, float_buffer=True)    # raw linear (Non-Color float)
    nrm = _image("lion_%s_nrm" % sex, NRM_TEX, data=True, alpha=False, fill=(0.5, 0.5, 1.0, 1.0))
    if ball_faces.any():
        _split_bake(sex, low, ball_faces, hi_objs, tmat, colour, nrm)
    else:
        _bake('EMIT', hi_objs, low, colour, True)
        _bake('NORMAL', hi_objs, low, nrm, True, normal_space='TANGENT')
    log(sex, "baked colour and normals")
    # 2. the low's own texel positions (coverage in alpha: no margin) and the delight field
    pos = _image("lion_%s_pos" % sex, TEX, data=True, float_buffer=True)
    pmat = _emit_material("bake_pos", lambda nodes, links: nodes.new("ShaderNodeTexCoord").outputs["Object"])
    low.data.materials.clear()
    low.data.materials.append(pmat)
    tn = pmat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.name = "bake_target"
    _bake('EMIT', [], low, pos, False, margin=0)
    P = _px(pos)
    covered = P[..., 3] > 0.5
    col = _px(colour)
    lum = vertex_luminance(low, col)
    field = delight_field(low, lum)
    attr = low.data.color_attributes.new("llow", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", np.repeat(field.astype(np.float32), 4).reshape(-1, 4).ravel())
    lmat = _emit_material("bake_llow", lambda nodes, links: _attr_node(nodes, "llow").outputs["Color"])
    low.data.materials.clear()
    low.data.materials.append(lmat)
    tn = lmat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.name = "bake_target"
    llow = _image("lion_%s_llow" % sex, TEX, data=True, float_buffer=True)
    _bake('EMIT', [], low, llow, False, margin=16)
    Lo = _px(llow)[..., 0]
    # positions in the margin texels: the nearest covered texel's (a margin-baked copy)
    pos_m = _image("lion_%s_posm" % sex, TEX, data=True, float_buffer=True)
    _bake_with(low, pmat, pos_m)
    Pm = _px(pos_m)
    albedo = re_texture(col, Pm, Lo, covered)
    os.makedirs(out_dir, exist_ok=True)
    p_diff = os.path.join(out_dir, DIFF_FILE % sex)
    _save_rgb("lion_%s_diff" % sex, albedo, p_diff)
    p_nrm = os.path.join(out_dir, NRM_FILE % sex)
    nrm.filepath_raw = p_nrm
    nrm.file_format = 'PNG'
    nrm.save()
    # debug maps (not assets): the raw colour bake and the delight field
    _save_rgb("dbg_raw", col[..., :3], os.path.join(out_dir, "dbg_%s_raw.jpg" % sex))
    _save_rgb("dbg_llow", np.repeat((Lo / max(float(np.median(Lo[covered])), 1e-4) * 0.4)[..., None], 3, -1),
              os.path.join(out_dir, "dbg_%s_llow.jpg" % sex))
    # mesh file
    me = low.data
    if any(len(p.vertices) != 3 for p in me.polygons):
        raise RuntimeError("low mesh is not all triangles")
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    tri = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", tri)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    p_mesh = os.path.join(out_dir, MESH_FILE % sex)
    np.savez_compressed(p_mesh, co=co.reshape(-1, 3), tri=tri.reshape(-1, 3), uv=uv.reshape(-1, 2))
    box = co.reshape(-1, 3)
    log(sex, "wrote", p_mesh, os.path.getsize(p_mesh), p_diff, os.path.getsize(p_diff), p_nrm, os.path.getsize(p_nrm))
    log(sex, "low box", box.min(0).round(4).tolist(), box.max(0).round(4).tolist(), "triangles", len(tri) // 3)
    return low


def _img_node(nodes, img):
    n = nodes.new("ShaderNodeTexImage")
    n.image = img
    return n


def _attr_node(nodes, name):
    n = nodes.new("ShaderNodeAttribute")
    n.attribute_type = 'GEOMETRY'
    n.attribute_name = name
    return n


def _bake_with(low, mat, img):
    low.data.materials.clear()
    low.data.materials.append(mat)
    _bake('EMIT', [], low, img, False, margin=16)


def preview(low, sex, out_dir, samples=48):
    """Cycles stills of the finished low lion (its files from ``out_dir``) under a low sun: three-quarter front, the
    face, the paw, the back."""
    from mathutils import Vector
    sc = bpy.context.scene
    diff = bpy.data.images.load(os.path.join(out_dir, DIFF_FILE % sex))
    nimg = bpy.data.images.load(os.path.join(out_dir, NRM_FILE % sex))
    nimg.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("preview_lion")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = diff
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = nimg
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.55
    low.data.materials.clear()
    low.data.materials.append(mat)
    for o in sc.objects:
        o.hide_render = o is not low
    ground = bpy.data.objects.get("preview_ground")
    if ground is None:
        gm = bpy.data.meshes.new("preview_ground")
        gm.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
        ground = bpy.data.objects.new("preview_ground", gm)
        sc.collection.objects.link(ground)
        gmat = bpy.data.materials.new("preview_ground")
        gmat.use_nodes = True
        gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.52, 0.47, 1)
        gm.materials.append(gmat)
    ground.hide_render = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("preview")
    w = sc.world
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.5, 0.68, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    sun = bpy.data.objects.get("preview_sun")
    if sun is None:
        sun = bpy.data.objects.new("preview_sun", bpy.data.lights.new("preview_sun", 'SUN'))
        sc.collection.objects.link(sun)
        sun.data.energy = 3.0
        sun.data.color = (1.0, 0.86, 0.7)
        sun.data.angle = math.radians(1.5)
        sun.rotation_euler = (math.radians(62), 0.0, math.radians(-35))
    sun.hide_render = False
    cam = bpy.data.objects.get("preview_cam")
    if cam is None:
        cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
        sc.collection.objects.link(cam)
    cam.hide_render = False
    sc.camera = cam
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = 900, 1100
    sx = -1.0 if sex == "m" else 1.0
    shots = (("full", (1.6 * sx, -3.6, 1.7), (0.0, 0.0, 1.08), 40),
             ("face", (0.35 * sx, -1.6, 1.9), (0.0, -0.3, 1.78), 55),
             ("paw", (0.55 * sx, -1.35, 1.15), (0.28 * sx, -0.45, 0.95), 55),
             ("back", (-2.2 * sx, 3.0, 1.9), (0.0, 0.0, 1.1), 40))
    for name, loc, tgt, lens in shots:
        cam.data.lens = lens
        cam.location = loc
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out_dir, "preview_%s_%s.png" % (sex, name))
        bpy.ops.render.render(write_still=True)
        log("preview", sc.render.filepath)


def prep(src, out_dir, sexes=SEXES, tris=LION_TRIS, previews=True):
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    hi, img = import_scan(src)
    info = to_model_frame(hi)
    zt = plinth_top(hi.data)
    log("plinth top (brocade) z %.4f (PLINTH_TOP %.3f)" % (zt, PLINTH_TOP))
    _gpu(sc, 16)
    lows = {}
    for sex in sexes:
        if sex == "f":
            objs, low_ball = [hi], None
        else:
            m, extra, low_ball = make_male(hi, sc)
            objs = [m] + extra
        lows[sex] = bake_lion(sex, objs, img, low_ball, out_dir, tris)
    if previews:
        for sex, low in lows.items():
            preview(low, sex, out_dir)
    return info


if __name__ == "__main__":
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep"])
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default="out/tmp/lion_prep")
    ap.add_argument("--sexes", default=",".join(SEXES))
    ap.add_argument("--tris", type=int, default=LION_TRIS)
    ap.add_argument("--no-ball", action="store_true")
    ap.add_argument("--no-previews", action="store_true")
    a = ap.parse_args(argv)
    if a.no_ball:
        BALL = False
    if a.cmd == "prep":
        prep(os.path.join(PROJECT, a.src), os.path.join(PROJECT, a.out), tuple(a.sexes.split(",")), a.tris,
             not a.no_previews)
