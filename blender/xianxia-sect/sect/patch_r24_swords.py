"""Round 24, lane 'swords': the gate's two weapons get their names on the plinth fronts and plain blades, in an existing
out/sect_chase.blend, so it matches what a fresh build of sect/areas/gate.py makes. Run on the cloud box, on a copy
first, and only AFTER the round-12 patches (patch_r12_libs, patch_r12_areas, patch_r12_world):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r24_swords.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-22): "I think the names of the two swords can be on the base, if it was a real weapon the name
wouldnt be on it". gate.py now has PLINTH_NAME = True (倚天 / 屠龍 in gold on the plinth's front panel, a 3 cm relief carved
into the plate like the saying on the sides) and BLADE_NAME = False (no name on either blade; the jian's name cartouche
goes with it, so its glowing ridge inlay runs unbroken; the saber's dragon and every other piece stay).

And so the names read where the visitor stops: gate.WEAPON_Y went from -25 to -22. At -25 the gate's hold (frame 93,
the site's 1600 x 900 framing) cut both plinth fronts at the frame's bottom edge and the sword's at its left edge; at
-22 all four characters are whole in the frame, 22-28 px tall, none behind the lions (x stays +-16, the turn 12 deg).

What it does: rebuilds 'gate.sword_monolith' (the Heaven Sword, mesh 'gate.heaven_sword') and
'gate.sword_monolith.001' (the Dragon Saber, 'gate.dragon_saber') with gate.weapon_mesh's steps, which carve every inlay
into its host (gate.carve_inlays, round 12: no face is left under the gold, so nothing new can flicker), and puts both
where gate.weapon_transform says (3 m nearer the gate). Same objects, names, parent and material slots; the old meshes
are freed. No object is added or removed.

State: each weapon's mesh must be either the round-12 build (blade names, plain plinth front; what patch_r12_areas
left) or this build (both are rebuilt in memory from gate.py and compared with the file's mesh, an order-free
comparison of every face), and its place either the round-12 one (x +-16, y -25) or gate.py's; anything else stops
the patch. Idempotent: on this build's file it prints 'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- both weapons: closed (every edge in two faces), within gate.WEAPON_TRI_BUDGET, the monolith's local box kept
  (x, y +-2.7, z 0..15.6), the saying still on both sides;
- names: gold on each plinth front, carved (a ray from the relief's face into the stone meets no front-facing face
  of the plate within 4.5 cm: the plate was cut under it);
- plain blades: no gold between the plinth's collar and the guard (z 2.95..10.25); the jian's ridge still glows
  where the cartouche was; the saber's dragon is still there;
- placed: at gate.weapon_transform; the plinth stands on the plaza (its base on gate.plaza's top within FOOT_TOL
  at FOOT_PTS points) and clears everything else near it by CLEAR_MIN, touching nothing;
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm, the weapons against themselves and
  everything near them, before and after; none may be gained (NEW_MAX);
- reading: chase.cam at the hold (93), 1600 x 900: every character of both names wholly in the frame, at least
  READ_SEEN of it unhidden and at least READ_MIN_PX tall; the climb (READ_FRAME) is logged too;
- names and counts: same object count, names and material slots; no scratch data left.
Prints 'PATCH CACHES ok' (names and world boxes kept) or 'PATCH CACHES needs audit' (the move: the weapons' world boxes
and the gate-swords hotspot move 3 m; export_web audit, then chunks,meta, then the gate chunk's bake), and
'PATCH DIGEST <md5>' of both weapons (order-free).
"""
import hashlib
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA)
from sect.areas import gate as G  # noqa: E402
from sect.lib import props as P  # noqa: E402

ROOT_EMPTY = "gate.root"
BOX_TOL = 0.01             # m: a world box within this of its old one keeps the export caches valid
SCAN_TOL = 0.0055          # m: parallel faces within 5 mm (as patch_r12_areas)
SCAN_TOL12 = 0.0125        # m: and the far-only band out to 12 mm
SCAN_PAR = 0.985           # |cos| between two faces counted as parallel
SCAN_STEP = 0.03           # m between samples
NEW_MAX = 0.02             # m2: same-facing overlap a weapon may gain against anything (both bands together)
CARVE_DEPTH = 0.045        # m: behind the name's face, no front-facing plate face within this (the relief is 3.4 cm)
SAYING_MIN = 0.01          # m2 of gold face on each side plate (the round-12 build: the sword 0.020-0.025, four
                           # 0.2 m characters a side; the saber 0.042-0.047, eight)
BLADE_Z = (2.95, 10.25)    # local z between the socket collar's top and the lowest fitting (the saber's 吞口 at 10.30)
HOLD_FRAME = 93            # the gate's hold
READ_FRAME = 85            # a climb frame, logged
READ_MIN_PX = 20.0         # a character's height at the hold (the round-24 build: 22-28 px)
READ_SEEN = 0.95           # share of a character's samples a ray from the camera reaches
RES = (1600, 900)
OLD_PLACE = (16.0, -25.0)  # the round-12 file's weapons: (side * x, y), turned as gate.weapon_transform
PLACE_TOL = 1e-4
FOOT_TOL = 0.01            # m: the plinth's base on the plaza's top
FOOT_PTS = 9               # points across the base (its centre and 8 round it)
CLEAR_MIN = 0.30           # m: nothing but the plaza nearer the weapon than this (the round-24 place: the balustrade
                           # 0.62 m, the banner stones 0.77 m)
CLEAR_SKIP = ("gate.plaza", "world.haze", "world.range", "world.roots")   # the floor and the world-sized pieces


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
            raise SystemExit("patch_r24_swords: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
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
    """(n, 3, 3) local triangles and their polygon's material index."""
    try:
        me.calc_loop_triangles()
    except Exception:  # noqa: BLE001  (evaluated meshes have them already)
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    mi = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("material_index", mi)
    return co.reshape(nv, 3)[tv.reshape(nt, 3)], mi


def faces_sig(me):
    """Order-free fingerprint of a mesh: every face as its rounded vertex coordinates (cyclic, from its smallest
    corner) and material slot's material name, sorted; plus the counts. Two builds of the same geometry match however
    Blender's boolean ordered its output."""
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


def local_box(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(0), co.max(0)


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (np.array([min(p[k] for p in pts) for k in range(3)]), np.array([max(p[k] for p in pts) for k in range(3)]))


def open_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n


def role_slot(spec, role):
    """Material slot of a role: gate._geo_to_mesh puts the slots in spec['materials'] order (carve_inlays keeps the
    indices)."""
    roles = list(spec["materials"])
    return roles.index(role) if role in roles else -1


# ----------------------------------------------------------------------------------------------------------- builds

def build(spec, plinth_name, blade_name, name, logf=None):
    """The weapon's mesh as gate.weapon_mesh builds it (weapon_geo_budget, _geo_to_mesh, carve_inlays for every CARVE
    pair), with PLINTH_NAME / BLADE_NAME set as given, under a scratch name (weapon_mesh would rename the file's mesh).
    Returns (mesh, info)."""
    keep = G.PLINTH_NAME, G.BLADE_NAME
    G.PLINTH_NAME, G.BLADE_NAME = plinth_name, blade_name
    info = {}

    def lg(*a):
        if len(a) > 6 and a[1] == "triangles":
            info.update(geo_tris=a[2], glyph_tris=a[4], couplet=a[6], res=a[8] if len(a) > 8 else None)
        if logf:
            logf(*a)
    try:
        g = G.weapon_geo_budget(spec, G.blender_glyph, log=lg)
        me = G._geo_to_mesh(g, name, spec["materials"])
        for host, inlays in G.CARVE:
            n = G.carve_inlays(me, g, host, inlays)
            if logf and n:
                logf(spec["key"], "carved", inlays, "into", host, "->", n, "faces")
        me["sect_shared"] = G.K + "." + spec["key"]
        me["gate_weapon_tris"] = g.tris()
        info["parts"] = sorted({p[0] for p in g.parts})
    finally:
        G.PLINTH_NAME, G.BLADE_NAME = keep
    return me, info


# ----------------------------------------------------------------------------------------------------------- checks

def name_faces(spec, me):
    """Local triangles of the plinth name: gold in front of the front plate, inside the panel."""
    T, mi = local_tris(me)
    gold = role_slot(spec, "gold")
    face = -(G.DIE[2] + 0.03)
    c = T.mean(1)
    sel = (mi == gold) & (c[:, 1] < face - 0.003) & (c[:, 2] > G.PANEL_Z[0]) & (c[:, 2] < G.PANEL_Z[1]) & \
        (np.abs(c[:, 0]) < 1.5)
    return T[sel]


def tri_normals(T):
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(cr, axis=1)
    ok = L > 1e-12
    n = np.zeros_like(cr)
    n[ok] = cr[ok] / L[ok, None]
    return n, 0.5 * L


def check_weapon(spec, ob, info, fail):
    me = ob.data
    key = spec["key"]
    t = tris(me)
    if t > G.WEAPON_TRI_BUDGET:
        fail.add("%s has %d triangles > %d (gate.WEAPON_TRI_BUDGET)" % (key, t, G.WEAPON_TRI_BUDGET))
    nm = open_edges(me)
    if nm:
        fail.add("%s has %d open edges" % (key, nm))
    lo, hi = local_box(me)
    want = (np.array([-G.WEAPON_HALF, -G.WEAPON_HALF, 0.0]), np.array([G.WEAPON_HALF, G.WEAPON_HALF, G.WEAPON_TOP]))
    if np.abs(lo - want[0]).max() > 1e-3 or np.abs(hi - want[1]).max() > 1e-3:
        fail.add("%s local box %s..%s is not the monolith's %s..%s" % (key, lo.round(4), hi.round(4), want[0], want[1]))
    if info and info.get("couplet") is not True:
        fail.add("%s lost the saying on its plinth sides (couplet %s)" % (key, info.get("couplet")))
    T, mi = local_tris(me)
    nrm, area = tri_normals(T)
    c = T.mean(1)
    gold, rune = role_slot(spec, "gold"), role_slot(spec, "rune")
    # the saying, on both sides (gold on the side plates)
    face = G.DIE[2] + 0.03
    for sgn in (-1.0, 1.0):
        s = (mi == gold) & (c[:, 0] * sgn > face + 0.001) & (c[:, 2] > G.PANEL_Z[0]) & (c[:, 2] < G.PANEL_Z[1])
        a = float(area[s & (nrm[:, 0] * sgn > 0.9)].sum())
        if a < SAYING_MIN:
            fail.add("%s: the saying on the %s side has %.3f m2 of gold face" % (key, "+x" if sgn > 0 else "-x", a))
    # the name on the front, its face and carved
    s = (mi == gold) & (c[:, 1] < -face - 0.003) & (c[:, 2] > G.PANEL_Z[0]) & (c[:, 2] < G.PANEL_Z[1]) & \
        (np.abs(c[:, 0]) < 1.5)
    front = s & (nrm[:, 1] < -0.9)
    a_name = float(area[front].sum())
    if a_name < 0.10:
        fail.add("%s: the plinth front has %.3f m2 of gold name face" % (key, a_name))
    ys = T[front][:, :, 1]
    tree = BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                     for i in range(len(T))], all_triangles=True)
    rng = np.random.default_rng(24)
    under, n_s = 0, 0
    for i in np.nonzero(front)[0]:
        k = int(min(6, max(1, round(area[i] / 0.0004))))
        u, v = rng.random(k), rng.random(k)
        f = u + v > 1.0
        u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
        for p in T[i, 0] + np.outer(u, T[i, 1] - T[i, 0]) + np.outer(v, T[i, 2] - T[i, 0]):
            n_s += 1
            o = Vector(p) + Vector((0.0, 1e-4, 0.0))
            loc, hn, fi, d = tree.ray_cast(o, Vector((0.0, 1.0, 0.0)), CARVE_DEPTH)
            if loc is not None and hn.y < -0.9 and mi[fi] != gold:
                under += 1
    if not n_s or under > 0.01 * n_s:
        fail.add("%s: %d of %d points of the name have a plate face under them (not carved)" % (key, under, n_s))
    zr = (float(ys.min()), float(ys.max())) if len(ys) else (0.0, 0.0)
    nb = (mi == gold) & (c[:, 2] > BLADE_Z[0]) & (c[:, 2] < BLADE_Z[1])
    if nb.any():
        fail.add("%s: %d gold faces on the blade (z %.2f..%.2f), want none" % (key, int(nb.sum()), *BLADE_Z))
    if spec["kind"] == "jian":
        mid = (mi == rune) & (c[:, 2] > G.J_PLATE[0]) & (c[:, 2] < G.J_PLATE[3])
        a_mid = float(area[mid].sum())
        if a_mid < 0.05:
            fail.add("jian: the ridge inlay does not glow where the cartouche was (%.3f m2)" % a_mid)
        art = "ridge inlay glowing over the old cartouche %.2f m2" % a_mid
    else:
        dr = (mi == rune) & (c[:, 2] > 3.0) & (c[:, 2] < 8.6)
        a_dr = float(area[dr].sum())
        if a_dr < 0.3:
            fail.add("dao: the dragon is missing (%.3f m2 of glow on the flat)" % a_dr)
        art = "dragon %.2f m2" % a_dr
    log("%s: %d triangles (budget %d), closed, local box kept, saying on both sides; name %.2f m2 of gold face "
        "%.3f..%.3f m in front of the plate, %d of %d points carved clean; blade plain (no gold at z %.2f..%.2f), %s"
        % (key, t, G.WEAPON_TRI_BUDGET, a_name, -face - zr[1], -face - zr[0], n_s - under, n_s, BLADE_Z[0],
           BLADE_Z[1], art))


def name_on_screen(sc, cam, spec, ob, frame):
    """Where the plinth name lands at ``frame`` in a 1600 x 900 frame: per character (left, right as the viewer sees
    them): (x0, x1, y0, y1) px, height px, share of its corners inside the frame, share of up to 80 of its points a
    ray from the camera reaches (not hidden by a lion or anything else), distance m."""
    from bpy_extras.object_utils import world_to_camera_view
    T = name_faces(spec, ob.data)
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    M = ob.matrix_world
    cw = cam.matrix_world.translation.copy()
    out = []
    for side in (-1.0, 1.0):
        S = T[(T.mean(1)[:, 0] * side) > 0]
        if not len(S):
            out.append(None)
            continue
        pts = [M @ Vector(p) for p in S.reshape(-1, 3)]
        ndc = [world_to_camera_view(sc, cam, p) for p in pts]
        xs = np.array([v.x * RES[0] for v in ndc])
        ys = np.array([(1.0 - v.y) * RES[1] for v in ndc])
        inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1])))
        V = S.reshape(-1, 3)
        R3 = M.to_3x3()
        seen, n = 0, 0
        for p in V[::max(1, len(V) // 80)]:
            q = M @ Vector(p) + R3 @ Vector((0.0, -0.01, 0.0))      # 1 cm in front of the relief
            d = q - cw
            hit, loc, nrm, idx, hob, _ = sc.ray_cast(dg, cw, d.normalized(), distance=d.length + 0.05)
            n += 1
            seen += bool(hit and hob is not None and getattr(hob, "original", hob).name == ob.name)
        mid = M @ Vector(tuple(V.mean(0)))
        out.append(((xs.min(), xs.max(), ys.min(), ys.max()), ys.max() - ys.min(), inside, seen / max(n, 1),
                    (mid - cw).length))
    return out


def placement(spec, ob):
    """'new' at gate.weapon_transform, 'old' at the round-12 file's place (OLD_PLACE, the same turn), else 'unknown'."""
    loc, rot = G.weapon_transform(spec)
    s = spec["side"]
    have_l, have_r = np.array(ob.location), np.array(ob.rotation_euler)
    if ob.rotation_mode != 'XYZ' or np.abs(have_r - np.array(rot)).max() > PLACE_TOL:
        return "unknown"
    if np.abs(have_l - np.array(loc)).max() <= PLACE_TOL:
        return "new"
    if np.abs(have_l - np.array((s * OLD_PLACE[0], OLD_PLACE[1], 0.0))).max() <= PLACE_TOL:
        return "old"
    return "unknown"


def world_tris(dg, owners=None, near=None, skip=()):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes: these owners, or those whose box meets the
    box ``near`` (lo, hi)."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own in skip:
            continue
        W = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L, _ = local_tris(o.data)
        if len(L):
            out.setdefault(own, []).append(L @ W[:3, :3].T + W[:3, 3])
    return {k: np.concatenate(v) for k, v in out.items()}


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                       for i in range(len(T))], all_triangles=True)


def check_place(spec, ob, dg, fail):
    """At gate.weapon_transform; the plinth's base on the plaza; nothing else within CLEAR_MIN, nothing touching."""
    key = spec["key"]
    if placement(spec, ob) != "new":
        fail.add("%s is at %s, not at gate.weapon_transform's %s" % (key, tuple(ob.location), G.weapon_transform(spec)))
    M = ob.matrix_world
    plaza = world_tris(dg, owners={"gate.plaza"}).get("gate.plaza")
    if plaza is None:
        fail.add("gate.plaza not found")
        return
    tp = bvh(plaza)
    worst = 0.0
    r = G.WEAPON_HALF - 0.3
    pts = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for a in np.linspace(0, 2 * np.pi, FOOT_PTS - 1, endpoint=False)]
    for x, y in pts:
        p = M @ Vector((x, y, 0.0))
        hit = tp.ray_cast(p + Vector((0.0, 0.0, 0.5)), Vector((0.0, 0.0, -1.0)), 2.0)
        gap = abs(hit[0].z - p.z) if hit[0] is not None else 9.0
        worst = max(worst, gap)
    if worst > FOOT_TOL:
        fail.add("%s: its base is %.3f m off the plaza's top" % (key, worst))
    T = world_tris(dg, owners={ob.name})[ob.name]
    lo, hi = T.reshape(-1, 3).min(0) - 1.5, T.reshape(-1, 3).max(0) + 1.5
    tw = bvh(T)
    V = T.reshape(-1, 3)[::3]
    near = []
    for own, To in world_tris(dg, near=(lo, hi), skip=set(CLEAR_SKIP) | {ob.name}).items():
        to = bvh(To)
        touch = len(tw.overlap(to))
        d = min(min(to.find_nearest(Vector(p))[3] for p in V), min(tw.find_nearest(Vector(p))[3] for p in To.reshape(-1, 3)))
        near.append((d, own, touch))
        if touch or d < CLEAR_MIN:
            fail.add("%s: %s is %.2f m from it (%d crossing triangle pairs), want %.2f m" % (key, own, d, touch,
                                                                                           CLEAR_MIN))
    near.sort()
    log("%s: at %s, turned %.1f deg; base on the plaza's top (worst %.4f m at %d points); nearest: %s" % (
        key, tuple(round(v, 3) for v in ob.location), np.degrees(ob.rotation_euler.z), worst, len(pts),
        ", ".join("%s %.2f m" % (o, d) for d, o, _t in near[:4]) or "nothing within 1.5 m"))


# ------------------------------------------------------------------------------------------------- the coplanar scan

def scan(dg, names, label):
    """{weapon: {other: [same <=5 mm, same 5-12 mm]}} m2 of same-facing parallel faces, sampled on the weapon's
    triangles against itself ('<self>') and every mesh whose box meets its own (as patch_r12_areas' Scan, without the
    exposure test)."""
    t0 = time.time()
    rng = np.random.default_rng(12)
    rows = {}
    for nm in names:
        ob = bpy.data.objects[nm]
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        L, _mi = local_tris(me)
        oe.to_mesh_clear()
        M = np.array(ob.matrix_world)
        T = L @ M[:3, :3].T + M[:3, 3]
        lo, hi = T.reshape(-1, 3).min(0) - 0.02, T.reshape(-1, 3).max(0) + 0.02
        others, oid = [], []
        for inst in dg.object_instances:
            o = inst.object
            if o.type != 'MESH':
                continue
            own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
            if own == nm:
                continue
            W = np.array(inst.matrix_world)
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
                continue
            Lo, _ = local_tris(o.data)
            if not len(Lo):
                continue
            To = Lo @ W[:3, :3].T + W[:3, 3]
            keep = ~((To.min(1) > hi).any(1) | (To.max(1) < lo).any(1))
            if keep.any():
                others.append(To[keep])
                oid += [own] * int(keep.sum())
        tn = None
        if others:
            N = np.concatenate(others)
            tn = BVHTree.FromPolygons([Vector(p) for p in N.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                             for i in range(len(N))], all_triangles=True)
        ts = BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                         for i in range(len(T))], all_triangles=True)
        nrm, ar = tri_normals(T)
        r = rows.setdefault(nm, {})
        for t in np.nonzero(ar > 1e-9)[0]:
            k = int(min(200, max(1, round(ar[t] / (SCAN_STEP * SCAN_STEP)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            n = Vector(nrm[t])
            w = ar[t] / k
            for p in T[t, 0] + np.outer(u, T[t, 1] - T[t, 0]) + np.outer(v, T[t, 2] - T[t, 0]):
                p = Vector(p)
                hits = []
                for sgn in (-1.0, 1.0):
                    loc, hn, fi, d = ts.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL12)
                    if loc is not None:
                        hits.append(("<self>", loc, hn))
                    if tn is not None:
                        loc, hn, fi, d = tn.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL12)
                        if loc is not None:
                            hits.append((oid[fi], loc, hn))
                for other, loc, hn in hits:
                    c = hn.dot(n)
                    g = (loc - p).dot(n)
                    if c < SCAN_PAR or abs(g) > SCAN_TOL12:
                        continue
                    row = r.setdefault(other, [0.0, 0.0])
                    row[0 if abs(g) <= SCAN_TOL else 1] += w
        tot = [sum(x[0] for x in r.values()), sum(x[1] for x in r.values())]
        top = sorted(r.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:5]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2%s" % (
            label, nm, tot[0], tot[1], "".join("; %s %.3f + %.3f" % (o, a, b) for o, (a, b) in top if a + b >= 0.001)))
    log("scan %s: %d weapons, %.1f s" % (label, len(names), time.time() - t0))
    return rows


# ------------------------------------------------------------------------------------------------------------- main

def digest(obs):
    h = hashlib.md5()
    for ob in sorted(obs, key=lambda o: o.name):
        h.update(ob.name.encode())
        h.update(np.round(np.array(ob.matrix_basis), 6).tobytes())
        h.update(ob.data.name.encode())
        h.update(faces_sig(ob.data).encode())
        h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
    return h.hexdigest()


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    root = bpy.data.objects.get(ROOT_EMPTY)
    targets = []
    for spec in G.WEAPONS:
        ob = bpy.data.objects.get(spec["object"])
        if ob is None or ob.type != 'MESH':
            fail.add("%s not found (or not a mesh): is this out/sect_chase.blend?" % spec["object"])
            continue
        if ob.parent != root:
            fail.add("%s's parent is %s, not %s" % (ob.name, ob.parent.name if ob.parent else None, ROOT_EMPTY))
        targets.append((spec, ob))
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    log("gate.py: PLINTH_NAME %s (res %d), BLADE_NAME %s, BLADE_NAME_BACK %s, budget %d" % (
        G.PLINTH_NAME, G.NAME_RES, G.BLADE_NAME, G.BLADE_NAME_BACK, G.WEAPON_TRI_BUDGET))
    if not G.PLINTH_NAME or G.BLADE_NAME:
        fail.add("gate.py is not the round-24 build (PLINTH_NAME True, BLADE_NAME False)")
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    n_scenes0 = sorted(s.name for s in bpy.data.scenes)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    before = {}
    for spec, ob in targets:
        before[ob.name] = dict(box=world_box(ob), basis=np.array(ob.matrix_basis), mesh=ob.data.name,
                               slots=[s.material.name if s.material else None for s in ob.material_slots],
                               sig=faces_sig(ob.data), tris=tris(ob.data))
        log("before %s: mesh %s, %d triangles, %d faces, carved %s, slots %s, at %s turned %.1f deg" % (
            ob.name, ob.data.name, before[ob.name]["tris"], len(ob.data.polygons), G.PART_ATTR in ob.data.attributes,
            before[ob.name]["slots"], tuple(round(v, 3) for v in ob.location), np.degrees(ob.rotation_euler.z)))
    dg = bpy.context.evaluated_depsgraph_get()
    scan0 = scan(dg, [ob.name for _s, ob in targets], "before") if do_scan else None
    # build this round's weapons, and the round-12 build to recognise the old state
    plan, infos = [], {}
    for spec, ob in targets:
        t1 = time.time()
        new, info = build(spec, True, False, "~r24." + spec["key"], logf=log)
        infos[spec["key"]] = info
        sig_new = faces_sig(new)
        if sig_new == before[ob.name]["sig"]:
            state = "new"
        else:
            old, oinfo = build(spec, False, True, "~r12." + spec["key"])
            state = "old" if faces_sig(old) == before[ob.name]["sig"] else "unknown"
            log("%s: the round-12 build: %d triangles (geo %s, glyphs %s, couplet %s)" % (
                spec["key"], tris(old), oinfo.get("geo_tris"), oinfo.get("glyph_tris"), oinfo.get("couplet")))
            bpy.data.meshes.remove(old)
        log("%s: state %s (file %d triangles; this build %d triangles, %d faces, geo %s, glyphs %s, couplet %s res %s, "
            "parts %s) %.1f s" % (spec["key"], state, before[ob.name]["tris"], tris(new), len(new.polygons),
                                  info.get("geo_tris"), info.get("glyph_tris"), info.get("couplet"), info.get("res"),
                                  ",".join(info.get("parts", [])), time.time() - t1))
        if state == "unknown":
            fail.add("%s: the file's mesh is neither the round-12 build nor this one" % ob.name)
        place = placement(spec, ob)
        log("%s: place %s (file at %s turned %.1f deg; gate.weapon_transform %s)" % (
            spec["key"], place, tuple(round(v, 4) for v in ob.location), np.degrees(ob.rotation_euler.z),
            G.weapon_transform(spec)))
        if place == "unknown":
            fail.add("%s is neither at the round-12 place (x +-%.1f, y %.1f) nor at gate.py's" % (ob.name, *OLD_PLACE))
        plan.append((spec, ob, new, state, place))
    if fail:
        for _s, _o, new, _st, _pl in plan:
            bpy.data.meshes.remove(new)
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    todo = any(st == "old" or pl == "old" for _s, _o, _n, st, pl in plan)
    # apply
    for spec, ob, new, state, place in plan:
        if place == "old":
            loc, rot = G.weapon_transform(spec)
            ob.location = loc
            ob.rotation_mode = 'XYZ'
            ob.rotation_euler = rot
            log("%s moved to %s (gate.WEAPON_Y %.1f, was %.1f)" % (ob.name, loc, G.WEAPON_Y, OLD_PLACE[1]))
        if state == "new":
            bpy.data.meshes.remove(new)
            log("%s mesh unchanged (already names on the plinth, plain blade)" % ob.name)
            continue
        old = ob.data
        name = old.name
        ob.data = new
        for s in ob.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if old.users == 0:
            bpy.data.meshes.remove(old)
        new.name = name
        log("%s rebuilt: mesh %s, %d triangles, %d faces (was %d triangles)" % (
            ob.name, new.name, tris(new), len(new.polygons), before[ob.name]["tris"]))
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != sc and not len(s_.objects):
            bpy.data.scenes.remove(s_)
    for m in list(bpy.data.meshes):
        if m.users == 0 and (m.name.startswith("~r24.") or m.name.startswith("~r12.") or m.name.startswith("~carve")):
            bpy.data.meshes.remove(m)
    bpy.context.view_layer.update()
    # checks
    dg = bpy.context.evaluated_depsgraph_get()
    for spec, ob, _new, _st, _pl in plan:
        check_weapon(spec, ob, infos.get(spec["key"]), fail)
        check_place(spec, ob, dg, fail)
        b = before[ob.name]
        if ob.data.name != b["mesh"]:
            fail.add("%s's mesh is %s, was %s" % (ob.name, ob.data.name, b["mesh"]))
        slots = [s.material.name if s.material else None for s in ob.material_slots]
        if slots != b["slots"]:
            fail.add("%s material slots %s, were %s" % (ob.name, slots, b["slots"]))
    # reading: the hold (every character whole, unhidden, READ_MIN_PX) and the climb (logged)
    cam = bpy.data.objects.get(EW.CAMERA)
    if cam is None:
        fail.add("%s not found" % EW.CAMERA)
    else:
        rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
        try:
            for frame in (HOLD_FRAME, READ_FRAME):
                for spec, ob, _n, _st, _pl in plan:
                    res = name_on_screen(sc, cam, spec, ob, frame)
                    for ch, r in zip(spec["name"], res):
                        if r is None:
                            fail.add("%s: no %s on the plinth front" % (spec["key"], ch))
                            continue
                        (x0, x1, y0, y1), h, inside, seen, dist = r
                        log("read frame %d %s %s: x %.0f..%.0f y %.0f..%.0f of %dx%d, %.0f px tall, %.0f%% in frame, "
                            "%.0f%% unhidden, %.1f m" % (frame, spec["key"], ch, x0, x1, y0, y1, RES[0], RES[1], h,
                                                         100 * inside, 100 * seen, dist))
                        if frame == HOLD_FRAME and (inside < 1.0 or seen < READ_SEEN or h < READ_MIN_PX):
                            fail.add("%s: %s does not read at the hold %d (%.0f px, %.0f%% in frame, %.0f%% unhidden)"
                                     % (spec["key"], ch, frame, h, 100 * inside, 100 * seen))
        finally:
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
            sc.frame_set(keep_frame)
    dg = bpy.context.evaluated_depsgraph_get()
    if do_scan:
        scan1 = scan(dg, [ob.name for _s, ob in targets], "after")
        for nm, rows in scan1.items():
            for other, (a, b) in rows.items():
                w = scan0.get(nm, {}).get(other, [0.0, 0.0])
                if a + b + w[0] + w[1] >= 0.001:
                    log("scan %s / %s: same-facing %.3f + %.3f -> %.3f + %.3f m2" % (nm, other, w[0], w[1], a, b))
                if a + b > w[0] + w[1] + NEW_MAX:
                    fail.add("new same-facing overlap %s / %s: %.3f + %.3f m2 (was %.3f + %.3f)" % (
                        nm, other, a, b, w[0], w[1]))
    # names and counts
    n_obj1 = len(bpy.data.objects)
    if n_obj1 != n_obj0:
        fail.add("objects %d -> %d" % (n_obj0, n_obj1))
    left = [o.name for o in bpy.data.objects if "~" in o.name] + [m.name for m in bpy.data.meshes if "~" in m.name]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if [s for s in scenes1 if s not in n_scenes0]:
        fail.add("scenes added: %s" % [s for s in scenes1 if s not in n_scenes0])
    log("objects %d -> %d; scenes %s" % (n_obj0, n_obj1, scenes1))
    # caches (a box that moved, not only one that grew: the visibility cache and chunk plan place records by them)
    stale = []
    for spec, ob, _n, _st, _pl in plan:
        lo0, hi0 = before[ob.name]["box"]
        lo1, hi1 = world_box(ob)
        if np.abs(lo1 - lo0).max() > BOX_TOL or np.abs(hi1 - hi0).max() > BOX_TOL:
            stale.append("%s %s..%s -> %s..%s" % (ob.name, lo0.round(2), hi0.round(2), lo1.round(2), hi1.round(2)))
    log("DIGEST", digest([ob for _s, ob, _n, _st, _pl in plan]))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if stale:
        log("CACHES needs audit: world boxes moved: %s - run export_web.py -- audit --profile full, then chunks,meta "
            "(the gate-swords hotspot and the heaven-sword / dragon-saber lore boxes move), then bake_web.py bakefull "
            "for gate and the backdrop, then pack" % "; ".join(stale))
    else:
        log("CACHES ok: names and world boxes kept (vis_cache, chunks and the gate-swords hotspot stay valid)%s" % (
            "; re-bake gate and the backdrop, then pack" if todo else "; nothing changed"))
    if not todo:
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
