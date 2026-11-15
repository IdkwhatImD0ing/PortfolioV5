"""Round 56: form and edges (docs/scene/form-r56.md), in an existing out/sect_chase.blend, so it matches what a fresh
build of sect/world.py, areas/mirror.py, areas/abode.py and areas/arena.py makes. Every number comes from those
modules (their round-56 values and the round-55 ones they replaced, *_R55), never from this file. Run on the cloud box,
on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r56_form.py -- [DRY_RUN=1] \
        [PARTS=rim,lawn,walls,sword,bridge] [WALLS_MODE=B|A] [<module>.<CONSTANT>=<python literal> ...]

Why (owner, 2026-11-09): "some of the objects in the scene are haphazardly placed and the quality is not good enough".
A sweep of the whole flight on 2026-11-10 found these five.

What it does (PARTS, default all five; every object keeps its name, the web export keys on names):
- rim: world.range's grass ends on a level line on every terrace. terrain_data is rebuilt with the committed Range
  (world.range['r48_range'], the round-48 state patch_r48_range.py stored; else world.py's default), its faces must
  equal world.range's polygons, and the top faces near a terrace (terrain_data near_top) whose material differs
  between world.RIM_RULE_R55 (c00 and c11 on the flat) and world.RIM_RULE (all four corners) take the new one:
  material_index only, nothing re-triangulated, 'world_veg' and every other face left alone. Logs moss->rock and
  rock->moss per anchor (rock->moss is 0 by construction).
- lawn: mirror.lawn dives under the terrace past r 40 (mirror.LAWN_EDGE), abode.ground past r 49.55
  (abode.LAWN_EDGE, kept off the two depart lanterns at r 49.1), both with mirror.lawn_edge (the dive, then seat_lawn
  on the vertices past the dive's start only); mirror.path_main and mirror.path_forge reach mirror.PATH_BOTTOM (-0.6,
  was -0.35). Meshes reshaped in place, same names. At the abode the lawn's rings are 0.73 m apart, so a dive from
  r 49 would tilt the faces the rail (r 48.5) stands on; from r 49.55 only the edge ring moves.
- walls: every world.link.<a>_<b>.rails, .foot_rail and .rest_rail: slot 0 becomes world_wall_marble (slot 1, the
  .rails' world_pier_stone undersides, stays). WALLS_MODE=B (default) also writes the per-vertex wall coordinates
  arch_gen / arch_dims from the mesh itself (world.wall_coords, with its strict layout check: a mesh that is not
  exactly what _ribbon / _prism lay down stops the patch); WALLS_MODE=A is the fallback that needs no attributes.
- sword: the Heavy Iron Sword's three tones per broad face and lighter worn edges (arena.HS_SIDE_EDGE,
  props_iron_heavy): patch_heavy_iron_sword.rebuild(), the in-place rebuild with its own checks (boxes inside
  HS_OLD_BOX, triangle caps, closed parts, the plaque gone).
- bridge: world.link.forge_arena.bridge.deck / .boards / .posts / .chains get the meshes world._chain_bridge builds
  with world.FORGE_ARENA_SAG (5.5 m, was 2.0), swapped into the same objects (flat shading as built).

State: each part is 'old' (as round 55 left it) or 'r56' (as this build makes it: nothing to do). Anything else stops
the patch before it changes anything. Idempotent: on a patched file it prints 'PATCH nothing changed: not saving' and
the same DIGEST. WALLS_MODE must be the one a patched file was patched with (switching starts from the round-55 file).

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- rim: world.range's faces equal terrain_data's, its top vertices on the recipe in XY, its slots rock_cliff /
  nature_soil_moss / world_rock_under; after: exactly the changed faces differ, vertices and world_veg unchanged;
- lawn: every lawn vertex inside the untouched radius unchanged; under every foot of everything standing on a lawn
  (the lowest point of each 0.5 m cell of each object near the lawn, instances included) the ground changes by at most
  SEAT_MAX inside that radius, and nothing anywhere loses its ground (a foot in or on the lawn before ends more than
  SINK_FLOAT over it); the lawn's scatter instances inside the radius keep their places (height within SEAT_MAX);
  each path's bottom edge lies on or under the lawn;
- walls: every wall mesh has the builder's layout (mode B), is used by one object, its slot 1 world_pier_stone; after:
  attributes equal wall_coords', slot 0 world_wall_marble in the asked mode;
- sword: patch_heavy_iron_sword.rebuild()'s checks; after: every part's 'edge' values and slots are round 56's;
- bridge: the old meshes are a sag-2.0 build, vertex for vertex within BRIDGE_TOL (else the ports moved: stop);
  after: same plank count, the level ends' planks unchanged, every riser <= world.RISER, every tread >=
  world.TREAD_MIN, the deck never dips, at least BRIDGE_CLEAR m over world.range along the middle 80 % of the free span and over it everywhere, no new contact with
  anything else, deck / boards / posts flat-shaded;
- still: no object outside the touched ones changed its world matrix, mesh or material slots; none vanished, none
  appeared; no scratch data left.
Prints 'PATCH CACHES needs [chunks,meta; ]bakefull <the changed parts' chunks>' (rim on all terraces: every area chunk
plus backdrop; lawn and bridge grow boxes downward, so they ask for chunks,meta) and 'PATCH DIGEST <md5>' of every
round-56 object (all five parts, whichever ran).
"""
import ast
import hashlib
import json
import os
import re
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world as W  # noqa: E402
from sect.areas import abode as AB  # noqa: E402
from sect.areas import arena as AR  # noqa: E402
from sect.areas import mirror as MR  # noqa: E402
from sect.lib import materials as M  # noqa: E402

PARTS = ("rim", "lawn", "walls", "sword", "bridge")
SCRATCH = "~r56"
SKIP = ("world.haze", "world.cloud", "world.stream", SCRATCH)
STILL_TOL = 1e-5               # world matrix entries
R48_PROP = "r48_range"         # world.range: the round-48 Range options (patch_r48_range.py)
RANGE = "world.range"
RANGE_SLOTS = ("rock_cliff", "nature_soil_moss", "world_rock_under")
RIM_XY_TOL = 0.05              # m: world.range's top vertices against the rebuilt recipe. Measured on the round-55 file
                               # (2026-11-10): 83 of 214,414 are 1 mm to 2.8 cm off sideways, scattered over the whole
                               # range, none nearer than 38 m to a terrace's centre. Why was not traced (the file was
                               # built on another machine). The faces are identical and the rule gives every near-top
                               # face the material the file has, so the recipe is the file's
RIM_XY_FACE = 1e-3             # m: ... but no vertex of a face this patch re-classes may be off by more than this
ROOT_TOL = 1e-3                # m: a lawn's world matrix against its area root's. Both are float32 at world
                               # coordinates past 1000 m, so the difference of the two can be 0.05 mm (abode: 4e-5)
# lawn
LAWNS = dict(mirror="mirror.lawn", abode="abode.ground")
PATHS = ("mirror.path_main", "mirror.path_forge")
FOOT_CELL = 0.5                # m: a standing object's foot is the lowest point of each such XY cell ...
FOOT_DEEP, FOOT_HIGH = 0.8, 0.05   # ... that lies from FOOT_DEEP under to FOOT_HIGH over the lawn
FOOT_MAX = 160                 # foot points per object at most (evenly picked)
SEAT_MAX = 0.02                # m: the ground under a foot (or a scatter instance) inside the untouched radius may change
                               # this much, the abode rail's RIM_SINK. More fails. The faces from the last ring inside the
                               # radius to the first dived one tilt: ground_patch's rings are 0.73-0.8 m apart, so at the
                               # abode (rail r 48.5, rings at 48.55 and 49.28, each jittered up to 0.22 m) a dive from
                               # r 49 moves the lawn under the rail's outer feet by 2-6 cm and can cut its lip as close
                               # as r 48.6 (scratchpad model, docs/scene/form-r56.md). If this check stops the abode, run
                               # with abode.LAWN_EDGE=(49.55,50.0,-0.6): only the edge ring (r 50) moves, nothing within
                               # r 49.06
SEAT_LOG = 0.001               # m: changes over this are listed
SINK_FLOAT = 0.005             # m: a foot this far over the ground still stands on it
# walls
WALL_RE = re.compile(r"^world\.link\.[a-z]+_[a-z]+(\.rails|\.foot_rail|\.rest_rail)$")
ATTR_TOL = 1e-4
# bridge
BRIDGE = "world.link.forge_arena.bridge"
BRIDGE_LINK = ("forge", "arena")
BRIDGE_PARTS = ("deck", "boards", "posts", "chains")
BRIDGE_FLAT = ("deck", "boards", "posts")
BRIDGE_CLEAR = 2.0             # m over world.range along the middle of the free span (w 0.1-0.9)
BRIDGE_MID = (0.1, 0.9)
BRIDGE_LATERAL = (-1.9, 0.0, 1.9)   # m: clearance rays across the deck (the chains hang at +-1.9)
BRIDGE_TOL = 1e-3              # m: the file's bridge against a scratch build, vertex for vertex
# chunks each part's change re-bakes (docs/scene/form-r56.md; the research's chunks.npz counts)
AREA_CHUNKS = W.ORDER
CHUNKS = dict(rim=AREA_CHUNKS + ("backdrop",),
              lawn=("mirror", "abode", "backdrop"),
              walls=("gate", "mirror", "forge", "library", "steles", "scroll", "formation", "abode", "summit",
                     "backdrop"),
              sword=("arena", "backdrop"),
              bridge=("forge", "backdrop"))
NEEDS_CHUNKS = ("lawn", "bridge")   # their boxes grow downward: export_web chunks,meta before the bake
MODULES = dict(world=W, mirror=MR, abode=AB, arena=AR)


def log(*a):
    print("PATCH", *a, flush=True)


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


def options():
    """(dry, parts, walls mode). Also <module>.<CONSTANT>=<python literal> for world, mirror, abode, arena or patch
    (this file), e.g. abode.LAWN_EDGE=(49.5,50.0,-0.6): for this run only (write it into the builder too, or a fresh
    build will differ from the file)."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, parts, mode = False, PARTS, "B"
    mods = dict(MODULES, patch=sys.modules[__name__])
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("patch_r56_form: not KEY=value: %r" % a)
        if k == "DRY_RUN":
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PARTS":
            parts = tuple(p.strip() for p in v.split(",") if p.strip())
            bad = [p for p in parts if p not in PARTS]
            if bad or not parts:
                raise SystemExit("patch_r56_form: unknown parts %s (known: %s)" % (bad, ",".join(PARTS)))
            parts = tuple(p for p in PARTS if p in parts)
        elif k == "WALLS_MODE":
            mode = v.strip().upper()
            if mode not in ("A", "B"):
                raise SystemExit("patch_r56_form: WALLS_MODE must be A or B")
        elif "." in k and k.split(".", 1)[0] in mods and k.split(".", 1)[1].isupper():
            mn, cn = k.split(".", 1)
            mod = mods[mn]
            if not hasattr(mod, cn):
                raise SystemExit("patch_r56_form: %s has no %s" % (mn, cn))
            setattr(mod, cn, ast.literal_eval(v))
            log("override %s.%s = %r" % (mn, cn, getattr(mod, cn)))
        else:
            raise SystemExit("patch_r56_form: unknown option %r (DRY_RUN=1, PARTS=%s, WALLS_MODE=B|A, "
                             "<module>.<CONSTANT>=...)" % (a, ",".join(PARTS)))
    return dry, parts, mode


# ---------------------------------------------------------------------------------------------------------- helpers

def obj(name):
    return bpy.data.objects.get(name)


def tag(mat):
    """A material's registered name (its sect_material tag, else its name without 'M.')."""
    if mat is None:
        return None
    t = mat.get(M.TAG)
    if t:
        return str(t)
    return mat.name[len(M.PREFIX):] if mat.name.startswith(M.PREFIX) else mat.name


def slots(ob):
    return [tag(s.material) for s in ob.material_slots]


def coords(me, dtype=np.float64):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.astype(dtype).reshape(-1, 3)


def mesh_faces(me):
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    return lt, lv


def face_mats(me):
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    return mi


def face_float(me, name):
    at = me.attributes.get(name)
    if at is None or at.domain != 'FACE':
        return None
    v = np.empty(len(me.polygons), np.float32)
    at.data.foreach_get("value", v)
    return v


def point_vec(me, name):
    at = me.attributes.get(name)
    if at is None or at.domain != 'POINT' or at.data_type != 'FLOAT_VECTOR':
        return None
    v = np.empty(len(me.vertices) * 3, np.float32)
    at.data.foreach_get("vector", v)
    return v.reshape(-1, 3)


def identity(ob, tol=1e-6):
    return np.allclose(np.array(ob.matrix_world), np.eye(4), atol=tol)


def faces_sig(me, decimals=4):
    """Order-free fingerprint of a mesh: every face as its rounded corners (cyclic from the smallest) and material."""
    co = coords(me)
    q = np.round(co * 10 ** decimals).astype(np.int64)
    mats = [tag(m) or "" for m in me.materials]
    lt, lv = mesh_faces(me)
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]]) if len(lt) else np.zeros(0, np.int64)
    mi = face_mats(me)
    out = []
    for s, n, m in zip(ls.tolist(), lt.tolist(), mi.tolist()):
        pts = [tuple(q[i]) for i in lv[s:s + n]]
        k = pts.index(min(pts))
        out.append((tuple(pts[k:] + pts[:k]), mats[m] if m < len(mats) else ""))
    out.sort()
    h = hashlib.md5()
    h.update(("%d %d" % (len(co), len(lt))).encode())
    for f, m in out:
        h.update(repr(f).encode())
        h.update(m.encode())
    return h.hexdigest()


def array_sig(*arrays):
    h = hashlib.md5()
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


class Scratch:
    """A scratch collection for builds compared with the file's objects (dropped with everything in it)."""

    def __init__(self):
        self.coll = bpy.data.collections.new(SCRATCH + ".coll")
        bpy.context.scene.collection.children.link(self.coll)

    def drop(self, keep_meshes=()):
        keep = set(keep_meshes)
        for ob in list(self.coll.all_objects):
            d = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if isinstance(d, bpy.types.Mesh) and d.users == 0 and d.name not in keep:
                bpy.data.meshes.remove(d)
        bpy.data.collections.remove(self.coll)


def local_tris(me):
    try:
        me.calc_loop_triangles()
    except Exception:  # noqa: BLE001
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    return co.reshape(nv, 3)[tv.reshape(nt, 3)]


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)],
                                [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(T))], all_triangles=True)


VOLUME_MATS = None


def volume_owner(ob):
    global VOLUME_MATS
    if VOLUME_MATS is None:
        VOLUME_MATS = {m.name for m in bpy.data.materials if m.node_tree is not None and
                       any(n.bl_idname.startswith("ShaderNodeVolume") for n in m.node_tree.nodes)}
    return ob.type == 'VOLUME' or any(s.material is not None and s.material.name in VOLUME_MATS
                                      for s in ob.material_slots)


def world_tris(dg, owners=None, near=None, skip_volumes=True, exclude=()):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes (instances under their instancer's name):
    these owners, or those whose box meets the box ``near`` (lo, hi), less ``exclude``. Hidden-from-render and volume
    objects left out."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own.startswith(SKIP) or own in exclude:
            continue
        src = bpy.data.objects.get(own)
        if src is not None and (src.hide_render or (skip_volumes and volume_owner(src))):
            continue
        Wm = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ Wm[:3, :3].T + Wm[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L = local_tris(o.data)
        if not len(L):
            continue
        T = L @ Wm[:3, :3].T + Wm[:3, 3]
        if near is not None:
            T = T[~((T.min(1) > near[1]).any(1) | (T.max(1) < near[0]).any(1))]
            if not len(T):
                continue
        out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def ground_at(tree, p, up=2.0, reach=6.0):
    loc, _n, _i, _d = tree.ray_cast(Vector((float(p[0]), float(p[1]), float(p[2]) + up)), Vector((0.0, 0.0, -1.0)),
                                    reach)
    return None if loc is None else float(loc.z)


# ------------------------------------------------------------------------------------------------------- the context

class Ctx:
    def __init__(self, mode):
        self.mode = mode
        self._range = None
        self.info = {}

    def committed_range(self):
        """The Range world.range was built and patched with (patch_r48_range's stored options), built once."""
        if self._range is None:
            an, yaws = W._norm_anchors(None), W._anchor_yaws(None)
            ob = obj(RANGE)
            st = json.loads(ob[R48_PROP]) if ob is not None and R48_PROP in ob.keys() else None
            if st is None:
                log("rim: world.range has no %r record: world.py's default Range (peak_mode %s)" % (R48_PROP,
                                                                                                    W.PEAK_MODE))
                self._range = W.Range(an, yaws)
            else:
                from sect import patch_r48_range as P48
                log("rim: the committed Range: round 48 variant %s (mode %s, preset %s, %d peaks kept as cones)" % (
                    st["variant"], st["mode"], st["preset"], len(st["skip"])))
                self._range = P48.make_range(an, yaws, st["mode"], st["preset"], st["skip"], st["only"],
                                             st["holds"], st["limits"])
        return self._range


# ------------------------------------------------------------------------------------------------------------ rim

def rim_state(ctx, fail):
    ob = obj(RANGE)
    if ob is None or ob.type != 'MESH':
        fail.add("rim: no world.range mesh")
        return "unknown"
    if not identity(ob):
        fail.add("rim: world.range has a transform; the range is built in world space")
        return "unknown"
    if tuple(slots(ob)) != RANGE_SLOTS:
        fail.add("rim: world.range's slots are %s, not %s" % (slots(ob), RANGE_SLOTS))
        return "unknown"
    t0 = time.time()
    if "rim_d" not in ctx.info:
        ctx.info["rim_d"] = W.terrain_data(ctx.committed_range())
    d = ctx.info["rim_d"]
    me = ob.data
    log("rim: terrain data in %.1f s: %d vertices, %d faces (world.range %d, %d)" % (
        time.time() - t0, len(d["verts"]), len(d["faces"]), len(me.vertices), len(me.polygons)))
    if len(d["verts"]) != len(me.vertices) or len(d["faces"]) != len(me.polygons):
        fail.add("rim: world.range is not the committed range's mesh (vertices %d / %d, faces %d / %d)" % (
            len(me.vertices), len(d["verts"]), len(me.polygons), len(d["faces"])))
        return "unknown"
    lt, lv = mesh_faces(me)
    if not (lt == 4).all() or not np.array_equal(lv.reshape(-1, 4), d["faces"]):
        fail.add("rim: world.range's faces differ from terrain_data's (another patch changed its topology)")
        return "unknown"
    co = coords(me)
    nt = d["n_top"]
    dxy_v = np.abs(co[:nt, :2] - d["verts"][:nt, :2]).max(axis=1)
    dxy = float(dxy_v.max())
    dz = np.abs(co[:nt, 2] - d["verts"][:nt, 2])
    log("rim: top vertices off the recipe: %.4f m in XY at most (%d by more than 1 mm), %d off in z by more than 1 mm" % (
        dxy, int((dxy_v > RIM_XY_FACE).sum()), int((dz > 1e-3).sum())))
    if dxy > RIM_XY_TOL:
        fail.add("rim: world.range's top vertices moved %.4f m sideways off the recipe" % dxy)
        return "unknown"
    nq = d["n_qt"]
    old, new = d["mats_r55"][:nq], d["mats_r56"][:nq]
    D = np.nonzero((old != new) & d["near_top"])[0]
    off = np.nonzero(dxy_v > RIM_XY_FACE)[0]
    n_off = int(np.isin(d["faces"][D], off).any(axis=1).sum()) if len(D) and len(off) else 0
    if n_off:
        fail.add("rim: %d of the faces to re-class use a vertex that sits off the recipe" % n_off)
        return "unknown"
    mi = face_mats(me)
    cur = mi[D]
    centres = d["verts"][d["faces"][D]].mean(axis=1)
    an = W._norm_anchors(None)
    keys = list(an)
    axy = np.array([an[k][:2] for k in keys])
    near_k = np.argmin(np.hypot(centres[:, 0:1] - axy[None, :, 0], centres[:, 1:2] - axy[None, :, 1]), axis=1) \
        if len(D) else np.zeros(0, int)
    rows = []
    for j, k in enumerate(keys):
        sel = near_k == j
        rows.append("%s %d moss->rock, %d rock->moss" % (k, int(((old[D] == 1) & (new[D] == 0) & sel).sum()),
                                                         int(((old[D] == 0) & (new[D] == 1) & sel).sum())))
    log("rim: %d top faces near the terraces change with the rule (%s)" % (len(D), "; ".join(rows)))
    other = int(((mi[:nq] != old) & d["near_top"]).sum()) - int((cur != old[D]).sum())
    log("rim: near the terraces, %d other top faces differ from the round-55 rule already (left alone)" % other)
    ctx.info["rim"] = dict(D=D, new=new[D], old=old[D], mi=mi, nq=nq)
    at_old, at_new = bool((cur == old[D]).all()), bool((cur == new[D]).all())
    log("rim: of the changing faces %d are as round 55 has them, %d as round 56" % (
        int((cur == old[D]).sum()), int((cur == new[D]).sum())))
    if not len(D):
        log("rim: WARN no face changes with the rule")
        return "r56"
    if at_old:
        return "old"
    if at_new:
        return "r56"
    fail.add("rim: the changing faces are neither all round 55's nor all round 56's")
    return "unknown"


def rim_apply(ctx, fail):
    ob = obj(RANGE)
    me = ob.data
    r = ctx.info["rim"]
    veg = face_float(me, "world_veg")
    ctx.info["rim_before"] = dict(co=array_sig(coords(me, np.float32)),
                                  veg=array_sig(veg if veg is not None else np.zeros(0)), mi=r["mi"].copy())
    mi = r["mi"].copy()
    mi[r["D"]] = r["new"]
    me.polygons.foreach_set("material_index", mi)
    me.update()
    log("rim: %d faces re-classed (material_index only)" % len(r["D"]))


def rim_check(ctx, fail):
    ob = obj(RANGE)
    me = ob.data
    r = ctx.info["rim"]
    b = ctx.info.get("rim_before")
    if b is None:
        return
    mi = face_mats(me)
    diff = np.nonzero(mi != b["mi"])[0]
    if not np.array_equal(np.sort(diff), np.sort(r["D"])):
        fail.add("rim: %d faces changed, %d meant to" % (len(diff), len(r["D"])))
    if array_sig(coords(me, np.float32)) != b["co"]:
        fail.add("rim: world.range's vertices changed")
    veg = face_float(me, "world_veg")
    if array_sig(veg if veg is not None else np.zeros(0)) != b["veg"]:
        fail.add("rim: world.range's world_veg changed")


def rim_digest(h):
    ob = obj(RANGE)
    if ob is None:
        h.update(b"no range")
        return
    me = ob.data
    h.update(array_sig(face_mats(me), np.round(coords(me) * 1e4).astype(np.int64)).encode())


# ------------------------------------------------------------------------------------------------------------ lawn

def lawn_spec(area):
    if area == "mirror":
        return dict(edge=tuple(MR.LAWN_EDGE), keep=(), keep_r=0.0,
                    run=lambda ob: MR.lawn_edge(ob, tuple(MR.LAWN_EDGE)))
    return dict(edge=tuple(AB.LAWN_EDGE), keep=tuple(AB.DEPART_LANTERN_AT), keep_r=AB.LAWN_KEEP[0],
                run=lambda ob: AB.lawn_edge(ob))


def in_root(ob, area, fail):
    """The lawn's own coordinates are its area's frame (its world matrix is the area root's): its radii are the
    builders'."""
    root = obj(area + ".root")
    rel = None if root is None else np.array(root.matrix_world.inverted() @ ob.matrix_world)
    ok = rel is not None and np.allclose(rel[:3, :3], np.eye(3), atol=1e-5) and \
        float(np.abs(rel[:3, 3]).max()) <= ROOT_TOL
    if not ok:
        fail.add("lawn: %s does not sit at %s's origin in its frame" % (ob.name, area))
    return ok


def lawn_state_one(area, fail):
    nm = LAWNS[area]
    ob = obj(nm)
    if ob is None or ob.type != 'MESH':
        fail.add("lawn: %s missing" % nm)
        return "unknown"
    if not in_root(ob, area, fail):
        return "unknown"
    if ob.data.users != 1:
        fail.add("lawn: %s's mesh has %d users" % (nm, ob.data.users))
        return "unknown"
    spec = lawn_spec(area)
    r0, r1, z1 = spec["edge"]
    co = coords(ob.data)
    r = np.hypot(co[:, 0], co[:, 1])
    zc, zs = MR.TERRACE_Z + MR.LAWN_CLEAR, MR.TERRACE_Z - MR.LAWN_SINK
    free = np.array([MR.edge_free(x, y, spec["edge"], spec["keep"], spec["keep_r"]) for x, y in co[:, :2]], bool)
    band = free & (co[:, 2] > zs + 1e-6) & (co[:, 2] < zc - 1e-6)
    outer = r >= r1 - 1e-3
    t = ob.data.get(MR.LAWN_EDGE_TAG)
    log("lawn: %s: %d vertices, %d on the edge ring (z %.3f..%.3f), %d past r %.1f in the seat band, tag %r" % (
        nm, len(co), int(outer.sum()), co[outer, 2].min() if outer.any() else float("nan"),
        co[outer, 2].max() if outer.any() else float("nan"), int(band.sum()), r0, t))
    if t is None and outer.any() and co[outer, 2].min() > z1 + 0.05:
        return "old"
    if t == MR.edge_tag((r0, r1, z1)) and not band.any():
        return "r56"
    fail.add("lawn: %s is in a state this patch does not know (tag %r, %d vertices in the seat band past r %.1f)" % (
        nm, t, int(band.sum()), r0))
    return "unknown"


def path_state_one(nm, fail):
    ob = obj(nm)
    if ob is None or ob.type != 'MESH' or ob.data.users != 1:
        fail.add("lawn: %s missing or its mesh shared" % nm)
        return "unknown"
    z = coords(ob.data)[:, 2]
    top = np.abs(z - MR.PATH_Z) < 1e-4
    bot = ~top
    zb = z[bot]
    log("lawn: %s: %d vertices, top %d at %.3f, bottom %d at %.3f..%.3f" % (
        nm, len(z), int(top.sum()), MR.PATH_Z, int(bot.sum()), zb.min() if len(zb) else 0, zb.max() if len(zb) else 0))
    if top.sum() != bot.sum() or not len(zb):
        fail.add("lawn: %s is not a flat strip (top / bottom vertices %d / %d)" % (nm, int(top.sum()), int(bot.sum())))
        return "unknown"
    if np.abs(zb - MR.PATH_BOTTOM_R55).max() < 1e-4:
        return "old"
    if np.abs(zb - MR.PATH_BOTTOM).max() < 1e-4:
        return "r56"
    fail.add("lawn: %s's bottom is at %.3f..%.3f, neither %.2f nor %.2f" % (nm, zb.min(), zb.max(),
                                                                         MR.PATH_BOTTOM_R55, MR.PATH_BOTTOM))
    return "unknown"


def lawn_state(ctx, fail):
    st = {a: lawn_state_one(a, fail) for a in LAWNS}
    st.update({p: path_state_one(p, fail) for p in PATHS})
    ctx.info["lawn_states"] = st
    log("lawn: states %s" % ", ".join("%s %s" % kv for kv in st.items()))
    vals = set(st.values())
    if "unknown" in vals:
        return "unknown"
    if vals == {"r56"}:
        return "r56"
    return "old"        # any piece still to do (the done ones are skipped)


def scatter_children(ob):
    return sorted(c.name for c in ob.children if any(m.type == 'NODES' for m in c.modifiers))


def scatter_points(dg, names):
    out = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.name in names:
            t = inst.matrix_world.translation
            out.append((inst.object.original.name if inst.object else "", float(t.x), float(t.y), float(t.z)))
    return out


def lawn_snapshot(area):
    """What stands on the lawn: {owner: (foot points (n, 3) world, ground under each)}, the scatter instances, the
    lawn's vertices (local) and the radius test (world -> r in the area's frame)."""
    dg = bpy.context.evaluated_depsgraph_get()
    nm = LAWNS[area]
    ob = obj(nm)
    root = obj(area + ".root")
    inv = np.array(root.matrix_world.inverted())
    T = world_tris(dg, owners={nm}, skip_volumes=False).get(nm)
    tree = bvh(T)
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    near = (lo - np.array([1.0, 1.0, 1.0]), hi + np.array([1.0, 1.0, 1.5]))
    coll = bpy.data.collections.get(area)
    members = {o.name for o in coll.all_objects} if coll else set()
    skip = {nm} | set(PATHS) | set(scatter_children(ob))
    out = {}
    others = {o.name for o in bpy.data.objects if o.name not in members} | skip
    for own, tr in world_tris(dg, near=near, exclude=others).items():
        V = tr.reshape(-1, 3)
        cell = np.floor(V[:, :2] / FOOT_CELL).astype(np.int64)
        key = cell[:, 0] * 1000003 + cell[:, 1]
        order = np.lexsort((V[:, 2], key))
        ks = key[order]
        first = order[np.concatenate([[True], ks[1:] != ks[:-1]])]
        pts, gs = [], []
        for p in V[first]:
            g = ground_at(tree, p)
            if g is not None and g - FOOT_DEEP <= p[2] <= g + FOOT_HIGH:
                pts.append(p)
                gs.append(g)
        if not pts:
            continue
        if len(pts) > FOOT_MAX:
            pick = np.linspace(0, len(pts) - 1, FOOT_MAX).astype(int)
            pts, gs = [pts[i] for i in pick], [gs[i] for i in pick]
        out[own] = (np.array(pts), np.array(gs))
    sc = scatter_children(ob)
    return dict(stand=out, inst=scatter_points(dg, set(sc)), scatter=sc, co=coords(ob.data), inv=inv)


def radius(snap, P):
    P = np.atleast_2d(P)
    L = P @ snap["inv"][:3, :3].T + snap["inv"][:3, 3]
    return np.hypot(L[:, 0], L[:, 1])


def lawn_apply(ctx, fail):
    st = ctx.info["lawn_states"]
    ctx.info["lawn_before"] = {a: lawn_snapshot(a) for a in LAWNS if st[a] == "old"}
    for a, snap in ctx.info["lawn_before"].items():
        log("lawn: %s: %d objects stand on it (%d foot points), %d scatter instances (%s)" % (
            LAWNS[a], len(snap["stand"]), sum(len(p) for p, _g in snap["stand"].values()), len(snap["inst"]),
            ", ".join(snap["scatter"]) or "no scatter"))
    for a in LAWNS:
        if st[a] != "old":
            continue
        ob = obj(LAWNS[a])
        n0 = len(ob.data.vertices)
        dived, seated = lawn_spec(a)["run"](ob)
        log("lawn: %s: past r %.1f %d vertices dived, %d seated; %d -> %d vertices, %d faces" % (
            ob.name, lawn_spec(a)["edge"][0], dived, seated, n0, len(ob.data.vertices), len(ob.data.polygons)))
    for p in PATHS:
        if st[p] != "old":
            continue
        me = obj(p).data
        co = coords(me)
        bot = np.abs(co[:, 2] - MR.PATH_BOTTOM_R55) < 1e-4
        co[bot, 2] = MR.PATH_BOTTOM
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.update()
        log("lawn: %s: %d bottom vertices %.2f -> %.2f" % (p, int(bot.sum()), MR.PATH_BOTTOM_R55, MR.PATH_BOTTOM))


def lawn_check(ctx, fail):
    bpy.context.view_layer.update()
    for a, before in ctx.info.get("lawn_before", {}).items():
        nm = LAWNS[a]
        r0 = lawn_spec(a)["edge"][0]
        after = lawn_snapshot(a)
        co0, co1 = before["co"], after["co"]
        r = np.hypot(co0[:, 0], co0[:, 1])
        inside = r <= r0
        if len(co1) < len(co0) or np.abs(co1[:len(co0)][inside] - co0[inside]).max(initial=0.0) > 1e-6:
            fail.add("lawn: %s: vertices inside r %.1f moved" % (nm, r0))
        new = co1[len(co0):]
        log("lawn: %s: %d new vertices (the seat's cut), %d of them inside r %.1f (on the cut faces' planes)" % (
            nm, len(new), int((np.hypot(new[:, 0], new[:, 1]) <= r0).sum()) if len(new) else 0, r0))
        # standing things
        dg = bpy.context.evaluated_depsgraph_get()
        tree = bvh(world_tris(dg, owners={nm}, skip_volumes=False)[nm])
        rows, n_in, worst = [], 0, 0.0
        for own, (P, G0) in sorted(before["stand"].items()):
            G1 = np.array([np.nan if g is None else g for g in (ground_at(tree, p) for p in P)])
            dz = G1 - G0
            rr = radius(before, P)
            lost = (G0 - P[:, 2] >= -SINK_FLOAT) & ~(G1 - P[:, 2] >= -SINK_FLOAT)
            ins = rr < r0
            n_in += int(ins.sum())
            if lost.any():
                fail.add("lawn: %s loses its ground on %s at %d foot points (r %.2f..%.2f, ground down %.3f m)" % (
                    own, nm, int(lost.sum()), rr[lost].min(), rr[lost].max(), float(np.nanmax(-dz[lost]))))
            big = ins & (np.abs(np.nan_to_num(dz, nan=1.0)) > SEAT_MAX)
            if big.any():
                fail.add("lawn: the ground under %s (inside r %.1f) moved %.3f m (> %.3f)" % (
                    own, r0, float(np.nanmax(np.abs(dz[big]))), SEAT_MAX))
            m = float(np.nanmax(np.abs(dz))) if len(dz) else 0.0
            worst = max(worst, float(np.nanmax(np.abs(dz[ins]))) if ins.any() else 0.0)
            if m > SEAT_LOG:
                rows.append("%s %.3f m (r %.1f..%.1f)" % (own, m, rr.min(), rr.max()))
        log("lawn: %s: %d standing objects, %d foot points inside r %.1f, the ground under them moved %.4f m at most" % (
            nm, len(before["stand"]), n_in, r0, worst))
        log("lawn: %s: ground changes over %.0f mm: %s" % (nm, SEAT_LOG * 1000, "; ".join(rows) or "none"))
        # scatter instances. The scatter draws its points per face, so a face the dive or the cut re-made draws
        # new ones: only inside r_still, the smallest radius any re-made face reaches in to, must every instance keep
        # its place. Instances lost or new between r_still and the lawn's edge are listed: bake_trees.py's plan says
        # whether any of them is one the web draws (grass is dropped past 40 m from the camera)
        me1 = obj(nm).data
        lt, lv = mesh_faces(me1)
        ls = np.empty(len(me1.polygons), np.int32)
        me1.polygons.foreach_get("loop_start", ls)
        ch = np.ones(len(co1), bool)
        ch[:len(co0)] = np.abs(co1[:len(co0)] - co0).max(axis=1) > 1e-6
        r1 = np.hypot(co1[:, 0], co1[:, 1])
        f_ch = np.maximum.reduceat(ch[lv].astype(np.int8), ls) > 0
        f_rmin = np.minimum.reduceat(r1[lv], ls)
        r_still = min(r0, float(f_rmin[f_ch].min())) if f_ch.any() else r0
        bi, ai = before["inst"], after["inst"]
        moved, gone, rim_gone = 0, [], []
        for nm_p, x, y, z in bi:
            rr = float(radius(before, np.array([[x, y, z]]))[0])
            hit = [q for q in ai if q[0] == nm_p and abs(q[1] - x) < 1e-3 and abs(q[2] - y) < 1e-3]
            if not hit:
                (gone if rr < r_still else rim_gone).append("%s at r %.2f (%.2f, %.2f, %.2f)" % (nm_p, rr, x, y, z))
            elif rr < r_still:
                if abs(hit[0][3] - z) > SEAT_MAX:
                    fail.add("lawn: a %s instance at r %.2f moved %.3f m in height" % (nm_p, rr, hit[0][3] - z))
                elif abs(hit[0][3] - z) > 1e-4:
                    moved += 1
        rim_new = []
        for nm_p, x, y, z in ai:
            if not [q for q in bi if q[0] == nm_p and abs(q[1] - x) < 1e-3 and abs(q[2] - y) < 1e-3]:
                rr = float(radius(before, np.array([[x, y, z]]))[0])
                rim_new.append("%s at r %.2f (%.2f, %.2f, %.2f)" % (nm_p, rr, x, y, z))
                if rr < r_still:
                    fail.add("lawn: a new %s instance at r %.2f, inside the untouched r %.2f" % (nm_p, rr, r_still))
        if gone:
            fail.add("lawn: %s's scatter lost or moved %d instances inside r %.2f: %s" % (nm, len(gone), r_still,
                                                                                         gone[:6]))
        log("lawn: %s: scatter instances %d -> %d; the faces re-made reach in to r %.2f; inside it %d followed the lawn "
            "by under %.0f mm" % (nm, len(bi), len(ai), r_still, moved, SEAT_MAX * 1000))
        if rim_gone or rim_new:
            log("lawn: %s: PLANTS on the re-made rim faces: %d gone (%s), %d new (%s): compare bake_trees.py's plan "
                "before and after" % (nm, len(rim_gone), "; ".join(rim_gone), len(rim_new), "; ".join(rim_new)))
    # paths: their bottom edge on or under the lawn (no side hovering over the lowered band)
    dg = bpy.context.evaluated_depsgraph_get()
    tree = bvh(world_tris(dg, owners={LAWNS["mirror"]}, skip_volumes=False)[LAWNS["mirror"]])
    for p in PATHS:
        ob = obj(p)
        Mw = np.array(ob.matrix_world)
        co = coords(ob.data)
        bot = co[co[:, 2] < MR.PATH_Z - 1e-4] @ Mw[:3, :3].T + Mw[:3, 3]
        gaps = []
        for q in bot:
            g = ground_at(tree, q, up=1.0)
            if g is not None and g < q[2] - 1e-3:
                gaps.append(q[2] - g)
        log("lawn: %s: %d bottom corners, %d over the lawn" % (p, len(bot), len(gaps)))
        if gaps:
            fail.add("lawn: %s's bottom hovers up to %.3f m over the lawn" % (p, max(gaps)))


def lawn_digest(h):
    for nm in tuple(LAWNS.values()) + PATHS:
        ob = obj(nm)
        h.update(nm.encode())
        if ob is None:
            h.update(b"absent")
            continue
        h.update(faces_sig(ob.data).encode())
        h.update(str(ob.data.get(MR.LAWN_EDGE_TAG)).encode())


# ------------------------------------------------------------------------------------------------------------ walls

def wall_objects():
    out = []
    for ob in bpy.data.objects:
        mt = WALL_RE.match(ob.name)
        if mt:
            out.append((ob, W.WALL_KINDS[mt.group(1)]))
    return sorted(out, key=lambda t: t[0].name)


def wall_state_one(ob, kind, mode, fail):
    if ob.type != 'MESH' or ob.data.users != 1:
        fail.add("walls: %s is not a mesh of its own" % ob.name)
        return "unknown", None
    if not np.allclose(np.array(ob.matrix_world.to_scale()), 1.0, atol=1e-6):
        fail.add("walls: %s is scaled" % ob.name)
        return "unknown", None
    sl = slots(ob)
    want_tail = ["world_pier_stone"] if kind == "ribbon" else []
    if sl[1:] != want_tail:
        fail.add("walls: %s's slots %s (want slot 1 %s)" % (ob.name, sl, want_tail or "none"))
        return "unknown", None
    me = ob.data
    coordsw = None
    if mode == "B":
        try:
            gen, dims, parts = W.wall_coords(coords(me), [tuple(p.vertices) for p in me.polygons], kind)
            coordsw = (gen, dims, parts)
        except ValueError as exc:
            fail.add("walls: %s does not have the %s layout (%s): WALLS_MODE=A needs no attributes" % (
                ob.name, kind, exc))
            return "unknown", None
    g0, d0 = point_vec(me, "arch_gen"), point_vec(me, "arch_dims")
    if sl[0] == W.WALL_MATERIAL_R55 and g0 is None and d0 is None:
        return "old", coordsw
    mat = ob.material_slots[0].material
    if sl[0] == W.WALL_MATERIAL and mat is not None and mat.get("wall_mode") == mode:
        if mode == "A" and g0 is None and d0 is None:
            return "r56", coordsw
        if mode == "B" and g0 is not None and d0 is not None and \
                np.abs(g0 - coordsw[0]).max() <= ATTR_TOL and np.abs(d0 - coordsw[1]).max() <= ATTR_TOL:
            return "r56", coordsw
    fail.add("walls: %s: slot 0 %s (mode %s), arch_gen %s, arch_dims %s: not a state this patch knows (mode %s)" % (
        ob.name, sl[0], mat.get("wall_mode") if mat is not None else None, g0 is not None, d0 is not None, mode))
    return "unknown", coordsw


def wall_state(ctx, fail):
    obs = wall_objects()
    if not obs:
        fail.add("walls: no world.link.*.rails / .foot_rail / .rest_rail objects")
        return "unknown"
    per = {}
    for ob, kind in obs:
        s, cw = wall_state_one(ob, kind, ctx.mode, fail)
        per[ob.name] = (s, kind, cw)
        if cw is not None:
            ps = cw[2]
            log("walls: %s (%s): %s; %d runs %.1f..%.1f m, heights %.2f..%.2f m" % (
                ob.name, kind, s, len(ps), min(p[3] for p in ps), max(p[3] for p in ps),
                float(cw[1][:, 2].min()), float(cw[1][:, 2].max())))
        else:
            log("walls: %s (%s): %s" % (ob.name, kind, s))
    ctx.info["walls"] = per
    vals = {s for s, _k, _c in per.values()}
    log("walls: %d objects: %s" % (len(per), ", ".join("%d %s" % (sum(1 for s, _k, _c in per.values() if s == v), v)
                                                      for v in sorted(vals))))
    if "unknown" in vals:
        return "unknown"
    if vals == {"r56"}:
        return "r56"
    if vals == {"old"}:
        return "old"
    fail.add("walls: some walls are patched and some are not")
    return "unknown"


def wall_apply(ctx, fail):
    if W.WALL_MODE != ctx.mode:
        W.set_wall_mode(ctx.mode)
    mat = M.get(W.WALL_MATERIAL)
    if mat.get("wall_mode") != ctx.mode:
        M.rebuild(W.WALL_MATERIAL)
    log("walls: material %s, mode %s" % (mat.name, mat.get("wall_mode")))
    for name, (s, kind, cw) in sorted(ctx.info["walls"].items()):
        if s != "old":
            continue
        ob = obj(name)
        ob.data.materials[0] = mat
        if ob.material_slots[0].link == 'OBJECT':
            ob.material_slots[0].material = mat
        if ctx.mode == "B":
            W.wall_attrs(ob, kind)
    log("walls: %d walls now in %s" % (sum(1 for s, _k, _c in ctx.info["walls"].values() if s == "old"),
                                         W.WALL_MATERIAL))


def wall_digest(h):
    for ob, _kind in wall_objects():
        h.update(ob.name.encode())
        h.update(repr(slots(ob)).encode())
        mat = ob.material_slots[0].material if ob.material_slots else None
        h.update(str(mat.get("wall_mode") if mat is not None else None).encode())
        for nm in ("arch_gen", "arch_dims"):
            v = point_vec(ob.data, nm)
            h.update((array_sig(np.round(v * 1e4).astype(np.int64)) if v is not None else "none").encode())


# ------------------------------------------------------------------------------------------------------------ sword

def sword_expect(era):
    geos = AR.heavy_sword_geo(era)
    mats = AR.heavy_sword_materials(era)
    return {p: (len(g.faces), np.round(np.sort(np.array(g.edge, float)), 4), list(mats[p])) for p, g in geos.items()}


def sword_have(part):
    ob = obj(AR.K + "." + part)
    if ob is None or ob.type != 'MESH':
        return None
    me = ob.data
    e = face_float(me, "edge")
    return (len(me.polygons), np.round(np.sort(e.astype(float)), 4) if e is not None else None, slots(ob),
            me.get("sect_heavy_sword"))


def sword_state(ctx, fail):
    exp = {era: sword_expect(era) for era in ("r55", "r56")}
    rows, eras = [], set()
    for part in AR.HS_PARTS:
        have = sword_have(part)
        if have is None or have[3] != part:
            fail.add("sword: arena.%s missing or not the Heavy Iron Sword's (patch_heavy_iron_sword first)" % part)
            return "unknown"
        found = [era for era, ex in exp.items() if have[0] == ex[part][0] and have[1] is not None and
                 len(have[1]) == len(ex[part][1]) and np.array_equal(have[1], ex[part][1]) and have[2] == ex[part][2]]
        # the glow, grip and tassel are the same in both eras
        tag_ = "both" if len(found) == 2 else (found[0] if found else "?")
        rows.append("%s %s" % (part, tag_))
        if not found:
            fail.add("sword: arena.%s is neither round 55's nor round 56's (faces %d, slots %s)" % (part, have[0],
                                                                                                   have[2]))
            return "unknown"
        if len(found) == 1:
            eras.add(found[0])
    log("sword: %s" % "; ".join(rows))
    if eras == {"r55"}:
        return "old"
    if eras == {"r56"}:
        return "r56"
    fail.add("sword: parts from both rounds")
    return "unknown"


def sword_apply(ctx, fail):
    from sect import patch_heavy_iron_sword as PH
    try:
        info = PH.rebuild(log=lambda *a: log("sword:", *a))
    except RuntimeError as exc:
        fail.add("sword: the in-place rebuild refused: %s" % exc)
        return
    ctx.info["sword"] = info
    if info["stale"]:
        log("sword: WARN world boxes grew: %s" % (info["stale"],))


def sword_digest(h):
    for part in AR.HS_PARTS:
        ob = obj(AR.K + "." + part)
        h.update(part.encode())
        if ob is None:
            h.update(b"absent")
            continue
        h.update((np.round(np.array(ob.matrix_world), 5) + 0.0).tobytes())
        h.update(faces_sig(ob.data).encode())
        e = face_float(ob.data, "edge")
        h.update(array_sig(np.round(np.sort(e) * 1e4).astype(np.int64)).encode() if e is not None else b"none")


# ------------------------------------------------------------------------------------------------------------ bridge

def bridge_ports(ctx):
    rng_ = ctx.committed_range()
    pa, pb = W.port(rng_, BRIDGE_LINK[0], "depart"), W.port(rng_, BRIDGE_LINK[1], "arrival")
    if pa is None or pb is None:
        raise RuntimeError("no forge depart / arena arrival")
    return rng_, pa["p"], pb["p"]


def bridge_build(ctx, sc_, sag):
    """{suffix: scratch object}, report, geometry of the chain bridge with ``sag``."""
    rng_, p0, p1 = bridge_ports(ctx)
    keep = set(o.name for o in bpy.data.objects)
    name = "%s.b%.3f" % (SCRATCH, sag)
    objs, rep, geo = W._chain_bridge(rng_, sc_.coll, p0, p1, name, sag=sag)
    made = {o.name[len(name) + 1:]: o for o in objs if o.name not in keep}
    return made, rep, geo


def mesh_close(a, b, tol=BRIDGE_TOL):
    """Two meshes with the same faces (vertex for vertex) and every vertex within ``tol`` m, same materials (a build's
    vertex order is fixed, so the file's and a scratch build line up; rounding-free, unlike faces_sig)."""
    if len(a.vertices) != len(b.vertices) or len(a.polygons) != len(b.polygons):
        return False
    la, lb = mesh_faces(a), mesh_faces(b)
    if not (np.array_equal(la[0], lb[0]) and np.array_equal(la[1], lb[1])):
        return False
    if [tag(m) for m in a.materials] != [tag(m) for m in b.materials]:
        return False
    return float(np.abs(coords(a) - coords(b)).max(initial=0.0)) <= tol


def bridge_state(ctx, fail):
    for sfx in BRIDGE_PARTS:
        ob = obj(BRIDGE + "." + sfx)
        if ob is None or ob.type != 'MESH' or ob.data.users != 1:
            fail.add("bridge: %s.%s missing or its mesh shared" % (BRIDGE, sfx))
            return "unknown"
        if not identity(ob):
            fail.add("bridge: %s.%s has a transform; the bridge is built in world space" % (BRIDGE, sfx))
            return "unknown"
    old_sag = W.LINK_SAG_R55.get(BRIDGE_LINK, W.CHAIN_SAG)
    new_sag = W.LINK_SAG.get(BRIDGE_LINK, W.CHAIN_SAG)
    sc_ = Scratch()
    try:
        old, rep_o, geo_o = bridge_build(ctx, sc_, old_sag)
        new, rep_n, geo_n = bridge_build(ctx, sc_, new_sag)
        is_old = {s: mesh_close(obj(BRIDGE + "." + s).data, old[s].data) for s in BRIDGE_PARTS}
        is_new = {s: mesh_close(obj(BRIDGE + "." + s).data, new[s].data) for s in BRIDGE_PARTS}
        differ = not all(mesh_close(old[s].data, new[s].data) for s in BRIDGE_PARTS)
        ctx.info["bridge_old"] = dict(rep=rep_o, geo=geo_o, co={s: coords(old[s].data) for s in BRIDGE_PARTS})
        ctx.info["bridge_new"] = dict(rep=rep_n, geo=geo_n)
    finally:
        sc_.drop()
    rows = ["%s %s" % (s, "old" if is_old[s] else "new" if is_new[s] else "?") for s in BRIDGE_PARTS]
    log("bridge: sag %.2f -> %.2f; %s" % (old_sag, new_sag, "; ".join(rows)))
    for nm_, rep in (("sag %.2f" % old_sag, rep_o), ("sag %.2f" % new_sag, rep_n)):
        log("bridge: %s: %.1f m, rise %.2f m, %d planks, %d steps, max riser %.3f, min tread %s, max slope %.1f deg, "
            "min clear %.1f m" % (nm_, rep["length"], rep["rise"], rep["planks"], rep["steps"], rep["max_riser"],
                                  rep["min_tread"], rep["max_slope_deg"], rep["min_clear"]))
    if all(is_old.values()) and differ:
        return "old"
    if all(is_new.values()):
        return "r56"
    fail.add("bridge: the bridge's meshes are neither a sag-%.2f build nor a sag-%.2f build (%s): did a port move?" % (
        old_sag, new_sag, "; ".join(rows)))
    return "unknown"


def bridge_contacts(dg, names, box):
    """Owners whose triangles cross the bridge parts ``names`` (BVH overlap) inside ``box``."""
    T = world_tris(dg, owners=set(names))
    if not T:
        return set()
    tb = bvh(np.concatenate(list(T.values())))
    out = set()
    for own, To in world_tris(dg, near=box, exclude=set(names) | {RANGE}).items():
        if tb.overlap(bvh(To)):
            out.add(own)
    return out


def bridge_box(extra=6.0):
    pts = np.concatenate([coords(obj(BRIDGE + "." + s).data) for s in BRIDGE_PARTS])
    return pts.min(0) - extra, pts.max(0) + extra


def bridge_apply(ctx, fail):
    names = [BRIDGE + "." + s for s in BRIDGE_PARTS]
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = bridge_box()
    lo[2] -= 6.0
    ctx.info["bridge_box"] = (lo, hi)
    ctx.info["bridge_contacts0"] = bridge_contacts(dg, set(names), (lo, hi))
    ctx.info["bridge_boxes0"] = {n: (coords(obj(n).data).min(0), coords(obj(n).data).max(0)) for n in names}
    log("bridge: touches before: %s" % (", ".join(sorted(ctx.info["bridge_contacts0"])) or "nothing"))
    sc_ = Scratch()
    keep_meshes = []
    try:
        new, rep, geo = bridge_build(ctx, sc_, W.LINK_SAG.get(BRIDGE_LINK, W.CHAIN_SAG))
        for sfx in BRIDGE_PARTS:
            ob = obj(BRIDGE + "." + sfx)
            old_me = ob.data
            new_me = new[sfx].data
            ob.data = new_me
            for s in ob.material_slots:
                if s.link != 'DATA':
                    s.link = 'DATA'
            if old_me.users == 0:
                bpy.data.meshes.remove(old_me)
            else:
                log("bridge: WARN %s's old mesh %s still has %d users: kept" % (ob.name, old_me.name, old_me.users))
            new_me.name = ob.name
            keep_meshes.append(new_me.name)
    finally:
        sc_.drop(keep_meshes=keep_meshes)
    ctx.info["bridge_rep"] = (rep, geo)
    log("bridge: swapped %s" % ", ".join(BRIDGE + "." + s for s in BRIDGE_PARTS))


def bridge_check(ctx, fail):
    if "bridge_rep" not in ctx.info:
        return
    rep, geo = ctx.info["bridge_rep"]
    old = ctx.info["bridge_old"]
    names = [BRIDGE + "." + s for s in BRIDGE_PARTS]
    _rng, p0, p1 = bridge_ports(ctx)
    d = p1[:2] - p0[:2]
    D = float(np.hypot(*d))
    u = d / D
    lvl = W.CHAIN_LEVEL
    deck = coords(obj(BRIDGE + ".deck").data)
    deck0 = old["co"]["deck"]
    if len(deck) != len(deck0) or len(deck) % 8:
        fail.add("bridge: %d deck vertices, the old deck %d (planks %d / %d)" % (len(deck), len(deck0),
                                                                              len(deck) // 8, len(deck0) // 8))
    else:
        q = ((deck.reshape(-1, 8, 3)[:, :, :2].mean(1) - p0[:2]) @ u)
        ends = (q <= lvl) | (q >= D - lvl)
        same = np.abs(deck.reshape(-1, 8, 3) - deck0.reshape(-1, 8, 3)).max(axis=(1, 2)) < 1e-5
        log("bridge: %d planks (as before); %d in the level ends, all unchanged: %s" % (
            len(q), int(ends.sum()), bool(same[ends].all())))
        if not same[ends].all():
            fail.add("bridge: %d planks in the level ends moved" % int((ends & ~same).sum()))
    if rep["max_riser"] > W.RISER + 1e-6:
        fail.add("bridge: a riser of %.3f m (> %.2f)" % (rep["max_riser"], W.RISER))
    if rep["min_tread"] is not None and rep["min_tread"] < W.TREAD_MIN - 1e-6:
        fail.add("bridge: a tread of %.2f m (< %.2f)" % (rep["min_tread"], W.TREAD_MIN))
    if rep["max_slope"] > W.RISER / W.TREAD_MIN + 1e-6:
        fail.add("bridge: slope %.3f (> %.3f)" % (rep["max_slope"], W.RISER / W.TREAD_MIN))
    z = np.asarray(geo["z"], float)
    if (np.diff(z) < -1e-6).any():
        fail.add("bridge: the deck dips (%d planks lower than the one before)" % int((np.diff(z) < -1e-6).sum()))
    # clearance over world.range along the free span
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = ctx.info["bridge_box"]
    RT = world_tris(dg, owners={RANGE}, near=(lo - np.array([0, 0, 200.0]), hi), skip_volumes=False).get(RANGE)
    allv = np.concatenate([coords(obj(n).data) for n in names])
    qa = (allv[:, :2] - p0[:2]) @ u
    nl = np.array([-u[1], u[0]])
    worst_mid, worst_all, where = 1e9, 1e9, None
    if RT is None:
        log("bridge: no world.range under the span")
    else:
        tr = bvh(RT)
        for q in np.asarray(geo["s"], float):
            if q < lvl or q > D - lvl:
                continue
            w = (q - lvl) / max(D - 2 * lvl, 1e-6)
            sel = np.abs(qa - q) < 0.6
            if not sel.any():
                continue
            zb = float(allv[sel, 2].min())
            for lat in BRIDGE_LATERAL:
                x, y = p0[:2] + u * q + nl * lat
                g = ground_at(tr, (x, y, zb), up=-0.01, reach=2000.0)
                if g is None:
                    continue
                c = zb - g
                worst_all = min(worst_all, c)
                if BRIDGE_MID[0] <= w <= BRIDGE_MID[1] and c < worst_mid:
                    worst_mid, where = c, (round(q, 1), round(w, 2), lat)
        log("bridge: over world.range: %.2f m at least along the middle (at q %s m, w, lateral), %.2f m anywhere on the "
            "free span" % (worst_mid, where, worst_all))
        if worst_mid < BRIDGE_CLEAR:
            fail.add("bridge: only %.2f m over world.range in the middle of the span (want %.1f)" % (worst_mid,
                                                                                               BRIDGE_CLEAR))
        if worst_all < 0.0:
            fail.add("bridge: the deck goes into world.range (%.2f m)" % worst_all)
    contacts = bridge_contacts(dg, set(names), (lo, hi))
    extra = contacts - ctx.info.get("bridge_contacts0", set())
    log("bridge: touches after: %s" % (", ".join(sorted(contacts)) or "nothing"))
    if extra:
        fail.add("bridge: the lowered bridge now touches %s" % sorted(extra))
    for sfx in BRIDGE_FLAT:
        me = obj(BRIDGE + "." + sfx).data
        sm = np.empty(len(me.polygons), bool)
        me.polygons.foreach_get("use_smooth", sm)
        if sm.any():
            fail.add("bridge: %s.%s has %d smooth faces" % (BRIDGE, sfx, int(sm.sum())))
    for n in names:
        b0 = ctx.info["bridge_boxes0"][n]
        c = coords(obj(n).data)
        log("bridge: %s box z %.2f..%.2f (was %.2f..%.2f)" % (n, c[:, 2].min(), c[:, 2].max(), b0[0][2], b0[1][2]))


def bridge_digest(h):
    for sfx in BRIDGE_PARTS:
        ob = obj(BRIDGE + "." + sfx)
        h.update(sfx.encode())
        h.update(faces_sig(ob.data).encode() if ob is not None else b"absent")


# ------------------------------------------------------------------------------------------------------- the round

STATE = dict(rim=rim_state, lawn=lawn_state, walls=wall_state, sword=sword_state, bridge=bridge_state)
APPLY = dict(rim=rim_apply, lawn=lawn_apply, walls=wall_apply, sword=sword_apply, bridge=bridge_apply)
CHECK = dict(rim=rim_check, lawn=lawn_check, walls=lambda c, f: None, sword=lambda c, f: None, bridge=bridge_check)
DIGEST = (rim_digest, lawn_digest, wall_digest, sword_digest, bridge_digest)


def touched(parts):
    names = set()
    if "rim" in parts:
        names.add(RANGE)
    if "lawn" in parts:
        names |= set(LAWNS.values()) | set(PATHS)
    if "walls" in parts:
        names |= {ob.name for ob, _k in wall_objects()}
    if "sword" in parts:
        names |= {AR.K + "." + p for p in AR.HS_PARTS}
        pl = obj(AR.K + ".plaque_sword")
        if pl is not None:
            names |= {pl.name} | {o.name for o in pl.children_recursive}
    if "bridge" in parts:
        names |= {BRIDGE + "." + s for s in BRIDGE_PARTS}
    return names


def still_snapshot(skip):
    """{object: (world matrix, mesh signature, slot materials)} of every object not in ``skip`` (meshes hashed once)."""
    cache = {}
    out = {}
    for ob in bpy.data.objects:
        if ob.name in skip:
            continue
        sig = None
        if ob.type == 'MESH' and ob.data is not None:
            k = ob.data.as_pointer()
            if k not in cache:
                me = ob.data
                lt, lv = mesh_faces(me)
                cache[k] = array_sig(coords(me, np.float32), lt, lv, face_mats(me)) + \
                    "|" + ",".join(tag(m) or "" for m in me.materials)
            sig = cache[k]
        out[ob.name] = (np.array(ob.matrix_world), sig, tuple(slots(ob)))
    return out


def digest():
    h = hashlib.md5()
    for f in DIGEST:
        f(h)
    return h.hexdigest()


def main():
    dry, parts, mode = options()
    t0 = time.time()
    fail = Fail()
    if obj("world.root") is None or obj(RANGE) is None:
        log("NOT SAVED: no world.root / world.range: is this out/sect_chase.blend?")
        raise SystemExit(1)
    log("round 56: parts %s; walls mode %s; rim rule %s (was %s); lawn edges mirror %s, abode %s; side facets %.2f, "
        "edge colour %s; bridge sag %.2f (was %.2f)" % (
            ",".join(parts), mode, W.RIM_RULE, W.RIM_RULE_R55, tuple(MR.LAWN_EDGE), tuple(AB.LAWN_EDGE),
            AR.HS_SIDE_EDGE, AR.HS_EDGE_COL, W.LINK_SAG.get(BRIDGE_LINK, W.CHAIN_SAG),
            W.LINK_SAG_R55.get(BRIDGE_LINK, W.CHAIN_SAG)))
    bpy.context.view_layer.update()
    n_obj0 = len(bpy.data.objects)
    names0 = set(o.name for o in bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    ctx = Ctx(mode)
    states = {}
    for p in parts:
        t1 = time.time()
        states[p] = STATE[p](ctx, fail)
        log("state %s: %s (%.1f s)" % (p, states[p], time.time() - t1))
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    todo = [p for p in parts if states[p] == "old"]
    skip = touched(parts)
    t1 = time.time()
    still0 = still_snapshot(skip)
    log("still: %d other objects recorded (%.1f s)" % (len(still0), time.time() - t1))
    plaque = set(o.name for o in bpy.data.objects if o.name.startswith(AR.K + ".plaque_sword"))
    for p in todo:
        t1 = time.time()
        APPLY[p](ctx, fail)
        log("applied %s (%.1f s)" % (p, time.time() - t1))
        if fail:
            break
    bpy.context.view_layer.update()
    if not fail:
        for p in todo:
            CHECK[p](ctx, fail)
        after = {}
        for p in parts:
            after[p] = STATE[p](ctx, Fail())
        log("after: states %s" % ", ".join("%s %s" % kv for kv in after.items()))
        if any(s != "r56" for s in after.values()):
            fail.add("after the patch the file is not this build: %s" % after)
    still1 = still_snapshot(skip)
    moved = [n for n, (m, _s, _sl) in still0.items() if n in still1 and not np.allclose(still1[n][0], m, atol=STILL_TOL)]
    remeshed = [n for n, (_m, s, sl) in still0.items() if n in still1 and (still1[n][1] != s or still1[n][2] != sl)]
    vanished = [n for n in still0 if n not in still1]
    log("still: %d other objects, %d moved, %d with another mesh or material, %d gone%s" % (
        len(still0), len(moved), len(remeshed), len(vanished),
        (" (e.g. %s)" % (moved + remeshed + vanished)[:6]) if moved or remeshed or vanished else ""))
    if moved or remeshed or vanished:
        fail.add("other objects changed: moved %s, remeshed %s, gone %s" % (moved[:6], remeshed[:6], vanished[:6]))
    names1 = set(o.name for o in bpy.data.objects)
    gone_ok = plaque if "sword" in todo else set()
    if names1 - names0 or (names0 - names1) - gone_ok:
        fail.add("objects appeared %s or vanished %s" % (sorted(names1 - names0)[:6], sorted((names0 - names1) -
                                                                                            gone_ok)[:6]))
    log("objects %d -> %d" % (n_obj0, len(bpy.data.objects)))
    left = [o.name for o in bpy.data.objects if o.name.startswith(SCRATCH)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(SCRATCH)] + \
        [c.name for c in bpy.data.collections if c.name.startswith(SCRATCH)]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    if sorted(s.name for s in bpy.data.scenes) != scenes0:
        fail.add("scenes changed")
    log("DIGEST", digest())
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not todo:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    chunks = [c for c in AREA_CHUNKS + ("backdrop",) if any(c in CHUNKS[p] for p in todo)]
    log("CACHES needs %sbakefull %s" % ("chunks,meta; " if any(p in NEEDS_CHUNKS for p in todo) else "",
                                         ",".join(chunks)))
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
