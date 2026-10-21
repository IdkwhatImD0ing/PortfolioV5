"""Web export for the real-time three.js fly-through (first test: Mountain Gate -> Heart-Mirror Terrace).

Run on the cloud box through the wrapper, never on the user's PC:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/export_web.py -- <command> [options]

Commands (one per Blender run; none of them saves the .blend):

    audit   Which objects chase.cam sees over --frames: frustum test with a margin plus a depth-buffer
            occlusion test (EEVEE renders the camera distance through a material override; an object
            counts as hidden in a frame when every depth texel under its screen rectangle is nearer
            than the object's nearest point). Triangle, material, modifier and instancing stats.
            Writes out/web/audit.json, out/web/audit.md and out/web/vis_cache.npz (per-instance
            visibility, which `scene` and `meta` read; run audit first).
    camera  out/web/proto/camera.json (three.js space, every frame of --frames).
    meta    out/web/proto/meta.json (sun, sky, fog, moon, cloud sea, waterfalls, hotspots, areas).
    sky     out/web/proto/sky.png: equirectangular sky of the world shader only (Cycles, AgX Punchy),
            three.js equirect convention (image centre = +X three = east).
    flyer   out/web/proto/flyer.glb (flyer only, rest pose, root at the origin) + flyer.json (path).
    scene   out/web/proto/scene_unbaked.glb (near/mid set, plain colours) + backdrop_unbaked.glb
            (far set, heavily reduced); merges "scene" and "baked": false into manifest.json (other keys,
            e.g. "clouds" and "water", are kept).
    clouds  out/web/proto/clouds.json: the volume cloud puffs as ellipsoids {"puffs": [{"c", "a", "d"}]}
            (drawn as soft sprites on the web); adds "clouds" to manifest.json. With --profile full it
            then appends the web-only mist (sect/mist.py, tagged "k": "mist.*"; also runs alone without
            Blender: python -I sect/mist.py).
    refs    EEVEE stills of chase.cam with the flyer hidden -> out/web/ref/ref_<frame>.png.
    auditmd Rewrites out/web/audit.md from audit.json, export_stats.json and meta.json (any Blender,
            e.g. --factory-startup without the .blend).
    verify  Fresh scene: imports the GLBs, rebuilds the camera from camera.json (three -> Blender) and
            renders out/web/verify/verify_<frame>.png to check the conversion end to end.

Options: --frames 1-288 (Blender frames), --step 2 (sampling for the audit), --look holds+between|holds|none
(audit: look-around views; default holds+between for the full profile, none for proto), --ref-frames 1,48,...,
--ref-dir DIR, --start-frame N (override START_FRAME = 27), --res 1280x720, --near 150 --mid 900 (distance
bands, m), --max-tris 1800000 (Blender-side budget; lands near 1.5M in the files), --merge-mid 1,
--out DIR (default out/web/proto). 'E:/...' paths are mapped onto the box's project mirror.

Output lands under out/web/ on the box and the wrapper copies it back; copy out/web/proto/* to
client/public/sect/proto/ on the PC.

FULL PATH (--profile full): all 11 areas along chase.cam frames 1-1729 (out/section_timeline.json). Commands may be
joined by commas (run in order in one Blender session):

    ... export_web.py -- audit --profile full                       (~35 min: 577 path + ~1000 look depth renders)
    ... export_web.py -- chunks,meta,standin,camcheck --profile full
    ... export_web.py -- clouds,camera,flyer,refs --profile full
    ... --factory-startup --python export_web.py -- verifyfull --profile full --ref-frames 93,772,1380

    audit      out/web/full/vis_cache.npz (+ 'visible within NM_BAND = 400 m' bits and the nearest frame per piece),
               audit.json, audit.md. The page lets the visitor turn the view all the way round, so after the path
               frames the audit also renders look-around views (--look, default holds+between): at each hold the hold
               camera turned to 8 compass headings at 5 tilts plus 4 views straight down (44 per hold), and between
               the holds every LOOK_EVERY-th frame at 8 headings and 2 tilts. Each look view is a column labelled
               with a frame (the hold frame, or its own frame), so the chunk plan and the need ranges use it like a
               path frame. A piece seen in any view is exported. For detail, the path keeps full weight (dmin,
               pxmax) and the look views count partly (dmin_look, pxmax_look; VIEW_PX_WEIGHT, VIEW_D_SCALE). The
               view matrices are stored as view_mats; every later step reads them with load_views(). --look none
               reproduces the old path-only audit, and the bake then skips its around-hold floor and density (the
               mode is stored as 'look'). The first run keeps the old cache as vis_cache.pre360.npz and prints what
               the look views add (the gate before the bake).
               Turning objects (TURNING_GROUPS: the forge ring's artifacts, the flying cranes) share one visibility
               per group (the union over its pieces) and one area chunk, in every --look mode (this replaces
               patch_forge_artifacts' cache patch), and the bake treats them as seen from every side.
    chunks     out/web/full/chunks.json + chunks.npz: every piece seen within 400 m belongs to the area chunk whose
               frame range holds the frame where it is nearest the camera (hotspot members: their hotspot's area);
               the range is split face by face (face_assign); pieces seen only farther go to the backdrop
    meta       <site>/meta.json (whole path; hotspots with area/chunk/kind, waterfalls and beams with chunk, areas
               with holdFrame) and out/web/full/hotspots.md
    standin    <site>/<area>.glb.gz per chunk + backdrop.glb.gz (far set + per-area proxies under 'proxy.<area>'
               Empties, extras {"proxyOf": area}) + manifest.json v2 ("baked": false); stats standin_stats.json
    camcheck   hotspot centres at the holds through Blender's camera vs camera.json maths -> camcheck.json
    verifyfull imports the stand-in set, shows chunks by their need range (proxies swapped), renders verify/
    camera/clouds/flyer/refs as above, for the whole path. <site> = out/web/full/site (copy to
    client/public/sect/full/). Hold frames: HOLD_OVERRIDES moves timeline hero frames that frame their area badly;
    the scene is evaluated at the forge hold (the artifact ring turns), see FULL_SCENE_FRAME.

Other scripts: EW.use_profile("full") first, then EW.gather(scene) (evaluates at the same frame), EW.load_cache(R)
(S gains 'vis_nm' and 'fnear'; 'd_eff' and 'px_eff' fold the look views into the path's dmin and pxmax: use them for
LOD and texel density), EW.load_views() (the audit's view matrices, frames and kinds in cache column order),
EW.load_chunks(R) -> (per-record chunk index, ids; -1 backdrop, -2 not exported, -3 split: EW.face_assign per face),
EW.hotspot_members() (item-level hotspots first), EW.turning_owners() (owner -> turning group), EW.AREAS (holdFrame
per area).

Conventions (the file contract, see the client page):
- three.js world = (bx, bz, -by): Y up, metres. Blender +Y (flight direction, north) is three -Z.
- Camera q orients a three.js camera (looks down local -Z, up +Y): q = C * R_blender, with
  C = rotation of -90 deg about X. Object q (flyer, waterfalls) = C * R * C^-1.
- glTF node names are Blender object names; instance groups are '<instancer>|<proto>' Empties whose
  children share one mesh (EXT_mesh_gpu_instancing when the exporter emits it). Hotspot nodes carry
  extras {"hotspot": id, "label": text}. Materials keep the Blender material names.

Extending (bake agent): gather() + load_cache() give every renderable instance with its visibility
summary (any, dmin, pxmax); export_mask() drops sky/FX/flyer; fit_budget() picks LOD levels; MeshPicker
returns the mesh per (proto, level) and prefers the scene's designed tree LODs; build_export() makes the
export objects (names, hotspot Empties, GPU-instance groups) and export_glb() writes them. For baking,
replace web_material() and the mesh source in MeshPicker/build_export with baked meshes + UVs, keep the
names and the manifest keys. Pitfalls: export with use_active_scene (the 5.2 exporter's GPU-instancing
pass breaks with several scenes); copy materials from the object's slots (object-linked slots get lost);
budget on glb_stats() (the exporter drops degenerate faces).
"""
import argparse
import collections
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_WEB = os.path.join(ROOT, "out", "web")
PROTO = os.path.join(OUT_WEB, "proto")
CACHE = os.path.join(OUT_WEB, "vis_cache.npz")
DEPTH_TMP = "/tmp/sect_web_depth"

CAMERA = "chase.cam"
FLYER_COLL = "flyer"
FLYER_ROOT = "flyer.root"
FPS = 24
FRAMES = (1, 288)
HOLDS = [dict(id="gate", label="Mountain Gate", frame=93),
         dict(id="mirror", label="Heart-Mirror Terrace", frame=217)]
AREAS = [dict(id="gate", label="Mountain Gate", titleZh="月华宗", frameStart=1, frameEnd=165, heroFrame=93),
         dict(id="mirror", label="Heart-Mirror Terrace", titleZh="心镜台", frameStart=166, frameEnd=287,
              heroFrame=217)]
REF_FRAMES = (1, 48, 93, 140, 190, 217, 288)
START_FRAME = 27             # picked from renders (out/web/ref/start): first frame with the gate centred at the
                             # top of the stairway and the haze cleared; frames 1-18 sit low in the haze
ASPECT = 16.0 / 9.0
DEPTH_RES = (768, 360)       # same vertical FOV as the film, 2.13:1, so wide browser windows are covered
FRUSTUM_MARGIN = 0.06        # NDC margin on the depth frustum (motion between sampled frames)
NEAR_MAX = 150.0
MID_MAX = 900.0
MIN_PX = 1.5                 # largest on-screen size (px at 1280x720) below which an object is dropped
OPENING_CLEAR_Y = -225.0     # world.cloud.opening bank is clear north of this (world.py)
GEOM_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD"}

# Click targets: id -> (label, object names whose subtree forms the target). The first name that
# exists becomes the glTF node carrying the extras; the others are merged into its bounds.
HOTSPOTS = [
    ("gate", "Mountain Gate", ["gate.paifang"]),
    ("mirror", "Heart-Mirror Terrace", ["mirror.mirror_stand"]),
]

C3 = Matrix(((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))   # Blender world -> three world

# ---- profiles: "proto" (default, the first test above) and "full" (all 11 areas, frames 1-1729) --------------
# use_profile("full") (or --profile full) swaps the module globals below; every command then works on the
# whole path. Outputs of the full profile go to out/web/full/ (WORK) and out/web/full/site/ (SITE, the files
# copied to client/public/sect/full/). Other scripts (bake_web.py, bake_trees.py) call EW.use_profile("full")
# before EW.gather / EW.load_cache / EW.load_chunks.
PROFILE = "proto"
WORK = OUT_WEB                 # audit.json/md, vis_cache.npz, chunks.json, ref/ (proto: out/web)
SITE = PROTO                   # default --out (proto: out/web/proto)
SCENE_FRAME = None             # frame gather() evaluates the scene at (None: as loaded, i.e. frame 1)
FULL = os.path.join(OUT_WEB, "full")
TIMELINE = os.path.join(ROOT, "out", "section_timeline.json")
LABELS_JSON = os.path.join(ROOT, "out", "tmp", "webfull", "labels.json")   # portfolio names (make_labels.py)
NM_BAND = 400.0                # full: near/mid band (m); pieces seen within it belong to an area chunk
FULL_STEP = 3                  # full: audit sampling (frames)
FULL_SCENE_FRAME = 352         # full: the forge's artifact ring turns over frames 1-1500; at the forge hold the
                               # exported artifacts (and their hotspots) sit where the reader sees them
AREA_NAMES = {                 # client/src/lib/sect/areas.ts (label, zh)
    "gate": ("Mountain Gate", "山门"), "mirror": ("Heart-Mirror Terrace", "心镜台"),
    "forge": ("Artifact Forge Peak", "炼器峰"), "arena": ("Sword-Discussion Arena", "论剑台"),
    "mission": ("Mission Hall", "任务殿"), "library": ("Scripture Pavilion", "藏经阁"),
    "steles": ("Stele Forest of Techniques", "碑林"), "scroll": ("Jade Slip Pavilion", "玉简阁"),
    "formation": ("Grand Sect-Protecting Formation", "护宗大阵"), "abode": ("Cave Abode", "洞府"),
    "summit": ("Moon-Gazing Summit", "望月台"),
}
HOLD_OVERRIDES = {             # full: area id -> hold frame where the timeline's hero frame frames the area badly
    "forge": 352,              # 389 leaves the cauldron and the artifact ring at the right edge, half out of frame
    "library": 772,            # 818 looks at a cliff and floating islands; the pagoda is cut off at the right edge
    "steles": 974,             # 967 has the entrance paifang's column across the right edge
    "formation": 1208,         # 1277 looks past the plaza at the abode's plateau; the plaza is below the frame
    "abode": 1380,             # 1449 shows the stair to the summit; the moon gate and balcony are out of frame
}
HOTSPOT_DEFS = []              # full: [{id, label, names, area, kind, metaOnly}] (build_hotspot_defs)
_MEMBERS = None                # hotspot_members() memo (export objects take over the original names)

# ---- look-around views ----------------------------------------------------------------------------------------------
# The page lets the visitor turn the view all the way round (yaw wraps; pitch keeps its limits). The path frames only
# ever look forward, so the audit adds views that look every way. Each one stands where chase.cam stands at its
# frame, with chase.cam's lens and no roll. A piece seen in any view is exported (full weight for visibility). For
# detail the look views count partly: on-screen size x VIEW_PX_WEIGHT (LOD: triangles ~ px^2) and distance x
# VIEW_D_SCALE (texel density ~ 1/d, decimation weights), so the fixed budgets still favour the flight view.
LOOK_MODES = ("holds+between", "holds", "none")
LOOK_YAWS = (0, 45, 90, 135, 180, 225, 270, 315)    # deg, compass headings (0 = +Y north, 90 = +X east)
LOOK_HOLD_TILTS = (-55.0, -25.0, 5.0, 35.0, 65.0)    # deg above the horizon, at every hold
LOOK_HOLD_DOWN_YAWS = (0, 90, 180, 270)              # straight-down views at every hold (the yaw turns the wide frame)
LOOK_EVERY = 48                # frames between two look-around points between the holds
LOOK_BETWEEN_TILTS = (-20.0, 10.0)
LOOK_HOLD_GAP = 12             # frames: no between point this near a hold (the hold's own views cover it)
VIEW_PATH, VIEW_HOLD, VIEW_BETWEEN = 0, 1, 2
VIEW_PX_WEIGHT = np.array([1.0, 0.5, 0.3])          # per view kind: factor on the on-screen size
VIEW_D_SCALE = np.array([1.0, 1.5, 2.0])            # per view kind: factor on the distance
# How a weight w becomes a distance factor: texel density goes as 1/d, so the atlas area a piece asks for goes as
# 1/d^2. Weight w on that area is a distance factor of 1/sqrt(w), rounded up to the next 0.5: hold w = 0.5 ->
# 1.41 -> 1.5 (the plan's value), between w = 0.3 -> 1.83 -> 2.0. Rounding up leans towards the flight view.

# Objects that turn on the page (idle motion): the forge ring's artifacts orbit the cauldron and the cranes glide over
# the abode and the summit, so every side of them shows. Every piece of a group shares the group's visibility (the
# union over its pieces) and the group's area chunk, so a piece the path never saw still exports (an artifact behind
# the cauldron at the export frame, a crane's crown). bake_web skips facing_flip for them and gives them uniform
# texel density and LOD floors. A group is its named objects (or name prefix) and everything parented under them.
# (library-spiral, formation-core: the page turns the library's scroll spiral round the pagoda and the formation's
# core on its axis (idle.ts); baked as still, the spiral's far side got half the texels, 10.3 vs 19.5 per metre,
# and turned to the front)
TURNING_GROUPS = (
    dict(id="forge-ring", area="forge", prefix="forge.artifact."),
    dict(id="abode-cranes", area="abode", names=("abode.crane_flying", "abode.crane_flying.001")),
    dict(id="summit-cranes", area="summit", names=("summit.crane", "summit.crane.001")),
    dict(id="library-spiral", area="library", names=("library.scroll_spiral",)),
    dict(id="formation-core", area="formation", names=("formation.core",)),
)
_TURNING = None                # turning_owners() memo


def use_profile(name):
    """Switch the module to a profile ('proto' keeps the defaults above; 'full' = whole path, 11 areas)."""
    global PROFILE, WORK, SITE, SCENE_FRAME, FRAMES, AREAS, HOLDS, REF_FRAMES, CACHE, FOCUS_AREAS, _MEMBERS, _TURNING
    if name == "proto":
        return
    if name != "full":
        raise SystemExit("unknown profile %r" % name)
    with open(TIMELINE, encoding="utf-8") as fh:
        tl = json.load(fh)
    areas = []
    for s in tl["sections"]:
        aid = s["area"]
        lab, zh = AREA_NAMES[aid]
        areas.append(dict(id=aid, sectionId=s["section_id"], label=lab, titleZh=zh, frameStart=s["frame_start"],
                          frameEnd=s["frame_end"], heroFrame=s["hero_frame"],
                          holdFrame=int(HOLD_OVERRIDES.get(aid, s["hero_frame"]))))
    PROFILE = "full"
    WORK = FULL
    SITE = os.path.join(FULL, "site")
    CACHE = os.path.join(FULL, "vis_cache.npz")
    SCENE_FRAME = next(x["holdFrame"] for x in areas if x["id"] == "forge")   # = FULL_SCENE_FRAME
    FRAMES = (int(tl["frame_start"]), int(tl["frame_end"]))
    AREAS = areas
    HOLDS = [dict(id=a["id"], label=a["label"], frame=a["holdFrame"]) for a in areas]
    hf = [a["holdFrame"] for a in areas]
    REF_FRAMES = tuple(sorted(set(hf + [(x + y) // 2 for x, y in zip(hf[:-1], hf[1:])])))
    FOCUS_AREAS = tuple(a["id"] for a in areas)
    _MEMBERS = None
    _TURNING = None
    if bpy.data.objects.get(CAMERA) is not None:
        build_hotspot_defs()
    log("profile full:", FRAMES, "holds", [(h["id"], h["frame"]) for h in HOLDS], "scene frame", SCENE_FRAME,
        "hotspots", len(HOTSPOT_DEFS))


def area_of_frame(f):
    """Index into AREAS of the area whose frame range holds Blender frame f (clamped to the ends)."""
    for k, a in enumerate(AREAS):
        if a["frameStart"] <= f <= a["frameEnd"]:
            return k
    return 0 if f < AREAS[0]["frameStart"] else len(AREAS) - 1


def log(*a):
    print("WEB", *a, flush=True)


# ---- conversions ------------------------------------------------------------------------------

def v3(v, nd=4):
    return [round(float(v[0]), nd), round(float(v[2]), nd), round(float(-v[1]), nd)]


def q_camera(rot3):
    q = (C3 @ rot3).to_quaternion()
    q.normalize()
    return [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]


def q_object(rot3):
    q = (C3 @ rot3 @ C3.transposed()).to_quaternion()
    q.normalize()
    return [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]


def s3(s):
    return [round(float(s[0]), 5), round(float(s[2]), 5), round(float(s[1]), 5)]


def hexcol(rgb_linear):
    """Linear RGB -> sRGB hex."""
    out = []
    for c in rgb_linear[:3]:
        c = max(0.0, min(1.0, float(c)))
        s = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(int(round(s * 255)))
    return "#%02x%02x%02x" % tuple(out)


def dump(path, data, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, separators=None if indent else (",", ":"),
                  default=lambda o: o.item() if hasattr(o, "item") else (o.tolist() if hasattr(o, "tolist") else str(o)))
    log("wrote", path, os.path.getsize(path), "bytes")


def fix_path(p):
    """'E:/...' -> '/E:/...' on the cloud box (the project mirror), so outputs are copied back."""
    if os.name != "nt" and len(p) > 2 and p[1] == ":" and p[0].isalpha():
        return "/" + p.replace("\\", "/")
    return p


def frame_range(s):
    a, b = s.split("-")
    return int(a), int(b)


# ---- scene structure --------------------------------------------------------------------------

def top_collections(scene):
    m = {}
    for top in scene.collection.children:
        stack = [top]
        while stack:
            c = stack.pop()
            m.setdefault(c.name, top.name)
            stack.extend(c.children)
    return m


def render_visible(scene):
    hidden = set()

    def walk(c, h):
        h = h or c.hide_render
        if h:
            hidden.add(c.name)
        for ch in c.children:
            walk(ch, h)
    walk(scene.collection, False)
    vis = set()
    for ob in scene.objects:
        if ob.hide_render:
            continue
        if ob.users_collection and all(c.name in hidden for c in ob.users_collection):
            continue
        vis.add(ob.name)
    return vis


def obj_top(ob, topmap):
    for c in ob.users_collection:
        if c.name in topmap:
            return topmap[c.name]
    return "?"


def root_of(ob):
    while ob.parent is not None:
        ob = ob.parent
    return ob


def hide_flyer(scene, keep=(CAMERA,)):
    coll = bpy.data.collections.get(FLYER_COLL)
    n = 0
    if coll is None:
        return n
    for ob in list(coll.all_objects):      # hide_render invalidates all_objects while iterating
        if ob is None or ob.name in keep:
            continue
        ob.hide_render = True
        n += 1
    return n


def turning_owners():
    """Object name -> turning group id (TURNING_GROUPS): the named objects, the ones matching the prefix, and
    everything parented under them."""
    global _TURNING
    if _TURNING is not None:
        return _TURNING
    m = {}
    for g in TURNING_GROUPS:
        pre, names = g.get("prefix"), set(g.get("names", ()))
        for ob in bpy.data.objects:
            if ob.name in names or (pre and ob.name.startswith(pre)):
                m[ob.name] = g["id"]
                for c in ob.children_recursive:
                    m.setdefault(c.name, g["id"])
    _TURNING = m
    return m


def turning_rows(R):
    """Turning group id -> record indices (by owner)."""
    tm = turning_owners()
    out = collections.defaultdict(list)
    for i, o in enumerate(R.owner):
        g = tm.get(o)
        if g is not None:
            out[g].append(i)
    return {g: np.array(v) for g, v in out.items()}


# ---- materials --------------------------------------------------------------------------------

def _reach(nt, out):
    seen, stack = set(), [out]
    nodes = []
    while stack:
        n = stack.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        nodes.append(n)
        for i in n.inputs:
            for l in i.links:
                stack.append(l.from_node)
    extra = []
    for n in nodes:
        if n.bl_idname == "ShaderNodeGroup" and n.node_tree:
            extra.extend(n.node_tree.nodes)
    return nodes + extra


def material_info(mat):
    d = dict(name=mat.name, colour=hexcol(mat.diffuse_color), procedural=False, images=0, emission=False,
             volume=False, surface=True, transparent=False, additive=False,
             render_method=getattr(mat, "surface_render_method", "?"))
    if not mat.node_tree:
        return d
    nt = mat.node_tree
    outs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    out = next((n for n in outs if n.is_active_output), outs[0] if outs else None)
    if out is None:
        return d
    d["volume"] = out.inputs["Volume"].is_linked
    d["surface"] = out.inputs["Surface"].is_linked
    nodes = _reach(nt, out)
    types = collections.Counter(n.bl_idname for n in nodes)
    d["procedural"] = any(t.startswith("ShaderNodeTex") and t not in ("ShaderNodeTexImage", "ShaderNodeTexEnvironment")
                          for t in types)
    d["images"] = types.get("ShaderNodeTexImage", 0)
    emis = types.get("ShaderNodeEmission", 0) > 0
    for n in nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            s = n.inputs.get("Emission Strength")
            if s is not None and (s.is_linked or s.default_value > 0.0):
                c = n.inputs.get("Emission Color")
                if c is None or c.is_linked or max(c.default_value[:3]) > 0.0:
                    emis = True
            a = n.inputs.get("Alpha")
            if a is not None and (a.is_linked or a.default_value < 1.0):
                d["transparent"] = True
            t = n.inputs.get("Transmission Weight")
            if t is not None and (t.is_linked or t.default_value > 0.0):
                d["transparent"] = True
    d["emission"] = emis
    if types.get("ShaderNodeBsdfTransparent", 0) or d["render_method"] == "BLENDED":
        d["transparent"] = True
    if types.get("ShaderNodeAddShader", 0) and types.get("ShaderNodeBsdfTransparent", 0):
        d["additive"] = True
    d["volume_only"] = d["volume"] and not d["surface"]
    d["occluder"] = d["surface"] and not d["transparent"] and not d["additive"]
    return d


# ---- gathering --------------------------------------------------------------------------------

def _mesh_tris(me):
    n = len(me.polygons)
    if n == 0:
        return 0, {}
    lt = np.empty(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    mi = np.empty(n, np.int32)
    me.polygons.foreach_get("material_index", mi)
    t = lt - 2
    per = np.bincount(mi, weights=t)
    return int(t.sum()), {int(i): int(v) for i, v in enumerate(per) if v > 0}


def tri_info(ob):
    """(triangles, {slot index: triangles}, [material names]) of an evaluated object."""
    mats = [s.material.name if s.material else "" for s in ob.material_slots]
    if ob.type == "MESH":
        t, per = _mesh_tris(ob.data)
        return t, per, mats
    try:
        me = ob.to_mesh()
    except Exception:
        return 0, {}, mats
    try:
        t, per = _mesh_tris(me) if me is not None else (0, {})
    finally:
        ob.to_mesh_clear()
    return t, per, mats


class Recs:
    """Every renderable geometry instance of the evaluated scene (one row per depsgraph instance)."""

    def __init__(self):
        self.key, self.name, self.owner, self.proto, self.top, self.inst = [], [], [], [], [], []
        self.tris, self.tkey, self.mw, self.bb = [], [], [], []
        self.tinfo = {}          # tkey -> (tris, per-slot tris, material names)

    def finish(self):
        self.mw = np.array(self.mw, float).reshape(-1, 4, 4)
        self.bb = np.array(self.bb, float).reshape(-1, 8, 3)
        self.tris = np.array(self.tris, np.int64)
        self.inst = np.array(self.inst, bool)
        w = np.einsum("nij,nkj->nki", self.mw[:, :3, :3], self.bb) + self.mw[:, None, :3, 3]
        self.corners = w
        self.lo = w.min(1)
        self.hi = w.max(1)
        return self

    def __len__(self):
        return len(self.key)


def gather(scene):
    t0 = time.time()
    if SCENE_FRAME is not None and scene.frame_current != SCENE_FRAME:
        scene.frame_set(SCENE_FRAME)
        log("gather: scene evaluated at frame", SCENE_FRAME)
    dg = bpy.context.evaluated_depsgraph_get()
    topmap = top_collections(scene)
    rvis = render_visible(scene)
    R = Recs()
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in GEOM_TYPES:
            continue
        orig = ob.original
        if inst.is_instance:
            par = inst.parent.original if inst.parent is not None else None
            owner = par.name if par is not None else "?"
            key = "%s|%s|%s" % (owner, orig.name, ".".join(str(i) for i in inst.persistent_id))
            tkey = orig.name
            top = obj_top(par, topmap) if par is not None else "?"
        else:
            owner = orig.name
            key = orig.name
            tkey = "#" + orig.name
            top = obj_top(orig, topmap)
        if owner not in rvis:
            continue
        if tkey not in R.tinfo:
            R.tinfo[tkey] = tri_info(ob)
        nt = R.tinfo[tkey][0]
        if nt == 0:
            continue
        R.key.append(key)
        R.name.append(orig.name)
        R.owner.append(owner)
        R.proto.append(orig.name if inst.is_instance else "")
        R.top.append(top)
        R.inst.append(inst.is_instance)
        R.tris.append(nt)
        R.tkey.append(tkey)
        R.mw.append([list(r) for r in inst.matrix_world])
        R.bb.append([tuple(c) for c in ob.bound_box])
    R.finish()
    log("gather", len(R), "geometry instances,", int(R.tris.sum()), "triangles,", round(time.time() - t0, 1), "s")
    return R


# ---- camera -----------------------------------------------------------------------------------

def _fcurves(ob):
    from sect import camera as C   # noqa: E402  (the shared slotted-action helper)
    return C._fcurves_of(ob)


def sample_matrices(ob, frames):
    """World matrices of an unparented, keyed object at frames (evaluates its F-curves directly)."""
    fcs = {}
    for fc in _fcurves(ob):
        fcs[(fc.data_path, fc.array_index)] = fc
    out = []
    from mathutils import Euler
    for f in frames:
        loc = [fcs[("location", i)].evaluate(f) if ("location", i) in fcs else ob.location[i] for i in range(3)]
        rot = [fcs[("rotation_euler", i)].evaluate(f) if ("rotation_euler", i) in fcs else ob.rotation_euler[i]
               for i in range(3)]
        sc = [fcs[("scale", i)].evaluate(f) if ("scale", i) in fcs else ob.scale[i] for i in range(3)]
        m = Matrix.LocRotScale(Vector(loc), Euler(rot, ob.rotation_mode), Vector(sc))
        out.append(m)
    if ob.parent is not None:
        raise RuntimeError("sample_matrices expects an unparented object: %s" % ob.name)
    return out


def camera_tan(cam):
    """(tan of half the horizontal FOV, tan of half the vertical FOV) of the 16:9 film."""
    d = cam.data
    if d.sensor_fit == "VERTICAL":
        tv = (d.sensor_height / 2) / d.lens
        return tv * ASPECT, tv
    th = (d.sensor_width / 2) / d.lens
    return th, th / ASPECT


# ---- visibility -------------------------------------------------------------------------------

def depth_setup(scene, cam, hide_names, res=DEPTH_RES):
    """Configure an EEVEE render whose RGB is the distance to the camera (alpha 0 = sky)."""
    mat = bpy.data.materials.new("web.depth_override")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    cd = nt.nodes.new("ShaderNodeCameraData")
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(cd.outputs["View Distance"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    bpy.context.view_layer.material_override = mat
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    r.use_compositing = False
    r.use_sequencer = False
    r.film_transparent = True
    r.use_motion_blur = False
    for k, v in (("filter_size", 0.0),):
        try:
            setattr(r, k, v)
        except Exception as e:
            log("depth: cannot set", k, e)
    ims = r.image_settings
    ims.file_format = "OPEN_EXR"
    ims.color_mode = "RGBA"
    ims.color_depth = "32"
    ee = scene.eevee
    for k, v in (("taa_render_samples", 1), ("use_shadows", False), ("use_raytracing", False),
                 ("use_volumetric_shadows", False), ("use_overscan", False), ("use_gtao", False),
                 ("use_bloom", False)):
        if hasattr(ee, k):
            try:
                setattr(ee, k, v)
            except Exception:
                pass
    vs = scene.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    n = 0
    for nm in hide_names:
        ob = bpy.data.objects.get(nm)
        if ob is not None and not ob.hide_render:
            ob.hide_render = True
            n += 1
    # a static camera that copies chase.cam per sample (no frame changes: the scene stays evaluated)
    cd = cam.data.copy()
    cd.name = "web.depthcam"
    th, tv = camera_tan(cam)
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 2 * tv * cd.lens
    dc = bpy.data.objects.new("web.depthcam", cd)
    scene.collection.objects.link(dc)
    scene.camera = dc
    log("depth: hid", n, "non-occluders; res", res, "tan_v", round(tv, 5))
    return dc, tv, res[0] / res[1]


def depth_render(scene, dc, M, path):
    dc.matrix_world = M
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]          # row 0 = top of the frame
    a = px[..., 3]
    with np.errstate(divide="ignore", invalid="ignore"):
        d = np.where(a >= 0.999, px[..., 0] / np.maximum(a, 1e-6), np.inf)
    return d.astype(np.float32)


def pyramid(D):
    lv = [D]
    while max(lv[-1].shape) > 1:
        a = lv[-1]
        if a.shape[0] % 2:
            a = np.vstack([a, a[-1:]])
        if a.shape[1] % 2:
            a = np.hstack([a, a[:, -1:]])
        lv.append(np.maximum(np.maximum(a[0::2, 0::2], a[1::2, 0::2]), np.maximum(a[0::2, 1::2], a[1::2, 1::2])))
    return lv


def rect_max(lv, x0, x1, y0, y1):
    """Conservative max of the depth over pixel rectangles (inclusive ints), via the max pyramid."""
    s = np.maximum(x1 - x0, y1 - y0) + 1
    L = np.ceil(np.log2(np.maximum(s, 1))).astype(int)
    out = np.empty(len(x0), np.float32)
    for l in np.unique(L):
        i = np.nonzero(L == l)[0]
        A = lv[min(l, len(lv) - 1)]
        h, w = A.shape
        cx0 = np.clip(x0[i] >> l, 0, w - 1)
        cx1 = np.clip(x1[i] >> l, 0, w - 1)
        cy0 = np.clip(y0[i] >> l, 0, h - 1)
        cy1 = np.clip(y1[i] >> l, 0, h - 1)
        out[i] = np.maximum(np.maximum(A[cy0, cx0], A[cy0, cx1]), np.maximum(A[cy1, cx0], A[cy1, cx1]))
    return out


def project(R, M, tan_v, aspect_w, margin=FRUSTUM_MARGIN):
    """Per record: in the (wide) frustum, nearest distance, NDC rect (clamped), size in film px."""
    inv = np.linalg.inv(np.asarray(M, float))
    v = R.corners @ inv[:3, :3].T + inv[:3, 3]
    z = -v[..., 2]
    front = z > 0.1
    anyf = front.any(1)
    allf = front.all(1)
    zc = np.maximum(z, 1e-3)
    nx = v[..., 0] / zc / (tan_v * aspect_w)
    ny = v[..., 1] / zc / tan_v
    nx = np.where(front, nx, np.nan)
    ny = np.where(front, ny, np.nan)
    with np.errstate(all="ignore"):
        x0, x1 = np.nanmin(nx, 1), np.nanmax(nx, 1)
        y0, y1 = np.nanmin(ny, 1), np.nanmax(ny, 1)
    part = anyf & ~allf          # straddles the camera plane: assume it covers the frame
    x0[part], x1[part], y0[part], y1[part] = -1, 1, -1, 1
    cam = np.asarray(M, float)[:3, 3]
    d = np.linalg.norm(np.maximum(np.maximum(R.lo - cam, cam - R.hi), 0.0), axis=1)
    inside = anyf & (x1 >= -1 - margin) & (x0 <= 1 + margin) & (y1 >= -1 - margin) & (y0 <= 1 + margin)
    inside &= d < 9000.0
    x0c, x1c = np.clip(x0, -1, 1), np.clip(x1, -1, 1)
    y0c, y1c = np.clip(y0, -1, 1), np.clip(y1, -1, 1)
    # size on the 16:9 film in pixels (1280x720): the wide frame is aspect_w/ASPECT times wider
    px = np.maximum((x1c - x0c) * 0.5 * 1280 * aspect_w / ASPECT, (y1c - y0c) * 0.5 * 720)
    film = inside & (x1 >= -ASPECT / aspect_w) & (x0 <= ASPECT / aspect_w) & (y1 >= -1) & (y0 <= 1)
    return inside, film, d, (x0c, x1c, y0c, y1c), np.nan_to_num(px)


def look_views(cam, frames, mode):
    """The look-around views of `mode` (LOOK_MODES) as [(label frame, view kind, world matrix)]. At each hold: the
    hold camera's position turned to the LOOK_YAWS headings at LOOK_HOLD_TILTS, plus straight-down views. Between the
    holds ('holds+between'): every LOOK_EVERY-th frame at LOOK_YAWS and LOOK_BETWEEN_TILTS. No roll; chase.cam's lens
    (the depth camera copies it)."""
    from mathutils import Euler
    if mode == "none":
        return []
    holds = sorted({int(h["frame"]) for h in HOLDS})
    pts = [(f, VIEW_HOLD) for f in holds]
    if mode == "holds+between":
        pts += [(f, VIEW_BETWEEN) for f in range(frames[0], frames[1] + 1, LOOK_EVERY)
                if min(abs(f - h) for h in holds) > LOOK_HOLD_GAP]
    hold_dirs = [(y, t) for t in LOOK_HOLD_TILTS for y in LOOK_YAWS] + [(y, -90.0) for y in LOOK_HOLD_DOWN_YAWS]
    between_dirs = [(y, t) for t in LOOK_BETWEEN_TILTS for y in LOOK_YAWS]
    out = []
    for (f, kind), M in zip(pts, sample_matrices(cam, [f for f, _ in pts])):
        loc = M.to_translation()
        for yaw, tilt in (hold_dirs if kind == VIEW_HOLD else between_dirs):
            # a camera looks down its local -Z: X by 90 deg + tilt lifts the view from straight down to the
            # horizon and above, Z by -yaw turns it from north (+Y) towards east (+X); the up vector stays upright
            rot = Euler((math.radians(90.0 + tilt), 0.0, -math.radians(yaw)), "XYZ")
            out.append((f, kind, Matrix.LocRotScale(loc, rot, Vector((1.0, 1.0, 1.0)))))
    out.sort(key=lambda v: (v[0], v[1]))
    return out


def visibility(scene, R, frames, step, hide_names, look="none"):
    """Per record and view: in frustum, visible (not occluded), within NM_BAND, the nearest frame. The views are the
    sampled path frames, then the look-around views of `look` (look_views). Distance and on-screen size are kept per
    column for the path only; the look views keep running summaries per record (dmin_look, pxmax_look, already
    weighted by VIEW_D_SCALE / VIEW_PX_WEIGHT). NM_BAND membership and the nearest frame use the weighted distance,
    so a look view takes a piece from the path's area only when it sees it clearly nearer."""
    cam = bpy.data.objects[CAMERA]
    sf = list(range(frames[0], frames[1] + 1, step))
    if sf[-1] != frames[1]:
        sf.append(frames[1])
    views = [(f, VIEW_PATH, M) for f, M in zip(sf, sample_matrices(cam, sf))] + look_views(cam, frames, look)
    dc, tan_v, aspect_w = depth_setup(scene, cam, hide_names)
    os.makedirs(DEPTH_TMP, exist_ok=True)
    W, H = DEPTH_RES
    n, F, P = len(R), len(views), len(sf)
    kinds = collections.Counter(k for _, k, _ in views)
    log("views: path", P, "hold look", kinds[VIEW_HOLD], "between look", kinds[VIEW_BETWEEN], "(look mode %s)" % look)
    vis = np.zeros((n, F), bool)
    film = np.zeros((n, F), bool)
    frus = np.zeros((n, F), bool)
    dist = np.full((n, P), np.inf, np.float32)
    size = np.zeros((n, P), np.float32)
    vis_nm = np.zeros((n, F), bool)            # visible and within NM_BAND (full profile: chunk membership)
    dmin_look = np.full(n, np.inf)             # look views: nearest weighted distance while visible
    pxmax_look = np.zeros(n)                   # look views: largest weighted on-screen size while visible
    best = np.full(n, np.inf)
    fnear = np.full(n, -1, np.int32)          # frame where the record is nearest the camera while visible
    t0 = time.time()
    for j, (f, kind, M) in enumerate(views):
        tag = "d_%04d.exr" % f if kind == VIEW_PATH else "l_%04d_%04d.exr" % (f, j)
        D = depth_render(scene, dc, M, os.path.join(DEPTH_TMP, tag))
        lv = pyramid(D)
        inside, onfilm, d, (x0, x1, y0, y1), px = project(R, M, tan_v, aspect_w)
        i = np.nonzero(inside)[0]
        X0 = np.floor((x0[i] + 1) * 0.5 * W).astype(int)
        X1 = np.floor((x1[i] + 1) * 0.5 * W).astype(int)
        Y0 = np.floor((1 - y1[i]) * 0.5 * H).astype(int)
        Y1 = np.floor((1 - y0[i]) * 0.5 * H).astype(int)
        X0, X1 = np.clip(X0, 0, W - 1), np.clip(X1, 0, W - 1)
        Y0, Y1 = np.clip(Y0, 0, H - 1), np.clip(Y1, 0, H - 1)
        mx = rect_max(lv, X0, X1, Y0, Y1)
        ok = mx >= d[i] * 0.995 - 0.5
        frus[i, j] = True
        vis[i[ok], j] = True
        v = vis[:, j]
        film[:, j] = onfilm & v
        dw = d * VIEW_D_SCALE[kind]
        if kind == VIEW_PATH:
            dist[:, j] = d
            size[:, j] = px
        else:
            dmin_look = np.where(v, np.minimum(dmin_look, dw), dmin_look)
            pxmax_look = np.where(v, np.maximum(pxmax_look, px * VIEW_PX_WEIGHT[kind]), pxmax_look)
        vis_nm[:, j] = v & (dw <= NM_BAND)
        upd = v & (dw < best)
        best[upd] = dw[upd]
        fnear[upd] = f
        if j % 12 == 0 or j == P:
            log("depth", "frame" if kind == VIEW_PATH else ("hold view" if kind == VIEW_HOLD else "between view"), f,
                "in frustum", len(i), "visible", int(ok.sum()), "tris visible", int(R.tris[i[ok]].sum()),
                "t", round(time.time() - t0, 1))
    log("visibility done", F, "views in", round(time.time() - t0, 1), "s")
    V = dict(frames=np.array([f for f, _, _ in views]), kind=np.array([k for _, k, _ in views], np.int8),
             mats=np.array([np.asarray(M, float) for _, _, M in views]), npath=P, look=look, vis=vis, film=film,
             frus=frus, dist=dist, size=size, vis_nm=vis_nm, fnear=fnear, best=best, dmin_look=dmin_look,
             pxmax_look=pxmax_look)
    _union_turning(R, V)
    return V


def _union_turning(R, V):
    """Every piece of a turning group (TURNING_GROUPS) gets the group's visibility: the OR of its bits, the nearest
    distance, the largest on-screen size and the frame of the nearest piece. The page turns these objects all the
    way round, so a side (or a whole piece) the path never saw shows anyway."""
    for gid, rows in sorted(turning_rows(R).items()):
        seen0 = int(V["vis"][rows].any(1).sum())
        for k in ("vis", "film", "frus", "vis_nm"):
            V[k][rows] = V[k][rows].any(0)
        V["dist"][rows] = V["dist"][rows].min(0)
        V["size"][rows] = V["size"][rows].max(0)
        V["dmin_look"][rows] = V["dmin_look"][rows].min()
        V["pxmax_look"][rows] = V["pxmax_look"][rows].max()
        b = rows[int(np.argmin(V["best"][rows]))]
        V["fnear"][rows] = V["fnear"][b]
        V["best"][rows] = V["best"][b]
        log("turning group", gid, "pieces", len(rows), "visible before the union", seen0, "after",
            int(V["vis"][rows].any(1).sum()), "triangles", int(R.tris[rows].sum()))


def summarize_vis(V):
    """Per record: the path's summary at full weight (dmin, pxmax, nearest distance and largest size while visible),
    the look views' weighted summary (dmin_look, pxmax_look; inf / 0 without look views), any = visible in any view
    (path OR look: what is exported), any_path, and the first / last frame label it is visible at."""
    vis, fr = V["vis"], np.asarray(V["frames"])
    P = int(V.get("npath", vis.shape[1]))
    vp = vis[:, :P]
    dv = np.where(vp, V["dist"][:, :P], np.inf)
    sv = np.where(vp, V["size"][:, :P], 0.0)
    anyp = vp.any(1)
    first = np.where(anyp, fr[:P][np.argmax(vp, 1)], -1)
    last = np.where(anyp, fr[:P][P - 1 - np.argmax(vp[:, ::-1], 1)], -1)
    lf = fr[P:]
    for f in np.unique(lf):
        has = vis[:, P:][:, lf == f].any(1)
        first = np.where(has & ((first < 0) | (first > f)), f, first)
        last = np.where(has & (last < f), f, last)
    n = vis.shape[0]
    return dict(any=vis.any(1), any_path=anyp, nvis=vis.sum(1), nfrus=V["frus"].sum(1), nfilm=V["film"].sum(1),
                dmin=dv.min(1), dmin_all=V["dist"][:, :P].min(1), pxmax=sv.max(1), first=first, last=last,
                dmin_look=np.asarray(V.get("dmin_look", np.full(n, np.inf)), float),
                pxmax_look=np.asarray(V.get("pxmax_look", np.zeros(n)), float))


def _effective(S):
    """d_eff / px_eff: the path's dmin / pxmax with the weighted look views folded in (LOD, texel density)."""
    S["d_eff"] = np.minimum(S["dmin"], S["dmin_look"])
    S["px_eff"] = np.maximum(S["pxmax"], S["pxmax_look"])
    return S


def save_cache(R, V, S):
    """Per record summary + the per-view visibility bits (packed), keyed by the record key. Also the bits of
    'visible within NM_BAND', the frame where each record is nearest (full profile: chunk plan), and the views
    themselves (view_mats, view_kind, frames = their frame labels; load_views)."""
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    extra = {}
    if "vis_nm" in V:
        extra = dict(vis_nm_bits=np.packbits(V["vis_nm"], axis=1), fnear=V["fnear"], nm_band=NM_BAND,
                     scene_frame=-1 if SCENE_FRAME is None else SCENE_FRAME)
    if "kind" in V:
        extra.update(view_mats=V["mats"], view_kind=V["kind"], npath=V["npath"], look=V["look"],
                     any_path=S["any_path"], dmin_look=S["dmin_look"].astype(np.float32),
                     pxmax_look=S["pxmax_look"].astype(np.float32))
    np.savez_compressed(CACHE, key=np.array(R.key), frames=V["frames"], nframes=V["vis"].shape[1],
                        vis_bits=np.packbits(V["vis"], axis=1), dmin=S["dmin"].astype(np.float32),
                        pxmax=S["pxmax"].astype(np.float32), nfrus=S["nfrus"], nfilm=S["nfilm"],
                        first=S["first"], last=S["last"], **extra)
    log("wrote", CACHE, os.path.getsize(CACHE))


def load_cache(R):
    """(S, frames): the per-record visibility summary of the last audit, matched by key. frames = the frame label of
    every cache column (path frames first, then the look views); S["vis"] has one column per view. S["d_eff"] and
    S["px_eff"] fold the look views into dmin and pxmax (caches without look views: equal to them)."""
    z = np.load(CACHE, allow_pickle=False)
    idx = {k: i for i, k in enumerate(z["key"].tolist())}
    order = np.array([idx.get(k, -1) for k in R.key])
    miss = order < 0
    if miss.any():
        log("WARN cache misses", int(miss.sum()), "of", len(R))
    o = np.maximum(order, 0)
    if "dist" in z.files:                       # old full format
        V = {k: z[k][o] for k in ("vis", "film", "dist", "size", "frus")}
        V["frames"] = z["frames"]
        S = summarize_vis(V)
    else:
        nf = int(z["nframes"])
        vis = np.unpackbits(z["vis_bits"][o], axis=1)[:, :nf].astype(bool)
        S = dict(any=vis.any(1), nvis=vis.sum(1), dmin=z["dmin"][o].astype(float), pxmax=z["pxmax"][o].astype(float),
                 nfrus=z["nfrus"][o], nfilm=z["nfilm"][o], first=z["first"][o], last=z["last"][o], vis=vis)
        if "vis_nm_bits" in z.files:
            S["vis_nm"] = np.unpackbits(z["vis_nm_bits"][o], axis=1)[:, :nf].astype(bool) & ~miss[:, None]
            S["fnear"] = np.where(miss, -1, z["fnear"][o])
        if "dmin_look" in z.files:
            S["dmin_look"] = np.where(miss, np.inf, z["dmin_look"][o]).astype(float)
            S["pxmax_look"] = np.where(miss, 0.0, z["pxmax_look"][o]).astype(float)
            S["any_path"] = z["any_path"][o] & ~miss
        else:
            S["dmin_look"] = np.full(len(R), np.inf)
            S["pxmax_look"] = np.zeros(len(R))
            S["any_path"] = S["any"].copy()
    S["view_kind"] = z["view_kind"] if "view_kind" in z.files else np.zeros(len(z["frames"]), np.int8)
    S["look"] = str(z["look"]) if "look" in z.files else "none"     # the audit's --look mode
    S["any"] = S["any"] & ~miss
    S["any_path"] = S["any_path"] & ~miss
    return _effective(S), z["frames"]


class Views:
    """The audit's camera views in vis_cache column order: the sampled path frames, then the look-around views.
    mats (world matrices), frames (frame labels), kind (VIEW_PATH / VIEW_HOLD / VIEW_BETWEEN), path (mask),
    dscale / pxw (per view distance and size factors), pos (camera positions)."""

    def __init__(self, mats, frames, kind):
        self.mats = [m if isinstance(m, Matrix) else Matrix(np.asarray(m, float).tolist()) for m in mats]
        self.frames = np.asarray(frames, int)
        self.kind = np.asarray(kind, np.int8)
        self.path = self.kind == VIEW_PATH
        self.dscale = VIEW_D_SCALE[self.kind]
        self.pxw = VIEW_PX_WEIGHT[self.kind]
        self.pos = np.array([np.asarray(m, float)[:3, 3] for m in self.mats], float).reshape(-1, 3)

    def __len__(self):
        return len(self.mats)

    def subset(self, mask):
        mask = np.asarray(mask, bool)
        return Views([m for m, k in zip(self.mats, mask) if k], self.frames[mask], self.kind[mask])


def load_views(cam=None):
    """Views of the last audit (vis_cache view_mats). A cache written before the look views: the path frames,
    rebuilt from chase.cam's F-curves as before."""
    z = np.load(CACHE, allow_pickle=False)
    frames = z["frames"]
    if "view_mats" in z.files:
        return Views(z["view_mats"], frames, z["view_kind"])
    cam = cam if cam is not None else bpy.data.objects[CAMERA]
    return Views(sample_matrices(cam, [int(f) for f in frames]), frames, np.zeros(len(frames), np.int8))


# ---- audit ------------------------------------------------------------------------------------

def non_occluders(scene, R, minfo):
    """Objects hidden in the depth render: flyer, volumes, transparent/additive-only geometry."""
    names = set()
    coll = bpy.data.collections.get(FLYER_COLL)
    if coll:
        names |= {o.name for o in coll.all_objects if o.name != CAMERA}
    owner_occ = collections.defaultdict(bool)
    for i in range(len(R)):
        mats = R.tinfo[R.tkey[i]][2]
        occ = any(minfo.get(m, {}).get("occluder", True) for m in mats if m) if any(mats) else True
        owner_occ[R.owner[i]] |= occ
    for o, occ in owner_occ.items():
        if not occ:
            names.add(o)
    return names


def band(d, near, mid):
    return np.where(d <= near, "near", np.where(d <= mid, "mid", "far"))


def cmd_audit(a):
    scene = bpy.context.scene
    t0 = time.time()
    frames = frame_range(a.frames)
    R = gather(scene)
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    hide = non_occluders(scene, R, minfo)
    pre = dict(objects=len(scene.objects), view=dict(transform=scene.view_settings.view_transform,
                                                     look=scene.view_settings.look,
                                                     exposure=scene.view_settings.exposure),
               render=dict(engine=scene.render.engine, taa=scene.eevee.taa_render_samples,
                           quality=scene.get("sect_look_quality")))
    V = visibility(scene, R, frames, a.step, hide, a.look)
    S = _effective(summarize_vis(V))
    prev = _keep_pre360(CACHE, lambda p: "view_mats" not in np.load(p, allow_pickle=False).files)
    save_cache(R, V, S)
    look = _audit_gate(R, S, V, prev)
    # the report below counts the path and the look views together (effective distance and size)
    S = dict(S, dmin=S["d_eff"], pxmax=S["px_eff"])

    near, mid = a.near, a.mid
    owners = np.array(R.owner)
    tops = np.array(R.top)
    anyv = S["any"]
    tris = R.tris
    b = band(S["dmin"], near, mid)
    keep = anyv & (S["pxmax"] >= MIN_PX)

    def sums(mask):
        return dict(instances=int(mask.sum()), triangles=int(tris[mask].sum()))

    total_objects = pre["objects"]
    out = dict(
        file="out/sect_chase.blend", camera=CAMERA, frames=list(frames), sampled_every=a.step, profile=PROFILE,
        scene_frame=SCENE_FRAME,
        sampled_frames=int(V["npath"]),
        method=("frustum test (16:9 film widened to %.2f:1 at the same vertical FOV, NDC margin %.2f) + "
                "conservative depth-buffer occlusion test (EEVEE %dx%d distance render, flyer, volumes and "
                "transparent/additive objects hidden); path frames plus look-around views (mode %s), which count "
                "at full weight for visibility and with distance x %s / size x %s for the nearest distance and "
                "largest size reported here" % (DEPTH_RES[0] / DEPTH_RES[1], FRUSTUM_MARGIN, DEPTH_RES[0],
                                                 DEPTH_RES[1], V["look"], VIEW_D_SCALE.tolist()[1:],
                                                 VIEW_PX_WEIGHT.tolist()[1:])),
        look=look,
        bands=dict(near_max_m=near, mid_max_m=mid, min_px=MIN_PX),
        scene=dict(objects=total_objects, geometry_instances=len(R), triangles=int(tris.sum()),
                   instanced_rows=int(R.inst.sum())),
        in_frustum=sums(S["nfrus"] > 0),
        visible=sums(anyv),
        visible_min_px=sums(keep),
        by_band={k: sums(keep & (b == k)) for k in ("near", "mid", "far")},
    )
    # per-frame load
    pf = []
    for j, f in enumerate(V["frames"][:V["npath"]]):          # path frames only
        m = V["vis"][:, j]
        mf = V["film"][:, j]
        pf.append(dict(frame=int(f), visible=int(m.sum()), tris=int(tris[m].sum()), film_tris=int(tris[mf].sum())))
    out["per_frame"] = pf
    out["per_frame_peak_tris"] = max(p["tris"] for p in pf)
    # by top collection
    bytop = []
    for t in sorted(set(R.top)):
        m = tops == t
        mv = m & keep
        row = dict(collection=t, instances=int(m.sum()), triangles=int(tris[m].sum()),
                   visible_instances=int(mv.sum()), visible_triangles=int(tris[mv].sum()))
        for k in ("near", "mid", "far"):
            row[k + "_tris"] = int(tris[mv & (b == k)].sum())
        row["nearest_m"] = round(float(S["dmin"][mv].min()), 1) if mv.any() else None
        bytop.append(row)
    out["by_collection"] = sorted(bytop, key=lambda r: -r["visible_triangles"])
    # owners (objects / instancers) ranked by visible triangles
    agg = collections.defaultdict(lambda: dict(n=0, nv=0, tris=0, vtris=0, dmin=np.inf, px=0.0, inst=False,
                                               protos=collections.Counter(), top=""))
    for i in np.nonzero(keep | (S["nfrus"] > 0))[0]:
        g = agg[R.owner[i]]
        g["n"] += 1
        g["tris"] += int(tris[i])
        g["top"] = R.top[i]
        if keep[i]:
            g["nv"] += 1
            g["vtris"] += int(tris[i])
            g["dmin"] = min(g["dmin"], float(S["dmin"][i]))
            g["px"] = max(g["px"], float(S["pxmax"][i]))
        if R.inst[i]:
            g["inst"] = True
            g["protos"][R.proto[i]] += int(keep[i])
    rows = []
    for o, g in agg.items():
        if g["nv"] == 0:
            continue
        rows.append(dict(owner=o, collection=g["top"], instancer=g["inst"], visible=g["nv"], in_frustum=g["n"],
                         visible_tris=g["vtris"], nearest_m=round(g["dmin"], 1), max_px=round(g["px"], 1),
                         band=str(band(np.array([g["dmin"]]), near, mid)[0]),
                         protos=dict(g["protos"].most_common(8)) if g["inst"] else None))
    rows.sort(key=lambda r: -r["visible_tris"])
    out["top_owners"] = rows[:60]
    out["visible_owner_count"] = len(rows)
    # instancing: what the scatter is made of (visible only)
    protos = collections.defaultdict(lambda: dict(count=0, tris_each=0, instancers=collections.Counter()))
    for i in np.nonzero(keep & R.inst)[0]:
        p = protos[R.proto[i]]
        p["count"] += 1
        p["tris_each"] = int(tris[i])
        p["instancers"][R.owner[i]] += 1
    prow = [dict(proto=k, visible=v["count"], tris_each=v["tris_each"], tris=v["count"] * v["tris_each"],
                 instancers=dict(v["instancers"].most_common(5))) for k, v in protos.items()]
    prow.sort(key=lambda r: -r["tris"])
    out["instanced_protos"] = prow[:60]
    veg = collections.Counter()
    vegt = collections.Counter()
    for r in prow:
        for k in ("pine", "blossom", "willow", "bamboo", "shrub", "grass", "lotus"):
            if k in r["proto"]:
                lod = r["proto"].rsplit(".", 1)[-1]
                veg["%s.%s" % (k, lod)] += r["visible"]
                vegt["%s.%s" % (k, lod)] += r["tris"]
    out["vegetation_visible"] = {k: dict(count=veg[k], tris=vegt[k]) for k in sorted(veg)}
    allveg = collections.Counter()
    for i in np.nonzero(R.inst)[0]:
        p = R.proto[i]
        for k in ("pine", "blossom", "willow", "bamboo", "shrub", "grass"):
            if k in p:
                allveg[k] += 1
    out["vegetation_whole_scene"] = dict(allveg)
    # materials (visible triangles per material)
    mt = collections.Counter()
    for i in np.nonzero(keep)[0]:
        t, per, mats = R.tinfo[R.tkey[i]]
        for slot, n in per.items():
            mt[mats[slot] if slot < len(mats) else ""] += n
    mrows = []
    for m, n in mt.most_common():
        info = minfo.get(m, dict(name=m))
        mrows.append(dict(material=m, visible_tris=int(n), **{k: info.get(k) for k in (
            "colour", "procedural", "images", "emission", "volume_only", "transparent", "additive",
            "render_method")}))
    out["materials_visible"] = mrows
    out["material_classes_visible"] = dict(
        procedural=sum(1 for r in mrows if r["procedural"]), emission=[r["material"] for r in mrows if r["emission"]],
        volume=[r["material"] for r in mrows if r["volume_only"]],
        transparent=[r["material"] for r in mrows if r["transparent"]],
        additive=[r["material"] for r in mrows if r["additive"]],
        image_textured=[r["material"] for r in mrows if r["images"]])
    # modifiers on visible owners
    mods = collections.Counter()
    gn = collections.Counter()
    vowners = {r["owner"] for r in rows}
    for o in vowners:
        ob = bpy.data.objects.get(o)
        if ob is None:
            continue
        for m in ob.modifiers:
            mods[m.type] += 1
            if m.type == "NODES" and m.node_group:
                gname = m.node_group.name
                gn["nature.scatter.random" if gname.startswith("nature.scatter") else gname.split(".gn.")[0] + ".gn.*"
                   if ".gn." in gname else gname] += 1
    out["modifiers_on_visible"] = dict(types=dict(mods), node_groups=dict(gn.most_common(20)))
    # world, sky, sun, special objects
    out["world"] = world_facts(scene, R, S, keep)
    out["world"]["view"] = pre["view"]
    out["world"]["render"] = pre["render"]
    # far content
    far = collections.defaultdict(lambda: dict(n=0, tris=0, dmin=np.inf))
    for i in np.nonzero(keep & (b == "far"))[0]:
        o = R.owner[i]
        grp = R.top[i] + ":" + (o.split(".")[0] + "." + o.split(".")[1] if o.count(".") >= 1 else o)
        g = far[grp]
        g["n"] += 1
        g["tris"] += int(tris[i])
        g["dmin"] = min(g["dmin"], float(S["dmin"][i]))
    out["far_groups"] = sorted([dict(group=k, instances=v["n"], tris=v["tris"], nearest_m=round(v["dmin"], 0))
                                for k, v in far.items()], key=lambda r: -r["tris"])[:40]
    # gate / mirror structure (root objects), for hotspots
    out["area_roots"] = area_roots(scene, R, S, keep)
    if PROFILE == "full":
        out["per_area"] = per_area_band(R, S, V, keep, near, mid)
    out["time_s"] = round(time.time() - t0, 1)
    dump(os.path.join(WORK, "audit.json"), out, indent=1)
    log("AUDIT", json.dumps({k: out[k] for k in ("scene", "in_frustum", "visible", "visible_min_px", "by_band",
                                                  "per_frame_peak_tris")}))
    (write_audit_md_full if PROFILE == "full" else write_audit_md)(a)


def _keep_pre360(path, is_old):
    """Copy an output written before the look views to <name>.pre360.<ext>, once (the gates compare against it).
    Returns the copy's path, or None."""
    import shutil
    root, ext = os.path.splitext(path)
    keep = root + ".pre360" + ext
    if os.path.isfile(path) and not os.path.isfile(keep) and is_old(path):
        shutil.copyfile(path, keep)
        log("kept the pre-360 output as", keep)
    return keep if os.path.isfile(keep) else None


def _audit_gate(R, S, V, prev):
    """What the look views add: pieces kept (visible at >= MIN_PX) with the path alone vs with the look views, by
    area (of the nearest frame) and collection, against the pre-360 cache when there is one, and the turning
    groups. Logged as 'LOOK GATE' and stored in audit.json 'look'."""
    tris = R.tris.astype(np.int64)

    def sums(m):
        return dict(instances=int(m.sum()), triangles=int(tris[m].sum()))
    keep_path = S["any_path"] & (S["pxmax"] >= MIN_PX)
    keep = S["any"] & (S["px_eff"] >= MIN_PX)
    new = keep & ~keep_path
    kinds = np.asarray(V["kind"])
    out = dict(mode=V["look"], views=dict(path=int(V["npath"]), hold=int((kinds == VIEW_HOLD).sum()),
                                          between=int((kinds == VIEW_BETWEEN).sum())),
               weights=dict(px=VIEW_PX_WEIGHT.tolist(), d_scale=VIEW_D_SCALE.tolist()),
               kept_path_only=sums(keep_path), kept_with_look=sums(keep), added_by_look=sums(new))
    if "fnear" in V:
        ar = np.array([a["id"] for a in AREAS])[_area_index_array(np.maximum(V["fnear"], 1))]
        out["added_by_area"] = {a["id"]: sums(new & (ar == a["id"])) for a in AREAS}
    tops = np.array(R.top)
    bt = collections.Counter()
    for i in np.nonzero(new)[0]:
        bt[tops[i]] += int(tris[i])
    out["added_by_collection"] = dict(bt.most_common(12))
    if prev:
        z = np.load(prev, allow_pickle=False)
        idx = {k: i for i, k in enumerate(z["key"].tolist())}
        order = np.array([idx.get(k, -1) for k in R.key])
        pv = np.unpackbits(z["vis_bits"], axis=1)[:, :int(z["nframes"])].any(1) & (z["pxmax"] >= MIN_PX)
        pk = np.where(order >= 0, pv[np.maximum(order, 0)], False)
        lost = pk & ~keep
        out["vs_pre360"] = dict(kept_before=sums(pk), kept_now=sums(keep), gained=sums(keep & ~pk), lost=sums(lost),
                                lost_examples=[R.key[i] for i in np.nonzero(lost)[0][:20]])
    out["turning"] = {g: dict(pieces=len(r), kept=int(keep[r].sum()), triangles=int(tris[r].sum()))
                      for g, r in sorted(turning_rows(R).items())}
    log("LOOK GATE", json.dumps(out))
    return out


def world_facts(scene, R, S, keep):
    owners = np.array(R.owner)

    def vis_of(name):
        m = owners == name
        if not m.any():
            return None
        mv = m & keep
        return dict(visible=bool(mv.any()), nearest_m=round(float(S["dmin"][mv].min()), 1) if mv.any() else None,
                    tris=int(R.tris[m].sum()))
    sun = bpy.data.objects.get("look.sun")
    f = {}
    if sun:
        f["sun"] = dict(direction_blender=[round(x, 4) for x in sun.matrix_world.to_3x3().col[2]],
                        colour=list(sun.data.color), strength=sun.data.energy,
                        angle_deg=round(math.degrees(getattr(sun.data, "angle", 0.0)), 2))
    w = scene.world
    sky = next((n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeTexSky"), None) if w and w.node_tree else None
    if sky:
        f["sky"] = dict(type=sky.sky_type, sun_elevation_deg=round(math.degrees(sky.sun_elevation), 2),
                        sun_rotation_deg=round(math.degrees(sky.sun_rotation), 2), altitude=sky.altitude,
                        air=sky.air_density, aerosol=getattr(sky, "aerosol_density", None),
                        ozone=sky.ozone_density, world_nodes=len(w.node_tree.nodes),
                        note="Sky Texture x0.18 + soft knee + painted sun disc/halo + procedural cloud floor "
                             "below the horizon (look.setup_world)")
    f["view"] = dict(transform=scene.view_settings.view_transform, look=scene.view_settings.look,
                     exposure=scene.view_settings.exposure)
    f["render"] = dict(engine=scene.render.engine, taa=scene.eevee.taa_render_samples,
                       quality=scene.get("sect_look_quality"))
    special = {}
    for nm in ("world.moon", "world.moon_halo", "world.haze", "world.cloud_sea", "world.cloud_fog", "world.range",
               "world.range.forest", "world.roots", "world.cirrus", "world.cirrus.001", "world.cirrus.002"):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        lo = np.array([ob.matrix_world @ Vector(c) for c in ob.bound_box])
        special[nm] = dict(type=ob.type, centre_blender=[round(x, 1) for x in (lo.min(0) + lo.max(0)) / 2],
                           size=[round(x, 1) for x in lo.max(0) - lo.min(0)],
                           materials=[s.material.name for s in ob.material_slots if s.material],
                           **(vis_of(nm) or {}))
    f["objects"] = special
    # waterfalls, islets, cloud banks, backdrop: visible counts and nearest distances
    groups = collections.defaultdict(lambda: dict(total=0, visible=0, nearest_m=None, names=[]))
    for i in range(len(R)):
        o = R.owner[i]
        mats = R.tinfo[R.tkey[i]][2]
        kind = None
        if any("waterfall" in m or "water_fall" in m for m in mats):
            kind = "waterfalls"
        elif o.startswith("world.islet") or (o.startswith("scenery.island")):
            kind = "islets"
        elif "cloud" in o and o != "world.cloud_sea" and o != "world.cloud_fog":
            kind = "cloud_banks"
        elif o.startswith("world.backdrop"):
            kind = "backdrop_massifs"
        elif o.startswith("world.link"):
            kind = "connectors"
        if kind is None:
            continue
        g = groups[kind]
        g["total"] += 1
        if keep[i]:
            g["visible"] += 1
            d = float(S["dmin"][i])
            g["nearest_m"] = round(d, 1) if g["nearest_m"] is None else min(g["nearest_m"], round(d, 1))
            if o not in g["names"] and len(g["names"]) < 40:
                g["names"].append(o)
    f["groups"] = dict(groups)
    return f


def area_roots(scene, R, S, keep):
    owners = np.array(R.owner)
    out = {}
    for key in FOCUS_AREAS:
        coll = bpy.data.collections.get(key)
        if coll is None:
            continue
        rows = []
        descend = collections.defaultdict(set)
        for ob in coll.all_objects:
            descend[root_of(ob).name].add(ob.name)
        for ob in coll.all_objects:
            if ob.parent is not None and ob.parent.name in coll.all_objects:
                if ob.parent.parent is not None:
                    continue           # only roots and their direct children
            names = {ob.name} | {c.name for c in ob.children_recursive}
            m = np.isin(owners, list(names))
            if not m.any():
                continue
            lo = R.lo[m].min(0)
            hi = R.hi[m].max(0)
            rows.append(dict(name=ob.name, type=ob.type, parent=ob.parent.name if ob.parent else None,
                             objects=len(names), tris=int(R.tris[m].sum()),
                             centre=[round(x, 2) for x in (lo + hi) / 2], size=[round(x, 2) for x in hi - lo],
                             visible=bool((m & keep).any()),
                             nearest_m=round(float(S["dmin"][m & keep].min()), 1) if (m & keep).any() else None))
        rows.sort(key=lambda r: -r["tris"])
        out[key] = rows[:80]
    return out


# ---- camera.json ------------------------------------------------------------------------------

def hotspot_boxes(R=None):
    """id -> (label, node name, lo, hi) in Blender world, from the evaluated geometry of the subtree."""
    out = {}
    main = HOTSPOTS if PROFILE == "proto" else [(h["id"], h["label"], h["names"]) for h in HOTSPOT_DEFS
                                                   if h["id"] in AREA_NAMES]
    for hid, label, names in main:
        b = _subtree_box(names)
        if b is None:
            log("WARN hotspot", hid, "has no objects", names)
            continue
        out[hid] = (label, "hotspot." + hid, b[0], b[1])
    return out


def ndc_three(p_cam, q, fovy_deg, aspect, pt):
    """Project a three.js world point with a three.js camera (pure math, independent of Blender)."""
    from mathutils import Quaternion
    Q = Quaternion((q[3], q[0], q[1], q[2]))
    v = Q.inverted() @ (Vector(pt) - Vector(p_cam))
    if v.z >= 0:
        return None
    t = math.tan(math.radians(fovy_deg) / 2)
    return (v.x / -v.z / (t * aspect), v.y / -v.z / t, -v.z)


def cmd_camera(a):
    scene = bpy.context.scene
    cam = bpy.data.objects[CAMERA]
    f0, f1 = frame_range(a.frames)
    frames = list(range(f0, f1 + 1))
    mats = sample_matrices(cam, frames)
    # cross-check the F-curve evaluation against the depsgraph at the hold frames
    for hf in [h["frame"] for h in HOLDS]:
        scene.frame_set(hf)
        dm = np.abs(np.array(cam.matrix_world) - np.array(mats[frames.index(hf)])).max()
        log("camera fcurve vs depsgraph max abs diff at %d:" % hf, float(dm))
        if dm > 1e-3:
            raise RuntimeError("chase.cam F-curves disagree with the depsgraph at frame %d (%g)" % (hf, dm))
    th, tv = camera_tan(cam)
    fovy = math.degrees(2 * math.atan(tv))
    rows = []
    for f, M in zip(frames, mats):
        loc, rot, _ = M.decompose()
        rows.append(dict(f=f, p=v3(loc, 3), q=q_camera(rot.to_matrix()), fovY=round(fovy, 4)))
    hs = hotspot_boxes()
    checks = {}
    start = None
    gate = hs.get("gate")
    for row in rows:
        f = row["f"]
        if gate is not None:
            lo, hi = gate[2], gate[3]
            corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
            pr = [ndc_three(row["p"], row["q"], fovy, ASPECT, v3(c)) for c in corners]
            cam_y_blender = -row["p"][2]
            full = all(p is not None and abs(p[0]) <= 0.92 and abs(p[1]) <= 0.92 for p in pr)
            if start is None and full and cam_y_blender > OPENING_CLEAR_Y:
                start = f
    hold_of = {h["id"]: h["frame"] for h in HOLDS}
    for hid, (label, node, lo, hi) in hs.items():
        fl = (93, 217, f0, f1) if PROFILE == "proto" else (hold_of[hid],) if hid in hold_of else ()
        for f in fl:
            row = rows[f - f0]
            c = v3((lo + hi) / 2)
            p = ndc_three(row["p"], row["q"], fovy, ASPECT, c)
            # same projection in Blender space for comparison
            M = mats[f - f0]
            vb = M.inverted() @ Vector((lo + hi) / 2)
            pb = (vb.x / -vb.z / th, vb.y / -vb.z / tv, -vb.z) if vb.z < 0 else None
            checks["%s@%d" % (hid, f)] = dict(three_ndc=[round(x, 3) for x in p] if p else None,
                                              blender_ndc=[round(x, 3) for x in pb] if pb else None)
    log("camera checks", json.dumps(checks))
    log("camera startFrame candidate (gate fully in frame, out of the opening bank):", start)
    start = a.start_frame or START_FRAME
    data = dict(fps=scene.render.fps, frameStart=f0, frameEnd=f1, frames=rows, holds=HOLDS,
                startFrame=int(start or f0), aspect=round(ASPECT, 6), refAspect=round(ASPECT, 6), near=0.1,
                far=cam.data.clip_end,
                convention="three.js world (Y up): p = (bx, bz, -by); q = camera orientation (x,y,z,w), "
                           "camera looks down local -Z; fovY in degrees for a 16:9 film (keep fovY fixed "
                           "on other aspects)", source="out/sect_chase.blend chase.cam")
    os.makedirs(a.out, exist_ok=True)
    dump(os.path.join(a.out, "camera.json"), data)


# ---- meta.json --------------------------------------------------------------------------------

def cmd_meta(a):
    from sect import world as W
    from sect.lib import look as L
    scene = bpy.context.scene
    sun = bpy.data.objects["look.sun"]
    sdir = sun.matrix_world.to_3x3().col[2].normalized()
    moon = bpy.data.objects["world.moon"]
    mc = moon.matrix_world.translation
    mr = max(moon.dimensions) / 2
    gate_view = Vector((0.0, -60.0, 60.0))
    R = gather(scene)
    S = load_cache(R)[0] if os.path.isfile(CACHE) else None
    # waterfalls visible in the stretch (one entry per waterfall object with a waterfall material)
    falls = []
    seen = set()
    for i in range(len(R)):
        mats = R.tinfo[R.tkey[i]][2]
        if not any("waterfall" in m or "water_fall" in m for m in mats):
            continue
        if S is not None and (not S["any"][i] or S["dmin"][i] > a.mid):
            continue
        nm = R.name[i] if not R.inst[i] else R.key[i]
        if nm in seen:
            continue
        seen.add(nm)
        M = Matrix(R.mw[i].tolist())
        loc, rot, sc = M.decompose()
        lo, hi = R.lo[i], R.hi[i]
        ob_f = bpy.data.objects.get(R.name[i])
        dims = ob_f.dimensions if ob_f is not None else Vector(hi - lo)
        falls.append(dict(name=nm, kind="stream" if ".stream" in nm else "sheet", position=v3((lo + hi) / 2, 2),
                          # local size on the three axes (x across, y up, z through); rotation turns it into place
                          size=[round(dims.x, 3), round(dims.z, 3), round(dims.y, 3)], worldSize=s3(hi - lo),
                          rotation=q_object(rot.to_matrix()),
                          origin=v3(loc, 2), nearestM=round(float(S["dmin"][i]), 1) if S is not None else None,
                          material=[m for m in mats if m]))
    hs = []
    for hid, (label, node, lo, hi) in hotspot_boxes().items():
        hs.append(dict(id=hid, label=label, node=node, center=v3((lo + hi) / 2, 2), size=s3(hi - lo)))
    for extra in EXTRA_HOTSPOTS:
        b = _subtree_box(extra[2])
        if b is None:
            log("WARN hotspot", extra[0], "has no objects")
            continue
        hs.append(dict(id=extra[0], label=extra[1], node="hotspot." + extra[0], center=v3((b[0] + b[1]) / 2, 2),
                       size=s3(b[1] - b[0])))
    anchors = {k: W.ANCHORS[k] for k in ("gate", "mirror")}
    LOOK = L.LOOK
    sky = {}
    sky_json = os.path.join(OUT_WEB, "sky_samples.json")
    if os.path.isfile(sky_json):
        with open(sky_json, encoding="utf-8") as fh:
            sky = json.load(fh)
    rendered = {}
    ref = os.path.join(OUT_WEB, "ref", "ref_48.png")
    if os.path.isfile(ref):
        img = bpy.data.images.load(ref)
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)[::-1, :, :3]
        hx = lambda c: "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in np.clip(c, 0, 1))
        rendered = dict(top=hx(px[:int(h * 0.04), int(w * 0.3):int(w * 0.6)].reshape(-1, 3).mean(0)),
                        low=hx(px[int(h * 0.25):int(h * 0.3), int(w * 0.4):int(w * 0.55)].reshape(-1, 3).mean(0)),
                        source="out/web/ref/ref_48.png (EEVEE, haze + AgX + grade)")
    data = dict(
        units="metres, three.js world (Y up): p = (bx, bz, -by)",
        sun=dict(direction=v3(sdir, 5), color=hexcol(sun.data.color), colorLinear=[round(c, 4) for c in sun.data.color],
                 intensity=sun.data.energy, intensityUnit="Blender W/m2 (sun lamp)",
                 elevationDeg=round(math.degrees(math.asin(sdir.z)), 2),
                 azimuthDeg=252.0, angleDeg=LOOK["sun_angle_deg"],
                 note="direction points from the scene toward the sun"),
        sky=dict(zenith=sky.get("zenith"), horizon=sky.get("horizon"), horizonSun=sky.get("horizon_sun"),
                 horizonNorth=sky.get("horizon_north"), horizonSouth=sky.get("horizon_south"),
                 belowHorizon=sky.get("below"), texture="sky.png" if sky else None, asRendered=rendered,
                 note="zenith/horizon/texture are the clean sky; the film adds haze, so the sky behind the "
                      "areas reads greyer (asRendered)",
                 textureMapping="equirectangular, three.js convention (u=0.5 is +X/east, u=0.25 north); "
                                "sRGB, already tone-mapped (AgX Punchy, exposure +0.25)",
                 blender=dict(type="MULTIPLE_SCATTERING", strength=LOOK["sky_strength"], air=LOOK["sky_air"],
                              aerosol=LOOK["sky_aerosol"], ozone=LOOK["sky_ozone"], altitude=LOOK["sky_altitude"])),
        fog=dict(color=rendered.get("low", "#8b8b9f"), scatterColor=hexcol(LOOK["haze_color"]),
                 density=W.HAZE["density"], baseY=W.HAZE["base_z"],
                 falloff=W.HAZE["falloff"], near=60.0, far=2600.0, exp2Density=0.00046,
                 note="Blender haze: exponential height fog, extinction density*exp(-(y-baseY)/falloff) per m; "
                      "at area heights it veils ~9% at 200 m, ~21% at 600 m, ~38% at 1500 m. near/far and "
                      "exp2Density are equivalents for THREE.Fog / FogExp2 (approximate)."),
        moon=dict(position=v3(mc, 1), radius=round(mr, 1),
                  angularSizeDegFromGate=round(math.degrees(2 * math.asin(mr / (mc - gate_view).length)), 2),
                  color="#e9edf5", halo=dict(position=v3(bpy.data.objects["world.moon_halo"].matrix_world.translation, 1),
                                             radius=round(max(bpy.data.objects["world.moon_halo"].dimensions) / 2, 1)),
                  note="self-lit, no shadows; a camera-facing disc or sphere at this position works (inside far=9000)"),
        cloudSea=dict(y=W.CLOUD_SEA_Z, billowTopY=W.CLOUD_SEA_Z + 15.0, fogTopY=20.0, fogBottomY=-90.0,
                      color=sky.get("cloud_sea", "#e9c9a8"), extent=9000.0,
                      note="opaque billowy sheet at y=-60 (warm tops, fades to the horizon colour with distance) "
                           "plus a volume fog layer from y=-90 to +20 that swallows the range's underside"),
        waterfalls=falls,
        hotspots=hs,
        areas=[dict(a, anchor=v3(anchors[a["id"]][:3], 2), footprint=anchors[a["id"]][3]) for a in AREAS],
        toneMapping=dict(blender=LOOK["view_transform"] + " / " + LOOK["look"], exposure=LOOK["exposure"],
                         bloomThresholdLuminance=LOOK["bloom_threshold"], vignette=LOOK["vignette_strength"]),
        lights=[dict(name=o.name, type=o.data.type, position=v3(o.matrix_world.translation, 2),
                     color=hexcol(o.data.color), power=o.data.energy, powerUnit="W (Blender point light)")
                for o in bpy.context.view_layer.objects if o.type == "LIGHT" and o.data.type != "SUN"
                and not o.hide_render and FLYER_COLL not in {c.name for c in o.users_collection}],
    )
    os.makedirs(a.out, exist_ok=True)
    dump(os.path.join(a.out, "meta.json"), data, indent=1)


EXTRA_HOTSPOTS = [      # (id, label, [object names]): other natural click targets in the two areas
    ("gate-lions", "Guardian Lions", ["gate.lion", "gate.lion.001"]),
    ("gate-swords", "Sword Monoliths", ["gate.sword_monolith", "gate.sword_monolith.001"]),
    ("mirror-pavilion", "Pond Pavilion", ["mirror.ting"]),
    ("mirror-pond", "Still Pond", ["mirror.pond"]),
    ("mirror-blossom", "Peach Blossom", ["mirror.blossom"]),
    ("mirror-censer", "Incense Burner", ["mirror.censer"]),
]


def _object_points(o, dg, M=None, depth=0):
    """World-space bounding-box corners of an object, following collection instances."""
    M = o.matrix_world if M is None else M
    pts = []
    if o.type in GEOM_TYPES:
        ev = o.evaluated_get(dg)
        pts.extend(M @ Vector(c) for c in ev.bound_box)
    if o.instance_type == "COLLECTION" and o.instance_collection is not None and depth < 4:
        coll = o.instance_collection
        off = Matrix.Translation(-Vector(coll.instance_offset))
        for c in coll.all_objects:
            pts.extend(_object_points(c, dg, M @ off @ c.matrix_world, depth + 1))
    return pts


def _subtree_box(names):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        for o in [ob] + list(ob.children_recursive):
            pts.extend(_object_points(o, dg))
    if not pts:
        return None
    p = np.array(pts)
    return p.min(0), p.max(0)


def _near_any(p, R, S, d):
    """True when the point is within d of a visible record (keeps only lights around the stretch)."""
    p = np.array(p)
    m = S["any"]
    dd = np.linalg.norm(np.maximum(np.maximum(R.lo[m] - p, p - R.hi[m]), 0.0), axis=1)
    return bool((dd < d).any())


# ---- sky panorama -----------------------------------------------------------------------------

def cmd_sky(a):
    """World-only equirectangular render (Cycles), plus sampled gradient colours."""
    src = bpy.context.scene
    sc = bpy.data.scenes.new("web.sky")
    sc.world = src.world
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:
        log("sky: GPU setup failed, CPU", e)
    sc.cycles.samples = 64
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 2048, 1024, 100
    sc.view_settings.view_transform = src.view_settings.view_transform
    sc.view_settings.look = src.view_settings.look
    sc.view_settings.exposure = src.view_settings.exposure
    sc.render.use_compositing = False
    sc.render.image_settings.file_format = "PNG"
    cd = bpy.data.cameras.new("web.skycam")
    cd.type = "PANO"
    try:
        cd.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        sc.cycles.panorama_type = "EQUIRECTANGULAR"
    co = bpy.data.objects.new("web.skycam", cd)
    sc.collection.objects.link(co)
    co.location = (0.0, 0.0, 60.0)
    co.rotation_euler = (math.radians(90), 0.0, math.radians(-90))     # image centre looks at +X (east)
    sc.camera = co
    out = os.path.join(a.out, "sky.png")
    os.makedirs(a.out, exist_ok=True)
    sc.render.filepath = out
    t0 = time.time()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    log("sky rendered", out, round(time.time() - t0, 1), "s")
    img = bpy.data.images.load(out)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[::-1, :, :3]        # row 0 = top (zenith); values are display sRGB 0..1

    def at(az_u, el_deg, du=0.02, dv=2.0):
        v0 = int((0.5 - (el_deg + dv) / 180.0) * h)
        v1 = max(v0 + 1, int((0.5 - (el_deg - dv) / 180.0) * h))
        u0 = int((az_u - du) * w) % w
        u1 = int((az_u + du) * w) % w
        cols = px[v0:v1, u0:u1] if u1 > u0 else np.concatenate([px[v0:v1, u0:], px[v0:v1, :u1]], 1)
        c = cols.reshape(-1, 3).mean(0)
        return "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in np.clip(c, 0, 1))
    # three.js equirect u: 0.25 north (-Z), 0.5 east (+X), 0.75 south (+Z), ~0.95 the sun (WSW)
    sun_u = (math.atan2(0.307, -0.944) / (2 * math.pi)) + 0.5
    samples = dict(zenith=at(0.5, 88.0, du=0.5, dv=2.0), horizon=at(0.25, 3.0, du=0.1),
                   horizon_north=at(0.25, 3.0, du=0.05), horizon_south=at(0.75, 3.0, du=0.05),
                   horizon_east=at(0.5, 3.0, du=0.05), horizon_sun=at(sun_u - 0.03, 4.0, du=0.02),
                   mid_north=at(0.25, 30.0, du=0.05), below=at(0.25, -8.0, du=0.1), sun_u=round(sun_u, 4))
    log("sky samples", json.dumps(samples))
    dump(os.path.join(OUT_WEB, "sky_samples.json"), samples, indent=1)


# ---- flyer ------------------------------------------------------------------------------------

def _all_children(ob):
    return list(ob.children_recursive)


def cmd_flyer(a):
    scene = bpy.context.scene
    root = bpy.data.objects[FLYER_ROOT]
    f0, f1 = frame_range(a.frames)
    frames = list(range(f0, f1 + 1))
    mats = sample_matrices(root, frames)
    rows = []
    for f, M in zip(frames, mats):
        loc, rot, sc = M.decompose()
        rows.append(dict(f=f, p=v3(loc, 3), q=q_object(rot.to_matrix())))
    scene.frame_set(f0)
    dg = bpy.context.evaluated_depsgraph_get()
    inv = root.matrix_world.inverted()
    coll = bpy.data.collections.new("web.flyer")
    scene.collection.children.link(coll)
    top = bpy.data.objects.new("flyer", None)
    coll.objects.link(top)
    cache = {}
    n_tris = 0
    made = {}
    kids = [o for o in _all_children(root) if o.type in GEOM_TYPES]
    for o in kids:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=False, depsgraph=dg)
        _slot_materials(me, ev)
        for i, m in enumerate(me.materials):
            me.materials[i] = web_material(m, cache)
        n_tris += _mesh_tris(me)[0]
        ob = bpy.data.objects.new(o.name, me)
        coll.objects.link(ob)
        ob.parent = top
        ob.matrix_basis = inv @ o.matrix_world
        made[o.name] = ob
    log("flyer meshes", len(made), "tris", n_tris)
    path = os.path.join(a.out, "flyer.glb")
    export_glb(path, [top] + list(made.values()))
    data = dict(fps=scene.render.fps, frameStart=f0, frameEnd=f1, frames=rows, node="flyer",
                convention="three.js world; p, q place the flyer.glb root (its local -Z is the flight "
                           "direction, +Y up). Cloth flutter (Blender Wave modifiers) is not exported.")
    dump(os.path.join(a.out, "flyer.json"), data)


# ---- glTF helpers -----------------------------------------------------------------------------

_RENAMED = {}


def web_material(src, cache):
    """A plain Principled material that keeps the source material's name (the source is renamed;
    the .blend is never saved). Base colour = the material's viewport colour."""
    if src is None:
        key = "_none"
        if key not in cache:
            m = bpy.data.materials.new("M.none")
            cache[key] = m
        return cache[key]
    if src.name in cache:
        return cache[src.name]
    if src.name.endswith(".web") or src.get("web_plain"):
        cache[src.name] = src
        return src
    info = material_info(src)
    name = src.name
    src.name = name + ".src"
    m = bpy.data.materials.new(name)
    m["web_plain"] = True
    m["web_src"] = json.dumps({k: info[k] for k in ("procedural", "emission", "transparent", "additive",
                                                     "volume_only")})
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    col = tuple(src.diffuse_color)
    b.inputs["Base Color"].default_value = (col[0], col[1], col[2], 1.0)
    b.inputs["Roughness"].default_value = float(getattr(src, "roughness", 0.5))
    b.inputs["Metallic"].default_value = float(getattr(src, "metallic", 0.0))
    if info["emission"]:
        b.inputs["Emission Color"].default_value = (col[0], col[1], col[2], 1.0)
        b.inputs["Emission Strength"].default_value = 2.0
    if info["transparent"] or info["additive"]:
        b.inputs["Alpha"].default_value = 0.45 if not info["additive"] else 0.25
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    m.diffuse_color = src.diffuse_color
    cache[src.name] = m
    cache[name] = m
    return m


def glb_stats(path):
    """What a browser will draw: triangles (instances multiplied out), mesh nodes, primitives (draw calls)."""
    import struct
    with open(path, "rb") as fh:
        data = fh.read()
    n = struct.unpack("<I", data[12:16])[0]
    j = json.loads(data[20:20 + n])
    tris = prims = mesh_nodes = inst_nodes = 0
    for nd in j.get("nodes", []):
        if "mesh" not in nd:
            continue
        mesh_nodes += 1
        cnt = 1
        ext = nd.get("extensions", {}).get("EXT_mesh_gpu_instancing")
        if ext:
            cnt = j["accessors"][ext["attributes"]["TRANSLATION"]]["count"]
            inst_nodes += 1
        for p in j["meshes"][nd["mesh"]]["primitives"]:
            prims += 1
            acc = p.get("indices", p["attributes"]["POSITION"])
            tris += j["accessors"][acc]["count"] // 3 * cnt
    return dict(triangles=tris, draw_calls=prims, mesh_nodes=mesh_nodes, instanced_nodes=inst_nodes,
                nodes=len(j.get("nodes", [])), materials=len(j.get("materials", [])), bytes=len(data))


def export_glb(path, objects, gpu_instances=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for ob in bpy.context.view_layer.objects:
        try:
            ob.select_set(False)
        except Exception:
            pass
    for ob in objects:
        ob.select_set(True)
    # use_active_scene matters: with several Blender scenes the 5.2 exporter writes several glTF scenes and its
    # EXT_mesh_gpu_instancing pass only cleans up the last one, leaving broken node indices
    kw = dict(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True, export_extras=True,
              export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
              export_animations=False, export_materials="EXPORT", export_texcoords=False,
              export_normals=True, export_draco_mesh_compression_enable=False)
    if gpu_instances:
        kw["export_gpu_instances"] = True
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    for k in list(kw):
        if k not in props:
            log("glTF option missing:", k)
            kw.pop(k)
    t0 = time.time()
    bpy.ops.export_scene.gltf(**kw)
    log("exported", path, os.path.getsize(path), "bytes in", round(time.time() - t0, 1), "s")


# ---- scene export (stand-in, plain colours) ---------------------------------------------------

LEVELS = np.array([1.0, 0.5, 0.25, 0.12, 0.06, 0.03, 0.015, 0.008])
MIN_TRIS = 12                 # never decimate below this
VEG_WORDS = ("pine", "blossom", "shrub", "grass", "bamboo", "willow")
VEG_CAP = 2500                # triangles per vegetation instance at most
SPLIT_MIN_TRIS = 50000        # big single meshes (the range) are split by distance to the camera path
SPLIT_MIN_DIAG = 250.0
SPLIT_RATIOS = dict(near=0.5, mid=0.2, far=0.05)
SPLIT_NEAR = 250.0
FX_WORDS = ("smoke", "mist", "cloud_puff", "haze", "heat", "cloud_fog")
EXCLUDE_OWNERS = ("world.cloud_sea", "world.moon", "world.moon_halo", "world.haze", "world.cloud_fog")
EXCLUDE_PREFIX = ("world.cirrus",)
BACKDROP_SHARE = 0.15         # of --max-tris for backdrop_unbaked.glb
FOCUS_AREAS = ("gate", "mirror")
LOD_WEIGHTS = dict(focus=10.0, links=4.0, scenery=1.0, other=0.5)   # importance in the triangle budget
LINK_FLOOR = 0.5   # near-band stairways keep >= this ratio: collapse turns long runs of steps into saw teeth


def _is_fx(info):
    if not info:
        return False
    return bool(info.get("volume_only") or info.get("additive") or any(w in info["name"] for w in FX_WORDS))


def export_mask(R, minfo):
    """True for records that never go into a GLB (flyer, sky objects, volumes, additive FX)."""
    ex = np.zeros(len(R), bool)
    for i in range(len(R)):
        o = R.owner[i]
        if R.top[i] == FLYER_COLL or o in EXCLUDE_OWNERS or o.startswith(EXCLUDE_PREFIX):
            ex[i] = True
            continue
        mats = [m for m in R.tinfo[R.tkey[i]][2] if m]
        if mats and all(_is_fx(minfo.get(m)) for m in mats):
            ex[i] = True
    return ex


def lod_weights(R, idx, members):
    """Importance per record: the two areas of this test (and their hotspots) first, then the stairways
    between them, then the scatter, then the other areas seen in the distance."""
    w = np.empty(len(idx))
    for j, i in enumerate(idx):
        t, o = R.top[i], R.owner[i]
        if t in FOCUS_AREAS or o in members:
            w[j] = LOD_WEIGHTS["focus"]
        elif o.startswith("world.link"):
            w[j] = LOD_WEIGHTS["links"]
        elif t in ("scenery", "world"):
            w[j] = LOD_WEIGHTS["scenery"]
        else:
            w[j] = LOD_WEIGHTS["other"]
    return w


def lod_floor(R, idx, S, near):
    d = S.get("d_eff", S["dmin"])
    return np.array([LINK_FLOOR if R.owner[i].startswith("world.link") and d[i] <= near else 0.0 for i in idx])


def lod_levels(R, px, k, idx, w=None, floor=None):
    """Chosen LOD level index per record in idx: triangles ~ k * weight * px^2 (screen-space error rule)."""
    orig = R.tris[idx].astype(float)
    w = np.ones(len(idx)) if w is None else w
    want = np.clip(k * w * px[idx] ** 2, MIN_TRIS, None)
    veg = np.array([any(w in R.tkey[i] for w in VEG_WORDS) for i in idx], bool)
    want = np.where(veg, np.minimum(want, VEG_CAP), want)
    ratio = np.minimum(want / np.maximum(orig, 1), 1.0)
    if floor is not None:
        ratio = np.maximum(ratio, floor)
    li = (LEVELS[None, :] >= ratio[:, None]).sum(1) - 1
    return np.maximum(li, 0)


def fit_budget(R, px, idx, budget, w, picker, label, rounds=5, floor=None):
    """solve_k on estimates, then measure the real decimated triangle counts (collapse cannot shrink
    disconnected leaf cards as far as the ratio says) and shrink the working budget until it fits."""
    b = budget
    tcache = {}
    k, lv, tot = 0.0, None, 0
    for it in range(rounds):
        k = solve_k(R, px, idx, b, w, floor)
        lv = lod_levels(R, px, k, idx, w, floor)
        tot = 0
        for i, li in zip(idx, lv):
            me = picker.get(R.tkey[i], float(LEVELS[li]))
            if me is None:
                continue
            if me.name not in tcache:
                tcache[me.name] = _mesh_tris(me)[0]
            tot += tcache[me.name]
        log(label, "budget fit", it, "k", k, "working budget", int(b), "actual", tot, "target", int(budget))
        if tot <= budget * 1.02:
            break
        b *= budget / tot * 0.97
    return k, lv, tot


def solve_k(R, px, idx, budget, w=None, floor=None):
    lo, hi = 1e-7, 1.0
    orig = R.tris[idx].astype(float)
    for _ in range(50):
        k = math.sqrt(lo * hi)
        est = (orig * LEVELS[lod_levels(R, px, k, idx, w, floor)]).sum()
        if est > budget:
            hi = k
        else:
            lo = k
    return lo


def all_hotspots():
    if PROFILE == "full":
        return [(h["id"], h["label"], h["names"]) for h in HOTSPOT_DEFS]
    return [(h[0], h[1], h[2]) for h in HOTSPOTS] + [(e[0], e[1], e[2]) for e in EXTRA_HOTSPOTS]


def hotspot_members():
    """object name -> hotspot id for every object in a hotspot subtree (memoized: computed before the export
    objects take over the original names). Full profile: item-level hotspots come first in HOTSPOT_DEFS, so
    e.g. the library's lit floors belong to 'school:<i>', not to the pagoda's 'library'."""
    global _MEMBERS
    if _MEMBERS is not None:
        return _MEMBERS
    m = {}
    for hid, label, names in all_hotspots():
        for nm in names:
            ob = bpy.data.objects.get(nm)
            if ob is None:
                continue
            for o in [ob] + list(ob.children_recursive):
                m.setdefault(o.name, hid)
    _MEMBERS = m
    return m


def capture_bases(tkeys):
    """tkey -> standalone evaluated mesh copy (taken from the first depsgraph instance of it)."""
    dg = bpy.context.evaluated_depsgraph_get()
    need = set(tkeys)
    out = {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in GEOM_TYPES:
            continue
        tk = ob.original.name if inst.is_instance else "#" + ob.original.name
        if tk in need and tk not in out:
            try:
                me = bpy.data.meshes.new_from_object(ob, preserve_all_data_layers=False, depsgraph=dg)
            except Exception as e:
                log("WARN mesh capture failed", tk, e)
                continue
            _slot_materials(me, ob)
            out[tk] = me
            if len(out) == len(need):
                break
    log("captured", len(out), "base meshes of", len(need))
    return out


def _slot_materials(me, ob):
    """Copy the object's effective slot materials onto a mesh copy (object-linked slots, e.g. the banner
    cloth, are otherwise lost and export as 'M.none')."""
    for i, slot in enumerate(ob.material_slots):
        if i < len(me.materials) and slot.material is not None:
            me.materials[i] = slot.material.original      # evaluated materials are read-only copies


LOD_CHAIN = ("hero", "mid", "far")


class MeshPicker:
    """Mesh for (tkey, LOD ratio). Trees with designed LODs (nature.proto.<kind>.<sp>.v<n>.hero|mid|far) use
    the least detailed designed LOD that still meets the target, and only then decimate: collapse turns
    leaf cards into sparse shards long before it reaches a low triangle count."""

    def __init__(self, bases, dec):
        self.bases, self.dec = bases, dec
        self.ntri = {}
        self.alt = {}

    def tris(self, me):
        if me.name not in self.ntri:
            self.ntri[me.name] = _mesh_tris(me)[0]
        return self.ntri[me.name]

    def designed(self, tkey):
        if tkey in self.alt:
            return self.alt[tkey]
        out = []
        parts = tkey.rsplit(".", 1)
        if tkey.startswith("nature.proto.") and len(parts) == 2 and parts[1] in LOD_CHAIN:
            stem, lod = parts
            for l in LOD_CHAIN[LOD_CHAIN.index(lod):]:
                nm = stem + "." + l
                me = self.bases.get(nm)
                if me is None:
                    ob = bpy.data.objects.get(nm)
                    if ob is not None and ob.type == "MESH":
                        me = ob.data.copy()
                        _slot_materials(me, ob)
                        self.bases[nm] = me
                if me is not None:
                    out.append((nm, me))
        self.alt[tkey] = out
        return out

    def get(self, tkey, ratio):
        base = self.bases.get(tkey)
        if base is None:
            return None
        lods = self.designed(tkey) if ratio < 0.999 else []
        if len(lods) > 1:
            target = self.tris(base) * ratio
            pick = lods[0]
            for nm, me in lods:
                if self.tris(me) >= 0.8 * target:
                    pick = (nm, me)
            nm, me = pick
            r = target / max(self.tris(me), 1)
            return self.dec.get(nm, me, r) if r < 0.85 else me
        return self.dec.get(tkey, base, ratio)


class Decimator:
    """Collapse-decimated copies of meshes, cached by (key, ratio)."""

    def __init__(self, scene=None):
        # a one-object scene, so each re-evaluation does not touch the 7,784-object sect
        self.sc = bpy.data.scenes.new("web.decimate")
        self.ob = bpy.data.objects.new("web.decimator", bpy.data.meshes.new("web.decimator"))
        self.sc.collection.objects.link(self.ob)
        self.mod = self.ob.modifiers.new("dec", "DECIMATE")
        self.mod.decimate_type = "COLLAPSE"
        self.mod.use_collapse_triangulate = True
        self.cache = {}
        self.n = 0
        self.t = 0.0

    def get(self, key, base, ratio):
        if ratio >= 0.999:
            return base
        ck = (key, round(ratio, 4))
        if ck in self.cache:
            return self.cache[ck]
        t0 = time.time()
        self.ob.data = base
        self.mod.ratio = ratio
        with bpy.context.temp_override(scene=self.sc, view_layer=self.sc.view_layers[0]):
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            ev = self.ob.evaluated_get(dg)
            me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=False, depsgraph=dg)
        self.cache[ck] = me
        self.n += 1
        self.t += time.time() - t0
        if self.n % 500 == 0:
            log("decimated", self.n, "meshes in", round(self.t, 1), "s")
        return me


def split_faces(me, M, cam_mats, tan_v, aspect_w, mid):
    """Face masks (near, mid, far) of a big mesh by distance to the sampled camera path; faces that never
    enter the widened frustum are dropped."""
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    M = np.asarray(M, float)
    c = c.reshape(n, 3) @ M[:3, :3].T + M[:3, 3]
    dmin = np.full(n, np.inf)
    seen = np.zeros(n, bool)
    for Mc in cam_mats:
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = c @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            nx = v[:, 0] / z / (tan_v * aspect_w)
            ny = v[:, 1] / z / tan_v
        inside = (z > 0.1) & (np.abs(nx) <= 1.15) & (np.abs(ny) <= 1.15)
        seen |= inside
        d = np.linalg.norm(c - Mc[:3, 3], axis=1)
        dmin = np.where(inside, np.minimum(dmin, d), dmin)
    near = seen & (dmin <= SPLIT_NEAR)
    midm = seen & (dmin > SPLIT_NEAR) & (dmin <= mid)
    far = seen & (dmin > mid)
    return near, midm, far


def submesh(me, mask, name):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f, k in zip(bm.faces, mask) if not k]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in me.materials:
        out.materials.append(m)
    return out


def merge_meshes(items, name):
    """One mesh from [(mesh, 4x4 world matrix)], materials remapped onto a shared slot list."""
    import bmesh
    slots = []
    bm = bmesh.new()
    for me, M in items:
        tmp = me.copy()
        M = np.asarray(M, float)
        tmp.transform(Matrix(M.tolist()))
        if np.linalg.det(M[:3, :3]) < 0:
            tmp.flip_normals()
        remap = []
        for m in me.materials:
            if m not in slots:
                slots.append(m)
            remap.append(slots.index(m))
        if remap and len(tmp.polygons):
            mi = np.empty(len(tmp.polygons), np.int32)
            tmp.polygons.foreach_get("material_index", mi)
            mi = np.array(remap, np.int32)[np.clip(mi, 0, len(remap) - 1)]
            tmp.polygons.foreach_set("material_index", mi)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in slots:
        out.materials.append(m)
    return out


def _free_name(name):
    """Make `name` available for a new object by renaming an existing original (the .blend is never saved)."""
    ob = bpy.data.objects.get(name)
    if ob is not None and not ob.get("web_export"):
        ob.name = name[:52] + ".src"
    return name


def _new_obj(name, data, coll, parent=None, basis=None):
    _free_name(name)
    ob = bpy.data.objects.new(name, data)
    ob["web_export"] = True
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    if basis is not None:
        ob.matrix_basis = Matrix(np.asarray(basis, float).tolist())
    return ob


def _short(s, n=60):
    import zlib
    return s if len(s) <= n else s[:n - 9] + "~%08x" % (zlib.crc32(s.encode()) & 0xffffffff)


def build_export(scene, R, S, idx, levels, split_pieces, picker, matcache, label, merge_mid, near_max,
                 prefix=None, root_obj=None, use_hotspots=True):
    """Create the export objects for records idx (LOD level indices `levels`) in a new collection.
    Non-instanced objects keep their Blender names (mid-band ones are joined per collection when
    merge_mid); instances become '<group>|<proto>|L<n>' Empties whose children share one mesh.
    prefix: top node / group name prefix (default 'coll.' for label 'scene', else 'far.'); root_obj: parent of
    the top nodes (e.g. a proxy root carrying extras); use_hotspots=False: no hotspot nodes (backdrop, proxies)."""
    coll = bpy.data.collections.new("web.export." + label)
    scene.collection.children.link(coll)
    made = []
    tops = {}
    members = hotspot_members() if use_hotspots else {}
    labels = {h[0]: h[1] for h in all_hotspots()}
    hnodes = {}
    gprefix = "" if prefix is None else prefix
    prefix = prefix if prefix is not None else ("coll." if label == "scene" else "far.")
    stats = collections.Counter()
    by_top = collections.Counter()

    def top_node(t):
        if t not in tops:
            tops[t] = _new_obj(prefix + t, None, coll, parent=root_obj)
            made.append(tops[t])
        return tops[t]

    def hot_node(hid, top):
        if hid not in hnodes:
            ob = _new_obj("hotspot." + hid, None, coll, parent=top_node(top))
            ob["hotspot"] = hid
            ob["label"] = labels.get(hid, hid)
            hnodes[hid] = ob
            made.append(ob)
        return hnodes[hid]

    def remat(me):
        for i, m in enumerate(me.materials):
            me.materials[i] = web_material(m, matcache)

    groups = collections.defaultdict(list)
    merged = collections.defaultdict(list)
    for i, li in zip(idx, levels):
        me = picker.get(R.tkey[i], float(LEVELS[li]))
        if me is None:
            stats["missing_mesh"] += 1
            continue
        hid = members.get(R.owner[i])
        if R.inst[i]:
            groups[(hid or "", R.top[i], R.proto[i], int(li))].append(i)
            continue
        if merge_mid and hid is None and S["dmin"][i] > near_max:
            merged[R.top[i]].append((me, R.mw[i]))
            continue
        remat(me)
        parent = hot_node(hid, R.top[i]) if hid else top_node(R.top[i])
        made.append(_new_obj(R.name[i], me, coll, parent=parent, basis=R.mw[i]))
        t = _mesh_tris(me)[0]
        stats["triangles"] += t
        by_top[R.top[i]] += t
        stats["named_nodes"] += 1
    for (top, owner), pieces in split_pieces.items():
        for piece_name, me in pieces:
            remat(me)
            made.append(_new_obj(piece_name, me, coll, parent=top_node(top), basis=np.eye(4)))
            t = _mesh_tris(me)[0]
            stats["triangles"] += t
            by_top[top] += t
            stats["split_nodes"] += 1
    for t, items in merged.items():
        me = merge_meshes(items, "merged." + t)
        remat(me)
        made.append(_new_obj(prefix + t + ".merged", me, coll, parent=top_node(t), basis=np.eye(4)))
        stats["triangles"] += _mesh_tris(me)[0]
        by_top[t] += _mesh_tris(me)[0]
        stats["merged_nodes"] += 1
        stats["merged_objects"] += len(items)
    for (hid, top, proto, li), items in groups.items():
        me = picker.get(R.tkey[items[0]], float(LEVELS[li]))
        remat(me)
        parent = hot_node(hid, top) if hid else top_node(top)
        g = _new_obj(_short(gprefix + "%s|%s|L%d" % (hid or top, proto, li)), None, coll, parent=parent)
        g["proto"] = proto
        g["lod"] = float(LEVELS[li])
        g["instances"] = len(items)
        made.append(g)
        t = _mesh_tris(me)[0]
        for j, i in enumerate(items):
            o = bpy.data.objects.new("%s#%d" % (g.name[:50], j), me)
            o["web_export"] = True
            coll.objects.link(o)
            o.parent = g
            o.matrix_basis = Matrix(np.asarray(R.mw[i], float).tolist())
            made.append(o)
        stats["triangles"] += t * len(items)
        by_top[top] += t * len(items)
        stats["instances"] += len(items)
        stats["instance_groups"] += 1
    stats["hotspot_nodes"] = len(hnodes)
    out = dict(stats)
    out["triangles_by_collection"] = dict(by_top.most_common())
    log(label, json.dumps(out))
    return made, out


def cmd_scene(a):
    scene = bpy.context.scene
    t0 = time.time()
    R = gather(scene)
    S, cache_frames = load_cache(R)
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    ex = export_mask(R, minfo)
    px = S["pxmax"].astype(float)
    sel = S["any"] & (px >= MIN_PX) & ~ex
    diag = np.linalg.norm(R.hi - R.lo, axis=1)
    big = sel & ~R.inst & (R.tris >= SPLIT_MIN_TRIS) & (diag >= SPLIT_MIN_DIAG)
    far = S["dmin"] > a.mid
    nm_idx = np.nonzero(sel & ~big & ~far)[0]
    far_idx = np.nonzero(sel & ~big & far)[0]
    big_idx = np.nonzero(big)[0]
    log("selected near/mid", len(nm_idx), int(R.tris[nm_idx].sum()), "far", len(far_idx), int(R.tris[far_idx].sum()),
        "split", [R.name[i] for i in big_idx], "excluded (fx/sky/flyer)", int((S["any"] & ex).sum()))

    cam = bpy.data.objects[CAMERA]
    cam_mats = load_views(cam).mats
    th, tv = camera_tan(cam)
    aspect_w = DEPTH_RES[0] / DEPTH_RES[1]
    bases = capture_bases([R.tkey[i] for i in np.concatenate([nm_idx, far_idx, big_idx])])
    dec = Decimator(scene)
    split_scene, split_far = {}, {}
    used_scene = used_far = 0
    for i in big_idx:
        base = bases.get(R.tkey[i])
        if base is None:
            continue
        msk = split_faces(base, R.mw[i], cam_mats, tv, aspect_w, a.mid)
        world_base = base.copy()
        world_base.transform(Matrix(np.asarray(R.mw[i], float).tolist()))
        for part, m in zip(("near", "mid", "far"), msk):
            if not m.any():
                continue
            nm = "%s.%s" % (R.name[i], part)
            sub = submesh(world_base, m, nm)
            me = dec.get(nm, sub, SPLIT_RATIOS[part])
            t = _mesh_tris(me)[0]
            target = split_far if part == "far" else split_scene
            target.setdefault((R.top[i], R.name[i]), []).append((nm, me))
            if part == "far":
                used_far += t
            else:
                used_scene += t
            log("split", R.name[i], part, "faces", int(m.sum()), "->", t, "tris")
    b_scene = a.max_tris * (1 - BACKDROP_SHARE) - used_scene
    b_far = a.max_tris * BACKDROP_SHARE - used_far
    members = hotspot_members()
    w_scene = lod_weights(R, nm_idx, members)
    picker = MeshPicker(bases, dec)
    fl = lod_floor(R, nm_idx, S, a.near)
    log("stairway floor: records", int((fl > 0).sum()), "source tris", int(R.tris[nm_idx][fl > 0].sum()))
    k_scene, lv_scene, _ = fit_budget(R, px, nm_idx, b_scene, w_scene, picker, "scene", floor=fl)
    k_far, lv_far, _ = fit_budget(R, px, far_idx, b_far, None, picker, "backdrop")
    log("k scene", k_scene, "k far", k_far, "budgets", int(b_scene), int(b_far),
        "level histogram scene", np.bincount(lv_scene, minlength=len(LEVELS)).tolist(),
        "far", np.bincount(lv_far, minlength=len(LEVELS)).tolist())
    matcache = {}
    stats = {}
    os.makedirs(a.out, exist_ok=True)
    made, stats["scene"] = build_export(scene, R, S, nm_idx, lv_scene, split_scene, picker, matcache, "scene",
                                        bool(a.merge_mid), a.near)
    p_scene = os.path.join(a.out, "scene_unbaked.glb")
    export_glb(p_scene, made, gpu_instances=True)
    stats["scene"]["bytes"] = os.path.getsize(p_scene)
    stats["scene"]["glb"] = glb_stats(p_scene)
    made_far, stats["backdrop"] = build_export(scene, R, S, far_idx, lv_far, split_far, picker, matcache,
                                               "backdrop", True, 0.0)
    p_far = os.path.join(a.out, "backdrop_unbaked.glb")
    export_glb(p_far, made_far, gpu_instances=True)
    stats["backdrop"]["bytes"] = os.path.getsize(p_far)
    stats["backdrop"]["glb"] = glb_stats(p_far)
    stats["k"] = dict(scene=k_scene, backdrop=k_far)
    stats["selected"] = dict(near_mid=len(nm_idx), near_mid_source_tris=int(R.tris[nm_idx].sum()),
                             far=len(far_idx), far_source_tris=int(R.tris[far_idx].sum()),
                             split=[R.name[i] for i in big_idx])
    stats["levels"] = LEVELS.tolist()
    stats["time_s"] = round(time.time() - t0, 1)
    dump(os.path.join(OUT_WEB, "export_stats.json"), stats, indent=1)
    # merge into the existing manifest (keeps keys other steps own, e.g. "clouds", "water", "sceneLow")
    mp = os.path.join(a.out, "manifest.json")
    manifest = {}
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8") as fh:
            manifest = json.load(fh)
    manifest.update(scene=["scene_unbaked.glb", "backdrop_unbaked.glb"], camera="camera.json", meta="meta.json",
                    flyer="flyer.glb", flyerPath="flyer.json", baked=False)
    for k in ("sceneLow", "water", "sceneDeferred"):      # baked-only keys (the stand-in carries its own waterfalls)
        manifest.pop(k, None)
    dump(mp, manifest, indent=1)
    log("SCENE", json.dumps(stats))


# ---- clouds -----------------------------------------------------------------------------------

def cmd_clouds(a):
    """Volume cloud puffs (world.cloud.*) as ellipsoids in three.js space -> <out>/clouds.json, the web
    contract format: {"puffs": [{"c": centre, "a": [three semi-axes], "d": density}]}. Each puff domain is a
    unit icosphere, so the world matrix columns are the semi-axes. Adds "clouds" to manifest.json."""
    puffs, skipped = [], 0
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or not ob.name.startswith("world.cloud."):
            continue
        if not ob.visible_get() or ob.hide_render:
            skipped += 1
            continue
        mw = ob.matrix_world
        m3 = C3 @ mw.to_3x3()
        c = C3 @ mw.translation
        puffs.append(dict(c=[round(c.x, 2), round(c.y, 2), round(c.z, 2)],
                          a=[[round(m3[r][k], 3) for r in range(3)] for k in range(3)],
                          d=round(float(ob.get("density", 1.0)), 4)))
    data = dict(units="three.js world (Y up), metres",
                format="c = centre; a = the three semi-axes (the puff is the unit sphere mapped by them); "
                       "d = Blender's size-normalised volume density",
                source="world.cloud.* volume puffs in out/sect_chase.blend (sect/export_web.py clouds)",
                puffs=puffs)
    os.makedirs(a.out, exist_ok=True)
    dump(os.path.join(a.out, "clouds.json"), data)
    mp = os.path.join(a.out, "manifest.json")
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8") as fh:
            man = json.load(fh)
        man["clouds"] = "clouds.json"
        dump(mp, man, indent=1)
    log("clouds", len(puffs), "puffs,", skipped, "hidden")
    if PROFILE == "full":
        # web-only mist round the peaks, in the gorges and under the islands (sect/mist.py: pure Python
        # from the baked GLBs in out/web/full/raw and site/camera.json + meta.json, so it also runs on
        # the PC without Blender). Decoration: never fail the export over it.
        try:
            from sect import mist as MIST
            MIST.apply(full=WORK, site=a.out)
        except (Exception, SystemExit) as e:  # noqa: BLE001  (mist.load_voxels raises SystemExit without raw GLBs;
            # uncaught, it would end Blender and skip the commands after 'clouds')
            log("clouds: mist skipped (%s: %s); run: python -I sect/mist.py" % (type(e).__name__, e))


# ---- verify -----------------------------------------------------------------------------------

def cmd_verify(a):
    """Run with --factory-startup and no .blend: import the GLBs, rebuild the camera from camera.json."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    scene = bpy.context.scene
    with open(os.path.join(a.out, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    with open(os.path.join(a.out, "camera.json"), encoding="utf-8") as fh:
        camj = json.load(fh)
    with open(os.path.join(a.out, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    for g in man["scene"]:
        bpy.ops.import_scene.gltf(filepath=os.path.join(a.out, g))
    log("imported", len(bpy.data.objects), "objects")
    cd = bpy.data.cameras.new("verify.cam")
    cam = bpy.data.objects.new("verify.cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cd.sensor_fit = "VERTICAL"
    cd.clip_start, cd.clip_end = 0.1, 9000.0
    sun = bpy.data.objects.new("verify.sun", bpy.data.lights.new("verify.sun", "SUN"))
    scene.collection.objects.link(sun)
    d3 = Vector(meta["sun"]["direction"])
    db = Vector((d3.x, -d3.z, d3.y))
    sun.rotation_euler = db.to_track_quat("Z", "Y").to_euler()
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.75, 0.55)
    world = bpy.data.worlds.new("verify.world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.5, 0.65, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 8
    w, h = (int(x) for x in a.res.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    out = os.path.join(OUT_WEB, "verify")
    os.makedirs(out, exist_ok=True)
    from mathutils import Quaternion
    for f in [int(x) for x in a.ref_frames.split(",")]:
        row = camj["frames"][f - camj["frameStart"]]
        p, q = row["p"], row["q"]
        cam.location = (p[0], -p[2], p[1])
        R3 = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = (C3.transposed() @ R3).to_quaternion()
        cd.sensor_height = 36.0 * 9 / 16
        cd.lens = (cd.sensor_height / 2) / math.tan(math.radians(row["fovY"]) / 2)
        scene.render.filepath = os.path.join(out, "verify_%d.png" % f)
        bpy.ops.render.render(write_still=True)
        log("verify", f, scene.render.filepath)


# ---- audit.md ---------------------------------------------------------------------------------

def _m(n):
    return "%.2fM" % (n / 1e6) if n >= 1e6 else ("%.0fk" % (n / 1e3) if n >= 1e4 else str(int(n)))


def write_audit_md(a):
    """out/web/audit.md from audit.json (+ export_stats.json and meta.json when present). No .blend needed."""
    with open(os.path.join(OUT_WEB, "audit.json"), encoding="utf-8") as fh:
        A = json.load(fh)
    st = {}
    p = os.path.join(OUT_WEB, "export_stats.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            st = json.load(fh)
    meta = {}
    p = os.path.join(PROTO, "meta.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            meta = json.load(fh)
    sc, vis, vp, bb = A["scene"], A["visible"], A["visible_min_px"], A["by_band"]
    non_scenery = sc["triangles"] - next(r["triangles"] for r in A["by_collection"] if r["collection"] == "scenery")
    L = []
    w = L.append
    w("# Web export audit: Mountain Gate to Heart-Mirror Terrace")
    w("")
    w("Source `out/sect_chase.blend`, camera `chase.cam`, frames %d-%d (24 fps), sampled every %d frames "
      "(%d samples). Written by `sect/export_web.py audit` (+ `auditmd`)." % (A["frames"][0], A["frames"][1],
                                                                             A["sampled_every"], A["sampled_frames"]))
    w("")
    w("## The short version")
    w("")
    w("- The whole file is **%s evaluated triangles** in %d objects (%d renderable geometry instances, %d of them "
      "instanced). The often-quoted 17.9M is the sect without the scenery pass (%s); scenery (forest, groves, "
      "islands, waterfalls) adds %s." % (_m(sc["triangles"]), sc["objects"], sc["geometry_instances"],
                                         sc["instanced_rows"], _m(non_scenery), _m(sc["triangles"] - non_scenery)))
    w("- chase.cam actually sees (frustum + depth-buffer occlusion) **%s triangles in %d instances** over the "
      "stretch; %s of them ever reach 1.5 px. A single frame peaks at **%s** visible triangles." % (
          _m(vis["triangles"]), vis["instances"], _m(vp["triangles"]), _m(A["per_frame_peak_tris"])))
    w("- By nearest distance to the camera: near (<= %d m) %s, mid (<= %d m) %s, far %s." % (
        A["bands"]["near_max_m"], _m(bb["near"]["triangles"]), A["bands"]["mid_max_m"], _m(bb["mid"]["triangles"]),
        _m(bb["far"]["triangles"])))
    veg_t = sum(v["tris"] for k, v in A["vegetation_visible"].items() if not k.startswith("lotus"))
    w("- Vegetation is %d %% of the visible triangles: far-LOD pines (~1k tris each), hero pines (14-18k each) "
      "and peach trees (15k each) dominate, then waterfall sheets (50-90k each), stone lanterns (~22k each) and "
      "roof beasts (2.6k each, hundreds of them)." % round(100.0 * veg_t / max(vp["triangles"], 1)))
    w("- Every material is procedural (no image textures at all), so colour detail only reaches the web through "
      "baking. A plain-colour stand-in reads as flat blocks.")
    w("")
    w("## Visible triangles by collection")
    w("")
    w("| collection | whole file | visible | near | mid | far | nearest m |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for r in A["by_collection"]:
        w("| %s | %s | %s | %s | %s | %s | %s |" % (r["collection"], _m(r["triangles"]), _m(r["visible_triangles"]),
                                                    _m(r["near_tris"]), _m(r["mid_tris"]), _m(r["far_tris"]),
                                                    r["nearest_m"]))
    w("")
    w("Gate and mirror sit entirely in the near band. Five other areas are seen in the background at 180-900 m "
      "(arena 180 m, mission 370 m, library 480 m, steles 620 m, scroll 800 m); forge comes within 57 m at the "
      "end (frame 288 already arrives at the forge). Abode, summit and formation are only ever beyond 900 m.")
    w("")
    w("## What the triangles are")
    w("")
    w("| proto (instanced) | visible | tris each | tris |")
    w("|---|---:|---:|---:|")
    for r in A["instanced_protos"][:14]:
        w("| %s | %d | %s | %s |" % (r["proto"], r["visible"], r["tris_each"], _m(r["tris"])))
    w("")
    w("| object / instancer | visible | tris | nearest m | max px |")
    w("|---|---:|---:|---:|---:|")
    for r in A["top_owners"][:16]:
        w("| %s | %d | %s | %s | %s |" % (r["owner"], r["visible"], _m(r["visible_tris"]), r["nearest_m"],
                                         r["max_px"]))
    w("")
    vv = A["vegetation_visible"]
    agg = collections.Counter()
    for k, v in vv.items():
        agg[k.split(".")[0] + "." + k.split(".")[-1] if k.split(".")[-1] in ("far", "mid", "hero", "low") else
            k.split(".")[0]] += v["count"]
    w("Visible plants: " + ", ".join("%s %d" % (k, v) for k, v in agg.most_common() if v > 5) +
      ". Whole file: " + ", ".join("%s %d" % (k, v) for k, v in A["vegetation_whole_scene"].items()) + ".")
    w("")
    w("## How the scene is built")
    w("")
    mods = A["modifiers_on_visible"]
    w("- **Instancing.** Geometry Nodes everywhere: %d `arch.gn.*` modifiers instance roof tiles, ridge beasts, "
      "rafter ends, dougong, balustrade posts and panels from single-mesh protos in the excluded `_protos` "
      "collection; %d `nature.scatter.random` modifiers scatter trees, shrubs and grass (protos "
      "`nature.proto.<kind>.v<n>.<far|mid|hero|low>`) over the forest, grove, cliff and island surfaces. "
      "Stone lanterns and lions are collection-instance Empties. Other modifiers: %d Wave (banners and the "
      "flyer's cloth)." % (mods["node_groups"].get("arch.gn.*", 0), mods["node_groups"].get("nature.scatter.random", 0),
                           mods["types"].get("WAVE", 0)))
    cl = A["material_classes_visible"]
    w("- **Materials.** %d of %d visible materials are procedural node trees (the rest are plain); none uses an "
      "image. All but two (mirror_face, flyer.skin) carry a viewport colour, which the stand-in uses. Emissive: %s. "
      "Volumes (no surface): %s. Transparent/blended: %s." % (cl["procedural"], len(A["materials_visible"]),
                                                            ", ".join(cl["emission"][:14]) + " ...",
                                                            ", ".join(cl["volume"]), ", ".join(cl["transparent"][:10]) + " ..."))
    wd = A["world"]
    w("- **Light.** One sun lamp (colour %s, %s W/m2, %s deg disc) at elevation 7 deg, azimuth 252 deg (WSW). Sky: "
      "%s Sky Texture x0.18 with a soft knee and a painted sun disc; below the horizon a procedural cloud floor. "
      "Haze: a 14 km volume box with height falloff. View: %s / %s, exposure %s; compositor bloom, grade, "
      "vignette. Render: EEVEE, quality '%s'." % (
          [round(c, 2) for c in wd["sun"]["colour"]], wd["sun"]["strength"], wd["sun"]["angle_deg"], wd["sky"]["type"],
          wd["view"]["transform"], wd["view"]["look"], wd["view"]["exposure"], wd["render"]["quality"]))
    g = wd["groups"]
    w("- **Cloud sea.** `world.cloud_sea`: an 18 km billowy sheet at z = -60 (51k tris, emissive warm tops) plus "
      "`world.cloud_fog`, a volume layer from -90 to +20. %d volume cloud banks (`world.cloud.*`, %d seen), including "
      "the opening bank the film starts in." % (g.get("cloud_banks", {}).get("total", 0),
                                                 g.get("cloud_banks", {}).get("visible", 0)))
    w("- **Moon.** `world.moon`, a self-lit sphere of radius 614 m about 6.4 km away (10.9 deg wide from the "
      "gate), with an additive halo disc. Always visible in the gate shots, upper right.")
    w("- **Waterfalls.** %d waterfall/stream objects with `nature_waterfall` (emissive + blended) are seen; %d "
      "of them lie within %d m. The sheets are dense (25-90k tris each)." % (
          g.get("waterfalls", {}).get("visible", 0), len(meta.get("waterfalls", [])), A["bands"]["mid_max_m"]))
    w("- **Islets.** %d floating-island pieces seen (rocks, roots and every plant instance on them), the nearest "
      "%s m away; their plant scatter is mostly shrubs at 3-20 px." % (g.get("islets", {}).get("visible", 0),
                                                                        g.get("islets", {}).get("nearest_m")))
    w("- **Far away.** %d of 14 backdrop massifs (from 685 m), the abode/summit/formation areas, far forest and "
      "islands. Largest far groups: %s." % (g.get("backdrop_massifs", {}).get("visible", 0),
                                            ", ".join("%s %s" % (r["group"].split(":")[1], _m(r["tris"]))
                                                      for r in A["far_groups"][:6])))
    w("")
    w("## Recommended export set")
    w("")
    w("1. **Near (<= 150 m), full detail, baked.** The gate and mirror collections, the gate stairway, the "
      "gate-to-mirror stairway and its arcade (`world.link.gate_mirror.*`), the range terrain within ~250 m of "
      "the path, and the groves and forest along the path. Bake lightmaps (Cycles) here; trees need their own "
      "LOD (hero pines at 16k are too heavy: use the `mid` protos or a 1-2k decimation with baked colour).")
    w("2. **Mid (150-900 m), reduced.** The other areas seen in the background (forge, arena, mission, library, "
      "steles, scroll), islands, waterfalls, far forest. Decimate hard (1-12 %), join per area, bake to vertex "
      "colour or a small atlas. Far pines become instanced cards or 30-60 tri blobs.")
    w("3. **Far (> 900 m), backdrop.** Backdrop massifs, abode, summit, formation, far islands and the moon: a baked "
      "panorama layer or a few low-poly silhouettes in a separate GLB, fogged. The sky itself is `sky.png`.")
    w("4. **Not geometry.** Haze, cloud fog, cloud banks, cirrus, smoke, mist, light beams and halos are volume or "
      "additive effects: recreate them in three.js (fog, sprites, a cloud-sea shader), using `meta.json`.")
    w("")
    if st:
        s1, s2 = st["scene"], st["backdrop"]
        w("## Stand-in export (`scene_unbaked.glb`, `backdrop_unbaked.glb`)")
        w("")
        w("Plain viewport colours, no UVs, LOD chosen per object so triangles ~ weight x on-screen size^2 "
          "(weights: gate/mirror and hotspots %s, stairways %s, scenery %s, other areas %s), fitted to "
          "--max-tris. Instanced protos are GPU-instanced (`EXT_mesh_gpu_instancing`)." % (
              LOD_WEIGHTS["focus"], LOD_WEIGHTS["links"], LOD_WEIGHTS["scenery"], LOD_WEIGHTS["other"]))
        w("")
        w("| file | triangles in file | draw calls | named nodes | instance groups / instances | merged | MB |")
        w("|---|---:|---:|---:|---:|---:|---:|")
        for nm, s_ in (("scene_unbaked.glb", s1), ("backdrop_unbaked.glb", s2)):
            g_ = s_.get("glb", {})
            w("| %s | %s | %s | %d | %d / %d | %d objects | %.1f |" % (
                nm, _m(g_.get("triangles", s_.get("triangles", 0))), g_.get("draw_calls", "?"), s_.get("named_nodes", 0),
                s_.get("instance_groups", 0), s_.get("instances", 0), s_.get("merged_objects", 0),
                s_.get("bytes", 0) / 1e6))
        w("")
        if s1.get("triangles_by_collection"):
            w("Scene triangles by collection (Blender side, before the exporter drops degenerate faces): " + ", ".join("%s %s" % (k, _m(v)) for k, v in
                                                            s1["triangles_by_collection"].items()) + ".")
            w("")
    w("## Surprises")
    w("")
    w("- 49.6M triangles, not 17.9M: the scenery pass nearly tripled the file.")
    w("- Frame 1 starts low in the haze at the stair foot; the gate is small and veiled until about frame 27. "
      "camera.json `startFrame` is 27 (first frame with the gate centred and clear, see `ref/start/`).")
    w("- Frame 288 is already the forge arrival (the forge section starts at 287), so the forge is in the near band.")
    w("- Even with occlusion, the camera sees 10-17M triangles in most frames because it flies along a canyon with "
      "forested slopes on both sides. Vegetation needs real LODs or impostors for the web.")
    w("- The waterfall sheets are the heaviest single objects (up to 90k triangles for a semi-transparent strip).")
    w("- Each stone lantern is ~22k triangles and there are 30+ on the gate stairway alone.")
    w("- Blender 5.2 glTF exporter: with more than one Blender scene in the file it writes several glTF scenes and "
      "its EXT_mesh_gpu_instancing pass corrupts the node list (export with use_active_scene). It also drops "
      "~15-20 % of the triangles of collapse-decimated meshes (degenerate faces), so budget on the file, not "
      "on Blender's count (`export_stats.json` -> `glb`).")
    w("- Collapse decimation shreds leaf-card trees; the stand-in swaps in the scene's own designed LODs "
      "(hero -> mid -> far protos) before decimating.")
    w("")
    w("## Files")
    w("")
    w("- `out/web/audit.json`: all numbers above plus per-frame load, top objects, materials, gate/mirror roots.")
    w("- `out/web/ref/ref_<frame>.png`: EEVEE references (flyer hidden), `ref/start/` for the start-frame choice.")
    w("- `client/public/sect/proto/`: manifest.json, camera.json, meta.json, sky.png, flyer.glb, flyer.json, "
      "scene_unbaked.glb, backdrop_unbaked.glb.")
    path = os.path.join(OUT_WEB, "audit.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    log("wrote", path)


def cmd_auditmd(a):
    write_audit_md(a)


# ---- reference renders ------------------------------------------------------------------------

def cmd_refs(a):
    scene = bpy.context.scene
    cam = bpy.data.objects[CAMERA]
    scene.camera = cam
    n = hide_flyer(scene)
    w, h = (int(x) for x in a.res.split("x"))
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.image_settings.file_format = "PNG"
    if scene.eevee.taa_render_samples < a.samples:
        scene.eevee.taa_render_samples = a.samples
    out = a.ref_dir or os.path.join(WORK, "ref")
    os.makedirs(out, exist_ok=True)
    log("refs: hid", n, "flyer objects; samples", scene.eevee.taa_render_samples)
    for f in [int(x) for x in a.ref_frames.split(",")]:
        t0 = time.time()
        scene.frame_set(f)
        r.filepath = os.path.join(out, "ref_%d.png" % f)
        bpy.ops.render.render(write_still=True)
        log("ref", f, r.filepath, round(time.time() - t0, 1), "s")


# ---- full path: hotspots ----------------------------------------------------------------------

FORGE_RING = (("dispatchai", "command_flag"), ("talktuahbank", "treasure_bowl"), ("sentinelai", "bell"),
              ("adapted", "bamboo_slips"), ("soundsearch", "lotus_lamp"), ("vocalyze", "spirit_brush"),
              ("tft", "immortal_peaches"), ("slugmeditate", "bead_string"), ("splatnft", "jade_disc"),
              ("swarmaid", "paper_cranes"), ("slugloop", "fire_wheel"))   # = areas/forge.py FORGE_RING (project id,
                                                                          # artifact): the winning projects
LIBRARY_FLOORS = ((1, 2), (3, 1), (5, 0))    # (library.LIT_FLOORS storey, EDUCATION index): library.py builds the
                                             # lit storeys bottom to top as Lynbrook, UCSC, USC; EDUCATION lists
                                             # USC first, so the bottom floor is school:2 and the top school:0
N_HACKATHONS = 36                            # arena: 40 banners, the first 36 (by banner index) are the wins
ABODE_FACTS = (                              # fact index -> (label, objects): PERSONAL_FACTS order
    ("Waterfall", ["abode.waterfall"]),                                   # 0: 4-year degree in 2.5 years
    ("Peach Blossom", ["abode.peach"]),                                   # 1: first hackathon win at 17
    ("Cliff Inscription", ["abode.inscription"]),                         # 2: Mandarin and English
    ("Wind Chimes", ["abode.wind_chime*"]),                               # 3: drums and piano
    ("Tea Table", ["abode.tea_table", "abode.tea_leg*", "abode.tea_set", "abode.cushion*"]),   # 4: noodles
    ("Crane", ["abode.crane"]),                                           # 5: a personal Jarvis
    ("Koi Pool", ["abode.pool", "abode.koi", "abode.koi.0*"]),           # 6: talk to software
)
AREA_HOTSPOTS = (                            # area level: (id, label or None = the area label, objects)
    ("gate", None, ["gate.paifang"]),
    ("gate-lions", "Guardian Lions", ["gate.lion", "gate.lion.001"]),
    ("gate-swords", "Sword Monoliths", ["gate.sword_monolith", "gate.sword_monolith.001"]),
    ("mirror", None, ["mirror.mirror_stand"]),
    ("mirror-pavilion", "Pond Pavilion", ["mirror.ting"]),
    ("mirror-pond", "Still Pond", ["mirror.pond"]),
    ("mirror-blossom", "Peach Blossom", ["mirror.blossom"]),
    ("mirror-censer", "Incense Burner", ["mirror.censer"]),
    ("forge", None, ["forge.ding", "forge.dais"]),
    ("forge-hall", "Forge Hall", ["forge.hall"]),
    ("arena", None, ["arena.sword"]),
    ("arena-judges", "Judges' Pavilion", ["arena.judges"]),
    ("mission", None, ["mission.hall"]),
    ("mission-bell", "Bell Tower", ["mission.bell_tower"]),
    ("library", None, ["library.pagoda"]),
    ("library-pond", "Lotus Pond", ["library.pond", "library.lotus"]),
    ("steles", None, ["steles.stele_master"]),
    ("scroll", None, ["scroll.pavilion"]),
    ("formation", None, ["formation.core"]),
    ("abode", None, ["abode.gate_ring", "abode.gate_ring_gold", "abode.cave_screen"]),
    ("abode-cranes", "Cranes in Flight", ["abode.crane_flying", "abode.crane_flying.001"]),
    ("summit", None, ["summit.pavilion"]),
    ("summit-arch", "Crescent Moon Arch", ["summit.arch*"]),
    ("summit-cranes", "Cranes to the Moon", ["summit.crane", "summit.crane.001"]),
)


def _labels():
    if os.path.isfile(LABELS_JSON):
        with open(LABELS_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    log("WARN", LABELS_JSON, "missing: item labels fall back to ids (run out/tmp/webfull/make_labels.py on the PC)")
    return {}


def _resolve(names):
    """Object names, 'prefix*' expanded against bpy.data.objects (top-level matches only: a match whose parent
    also matches is covered by its parent's subtree)."""
    out = []
    for nm in names:
        if nm.endswith("*"):
            pre = nm[:-1]
            hits = sorted(o.name for o in bpy.data.objects if o.name.startswith(pre)
                          and not (o.parent is not None and o.parent.name.startswith(pre)))
            out.extend(h for h in hits if h not in out)
        elif bpy.data.objects.get(nm) is not None and nm not in out:
            out.append(nm)
    return out


def build_hotspot_defs():
    """HOTSPOT_DEFS for the full path: item level first (they win the membership of shared subtrees), then the
    area level. Labels come from the portfolio data (labels.json), never invented."""
    L = _labels()
    defs = []
    miss = []

    def add(hid, label, names, area, kind, meta_only=False):
        res = _resolve(names)
        if not res:
            miss.append((hid, names))
        defs.append(dict(id=hid, label=label, names=res, area=area, kind=kind, metaOnly=meta_only))

    names = {p["id"]: p["name"] for p in L.get("projects", [])}
    for pid, kind in FORGE_RING:
        add("project:%s" % pid, names.get(pid, pid), ["forge.artifact." + kind], "forge", "item")
    hacks = L.get("hackathons", [])
    for i in range(N_HACKATHONS):
        h = hacks[i] if i < len(hacks) else dict(name="hackathon %d" % i, year=None)
        lab = h["name"] + (" %d" % h["year"] if h.get("year") else "")
        add("hackathon:%d" % i, lab, ["arena.banner" + ("" if i == 0 else ".%03d" % i)], "arena", "item")
    roles = L.get("roles", [])
    for i in range(7):
        sfx = "" if i == 0 else ".%03d" % i
        r = roles[i] if i < len(roles) else dict(role="role %d" % i)
        add("role:%d" % i, r["role"], ["mission.role_tablet" + sfx, "mission.tablet_halo" + sfx], "mission", "item")
    schools = L.get("schools", [])
    for storey, si in LIBRARY_FLOORS:
        add("school:%d" % si, schools[si] if si < len(schools) else "school %d" % si,
            ["library.lit_core.%d" % storey, "library.shelves.%d" % storey], "library", "item")
    for r in range(5):
        add("skills:%d" % r, "Stele row %d" % (r + 1), ["steles.stele.r%d" % r, "steles.stele.r%d.*" % r], "steles",
            "item")
    flow = L.get("flow", [])
    for k in range(8):
        lab = ("%02d %s" % (k + 1, flow[k]) if k < len(flow) else "step %d" % (k + 1)) if k < 6 else \
            ("Stack" if k == 6 else "Code")
        add("arch:%d" % k, lab, ["formation.pillar.%d" % k], "formation", "item")
    for k, (lab, names) in enumerate(ABODE_FACTS):
        add("fact:%d" % k, lab, names, "abode", "item")
    add("resume", "Jade Slip Scroll", ["scroll.jade_scroll"], "scroll", "item")
    add("moon", "The Moon", ["world.moon"], "summit", "item", meta_only=True)
    for hid, lab, names in AREA_HOTSPOTS:
        area = hid.split("-")[0]
        add(hid, lab or AREA_NAMES[area][0], names, area, "area")
    HOTSPOT_DEFS[:] = defs
    if miss:
        log("WARN hotspots without objects:", miss)
    return defs


# ---- full path: chunk plan --------------------------------------------------------------------

FULL_SPLIT_DIAG = 500.0        # meshes this long (diagonal) or SPAN_H wide span several areas: the range and the
SPAN_H = 250.0                 # roots are split face by face, the long streams go to the global set (code -4)
CHUNK_TRIS = 1_000_000         # stand-in: Blender-side triangles per chunk (~85 % reach the file)
FAR_TRIS = 350_000             # stand-in backdrop: far set
PROXY_TRIS = 25_000            # stand-in backdrop: per-area proxy
PROXY_MIN_DIAG = 3.0           # m: smaller pieces are left out of the proxies
PROXY_MAX_RECS = 900           # pieces per proxy at most (each costs >= MIN_TRIS)
FAR_MIN_PX = 3.0               # backdrop far set: pieces smaller than this on screen are dropped
PROXY_SPLIT_RATIO = 0.03       # terrain under a proxy
FAR_SPLIT_RATIO = 0.05         # terrain only seen from afar
HOLD_NEAR_FULL = 40.0          # m from a hold camera: full detail (<= HOLD_FULL_TRIS), cf. bake_web.HOLD_NEAR
HOLD_AREA_NEAR_FULL = 95.0     # m: small pieces (<= 8000 tris) of the hold's own area keep full detail
HOLD_FULL_TRIS_FULL = 30000
FLOOR_SHARE = 0.45             # stand-in: LOD floors may claim at most this share of a chunk's budget
PROTO_K = 3.3356e-05           # the prototype stand-in's screen-space constant (export_stats.json k.scene)


def _area_index_array(frames_arr):
    starts = np.array([a["frameStart"] for a in AREAS])
    return np.clip(np.searchsorted(starts, np.asarray(frames_arr), side="right") - 1, 0, len(AREAS) - 1)


def _is_fall(R, i):
    return any("waterfall" in m or "water_fall" in m for m in R.tinfo[R.tkey[i]][2] if m)


def face_assign(me, M, cam_mats, frames, tan_v, aspect_w, band=NM_BAND, dscale=None):
    """Per face of a big mesh (local coordinates, world matrix M): (chunk index, nearest distance, first and last
    sampled frame inside the widened frustum within `band`). Chunk = the area of the frame where the face is
    nearest the camera (frustum only, no occlusion); -1 = only seen beyond the band (backdrop); -2 = never seen.
    cam_mats / frames: every view of the audit (load_views), so faces only a look-around view sees are kept;
    dscale (Views.dscale) weights each view's distance for the nearest distance and the chunk."""
    ch, dmin, rng = face_scan(me, M, cam_mats, frames, tan_v, aspect_w, (band,), dscale=dscale)
    return ch, dmin, rng[band][0], rng[band][1]


def face_scan(me, M, cam_mats, frames, tan_v, aspect_w, bands=(NM_BAND, NEAR_MAX), dscale=None):
    """face_assign plus the first/last frame within each of `bands` (m): (chunk, dmin, {band: (first, last)}); the
    chunk always uses NM_BAND. dmin and the chunk use the weighted distance (dscale per view), the band ranges the
    real one (they feed the need ranges: when the page must draw the chunk)."""
    ds = np.ones(len(frames)) if dscale is None else np.asarray(dscale, float)
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    M = np.asarray(M, float)
    c = c.reshape(n, 3) @ M[:3, :3].T + M[:3, 3]
    dmin = np.full(n, np.inf)
    fbest = np.full(n, -1)
    rng = {b: [np.full(n, 10 ** 9), np.full(n, -1)] for b in set(bands) | {NM_BAND}}
    seen = np.zeros(n, bool)
    for f, Mc, s_ in zip(frames, cam_mats, ds):
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = c @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            nx = v[:, 0] / z / (tan_v * aspect_w)
            ny = v[:, 1] / z / tan_v
        inside = (z > 0.1) & (np.abs(nx) <= 1.15) & (np.abs(ny) <= 1.15)
        seen |= inside
        d = np.linalg.norm(c - Mc[:3, 3], axis=1)
        dw = d * s_
        upd = inside & (dw < dmin)
        dmin[upd] = dw[upd]
        fbest[upd] = f
        for b, fl in rng.items():
            inb = inside & (d <= b)
            fl[0] = np.where(inb & (fl[0] > f), f, fl[0])
            fl[1] = np.where(inb & (fl[1] < f), f, fl[1])         # the look views come after the path: not in order
    ch = np.where(seen & (dmin <= NM_BAND), _area_index_array(np.maximum(fbest, 1)), np.where(seen, -1, -2))
    return ch.astype(np.int16), dmin, rng


def chunk_assign(R, S, minfo):
    """Per record: area chunk index (0..10, AREAS order), -1 backdrop (seen, but never within NM_BAND), -2 not
    exported (never visible in any view, < MIN_PX, sky/FX/flyer), -3 split face by face (face_assign). Rule: the
    area whose frame range holds the frame where the piece is nearest the camera (path frames and look views, by
    their frame labels and weighted distance). Hotspot members always go to their hotspot's area (so every click
    target sits in the chunk of the area that presents it); turning groups (TURNING_GROUPS) to the group's area.
    Size test: px_eff (the path's pxmax, or the weighted look views' when larger)."""
    n = len(R)
    ex = export_mask(R, minfo)
    px = S["px_eff"]
    sel = S["any"] & (px >= MIN_PX) & ~ex
    nm_any = S["vis_nm"].any(1)
    fa = _area_index_array(np.maximum(S["fnear"], 1))
    ch = np.full(n, -2, np.int16)
    ch[sel & nm_any] = fa[sel & nm_any]
    ch[sel & ~nm_any] = -1
    members = hotspot_members()
    hot_area = {h["id"]: h["area"] for h in HOTSPOT_DEFS}
    ids = [a["id"] for a in AREAS]
    forced = collections.Counter()
    hot_recs = collections.defaultdict(list)
    for i in range(n):
        hid = members.get(R.owner[i])
        if hid and not ex[i] and hid in hot_area:
            hot_recs[hid].append(i)
    for hid, recs in hot_recs.items():
        k = ids.index(hot_area[hid])
        vis_recs = [i for i in recs if sel[i]]
        for i in (vis_recs or recs):          # a hotspot nothing of which is ever visible keeps all its pieces
            if ch[i] != k:
                forced[hid] += 1
            ch[i] = k
    # turning objects (TURNING_GROUPS): the whole group in the group's area (load_cache already gave every piece
    # the group's visibility, so they are selected together)
    for g in TURNING_GROUPS:
        rows = turning_rows(R).get(g["id"])
        if rows is None or g["area"] not in ids:
            continue
        rows = rows[sel[rows]]
        k = ids.index(g["area"])
        forced["turning:" + g["id"]] += int((ch[rows] != k).sum())
        ch[rows] = k
    ext = R.hi - R.lo
    horiz = np.maximum(ext[:, 0], ext[:, 1])
    diag = np.linalg.norm(ext, axis=1)
    falls = np.array([_is_fall(R, i) for i in range(n)], bool)
    long_ = (ch >= 0) & ~R.inst & ((horiz >= SPAN_H) | (diag >= FULL_SPLIT_DIAG))
    big = long_ & ~falls & (R.tris >= 500)
    span = long_ & falls
    ch[big] = -3
    ch[span] = -4
    log("chunk_assign: forced hotspot pieces", sum(forced.values()), dict(forced.most_common(12)),
        "split", [R.name[i] for i in np.nonzero(big)[0]], "span (global)", [R.name[i] for i in np.nonzero(span)[0]])
    return ch, forced


def _nm_first_last(S, frames):
    vn = S["vis_nm"]
    has = vn.any(1)
    fr = np.asarray(frames)
    fi = np.where(vn, fr[None, :], 10 ** 9).min(1)
    la = np.where(vn, fr[None, :], -1).max(1)
    return has, np.where(has, fi, -1), la


def _cam_setup():
    cam = bpy.data.objects[CAMERA]
    th, tv = camera_tan(cam)
    return cam, tv, DEPTH_RES[0] / DEPTH_RES[1]


BANDS_REPORTED = (NM_BAND, 250.0, NEAR_MAX)     # chunks.json: need (400 m), need250, core (150 m)


def _band_ranges(R, S, frames, cam_mats, bands):
    """Per record and band: first/last frame label where it is visible (depth-tested bits) within the band (box
    distance to the camera, as in the audit). frames / cam_mats: every view of the audit (load_views), so a piece
    a look-around view sees within the band widens the range to that view's frame."""
    n = len(R)
    out = {b: [np.full(n, 10 ** 9), np.full(n, -1)] for b in bands}
    vis = S["vis"]
    for j, (f, Mc) in enumerate(zip(frames, cam_mats)):
        c = np.asarray(Mc, float)[:3, 3]
        d = np.linalg.norm(np.maximum(np.maximum(R.lo - c, c - R.hi), 0.0), axis=1)
        for b, fl in out.items():
            inb = vis[:, j] & (d <= b)
            fl[0] = np.where(inb & (fl[0] > f), f, fl[0])
            fl[1] = np.where(inb & (fl[1] < f), f, fl[1])         # the look views come after the path: not in order
    return out


def cmd_chunks(a):
    """out/web/full/chunks.json (+ chunks.npz: the per-record assignment by record key, for bake_web/bake_trees)."""
    scene = bpy.context.scene
    t0 = time.time()
    R = gather(scene)
    S, frames = load_cache(R)
    frames = np.asarray(frames)
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    ch, forced = chunk_assign(R, S, minfo)
    ids = [x["id"] for x in AREAS]
    cam, tv, aspect_w = _cam_setup()
    views = load_views(cam)                      # path frames, then the look-around views (cache column order)
    cam_mats, frames = views.mats, views.frames
    hold_pos = [np.asarray(m, float)[:3, 3] for m in sample_matrices(cam, [x["holdFrame"] for x in AREAS])]
    step = int(frames[1] - frames[0]) if len(frames) > 1 else 1
    br = _band_ranges(R, S, frames, cam_mats, BANDS_REPORTED)
    # split meshes: per-face assignment
    big_idx = np.nonzero(ch == -3)[0]
    bases = capture_bases([R.tkey[i] for i in big_idx]) if len(big_idx) else {}
    split = collections.defaultdict(lambda: dict(faces=0, tris=0, rng={b: [10 ** 9, -1] for b in BANDS_REPORTED}))
    split_rows = []
    for i in big_idx:
        me = bases.get(R.tkey[i])
        if me is None:
            continue
        fch, fd, frng = face_scan(me, R.mw[i], cam_mats, frames, tv, aspect_w, BANDS_REPORTED, dscale=views.dscale)
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_total", lt)
        row = dict(name=R.name[i], faces=len(me.polygons), tris=int((lt - 2).sum()), by_chunk={})
        for k in sorted(set(fch.tolist())):
            m = fch == k
            key = ids[k] if k >= 0 else ("backdrop" if k == -1 else "unseen")
            row["by_chunk"][key] = dict(faces=int(m.sum()), tris=int((lt[m] - 2).sum()))
            if k >= 0:
                s_ = split[k]
                s_["faces"] += int(m.sum())
                s_["tris"] += int((lt[m] - 2).sum())
                for b in BANDS_REPORTED:
                    ff, fl = frng[b]
                    s_["rng"][b][0] = min(s_["rng"][b][0], int(ff[m].min()))
                    s_["rng"][b][1] = max(s_["rng"][b][1], int(fl[m].max()))
        split_rows.append(row)
    vis = S["vis"][:, views.path]               # peak load: path frames only
    chunks = []
    w = lod_weights(R, np.arange(len(R)), hotspot_members())

    def rng_of(k, b, ar, pad_area):
        m = ch == k
        f0, f1 = br[b]
        mh = m & (f1 >= 0)
        lo_f = int(f0[mh].min()) if mh.any() else 10 ** 9
        hi_f = int(f1[mh].max()) if mh.any() else -1
        sr = split[k]["rng"][b]
        lo_f, hi_f = min(lo_f, sr[0]), max(hi_f, sr[1])
        if pad_area:
            lo_f, hi_f = min(lo_f, ar["frameStart"]), max(hi_f, ar["frameEnd"])
        else:
            lo_f, hi_f = min(lo_f, ar["holdFrame"]), max(hi_f, ar["holdFrame"])
        return [int(max(FRAMES[0], lo_f - step)), int(min(FRAMES[1], hi_f + step))]
    for k, ar in enumerate(AREAS):
        idx = np.nonzero(ch == k)[0]
        tris = R.tris[idx]
        own = collections.defaultdict(lambda: [0, 0])
        for i in idx:
            own[R.owner[i]][0] += 1
            own[R.owner[i]][1] += int(R.tris[i])
        peak = int((vis[idx].astype(np.int64) * tris[:, None]).sum(0).max()) if len(idx) else 0
        est = 0
        if len(idx):
            lv = lod_levels(R, S["px_eff"].astype(float), PROTO_K, idx, w[idx])
            est = int((tris * LEVELS[lv]).sum())
        tops = collections.Counter()
        for i in idx:
            tops[R.top[i]] += int(R.tris[i])
        chunks.append(dict(
            id=ar["id"], area=ar["id"], section=ar["sectionId"], label=ar["label"],
            frameRange=[ar["frameStart"], ar["frameEnd"]], hold=ar["holdFrame"],
            holdCamera=[round(float(x), 2) for x in hold_pos[k]],
            need=rng_of(k, NM_BAND, ar, True), need250=rng_of(k, 250.0, ar, True), core=rng_of(k, NEAR_MAX, ar, False),
            records=int(len(idx)), owners_count=len(own), tris_source=int(tris.sum()) + split[k]["tris"],
            tris_records=int(tris.sum()), tris_split=split[k]["tris"], split_faces=split[k]["faces"],
            tris_visible_peak=peak, tris_est_proto_rule=est + int(split[k]["tris"] * 0.35),
            by_collection=dict(tops.most_common()),
            owners=[dict(owner=o, records=v[0], tris=v[1]) for o, v in sorted(own.items(), key=lambda kv: -kv[1][1])]))
    conc = {}
    for key in ("need", "need250", "core"):
        cnt = np.array([sum(c[key][0] <= f <= c[key][1] for c in chunks) for f in range(FRAMES[0], FRAMES[1] + 1)])
        conc[key] = dict(max=int(cnt.max()), mean=round(float(cnt.mean()), 2),
                         at_holds={c["id"]: int(cnt[c["hold"] - FRAMES[0]]) for c in chunks})
    bd = ch == -1
    own_b = collections.Counter()
    for i in np.nonzero(bd)[0]:
        own_b[R.top[i]] += int(R.tris[i])
    sp = ch == -4
    data = dict(
        version=2, profile=PROFILE, source="out/sect_chase.blend chase.cam", frames=list(FRAMES),
        sampled_every=step, scene_frame=SCENE_FRAME, band_m=NM_BAND,
        look=dict(views=dict(path=int(views.path.sum()), hold=int((views.kind == VIEW_HOLD).sum()),
                             between=int((views.kind == VIEW_BETWEEN).sum())),
                  note="look-around views (export_web audit --look) are labelled with a frame (the hold frame, or "
                       "their own) and widen need/need250/core like path frames"),
        rule="Every piece seen within band_m of the camera at some sampled frame belongs to the area chunk whose "
             "frame range holds the frame where it is nearest the camera (depth-tested visibility). Hotspot "
             "members (the visible ones) always go to their hotspot's area. Meshes that span several areas (>= %d m "
             "wide or %d m long: the range, the roots) are split face by face with the same rule (frustum only); "
             "long streams (water, >= %d m wide) are global ('span', drawn all the time). Pieces seen only beyond "
             "band_m go to the global backdrop; each area also gets a heavily reduced proxy there "
             "(extras proxyOf)." % (SPAN_H, FULL_SPLIT_DIAG, SPAN_H),
        need="Blender frames during which the chunk must be drawn: every sampled frame where one of its pieces is "
             "visible within band_m (400 m), plus the area's own frame range, padded by one sampling step. "
             "need250: the same within 250 m. core: within 150 m (and the hold frame), where full detail matters; "
             "between core and need the proxy is a fair stand-in.",
        concurrency=conc,
        chunks=chunks,
        span=dict(records=int(sp.sum()), tris=int(R.tris[sp].sum()), names=[R.name[i] for i in np.nonzero(sp)[0]]),
        backdrop=dict(records=int(bd.sum()), tris_source=int(R.tris[bd].sum()), by_collection=dict(own_b.most_common())),
        not_exported=dict(records=int((ch == -2).sum()), tris=int(R.tris[ch == -2].sum())),
        split=split_rows, forced_hotspot_pieces=dict(forced),
        files=dict(assignment="chunks.npz (key = record key as in vis_cache.npz, chunk = index into ids; -1 "
                              "backdrop, -2 not exported, -3 split per face: export_web.face_assign, -4 global span "
                              "piece (long streams): drawn all the time)"),
        time_s=round(time.time() - t0, 1))
    os.makedirs(WORK, exist_ok=True)
    cj = os.path.join(WORK, "chunks.json")
    pre = os.path.isfile(cj) and _plan_is_pre360(cj)
    prev = _keep_pre360(cj, _plan_is_pre360)
    prev_npz = _keep_pre360(os.path.join(WORK, "chunks.npz"), lambda p: pre)
    data["gate"] = _chunks_gate(R, S, ch, ids, data, prev, prev_npz, export_mask(R, minfo))
    dump(os.path.join(WORK, "chunks.json"), data, indent=1)
    np.savez_compressed(os.path.join(WORK, "chunks.npz"), key=np.array(R.key), chunk=ch, ids=np.array(ids),
                        first_nm=br[NM_BAND][0], last_nm=br[NM_BAND][1], first_core=br[NEAR_MAX][0],
                        last_core=br[NEAR_MAX][1], fnear=S["fnear"])
    log("CHUNKS", json.dumps([(c["id"], c["need"], c["core"], c["records"], c["tris_source"])
                              for c in chunks]), "concurrency",
        json.dumps({k: (v["max"], v["mean"]) for k, v in conc.items()}))


def _plan_is_pre360(path):
    with open(path, encoding="utf-8") as fh:
        return "look" not in json.load(fh)


def _chunks_gate(R, S, ch, ids, data, prev, prev_npz, ex):
    """What the look views change in the chunk plan: pieces that were not exported (-2) and now are (by chunk; against
    the pre-360 chunks.npz when there is one, else against the path-only rule), and per chunk the source triangles,
    split faces, need range and concurrency at the holds against the pre-360 plan. Logged as 'CHUNKS GATE'.
    ex: export_mask (FX, additive, transparent pieces): left out of turning_chunks, counted in turning_fx."""
    tris = R.tris.astype(np.int64)
    if prev_npz:
        z = np.load(prev_npz, allow_pickle=False)
        idx = {k: i for i, k in enumerate(z["key"].tolist())}
        order = np.array([idx.get(k, -1) for k in R.key])
        was_out = np.where(order >= 0, z["chunk"][np.maximum(order, 0)] == -2, True)
        basis = "pre-360 chunks.npz"
    else:
        was_out = ~(S["any_path"] & (S["pxmax"] >= MIN_PX))
        basis = "path-only rule (no pre-360 chunks.npz)"
    rescued = was_out & (ch != -2)
    names = {k: ids[k] for k in range(len(ids))}
    names.update({-1: "backdrop", -3: "split", -4: "global"})
    by = collections.defaultdict(lambda: [0, 0])
    for i in np.nonzero(rescued)[0]:
        b = by[names.get(int(ch[i]), str(int(ch[i])))]
        b[0] += 1
        b[1] += int(tris[i])
    out = dict(rescued=dict(basis=basis, records=int(rescued.sum()), tris=int(tris[rescued].sum()),
                            by_chunk={k: dict(records=v[0], tris=v[1]) for k, v in sorted(by.items())}),
               not_exported=data["not_exported"])
    if prev_npz:
        lost = ~was_out & (ch == -2)
        out["lost"] = dict(records=int(lost.sum()), tris=int(tris[lost].sum()),
                           examples=[R.key[i] for i in np.nonzero(lost)[0][:20]])
    old = None
    if prev:
        with open(prev, encoding="utf-8") as fh:
            old = json.load(fh)
        oc = {c["id"]: c for c in old["chunks"]}
        rows = {}
        for c in data["chunks"]:
            o = oc.get(c["id"])
            if o is None:
                continue
            rows[c["id"]] = dict(tris_source=[o["tris_source"], c["tris_source"]],
                                 growth=round(c["tris_source"] / max(o["tris_source"], 1) - 1.0, 3),
                                 tris_split=[o.get("tris_split"), c["tris_split"]], records=[o["records"], c["records"]],
                                 need=[o["need"], c["need"]], core=[o.get("core"), c.get("core")])
        out["vs_pre360"] = dict(chunks=rows, not_exported=[old["not_exported"], data["not_exported"]],
                                need_at_holds=[old.get("concurrency", {}).get("need", {}).get("at_holds"),
                                               data["concurrency"]["need"]["at_holds"]],
                                core_at_holds=[old.get("concurrency", {}).get("core", {}).get("at_holds"),
                                               data["concurrency"]["core"]["at_holds"]])
    tg, tfx = {}, {}
    for g, rows_ in sorted(turning_rows(R).items()):
        tg[g] = sorted({names.get(int(x), str(int(x))) for x in ch[rows_[~ex[rows_]]]})
        tfx[g] = int(ex[rows_].sum())
    out["turning_chunks"] = tg        # every exported piece of a group: its area only
    out["turning_fx"] = tfx           # pieces never exported (glow shells, transparent parts): expected
    log("CHUNKS GATE", json.dumps(out))
    return out


def load_chunks(R):
    """(per-record chunk index matched by key, chunk ids) from out/web/full/chunks.npz."""
    z = np.load(os.path.join(WORK, "chunks.npz"), allow_pickle=False)
    idx = {k: i for i, k in enumerate(z["key"].tolist())}
    order = np.array([idx.get(k, -1) for k in R.key])
    ch = np.where(order >= 0, z["chunk"][np.maximum(order, 0)], -2).astype(np.int16)
    if (order < 0).any():
        log("WARN chunk misses", int((order < 0).sum()), "of", len(R))
    return ch, [str(x) for x in z["ids"]]


# ---- full path: meta.json ---------------------------------------------------------------------

BEAM_WORDS = ("light_beam", "formation_beam", "props_beam")


def _beam(R, i, mats, d):
    obb = bpy.data.objects.get(R.name[i])
    if obb is None or obb.type != "MESH" or len(obb.data.vertices) < 2:
        return None
    co = np.array([v.co[:] for v in obb.data.vertices], float)
    M = np.asarray(R.mw[i], float)
    w = co @ M[:3, :3].T + M[:3, 3]
    c = w.mean(0)
    _, _, vt = np.linalg.svd(w - c, full_matrices=False)
    ax = vt[0] if vt[0][2] >= 0 else -vt[0]
    t = (w - c) @ ax
    rad = float(np.percentile(np.linalg.norm((w - c) - np.outer(t, ax), axis=1), 90))
    mat = bpy.data.materials.get(next(m for m in mats if any(b in m for b in BEAM_WORDS)))
    return dict(name=R.name[i], base=v3(c + ax * t.min(), 3), top=v3(c + ax * t.max(), 3),
                radius=round(max(rad, 0.05), 2), color=hexcol(mat.diffuse_color) if mat is not None else "#9ff3ff",
                material=mat.name if mat is not None else None, nearestM=round(d, 1))


def _fall_shape(ob, M, dg):
    """corners (lip-left, lip-right, foot-right, foot-left), lip, foot in three space (cf. bake_web water)."""
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    bpy.data.meshes.remove(me)
    co = co.reshape(-1, 3)
    if len(co) < 3:
        return {}
    M = np.asarray(M, float)
    w = co @ M[:3, :3].T + M[:3, 3]
    xd = M[:3, 0] / max(np.linalg.norm(M[:3, 0]), 1e-9)
    zr = w[:, 2]
    h = float(zr.max() - zr.min())
    top = w[zr >= zr.max() - 0.04 * max(h, 1.0)]
    bot = w[zr <= zr.min() + 0.04 * max(h, 1.0)]

    def ends(P):
        s = P @ xd
        return P[np.argmin(s)], P[np.argmax(s)]
    tl, tr = ends(top)
    bl, br = ends(bot)
    return dict(corners=[v3(tl, 3), v3(tr, 3), v3(br, 3), v3(bl, 3)], lip=v3(top.mean(0), 3),
                foot=v3(bot.mean(0), 3), height=round(h, 2),
                sizeLocal=[round(float(x), 3) for x in (ob.dimensions.x, ob.dimensions.z, ob.dimensions.y)],
                flow=float(ob.get("flow", 1.0)))


def cmd_meta_full(a):
    from sect import world as W
    from sect.lib import look as Lk
    scene = bpy.context.scene
    R = gather(scene)
    S, frames = load_cache(R)
    ch, ids = load_chunks(R) if os.path.isfile(os.path.join(WORK, "chunks.npz")) else (None, [x["id"] for x in AREAS])
    dg = bpy.context.evaluated_depsgraph_get()
    sun = bpy.data.objects["look.sun"]
    sdir = sun.matrix_world.to_3x3().col[2].normalized()
    moon = bpy.data.objects["world.moon"]
    mc = moon.matrix_world.translation
    mr = max(moon.dimensions) / 2
    gate_view = Vector((0.0, -60.0, 60.0))
    LOOK = Lk.LOOK

    def chunk_of(i):
        if ch is None:
            return None
        k = int(ch[i])
        if k >= 0:
            return ids[k]
        if k == -1:
            return "backdrop"
        if k == -4:
            return "global"
        if S["any"][i] and S["fnear"][i] > 0:
            return ids[area_of_frame(int(S["fnear"][i]))]
        return None
    falls, beams, seen = [], [], set()
    for i in range(len(R)):
        mats = [m for m in R.tinfo[R.tkey[i]][2] if m]
        is_fall = any("waterfall" in m or "water_fall" in m for m in mats)
        is_beam = any(any(b in m for b in BEAM_WORDS) for m in mats)
        if not (is_fall or is_beam) or not S["any"][i] or R.top[i] == FLYER_COLL:
            continue
        nm = R.name[i] if not R.inst[i] else R.key[i]
        if nm in seen:
            continue
        seen.add(nm)
        d = float(S["d_eff"][i])               # nearest distance, look-around views included (weighted)
        if is_beam:
            b = _beam(R, i, mats, d)
            if b is not None:
                b["area"] = R.top[i] if R.top[i] in AREA_NAMES else (ids[area_of_frame(int(S["fnear"][i]))])
                b["chunk"] = b["area"]
                beams.append(b)
            continue
        if d > MID_MAX:
            continue
        M = Matrix(R.mw[i].tolist())
        loc, rot, sc = M.decompose()
        lo, hi = R.lo[i], R.hi[i]
        ob_f = bpy.data.objects.get(R.name[i])
        dims = ob_f.dimensions if ob_f is not None else Vector(hi - lo)
        e = dict(name=nm, kind="stream" if ".stream" in nm else "sheet", position=v3((lo + hi) / 2, 2),
                 size=[round(dims.x, 3), round(dims.z, 3), round(dims.y, 3)], worldSize=s3(hi - lo),
                 rotation=q_object(rot.to_matrix()), origin=v3(loc, 2), nearestM=round(d, 1), material=mats,
                 chunk=chunk_of(i), area=ids[area_of_frame(int(S["fnear"][i]))] if S["fnear"][i] > 0 else None)
        if ob_f is not None and not R.inst[i] and ob_f.type == "MESH":
            shp = _fall_shape(ob_f, R.mw[i], dg)
            if shp:
                e.update(shp)
                e["size"] = shp["sizeLocal"]
        falls.append(e)
    hs = []
    for h in HOTSPOT_DEFS:
        b = _subtree_box(h["names"])
        if b is None:
            log("WARN hotspot", h["id"], "has no geometry", h["names"])
            continue
        hs.append(dict(id=h["id"], label=h["label"], node=None if h["metaOnly"] else "hotspot." + h["id"],
                       center=v3((b[0] + b[1]) / 2, 2), size=s3(b[1] - b[0]), area=h["area"], chunk=h["area"],
                       kind=h["kind"], objects=h["names"]))
    sky = {}
    sky_json = os.path.join(OUT_WEB, "sky_samples.json")
    if os.path.isfile(sky_json):
        with open(sky_json, encoding="utf-8") as fh:
            sky = json.load(fh)
    rendered = dict(top="#737995", low="#84889e", source="prototype meta.json (out/web/ref/ref_48.png)")
    anchors = W.ANCHORS
    areas = []
    for ar in AREAS:
        an = anchors[ar["id"]]
        areas.append(dict(ar, anchor=v3(an[:3], 2), footprint=an[3], chunk=ar["id"]))
    data = dict(
        units="metres, three.js world (Y up): p = (bx, bz, -by)",
        version=2, profile=PROFILE, sceneFrame=SCENE_FRAME,
        sun=dict(direction=v3(sdir, 5), color=hexcol(sun.data.color), colorLinear=[round(c, 4) for c in sun.data.color],
                 intensity=sun.data.energy, intensityUnit="Blender W/m2 (sun lamp)",
                 elevationDeg=round(math.degrees(math.asin(sdir.z)), 2), azimuthDeg=252.0,
                 angleDeg=LOOK["sun_angle_deg"], note="direction points from the scene toward the sun"),
        sky=dict(zenith=sky.get("zenith"), horizon=sky.get("horizon"), horizonSun=sky.get("horizon_sun"),
                 horizonNorth=sky.get("horizon_north"), horizonSouth=sky.get("horizon_south"),
                 belowHorizon=sky.get("below"), texture="sky.webp", asRendered=rendered,
                 note="the prototype's sky (one world shader for the whole path)",
                 textureMapping="equirectangular, three.js convention (u=0.5 is +X/east, u=0.25 north); "
                                "sRGB, already tone-mapped (AgX Punchy, exposure +0.25)"),
        fog=dict(color=rendered["low"], scatterColor=hexcol(LOOK["haze_color"]), density=W.HAZE["density"],
                 baseY=W.HAZE["base_z"], falloff=W.HAZE["falloff"], near=60.0, far=2600.0, exp2Density=0.00046,
                 note="Blender haze: exponential height fog, extinction density*exp(-(y-baseY)/falloff) per m."),
        moon=dict(position=v3(mc, 1), radius=round(mr, 1),
                  angularSizeDegFromGate=round(math.degrees(2 * math.asin(mr / (mc - gate_view).length)), 2),
                  color="#e9edf5", halo=dict(position=v3(bpy.data.objects["world.moon_halo"].matrix_world.translation, 1),
                                             radius=round(max(bpy.data.objects["world.moon_halo"].dimensions) / 2, 1)),
                  hotspot="moon", note="self-lit; drawn by the page (not in the GLBs); click target 'moon'"),
        cloudSea=dict(y=W.CLOUD_SEA_Z, billowTopY=W.CLOUD_SEA_Z + 15.0, fogTopY=20.0, fogBottomY=-90.0,
                      color=sky.get("cloud_sea", "#e9c9a8"), extent=9000.0),
        waterfalls=falls,
        beams=beams,
        hotspots=hs,
        areas=areas,
        toneMapping=dict(blender=LOOK["view_transform"] + " / " + LOOK["look"], exposure=LOOK["exposure"],
                         bloomThresholdLuminance=LOOK["bloom_threshold"], vignette=LOOK["vignette_strength"]),
        vignette=LOOK["vignette_strength"], exposure=LOOK["exposure"],
        lights=[dict(name=o.name, type=o.data.type, position=v3(o.matrix_world.translation, 2),
                     color=hexcol(o.data.color), power=o.data.energy, powerUnit="W (Blender point light)",
                     area=next((c.name for c in o.users_collection if c.name in AREA_NAMES), None))
                for o in bpy.context.view_layer.objects if o.type == "LIGHT" and o.data.type != "SUN"
                and not o.hide_render and FLYER_COLL not in {c.name for c in o.users_collection}],
    )
    os.makedirs(a.out, exist_ok=True)
    dump(os.path.join(a.out, "meta.json"), data, indent=1)
    counts = collections.Counter(h["id"].split(":")[0] if ":" in h["id"] else ("area" if h["kind"] == "area"
                                                                              else h["id"]) for h in hs)
    log("META hotspots", len(hs), dict(counts), "waterfalls", len(falls), "beams", len(beams))
    write_hotspots_md(hs)


def write_hotspots_md(hs):
    L = ["# Hotspots: item -> scene objects", "",
         "Written by `sect/export_web.py --profile full meta`. Ids follow "
         "`client/src/app/sect/content/index.tsx`. Each hotspot is a glTF node `hotspot.<id>` (extras "
         "{hotspot, label}) in its area's chunk GLB, with its click box in meta.json `hotspots[]` (centre/size in "
         "three space, plus `area` and `chunk`). Objects are Blender names in `out/sect_chase.blend`; a hotspot "
         "node holds every object in their subtrees (and the instances they emit). 'moon' has no node: the page "
         "draws the moon, so its click box is meta-only.", ""]
    by = collections.Counter()
    for h in hs:
        head = h["id"].split(":")[0] if ":" in h["id"] else ("area level" if h["kind"] == "area" else h["id"])
        by[head] += 1
    L.append("Counts: " + ", ".join("%s %d" % kv for kv in by.items()) + " (total %d)." % len(hs))
    L.append("")
    L.append("Order rules: forge artifacts by `forge.FORGE_RING` (project id, artifact), the winning projects only; "
             "arena banners by "
             "banner index (`arena.banner`, `.001` ... going round the ring from the front gap) -> HACKATHONS "
             "0-35, banners 36-39 decorative; mission tablets left to right -> EXPERIENCE order; library lit "
             "storeys 1, 3, 5 (bottom to top) are Lynbrook, UCSC, USC in library.py, i.e. EDUCATION indices 2, 1, 0; "
             "steles rows r0 (front, cyan) to r4 (back, amber), four steles per row; formation pillars in "
             "PILLAR_ANGLES order (k = 0..7, 22.5 + 45 k deg): 0-5 = FLOW steps, 6 = STACK, 7 = SNIPPET; abode "
             "facts in PERSONAL_FACTS order.")
    L.append("")
    L.append("| id | label | area / chunk | objects | centre (three) |")
    L.append("|---|---|---|---|---|")
    for h in hs:
        ob = h.get("objects") or []
        obs = ", ".join("`%s`" % o for o in ob[:6]) + (" +%d" % (len(ob) - 6) if len(ob) > 6 else "")
        L.append("| `%s` | %s | %s | %s | %s |" % (h["id"], h["label"], h["area"], obs, h["center"]))
    p = os.path.join(WORK, "hotspots.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    log("wrote", p)


# ---- full path: stand-in GLBs + manifest ------------------------------------------------------

def _gz(path):
    import gzip
    with open(path, "rb") as fh:
        raw = fh.read()
    out = path + ".gz"
    with open(out, "wb") as fh:
        fh.write(gzip.compress(raw, compresslevel=9, mtime=0))
    return out


def _remove_objects(objs):
    for ob in objs:
        try:
            bpy.data.objects.remove(ob, do_unlink=True)
        except Exception:
            pass


def _hold_floor(R, idx, hold_pos, area_id):
    """Stand-in LOD floors near a hold camera (lighter than bake_web's: the stand-in only has to read)."""
    d = np.linalg.norm(np.maximum(np.maximum(R.lo[idx] - hold_pos, hold_pos - R.hi[idx]), 0.0), axis=1)
    t = R.tris[idx]
    own = np.array([R.top[i] == area_id for i in idx], bool)
    fl = np.where(d <= HOLD_NEAR_FULL, np.where(t <= 8000, 1.0, 0.25), 0.0)
    fl = np.maximum(fl, np.where((d <= HOLD_AREA_NEAR_FULL) & own & (t <= 3000), 1.0, 0.0))
    return fl


def cmd_standin(a):
    """Unbaked stand-in set for the full path: <site>/<area>.glb.gz per chunk (plain viewport colours, hotspot
    nodes, GPU instancing), <site>/backdrop.glb.gz (far set + one proxy per area under 'proxy.<area>' Empties with
    extras {"proxyOf": "<area>"}), and manifest.json v2 ("baked": false)."""
    scene = bpy.context.scene
    t0 = time.time()
    R = gather(scene)
    S, cache_frames = load_cache(R)
    frames = np.asarray(cache_frames)
    ch, ids = load_chunks(R)
    px = S["px_eff"].astype(float)
    n = len(R)
    diag = np.linalg.norm(R.hi - R.lo, axis=1)
    cam, tv, aspect_w = _cam_setup()
    views = load_views(cam)
    cam_mats, frames = views.mats, views.frames
    hold_pos = [np.asarray(m, float)[:3, 3] for m in sample_matrices(cam, [x["holdFrame"] for x in AREAS])]
    far_idx = np.nonzero((ch == -1) & (px >= FAR_MIN_PX))[0]
    big_idx = np.nonzero(ch == -3)[0]
    span_idx = np.nonzero(ch == -4)[0]
    want = np.nonzero((ch >= 0) | (ch == -3) | (ch == -4))[0].tolist() + far_idx.tolist()
    bases = capture_bases([R.tkey[i] for i in want])
    dec = Decimator(scene)
    picker = MeshPicker(bases, dec)
    members = hotspot_members()
    items = {h["id"]: h["kind"] == "item" for h in HOTSPOT_DEFS}
    split = collections.defaultdict(dict)
    split_proxy = collections.defaultdict(dict)
    split_far = {}
    used_split = collections.Counter()
    used_proxy = collections.Counter()
    used_far = 0
    for i in big_idx:
        base = bases.get(R.tkey[i])
        if base is None:
            continue
        fch, fd, _, _ = face_assign(base, R.mw[i], cam_mats, frames, tv, aspect_w, dscale=views.dscale)
        wb = base.copy()
        wb.transform(Matrix(np.asarray(R.mw[i], float).tolist()))
        for k in sorted(set(fch.tolist())):
            m = fch == k
            if k == -2:
                continue
            if k == -1:
                nm = "%s.far" % R.name[i]
                me = dec.get(nm, submesh(wb, m, nm), FAR_SPLIT_RATIO)
                split_far.setdefault((R.top[i], R.name[i]), []).append((nm, me))
                used_far += _mesh_tris(me)[0]
                continue
            for part, mm, ratio in (("near", m & (fd <= SPLIT_NEAR), SPLIT_RATIOS["near"]),
                                    ("mid", m & (fd > SPLIT_NEAR), SPLIT_RATIOS["mid"])):
                if not mm.any():
                    continue
                nm = "%s.%s.%s" % (R.name[i], ids[k], part)
                me = dec.get(nm, submesh(wb, mm, nm), ratio)
                split[k].setdefault((R.top[i], R.name[i]), []).append((nm, me))
                used_split[k] += _mesh_tris(me)[0]
            nm = "%s.%s.proxy" % (R.name[i], ids[k])
            me = dec.get(nm, submesh(wb, m, nm), PROXY_SPLIT_RATIO)
            split_proxy[k].setdefault((R.top[i], R.name[i]), []).append((nm, me))
            used_proxy[k] += _mesh_tris(me)[0]
        log("split", R.name[i], {(ids[k] if k >= 0 else k): int((fch == k).sum()) for k in sorted(set(fch.tolist()))})
    matcache = {}
    os.makedirs(a.out, exist_ok=True)
    stats = dict(chunks={}, backdrop={})
    w_all = lod_weights(R, np.arange(n), members)
    for k, cid in enumerate(ids):
        idx = np.nonzero(ch == k)[0]
        w = np.where([R.top[i] == cid or R.owner[i] in members for i in idx], LOD_WEIGHTS["focus"], w_all[idx])
        w = np.where(np.array([R.top[i] in AREA_NAMES and R.top[i] != cid for i in idx], bool), LOD_WEIGHTS["other"], w)
        fl = np.maximum(lod_floor(R, idx, S, a.near), _hold_floor(R, idx, hold_pos[k], cid))
        fl = np.maximum(fl, np.array([0.5 if items.get(members.get(R.owner[i])) and R.tris[i] <= 20000 else 0.0
                                      for i in idx]))
        budget = max(a.chunk_tris - used_split[k], 50_000)
        fl_tris = float((R.tris[idx] * fl).sum())
        if fl_tris > FLOOR_SHARE * budget:          # floors may take at most FLOOR_SHARE of the budget
            fl = fl * (FLOOR_SHARE * budget / fl_tris)
            log(cid, "floors scaled by", round(FLOOR_SHARE * budget / fl_tris, 3), "(floored tris", int(fl_tris), ")")
        kk, lv, tot = fit_budget(R, px, idx, budget, w, picker, cid, floor=fl)
        made, st = build_export(scene, R, S, idx, lv, split[k], picker, matcache, cid, bool(a.merge_mid), a.near,
                                prefix=cid + ":")
        p = os.path.join(a.out, cid + ".glb")
        export_glb(p, made, gpu_instances=True)
        st["glb"] = glb_stats(p)
        st["k"] = kk
        pg = _gz(p)
        os.remove(p)
        st["gz_bytes"] = os.path.getsize(pg)
        st["file"] = os.path.basename(pg)
        stats["chunks"][cid] = st
        _remove_objects(made)
        log("CHUNK", cid, "records", len(idx), "file tris", st["glb"]["triangles"], "draws", st["glb"]["draw_calls"],
            "MB", round(st["glb"]["bytes"] / 1e6, 2), "gz MB", round(st["gz_bytes"] / 1e6, 2))
    # backdrop: far set + per-area proxies
    coll = bpy.data.collections.new("web.export.backdrop.roots")
    scene.collection.children.link(coll)
    made_all = []
    root_far = _new_obj("backdrop.far", None, coll)
    made_all.append(root_far)
    kf, lvf, totf = fit_budget(R, px, far_idx, max(a.far_tris - used_far, 50_000), None, picker, "far")
    made, st = build_export(scene, R, S, far_idx, lvf, split_far, picker, matcache, "far", True, -1.0,
                            prefix="far:", root_obj=root_far, use_hotspots=False)
    made_all += made
    stats["backdrop"]["far"] = dict(st, records=int(len(far_idx)))
    if len(span_idx):
        # pieces that span several areas (long streams): global, drawn all the time, kept fairly detailed
        root_span = _new_obj("global.span", None, coll)
        made_all.append(root_span)
        lvs = np.full(len(span_idx), int(np.nonzero(LEVELS <= 0.5)[0][0]))
        made, st = build_export(scene, R, S, span_idx, lvs, {}, picker, matcache, "span", False, 1e9,
                                prefix="span:", root_obj=root_span, use_hotspots=False)
        made_all += made
        stats["backdrop"]["span"] = dict(st, records=int(len(span_idx)))
    for k, cid in enumerate(ids):
        idx = np.nonzero(ch == k)[0]
        cand = idx[diag[idx] >= PROXY_MIN_DIAG]
        score = diag[cand] * np.where([R.top[i] == cid for i in cand], 3.0, 1.0)
        cand = cand[np.argsort(-score)][:PROXY_MAX_RECS]
        pxp = np.zeros(n)
        pxp[cand] = diag[cand] * 2.0
        root = _new_obj("proxy." + cid, None, coll)
        root["proxyOf"] = cid
        made_all.append(root)
        kp, lvp, totp = fit_budget(R, pxp, cand, max(a.proxy_tris - used_proxy[k], 5000), None, picker, "proxy." + cid)
        made, st = build_export(scene, R, S, cand, lvp, split_proxy[k], picker, matcache, "proxy." + cid, True, -1.0,
                                prefix="proxy." + cid + ":", root_obj=root, use_hotspots=False)
        made_all += made
        stats["backdrop"]["proxy." + cid] = dict(st, records=int(len(cand)))
    p = os.path.join(a.out, "backdrop.glb")
    export_glb(p, made_all, gpu_instances=True)
    stats["backdrop"]["glb"] = glb_stats(p)
    pg = _gz(p)
    os.remove(p)
    stats["backdrop"]["gz_bytes"] = os.path.getsize(pg)
    stats["time_s"] = round(time.time() - t0, 1)
    dump(os.path.join(WORK, "standin_stats.json"), stats, indent=1)
    write_manifest(a.out, stats)
    log("STANDIN", round(time.time() - t0, 1), "s")


def write_manifest(site, stats=None):
    """manifest.json v2 from chunks.json and the files present in `site`."""
    with open(os.path.join(WORK, "chunks.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    if stats is None and os.path.isfile(os.path.join(WORK, "standin_stats.json")):
        with open(os.path.join(WORK, "standin_stats.json"), encoding="utf-8") as fh:
            stats = json.load(fh)
    stats = stats or dict(chunks={})
    chunks = []
    for c in plan["chunks"]:
        f = c["id"] + ".glb.gz"
        p = os.path.join(site, f)
        st = stats["chunks"].get(c["id"], {})
        chunks.append(dict(id=c["id"], files=[f], filesLow=None, need=c["need"],
                           bytes=os.path.getsize(p) if os.path.isfile(p) else 0, bytesLow=None,
                           tris=st.get("glb", {}).get("triangles", c["tris_source"]),
                           core=c.get("core"), need250=c.get("need250"), hold=c["hold"]))
    has = lambda f: f if os.path.isfile(os.path.join(site, f)) else None   # noqa: E731
    man = {"version": 2, "baked": False, "camera": "camera.json", "meta": "meta.json", "clouds": has("clouds.json"),
           "flyer": has("flyer.glb"), "flyerPath": has("flyer.json"), "water": None,
           "global": ["backdrop.glb.gz"], "globalLow": None, "chunks": chunks}
    dump(os.path.join(site, "manifest.json"), man, indent=1)


def cmd_manifest(a):
    write_manifest(a.out)


# ---- full path: checks ------------------------------------------------------------------------

def cmd_camcheck(a):
    """Project hotspot centres at the hold frames through Blender's own camera (depsgraph at that frame,
    world_to_camera_view) and through camera.json's numbers (three.js maths); report the screen difference."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    cam = bpy.data.objects[CAMERA]
    scene.camera = cam
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1280, 720, 100
    with open(os.path.join(a.out, "camera.json"), encoding="utf-8") as fh:
        camj = json.load(fh)
    with open(os.path.join(a.out, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    rows = []
    worst = 0.0
    for h in camj["holds"]:
        f = h["frame"]
        scene.frame_set(f)
        row = camj["frames"][f - camj["frameStart"]]
        for hs in [x for x in meta["hotspots"] if x["area"] == h["id"]]:
            c3 = hs["center"]
            pb = Vector((c3[0], -c3[2], c3[1]))
            vb = world_to_camera_view(scene, cam, pb)
            nd = ndc_three(row["p"], row["q"], row["fovY"], camj.get("refAspect", ASPECT), c3)
            if nd is None or vb.z <= 0:
                continue
            x3, y3 = (nd[0] + 1) / 2, (nd[1] + 1) / 2
            dx, dy = (x3 - vb.x) * 1280, (y3 - vb.y) * 720
            on = 0 <= vb.x <= 1 and 0 <= vb.y <= 1
            rows.append(dict(hold=h["id"], frame=f, hotspot=hs["id"], blender_px=[round(vb.x * 1280, 2),
                             round((1 - vb.y) * 720, 2)], three_px=[round(x3 * 1280, 2), round((1 - y3) * 720, 2)],
                             diff_px=round(math.hypot(dx, dy), 4), on_screen=on))
            worst = max(worst, math.hypot(dx, dy))
    out = dict(max_diff_px=round(worst, 4), checks=rows)
    dump(os.path.join(WORK, "camcheck.json"), out, indent=1)
    on = [x for x in rows if x["on_screen"]]
    log("CAMCHECK", len(rows), "projections,", len(on), "on screen, max diff px", round(worst, 4))


def cmd_verifyfull(a):
    """Factory startup, no .blend: import the stand-in GLBs from the site folder, show per frame the chunks whose
    need range holds it (their proxies hidden, the other proxies shown), rebuild the camera from camera.json and
    render WORK/verify/verify_<frame>.png."""
    import gzip
    from mathutils import Quaternion
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    scene = bpy.context.scene
    site = a.out
    with open(os.path.join(site, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    with open(os.path.join(site, "camera.json"), encoding="utf-8") as fh:
        camj = json.load(fh)
    with open(os.path.join(site, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    tmp = "/tmp/sect_verify_full"
    os.makedirs(tmp, exist_ok=True)

    def imp(fname):
        src = os.path.join(site, fname)
        dst = os.path.join(tmp, os.path.basename(fname).replace(".gz", ""))
        with gzip.open(src, "rb") as fi, open(dst, "wb") as fo:
            fo.write(fi.read())
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=dst)
        return [o for o in bpy.data.objects if o not in before]
    glob_objs = []
    for g in man["global"]:
        glob_objs += imp(g)
    proxies = {}
    for o in glob_objs:
        p = o.get("proxyOf")
        if p:
            proxies[p] = [o] + list(o.children_recursive)
    chunk_objs = {}
    for c in man["chunks"]:
        chunk_objs[c["id"]] = []
        for f in c["files"]:
            chunk_objs[c["id"]] += imp(f)
    log("verify: imported", len(bpy.data.objects), "objects; proxies", sorted(proxies))
    cd = bpy.data.cameras.new("verify.cam")
    cam = bpy.data.objects.new("verify.cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cd.sensor_fit = "VERTICAL"
    cd.clip_start, cd.clip_end = 0.1, 9000.0
    sun = bpy.data.objects.new("verify.sun", bpy.data.lights.new("verify.sun", "SUN"))
    scene.collection.objects.link(sun)
    d3 = Vector(meta["sun"]["direction"])
    sun.rotation_euler = Vector((d3.x, -d3.z, d3.y)).to_track_quat("Z", "Y").to_euler()
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.75, 0.55)
    world = bpy.data.worlds.new("verify.world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.5, 0.65, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 8
    w, h = (int(x) for x in a.res.split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    out = os.path.join(WORK, "verify")
    os.makedirs(out, exist_ok=True)
    need = {c["id"]: c["need"] for c in man["chunks"]}
    report = []
    for f in [int(x) for x in a.ref_frames.split(",")]:
        drawn = [cid for cid, (n0, n1) in need.items() if n0 <= f <= n1]
        for cid, objs in chunk_objs.items():
            for o in objs:
                o.hide_render = cid not in drawn
        for cid, objs in proxies.items():
            for o in objs:
                o.hide_render = cid in drawn
        row = camj["frames"][f - camj["frameStart"]]
        p, q = row["p"], row["q"]
        cam.location = (p[0], -p[2], p[1])
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = (C3.transposed() @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix()).to_quaternion()
        cd.sensor_height = 36.0 * 9 / 16
        cd.lens = (cd.sensor_height / 2) / math.tan(math.radians(row["fovY"]) / 2)
        scene.render.filepath = os.path.join(out, "verify_%d.png" % f)
        bpy.ops.render.render(write_still=True)
        report.append(dict(frame=f, chunks=drawn))
        log("verify", f, "chunks", drawn)
    dump(os.path.join(out, "verify.json"), report, indent=1)


# ---- full path: audit.md ----------------------------------------------------------------------

def per_area_band(R, S, V, keep, near, mid):
    """Per area frame range: peak visible triangles in one sampled path frame (all, within near, within mid)."""
    fr = np.asarray(V["frames"])[:int(V.get("npath", len(V["frames"])))]
    tris = R.tris.astype(np.int64)
    out = []
    for ar in AREAS:
        js = np.nonzero((fr >= ar["frameStart"]) & (fr <= ar["frameEnd"]))[0]
        best = dict(all=0, near=0, mid=0, frame=None)
        for j in js:
            m = V["vis"][:, j] & keep
            d = V["dist"][:, j]
            t_all = int(tris[m].sum())
            if t_all > best["all"]:
                best.update(all=t_all, near=int(tris[m & (d <= near)].sum()), mid=int(tris[m & (d <= mid)].sum()),
                            frame=int(fr[j]))
        out.append(dict(area=ar["id"], frames=[ar["frameStart"], ar["frameEnd"]], peak_frame=best["frame"],
                        peak_visible_tris=best["all"], peak_within_near=best["near"], peak_within_mid=best["mid"]))
    return out


def write_audit_md_full(a):
    with open(os.path.join(WORK, "audit.json"), encoding="utf-8") as fh:
        A = json.load(fh)
    plan = None
    if os.path.isfile(os.path.join(WORK, "chunks.json")):
        with open(os.path.join(WORK, "chunks.json"), encoding="utf-8") as fh:
            plan = json.load(fh)
    st = None
    if os.path.isfile(os.path.join(WORK, "standin_stats.json")):
        with open(os.path.join(WORK, "standin_stats.json"), encoding="utf-8") as fh:
            st = json.load(fh)
    sc, vp, bb = A["scene"], A["visible_min_px"], A["by_band"]
    nb, mb = A["bands"]["near_max_m"], A["bands"]["mid_max_m"]
    L = []
    w = L.append
    w("# Web export audit: the whole flight (11 areas)")
    w("")
    w("Source `out/sect_chase.blend`, camera `chase.cam`, frames %d-%d (24 fps), sampled every %d frames (%d samples), "
      "scene evaluated at frame %s. Frustum + depth-buffer occlusion, as in the prototype. Written by "
      "`sect/export_web.py --profile full audit` (+ `auditmd`)." % (A["frames"][0], A["frames"][1], A["sampled_every"],
                                                                  A["sampled_frames"], A.get("scene_frame")))
    w("")
    w("## Short version")
    w("")
    w("- The file is %s triangles in %d geometry instances. Over the whole flight the camera sees %s of them "
      "(%d instances at >= 1.5 px)." % (_m(sc["triangles"]), sc["geometry_instances"], _m(vp["triangles"]),
                                         vp["instances"]))
    w("- Nearest distance bands: near (<= %d m) %s, mid (%d-%d m) %s, far (> %d m) %s. Near + mid is what the "
      "area chunks hold; far goes to the backdrop." % (nb, _m(bb["near"]["triangles"]), nb, mb,
                                                       _m(bb["mid"]["triangles"]), mb, _m(bb["far"]["triangles"])))
    w("- One sampled frame peaks at %s visible triangles." % _m(A["per_frame_peak_tris"]))
    lk = A.get("look")
    if lk and lk.get("mode") != "none":
        w("- Look-around views (%s): %d at the holds, %d between them. They add %d pieces (%s triangles) that the "
          "path alone never shows at >= 1.5 px. The counts above include them (distance x %s, size x %s)." % (
              lk["mode"], lk["views"]["hold"], lk["views"]["between"], lk["added_by_look"]["instances"],
              _m(lk["added_by_look"]["triangles"]), "/".join(str(x) for x in lk["weights"]["d_scale"][1:]),
              "/".join(str(x) for x in lk["weights"]["px"][1:])))
    w("")
    w("## Visible triangles per collection and band")
    w("")
    w("| collection | visible | near <= %d m | mid <= %d m | far | nearest m |" % (nb, mb))
    w("|---|---:|---:|---:|---:|---:|")
    for r in A["by_collection"]:
        if r["visible_triangles"] == 0:
            continue
        w("| %s | %s | %s | %s | %s | %s |" % (r["collection"], _m(r["visible_triangles"]), _m(r["near_tris"]),
                                               _m(r["mid_tris"]), _m(r["far_tris"]), r["nearest_m"]))
    w("")
    if A.get("per_area"):
        w("## Load per area (peak sampled frame inside the area's frame range)")
        w("")
        w("| area | frames | peak frame | visible | within %d m | within %d m |" % (nb, mb))
        w("|---|---|---:|---:|---:|---:|")
        for r in A["per_area"]:
            w("| %s | %d-%d | %s | %s | %s | %s |" % (r["area"], r["frames"][0], r["frames"][1], r["peak_frame"],
                                                     _m(r["peak_visible_tris"]), _m(r["peak_within_near"]),
                                                     _m(r["peak_within_mid"])))
        w("")
    if plan:
        w("## Chunk plan (`chunks.json`)")
        w("")
        w(plan["rule"])
        w("")
        w("| chunk | frames | hold | need (400 m) | core (150 m) | pieces | owners | source tris | prototype-rule estimate | stand-in file tris | stand-in gz MB |")
        w("|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|")
        for c in plan["chunks"]:
            s_ = (st or {}).get("chunks", {}).get(c["id"], {})
            core = c.get("core") or [0, 0]
            w("| %s | %d-%d | %d | %d-%d | %d-%d | %d | %d | %s | %s | %s | %s |" % (
                c["id"], c["frameRange"][0], c["frameRange"][1], c["hold"], c["need"][0], c["need"][1], core[0],
                core[1], c["records"], c["owners_count"], _m(c["tris_source"]), _m(c["tris_est_proto_rule"]),
                _m(s_.get("glb", {}).get("triangles", 0)) if s_ else "-",
                "%.1f" % (s_.get("gz_bytes", 0) / 1e6) if s_ else "-"))
        b = plan["backdrop"]
        w("")
        cc = plan.get("concurrency", {})
        if cc:
            w("Chunks that must be drawn at the same time (per frame): need %s at most, %s on average; within 250 m "
              "%s / %s; core %s / %s. With a 400 m band the areas (140-350 m apart) overlap a lot, so `core` is the "
              "better cue for where full detail matters; between core and need the area's proxy reads fine." % (
                  cc["need"]["max"], cc["need"]["mean"], cc["need250"]["max"], cc["need250"]["mean"],
                  cc["core"]["max"], cc["core"]["mean"]))
            w("")
        sp = plan.get("span")
        if sp and sp.get("records"):
            w("Global span pieces (long streams, drawn all the time): %s (%s triangles)." % (
                ", ".join(sp["names"]), _m(sp["tris"])))
            w("")
        w("Backdrop (seen only beyond %d m): %d pieces, %s source triangles (%s). Not exported: %d pieces." % (
            plan["band_m"], b["records"], _m(b["tris_source"]),
            ", ".join("%s %s" % (k, _m(v)) for k, v in list(b["by_collection"].items())[:6]),
            plan["not_exported"]["records"]))
        if st and st.get("backdrop", {}).get("glb"):
            g = st["backdrop"]["glb"]
            w("Stand-in `backdrop.glb.gz`: %s triangles, %d draw calls, %.1f MB gz (far set + 11 proxies)." % (
                _m(g["triangles"]), g["draw_calls"], st["backdrop"]["gz_bytes"] / 1e6))
        w("")
    far = A.get("far_groups", [])[:8]
    w("## What lies far away")
    w("")
    w("Largest groups only ever seen beyond %d m: " % mb + ", ".join(
        "%s %s (from %d m)" % (r["group"], _m(r["tris"]), r["nearest_m"]) for r in far) + ".")
    w("")
    notes = {}
    np_ = os.path.join(os.path.dirname(LABELS_JSON), "audit_notes.json")     # written on the PC, uploaded
    if os.path.isfile(np_):
        with open(np_, encoding="utf-8") as fh:
            notes = json.load(fh)
    for title, key in (("Hold frames", "holds"), ("Surprises", "surprises")):
        if notes.get(key):
            w("## " + title)
            w("")
            for s_ in notes[key]:
                w("- " + s_)
            w("")
    path = os.path.join(WORK, "audit.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    log("wrote", path)


# ---- main -------------------------------------------------------------------------------------

COMMANDS = ["audit", "camera", "meta", "sky", "flyer", "scene", "refs", "verify", "auditmd", "clouds",
            "chunks", "standin", "manifest", "camcheck", "verifyfull"]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="export_web.py")
    ap.add_argument("command", help="one of %s, or several joined by commas (run in order)" % ", ".join(COMMANDS))
    ap.add_argument("--profile", default="proto", choices=["proto", "full"],
                    help="proto: the first test (gate/mirror, frames 1-288, out/web/proto); full: all 11 areas, "
                         "frames 1-1729, out/web/full (+ site/)")
    ap.add_argument("--frames", default="")
    ap.add_argument("--step", type=int, default=0)
    ap.add_argument("--near", type=float, default=NEAR_MAX)
    ap.add_argument("--mid", type=float, default=0.0)
    ap.add_argument("--max-tris", type=int, default=1_800_000,
                    help="Blender-side budget; the glTF exporter drops ~20 %% (degenerate faces), so 1.8M lands "
                         "near 1.45M in the files (export_stats.json 'glb' has the measured numbers)")
    ap.add_argument("--chunk-tris", type=int, default=CHUNK_TRIS, help="full standin: Blender-side tris per chunk")
    ap.add_argument("--far-tris", type=int, default=FAR_TRIS, help="full standin: backdrop far set")
    ap.add_argument("--proxy-tris", type=int, default=PROXY_TRIS, help="full standin: per-area proxy")
    ap.add_argument("--ref-frames", default="")
    ap.add_argument("--start-frame", type=int, default=0)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--ref-dir", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--merge-mid", type=int, default=1, help="1: join mid-band objects per collection (fewer draws)")
    ap.add_argument("--look", default="", choices=("",) + LOOK_MODES,
                    help="audit: look-around views after the path frames (default holds+between for --profile full, "
                         "none for proto). holds: 44 views per hold; holds+between: also every %d frames between "
                         "the holds; none: the path only, as before" % LOOK_EVERY)
    a = ap.parse_args(argv)
    use_profile(a.profile)
    full = PROFILE == "full"
    a.frames = a.frames or "%d-%d" % FRAMES
    a.step = a.step or (FULL_STEP if full else 2)
    a.mid = a.mid or (NM_BAND if full else MID_MAX)
    a.look = a.look or ("holds+between" if full else "none")
    a.ref_frames = a.ref_frames or ",".join(str(f) for f in REF_FRAMES)
    a.out = fix_path(a.out) if a.out else SITE
    a.ref_dir = fix_path(a.ref_dir) if a.ref_dir else ""
    cmds = a.command.split(",")
    for c in cmds:
        if c not in COMMANDS:
            raise SystemExit("unknown command %r (one of %s)" % (c, ", ".join(COMMANDS)))
    for c in cmds:
        t0 = time.time()
        if full and c == "meta":
            cmd_meta_full(a)
        elif full and c == "auditmd":
            write_audit_md_full(a)
        else:
            globals()["cmd_" + c](a)
        log("done", c, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
