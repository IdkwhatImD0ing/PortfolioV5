"""Round 29, lane 'detail': the Artifact Forge Peak's two chimney towers and three furnaces rebuilt in detail, with
flame anchors, in an existing out/sect_chase.blend, so it matches what a fresh build makes once areas/forge.py calls
sect/lib/forge_detail.py (r29/pending_forge.diff). Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r29_forge.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-23): "The two pillars behind the artifact forge peak look a bit low detail i think, same with the
furnaces, and i wish they had animated flames inside of them". The pillars are forge.py's two furnace chimneys
(_chimney: an eight-sided stack of 128 triangles, two hoops, red posts round a glowing box, a small roof); the furnaces
are _furnaces' three boxes with a glowing square on each. forge_detail.py's docstring describes the new build.

What it does: deletes the round-12 pieces (forge.chimney.{0,1}, forge.chimney_hoop.*, forge.chimney_posts.*,
forge.chimney_fire.*, the forge.chimney_roof.* hierarchies, forge.furnace.{0,1,2}, forge.furnace_top.*,
forge.furnace_mouth.*) and builds forge_detail's towers, furnaces, bellows, racks, coal heap and the six flame
anchors (forge.fire.furnace.{0,1,2}, forge.fire.chimney.{0,1}, forge.fire.ding) under forge.root in the forge
collection. Kept as they are: forge.chimney_smoke.*, forge.flue.*, forge.furnace_light, the hall and the ding.

State: 'old' (the round-12 pieces, untagged) or 'r29' (objects tagged forge_detail.TAG). An r29 file is compared with
a scratch build of the current forge_detail (every face, order-free): equal -> 'PATCH nothing changed: not saving' and
the same DIGEST; different -> 'stale', rebuilt. Anything else (a mix, a missing piece) stops the patch.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- pieces: every new mesh closed where it should be (forge_detail.Geo.open_edges of the solids is 0), within
  forge_detail.TRI_BUDGET per tower / furnace / the rest, tagged, parented to forge.root, in the forge collection;
- silhouette: each tower's forge-local footprint and top within SIL_TOL of the round-12 tower's, and its box at the
  forge hold (chase.cam frame 352, 1600 x 900) within SIL_PX of the old one's;
- clearance: no new piece crosses or comes within CLEAR_MIN of anything but what it is meant to meet (ALLOW: the
  paving under the towers, the flues, the smoke plumes, the hall floor and back wall behind the furnaces, each other);
- camera: chase.cam (every frame) never comes nearer the new pieces than CAM_MIN;
- hotspots: the 'forge' and 'forge-hall' click boxes (export_web._subtree_box) unchanged;
- flames: six anchors, each on its bed, its flame volume inside its firebox / fire storey, a clear line from the
  flame out through its mouth; how much of each flame the hold camera sees is logged; each furnace's fire-box plane
  (fire_opening: where the page draws its fire box) on the firebox floor, its quad's top corners behind the arch, a
  clear line out, the traced box as deep as the firebox;
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm, the new pieces against themselves and
  everything near them; at most NEW_MAX m2 per piece;
- names and counts: no scratch data left, no scene added, the light kept.
Prints 'PATCH CACHES needs audit' (new pieces: vis_cache, the chunk plan and the forge bake are stale) and
'PATCH DIGEST <md5>' of the tagged objects.
"""
import hashlib
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect.lib import forge_detail as FD  # noqa: E402
from sect.lib import util as U  # noqa: E402

ROOT_EMPTY = "forge.root"
OLD_NAMES = (["forge.chimney.%d" % i for i in (0, 1)] + ["forge.chimney_hoop.%d.%d" % (i, k) for i in (0, 1)
                                                          for k in (0, 1)] +
             ["forge.chimney_posts.%d" % i for i in (0, 1)] + ["forge.chimney_fire.%d" % i for i in (0, 1)] +
             ["forge.chimney_roof.%d" % i for i in (0, 1)] + ["forge.furnace.%d" % k for k in (0, 1, 2)] +
             ["forge.furnace_top.%d" % k for k in (0, 1, 2)] + ["forge.furnace_mouth.%d" % k for k in (0, 1, 2)])
OLD_ONLY = ("forge.chimney_hoop.0.0", "forge.chimney_posts.0")      # names only the round-12 build has
OLD_TRIS = {"forge.chimney.0": 128, "forge.furnace.0": 12, "forge.furnace_mouth.0": 12}
KEEP = ("forge.chimney_smoke.0", "forge.chimney_smoke.1", "forge.flue.0", "forge.flue.1", "forge.furnace_light")
SCRATCH = "~r29"
HOLD = 352
RES = (1600, 900)
SIL_TOL = (0.35, 1.0)      # m: footprint half-width may grow by at most this; the top may move by at most this
SIL_PX = 30.0              # px: the tower's box edges at the hold
CLEAR_MIN = 0.02           # m
CAM_MIN = 25.0             # m
NEW_MAX = 0.05             # m2 of same-facing parallel faces per new piece (both bands)
SCAN_TOL, SCAN_TOL12, SCAN_PAR, SCAN_STEP = 0.0055, 0.0125, 0.985, 0.06
# what each family may meet (name or prefix); new pieces may always meet each other
ALLOW = dict(chimney=("forge.paving", "forge.flue.", "forge.chimney_smoke."),
             furnace=("forge.hall.platform", "forge.hall.walls", "forge.flue."),
             extras=("forge.hall.platform", "forge.hall.walls"))
SKIP = ("world.haze", "world.range", "world.roots", "world.stream")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry, scan = False, True
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "SCAN" and eq:
            scan = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r29_forge: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
    return dry, scan


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------ mesh helpers

def tris(me):
    n = len(me.polygons)
    lt = np.zeros(n, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(lt.sum() - 2 * n)


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


def faces_sig(me):
    """Order-free fingerprint: every face as its rounded corners (cyclic from the smallest) and material name."""
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    q = np.round(co.reshape(nv, 3) * 1e4).astype(np.int64)
    mats = [m.name if m is not None else "" for m in me.materials]
    out = []
    for p in me.polygons:
        pts = [tuple(q[i]) for i in p.vertices]
        k = pts.index(min(pts))
        out.append((tuple(pts[k:] + pts[:k]), mats[p.material_index] if p.material_index < len(mats) else ""))
    out.sort()
    h = hashlib.md5()
    h.update(("%d %d" % (nv, len(me.polygons))).encode())
    for f, m in out:
        h.update(repr(f).encode())
        h.update(m.encode())
    return h.hexdigest()


def world_tris_of(obs):
    out = []
    for ob in obs:
        if ob.type != 'MESH' or not len(ob.data.polygons):
            continue
        L = local_tris(ob.data)
        W = np.array(ob.matrix_world)
        out.append(L @ W[:3, :3].T + W[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                       for i in range(len(T))], all_triangles=True)


def tri_normals(T):
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(cr, axis=1)
    ok = L > 1e-12
    n = np.zeros_like(cr)
    n[ok] = cr[ok] / L[ok, None]
    return n, 0.5 * L


def tree(ob):
    return [ob] + list(ob.children_recursive)


def props_of(ob):
    out = {}
    for k in sorted(ob.keys()):
        if k.startswith("_"):
            continue
        v = ob[k]
        if isinstance(v, str):
            pass
        elif isinstance(v, (int, float)):
            v = round(float(v), 5)
        else:
            try:
                v = [round(float(x), 5) for x in v]
            except (TypeError, ValueError):
                v = repr(v)
        out[k] = v
    return out


def digest(obs, strip):
    """md5 of objects (names with ``strip`` replaced by 'forge'), their transforms, meshes, slots and props."""
    h = hashlib.md5()
    for ob in sorted(obs, key=lambda o: o.name.replace(strip, "forge", 1)):
        h.update(ob.name.replace(strip, "forge", 1).encode())
        h.update(np.round(np.array(ob.matrix_basis), 5).tobytes())
        h.update(repr((ob.parent.name.replace(strip, "forge", 1) if ob.parent else None)).encode())
        if ob.type == 'MESH':
            h.update(faces_sig(ob.data).encode())
            h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
        h.update(repr(props_of(ob)).encode())
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------- the build

def build_all(coll, root, ding):
    """Every forge_detail piece; returns the top-level new objects."""
    obs = []
    for i, x, emb in FD.CHIMNEYS:
        obs += FD.build_chimney(coll, root, i, x, FD.CHIMNEY_Y, emb)
    obs += FD.build_furnaces(coll, root)
    a = FD.build_ding_anchor(coll, root, ding)
    if a is not None:
        obs.append(a)
    return obs


def scratch_build(coll, root, ding):
    """Build under SCRATCH names in a scratch collection: (objects with their trees, collection)."""
    keep = FD.KEY
    sc = bpy.data.collections.new(SCRATCH + ".coll")
    bpy.context.scene.collection.children.link(sc)
    try:
        FD.KEY = SCRATCH
        tops = build_all(sc, root, ding)
    finally:
        FD.KEY = keep
    return [o for t in tops for o in tree(t)], sc


def remove_tree(obs):
    names = [o.name for o in obs]
    for nm in names:
        o = bpy.data.objects.get(nm)
        if o is not None:
            U.delete_hierarchy(o)


def group_of(name):
    """'chimney.<i>', 'furnace.<k>' or 'extras' for a new object's name (forge.* or ~r29.*)."""
    s = name.split(".", 1)[1] if "." in name else name
    head = s.split(".")[0]
    idx = s.split(".")[1] if len(s.split(".")) > 1 else ""
    if head.startswith("chimney"):
        return "chimney." + idx
    if head == "fire":
        return "anchor"
    if head in ("furnace", "furnace_mouth", "furnace_iron", "furnace_top", "furnace_ash"):
        return "furnace." + idx
    return "extras"


# ------------------------------------------------------------------------------------------------------------ checks

def local_box(obs, root):
    Minv = np.array(root.matrix_world.inverted())
    pts = []
    for o in obs:
        if o.type != 'MESH' or not len(o.data.vertices):
            continue
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        W = Minv @ np.array(o.matrix_world)
        pts.append(co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3])
    P = np.concatenate(pts)
    return P.min(0), P.max(0)


def screen_box(obs, sc, cam):
    from bpy_extras.object_utils import world_to_camera_view
    xs, ys = [], []
    for o in obs:
        if o.type != 'MESH':
            continue
        M = o.matrix_world
        vs = o.data.vertices
        step = max(1, len(vs) // 3000)
        for k in range(0, len(vs), step):
            v = world_to_camera_view(sc, cam, M @ vs[k].co)
            if v.z > 0:
                xs.append(v.x * RES[0])
                ys.append((1.0 - v.y) * RES[1])
    return (min(xs), max(xs), min(ys), max(ys)) if xs else None


def old_towers(root):
    out = {}
    for i in (0, 1):
        obs = []
        for nm in ("forge.chimney.%d" % i, "forge.chimney_posts.%d" % i, "forge.chimney_fire.%d" % i,
                   "forge.chimney_hoop.%d.0" % i, "forge.chimney_hoop.%d.1" % i, "forge.chimney_roof.%d" % i):
            o = bpy.data.objects.get(nm)
            if o is not None:
                obs += tree(o)
        if obs:
            out[i] = obs
    return out


def new_towers(new):
    out = {}
    for o in new:
        g = group_of(o.name)
        if g.startswith("chimney."):
            out.setdefault(int(g.split(".")[1]), []).append(o)
    return out


def check_pieces(new, coll, root, fail):
    budget = {}
    for o in new:
        if o.get(FD.TAG) != 1:
            fail.add("%s is not tagged %s" % (o.name, FD.TAG))
        if o.parent is None:
            fail.add("%s has no parent" % o.name)
        if coll.name not in {c.name for c in o.users_collection}:
            fail.add("%s is not in the %s collection" % (o.name, coll.name))
        if o.type == 'MESH':
            g = group_of(o.name)
            budget[g] = budget.get(g, 0) + tris(o.data)
    for g, t in sorted(budget.items()):
        cap = FD.TRI_BUDGET.get(g.split(".")[0], FD.TRI_BUDGET["extras"])
        log("budget %-10s %6d triangles (cap %d)" % (g, t, cap))
        if t > cap:
            fail.add("%s has %d triangles > %d" % (g, t, cap))
    oe = 0
    for _i, x, emb in FD.CHIMNEYS:
        oe += sum(gg.open_edges() for gg in FD.chimney_geos(emb, FD.flue_u(x)).values())
    for fz in FD.FURNACES:
        oe += sum(gg.open_edges() for gg in FD.furnace_geos(fz).values())
    oe += FD.bellows().open_edges() + FD.tool_rack(1).open_edges() + FD.coal_heap().open_edges()
    if oe:
        fail.add("%d open edges on solid pieces" % oe)
    return sum(budget.values())


def check_silhouette(old, new, root, sc, cam, fail):
    for i in sorted(new):
        nlo, nhi = local_box(new[i], root)
        if i not in old:
            fail.add("no round-12 tower %d to compare with" % i)
            continue
        olo, ohi = old[i]["box"]
        cx = (olo[0] + ohi[0]) / 2
        cy = (olo[1] + ohi[1]) / 2
        oh = max(ohi[0] - cx, cx - olo[0], ohi[1] - cy, cy - olo[1])
        nh = max(nhi[0] - cx, cx - nlo[0], nhi[1] - cy, cy - nlo[1])
        log("tower %d: forge-local footprint half %.2f -> %.2f m, top z %.2f -> %.2f, centre (%.2f, %.2f)" % (
            i, oh, nh, ohi[2], nhi[2], cx, cy))
        if nh > oh + SIL_TOL[0] or abs(nhi[2] - ohi[2]) > SIL_TOL[1]:
            fail.add("tower %d silhouette moved: half %.2f -> %.2f, top %.2f -> %.2f" % (i, oh, nh, ohi[2], nhi[2]))
        ob_, nb_ = old[i]["screen"], screen_box(new[i], sc, cam)
        if ob_ and nb_:
            d = [nb_[k] - ob_[k] for k in range(4)]
            log("tower %d at the hold: x %.0f..%.0f y %.0f..%.0f px (was x %.0f..%.0f y %.0f..%.0f)" % (
                (i,) + tuple(nb_) + tuple(ob_)))
            if max(abs(d[0]), abs(d[1]), abs(d[2])) > SIL_PX:
                fail.add("tower %d's box at the hold moved by %s px" % (i, [round(v) for v in d]))


def neighbours(dg, lo, hi, exclude):
    """{owner: (n,3,3) world triangles} of evaluated meshes whose box meets (lo, hi), owners not in exclude."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if own in exclude or own.startswith(SKIP):
            continue
        W = np.array(inst.matrix_world)
        bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
        if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
            continue
        L = local_tris(o.data)
        if not len(L):
            continue
        T = L @ W[:3, :3].T + W[:3, 3]
        keep = ~((T.min(1) > hi).any(1) | (T.max(1) < lo).any(1))
        if keep.any():
            out.setdefault(own, []).append(T[keep])
    return {k: np.concatenate(v) for k, v in out.items()}


def check_clearance(new, dg, fail):
    names = {o.name for o in new}
    groups = {}
    for o in new:
        if o.type == 'MESH':
            groups.setdefault(group_of(o.name), []).append(o)
    for g, obs in sorted(groups.items()):
        fam = g.split(".")[0]
        allow = ALLOW.get(fam, ALLOW["extras"])
        T = world_tris_of(obs)
        if not len(T):
            continue
        lo, hi = T.reshape(-1, 3).min(0) - 0.3, T.reshape(-1, 3).max(0) + 0.3
        tw = bvh(T)
        V = T.reshape(-1, 3)[::7]
        near = []
        for own, To in neighbours(dg, lo, hi, names).items():
            if any(own == a or own.startswith(a) for a in allow):
                continue
            to = bvh(To)
            touch = len(tw.overlap(to))
            d = min(min(to.find_nearest(Vector(p))[3] for p in V),
                    min(tw.find_nearest(Vector(p))[3] for p in To.reshape(-1, 3)[::3]))
            near.append((d, own, touch))
            if touch or d < CLEAR_MIN:
                fail.add("%s: %s is %.3f m from it (%d crossing triangle pairs)" % (g, own, d, touch))
        near.sort()
        log("clear %-10s nearest: %s" % (g, ", ".join("%s %.2f m" % (o, d) for d, o, _t in near[:4]) or "nothing"))


def check_camera(new, sc, cam, fail):
    T = world_tris_of([o for o in new if o.type == 'MESH'])
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    best, bf = 1e9, 0
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    for f, M in zip(frames, EW.sample_matrices(cam, frames)):
        p = np.array(M.translation)
        d = float(np.linalg.norm(np.maximum(0.0, np.maximum(lo - p, p - hi))))
        if d < best:
            best, bf = d, f
    log("camera: chase.cam comes within %.1f m of the new pieces' box (frame %d)" % (best, bf))
    if best < CAM_MIN:
        fail.add("chase.cam comes within %.1f m of the new pieces (frame %d)" % (best, bf))


def check_flames(new, root, dg, sc, cam, fail):
    anchors = [o for o in new if o.get(FD.FIRE_TAG)]
    kinds = sorted(o[FD.FIRE_TAG] for o in anchors)
    log("flame anchors:", ", ".join("%s (%s)" % (o.name, o[FD.FIRE_TAG])
                                    for o in sorted(anchors, key=lambda o: o.name)))
    if kinds != ["cauldron", "chimney", "chimney", "furnace", "furnace", "furnace"]:
        fail.add("flame anchors %s, want 3 furnace, 2 chimney, 1 cauldron" % kinds)
    keep = sc.frame_current
    sc.frame_set(HOLD)
    dg = bpy.context.evaluated_depsgraph_get()
    cw = cam.matrix_world.translation.copy()
    for a in sorted(anchors, key=lambda o: o.name):
        M = a.matrix_world
        R3 = M.to_3x3().normalized()
        w, h, d = (float(v) for v in a["fire_size"])
        foot = M.translation
        kind = a[FD.FIRE_TAG]
        # on its bed: a ray down from 0.4 m over the foot meets the bed within 0.6 m
        hit, loc, nrm, idx, hob, _ = sc.ray_cast(dg, foot + Vector((0, 0, 0.4)), Vector((0, 0, -1)), distance=0.6)
        bed = getattr(hob, "original", hob).name if hit else None
        want_bed = {"furnace": "furnace_mouth", "chimney": "chimney_fire", "cauldron": "ding"}[kind]
        ok_bed = kind == "cauldron" or (bed is not None and want_bed in bed)
        # inside: rays from the flame's middle to the corners of a flame-shaped volume (full width at its foot, a
        # fifth of it at the top) meet nothing solid before the corner
        mid = foot + R3 @ Vector((0, 0, h * 0.5))
        blocked = 0
        for sx in (-0.5, 0.5):
            for sy in (-0.5, 0.5):
                for sz, kw in ((0.1, 1.0), (1.0, 0.4)):
                    c = foot + R3 @ Vector((sx * w * kw, sy * d * kw, sz * h))
                    v = c - mid
                    hit2, *_ = sc.ray_cast(dg, mid, v.normalized(), distance=max(v.length - 0.02, 0.0))
                    blocked += bool(hit2)
        # a clear line out along local -Y: a furnace's through its mouth, a chimney's through the front's right opening
        out_dir = R3 @ Vector((0, -1, 0))
        start = mid if kind != "chimney" else foot + R3 @ Vector(((FD.HI + FD.MULLION) / 2, 0.0, 0.75))
        hit3, loc3, *_ = sc.ray_cast(dg, start, out_dir, distance=4.0)
        clear = not hit3 if kind != "cauldron" else True
        # seen from the hold camera: share of 27 points in the flame volume a ray from the camera reaches
        seen, n = 0, 0
        for fx in (-0.35, 0.0, 0.35):
            for fy in (-0.3, 0.0, 0.3):
                for fz in (0.15, 0.45, 0.75):
                    p = foot + R3 @ Vector((fx * w, fy * d, fz * h))
                    v = p - cw
                    hit4, *_ = sc.ray_cast(dg, cw, v.normalized(), distance=v.length - 0.01)
                    seen += not hit4
                    n += 1
        log("flame %-24s %-8s foot %s size %.2f x %.2f x %.2f; bed %s; corners blocked %d/8; clear out %s; "
            "seen from the hold %d%%" % (a.name, kind,
                                        tuple(round(v, 2) for v in (root.matrix_world.inverted() @ foot)),
                                        w, h, d, bed, blocked, clear, round(100 * seen / n)))
        if kind == "furnace":
            check_opening(a, sc, dg, fail)
        if not ok_bed:
            fail.add("%s is not on its bed (ray down meets %s)" % (a.name, bed))
        if kind != "cauldron" and blocked:
            fail.add("%s: %d corners of its flame volume are behind solid faces" % (a.name, blocked))
        if not clear:
            fail.add("%s: no clear line out of its mouth" % a.name)
    sc.frame_set(keep)


MOUTH_LIFT = FD.PAGE_MOUTH_LIFT    # client/src/lib/sect/forge-flames.ts FLAMES.mouthLift: the quad stands this far out


def check_opening(a, sc, dg, fail):
    """A furnace anchor's fire-box plane (fire_opening, what the page draws: a quad MOUTH_LIFT in front of it, width x
    height, tracing a box depth deep behind it): on the firebox floor, its top corners hidden behind the arch (rays from
    its middle to them meet stone first), a clear line out, and the traced box as deep as the real one (5 cm)."""
    if a.get("fire_opening") is None:
        fail.add("%s has no fire_opening" % a.name)
        return
    M = a.matrix_world
    R3 = M.to_3x3().normalized()
    ow, oh, od = (float(v) for v in a["fire_opening"])
    n = R3 @ Vector((0.0, -1.0, 0.0))
    x = R3 @ Vector((1.0, 0.0, 0.0))
    up = Vector((0.0, 0.0, 1.0))
    base = M @ Vector(tuple(a["fire_opening_at"])) + n * MOUTH_LIFT
    hit, _l, _n, _i, hob, _ = sc.ray_cast(dg, base + up * 0.3, -up, distance=0.45)
    floor = getattr(hob, "original", hob).name if hit else None
    mid = base + up * (oh * 0.5)
    hidden = 0
    for s in (-1.0, 1.0):
        c = base + x * (s * ow * 0.5) + up * oh
        v = c - mid
        h2, *_ = sc.ray_cast(dg, mid, v.normalized(), distance=v.length - 0.01)
        hidden += bool(h2)
    h3, *_ = sc.ray_cast(dg, mid, n, distance=3.0)
    p = base + up * (oh * 0.3)
    h4, l4, *_ = sc.ray_cast(dg, p, -n, distance=od + 1.0)
    back = (l4 - p).length if h4 else None
    log("opening %-24s %.2f x %.2f x %.2f; floor %s; top corners behind stone %d/2; clear out %s; back wall %s m" % (
        a.name, ow, oh, od, floor, hidden, not h3, None if back is None else round(back, 3)))
    if floor is None or "furnace" not in floor:
        fail.add("%s: its fire-box plane is not on the firebox floor (ray down meets %s)" % (a.name, floor))
    if hidden != 2:
        fail.add("%s: the fire-box quad's top corners are not behind the arch (%d/2)" % (a.name, hidden))
    if h3:
        fail.add("%s: no clear line out of the fire-box plane" % a.name)
    if back is None or abs(back - od) > 0.05:
        fail.add("%s: the traced box is %.2f m deep, the firebox %s m" % (a.name, od, back))


def scan(dg, obs, label):
    """{piece: [same <=5 mm, same 5-12 mm]} m2 of same-facing parallel faces against itself and its neighbours."""
    t0 = time.time()
    rng = np.random.default_rng(29)
    rows = {}
    names = {o.name for o in obs}
    for ob in obs:
        if ob.type != 'MESH' or not len(ob.data.polygons):
            continue
        L = local_tris(ob.data)
        M = np.array(ob.matrix_world)
        T = L @ M[:3, :3].T + M[:3, 3]
        lo, hi = T.reshape(-1, 3).min(0) - 0.02, T.reshape(-1, 3).max(0) + 0.02
        others, oid = [], []
        for own, To in neighbours(dg, lo, hi, {ob.name}).items():
            others.append(To)
            oid += [own] * len(To)
        tn = bvh(np.concatenate(others)) if others else None
        ts = bvh(T)
        nrm, ar = tri_normals(T)
        tot = [0.0, 0.0]
        worst = {}
        for t in np.nonzero(ar > 1e-9)[0]:
            k = int(min(120, max(1, round(ar[t] / (SCAN_STEP * SCAN_STEP)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            n = Vector(nrm[t])
            w = ar[t] / k
            for p in T[t, 0] + np.outer(u, T[t, 1] - T[t, 0]) + np.outer(v, T[t, 2] - T[t, 0]):
                p = Vector(p)
                for sgn in (-1.0, 1.0):
                    for tr, who in ((ts, None), (tn, oid)):
                        if tr is None:
                            continue
                        loc, hn, fi, _d = tr.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL12)
                        if loc is None or hn.dot(n) < SCAN_PAR:
                            continue
                        g = abs((loc - p).dot(n))
                        if g > SCAN_TOL12:
                            continue
                        b = 0 if g <= SCAN_TOL else 1
                        tot[b] += w
                        o = "<self>" if who is None else who[fi]
                        worst[o] = worst.get(o, 0.0) + w
        rows[ob.name] = (tot, worst)
    for nm, (tot, worst) in sorted(rows.items()):
        if tot[0] + tot[1] >= 0.001:
            top = sorted(worst.items(), key=lambda kv: -kv[1])[:3]
            log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2; %s" % (
                label, nm, tot[0], tot[1], ", ".join("%s %.3f" % kv for kv in top)))
    log("scan %s: %d pieces, %.1f s" % (label, len(rows), time.time() - t0))
    del names
    return rows


# ------------------------------------------------------------------------------------------------------------- main

def apply(fail, do_scan=False, checks=True):
    """Bring the open file to this round's build. Returns dict(todo, state, new, digest)."""
    sc = bpy.context.scene
    root = bpy.data.objects.get(ROOT_EMPTY)
    ding = bpy.data.objects.get("forge.ding")
    if root is None or ding is None:
        fail.add("forge.root / forge.ding not found: is this out/sect_chase.blend?")
        return dict(todo=False)
    coll = root.users_collection[0]
    tagged = [o for o in bpy.data.objects if o.get(FD.TAG) == 1 and not o.name.startswith(SCRATCH)]
    has_old = [nm for nm in OLD_ONLY if bpy.data.objects.get(nm) is not None]
    missing_old = [nm for nm in OLD_NAMES if bpy.data.objects.get(nm) is None]
    if tagged and has_old:
        fail.add("both the round-12 pieces %s and %d tagged pieces: a mixed file" % (has_old, len(tagged)))
        return dict(todo=False)
    if not tagged:
        if missing_old:
            fail.add("round-12 pieces missing: %s" % missing_old)
            return dict(todo=False)
        for nm, t in OLD_TRIS.items():
            have = tris(bpy.data.objects[nm].data)
            if have != t:
                fail.add("%s has %d triangles, the round-12 build has %d" % (nm, have, t))
        if fail:
            return dict(todo=False)
        state = "old"
    else:
        state = "r29"
    kept = {nm: (np.array(bpy.data.objects[nm].matrix_world), faces_sig(bpy.data.objects[nm].data)
                 if bpy.data.objects[nm].type == 'MESH' else None) for nm in KEEP if bpy.data.objects.get(nm)}
    if len(kept) != len(KEEP):
        fail.add("kept pieces missing: %s" % [nm for nm in KEEP if nm not in kept])
        return dict(todo=False)
    light = bpy.data.objects["forge.furnace_light"]
    light0 = (tuple(light.matrix_world.translation), light.data.energy)
    hs0 = {h: EW._subtree_box(n) for h, n in (("forge", ["forge.ding", "forge.dais"]), ("forge-hall", ["forge.hall"]))}
    cam = bpy.data.objects.get(EW.CAMERA)
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    keep_frame = sc.frame_current
    sc.frame_set(HOLD)
    old = {}
    if state == "old":
        for i, obs in old_towers(root).items():
            old[i] = dict(box=local_box(obs, root), screen=screen_box(obs, sc, cam))
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    # the scratch build: the digest this round's build has
    t0 = time.time()
    scr, scoll = scratch_build(coll, root, ding)
    want = digest([o for o in scr], SCRATCH)
    n_scr = len(scr)
    remove_tree([o for o in scr if o.parent == root])
    bpy.data.collections.remove(scoll)
    log("scratch build: %d objects, digest %s (%.1f s)" % (n_scr, want, time.time() - t0))
    if state == "r29":
        have = digest(tagged, "forge")
        if have == want:
            log("state r29: the file has this build (%d tagged objects)" % len(tagged))
            sc.frame_set(keep_frame)
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
            return dict(todo=False, state="r29", new=tagged, digest=have)
        state = "stale"
        log("state stale: tagged objects differ from this build (file %s): rebuilding" % have)
    # apply
    if state == "old":
        for nm in OLD_NAMES:
            o = bpy.data.objects.get(nm)
            if o is not None:
                U.delete_hierarchy(o)
        log("removed the round-12 pieces: %d names" % len(OLD_NAMES))
    else:
        remove_tree([o for o in tagged if o.parent == root])
        log("removed %d stale tagged objects" % len(tagged))
    tops = build_all(coll, root, ding)
    new = [o for t in tops for o in tree(t)]
    bpy.context.view_layer.update()
    log("built %d objects (%d top-level) in %s" % (len(new), len(tops), coll.name))
    if checks:
        dg = bpy.context.evaluated_depsgraph_get()
        total = check_pieces(new, coll, root, fail)
        log("new pieces: %d triangles in all" % total)
        if old:
            check_silhouette(old, new_towers(new), root, sc, cam, fail)
        check_clearance(new, dg, fail)
        check_camera(new, sc, cam, fail)
        check_flames(new, root, dg, sc, cam, fail)
        for h, b0 in hs0.items():
            b1 = EW._subtree_box(["forge.ding", "forge.dais"] if h == "forge" else ["forge.hall"])
            if b0 is None or b1 is None or np.abs(np.array(b1[0]) - np.array(b0[0])).max() > 1e-4 or \
                    np.abs(np.array(b1[1]) - np.array(b0[1])).max() > 1e-4:
                fail.add("hotspot %s's box changed" % h)
        log("hotspots forge and forge-hall: boxes unchanged")
        for nm, (M0, s0) in kept.items():
            o = bpy.data.objects.get(nm)
            if o is None or np.abs(np.array(o.matrix_world) - M0).max() > 1e-6 or \
                    (s0 is not None and faces_sig(o.data) != s0):
                fail.add("%s changed" % nm)
        if (tuple(light.matrix_world.translation), light.data.energy) != light0:
            fail.add("forge.furnace_light changed")
        if do_scan:
            rows = scan(bpy.context.evaluated_depsgraph_get(), [o for o in new if o.type == 'MESH'], "after")
            for nm, (tot, _w) in rows.items():
                if tot[0] + tot[1] > NEW_MAX:
                    fail.add("same-facing overlap on %s: %.3f + %.3f m2" % (nm, tot[0], tot[1]))
        left = [o.name for o in bpy.data.objects if o.name.startswith(SCRATCH) or "~" in o.name]
        left += [m.name for m in bpy.data.meshes if m.name.startswith(SCRATCH)]
        if left:
            fail.add("scratch data left: %s" % left[:8])
        scenes1 = sorted(s.name for s in bpy.data.scenes)
        if scenes1 != scenes0:
            fail.add("scenes %s -> %s" % (scenes0, scenes1))
        log("objects %d -> %d" % (n_obj0, len(bpy.data.objects)))
    sc.frame_set(keep_frame)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
    have = digest([o for o in bpy.data.objects if o.get(FD.TAG) == 1], "forge")
    if have != want:
        fail.add("the build's digest %s is not the scratch build's %s" % (have, want))
    return dict(todo=True, state=state, new=new, digest=have)


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    log("forge_detail: tag %s, %d chimneys, %d furnaces" % (FD.TAG, len(FD.CHIMNEYS), len(FD.FURNACES)))
    res = apply(fail, do_scan=do_scan)
    if res.get("digest"):
        log("DIGEST", res["digest"])
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not res.get("todo"):
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs audit: new forge pieces (the chimney towers, furnaces, bellows, racks, coal, flame anchors) - "
        "run export_web.py -- audit --profile full, then chunks,meta (with r29/pending_export_fires.diff applied, "
        "meta.json gains fires[]), then bake_web.py bakefull for the forge chunk and the backdrop (the towers are "
        "seen from far), then pack")
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
