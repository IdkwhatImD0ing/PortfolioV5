"""Round 36, lane 'icefire': Ice-Fire Island 冰火島 (scenery.island.009) rebuilt whole by sect/lib/icefire_island.py, in
an existing out/sect_chase.blend, so it matches what a fresh build makes (scenery.build_icefire calls icefire_island
once the round-36 source change is in). Run on the cloud box, on a copy first, AFTER round 34's centre lane (it turns
island.009 about 150 deg and drops it about 25 m; this patch builds on the island wherever it stands):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r36_icefire.py [-- DRY_RUN=1] [SCAN=0]

Why (owner, 2026-10-23): "The ice fire island is very broken right now lol". At the library hold (772) the page draws
the backdrop's stand-in copy of the island (proxy.formation), decimated piece by piece: round 12's tidy_rock had moved
the cone's last four rings onto one point without merging them, so below about 6 % the collapse decimation kept only
the cone's bottom 59 m; the glacier cap, the volcano and the separate lava slabs were left floating (a grey wedge, an
ice spike, a dark shard and lava lines like lightning). The island is rebuilt as one closed island instead: a single
rock mesh with one tip vertex, the lava sunk into it as faces of the rock, the ice and basalt halves split along mesh
edges; see icefire_island's module doc.

What it does: the island's old parts (icefire_props: glacier, icicles, stalactites, volcano, lava_flow, lava_veins and
the 19 steam puffs) are removed and icefire_island.build(rock) runs: the rock keeps its object, name, transform,
collection and lore role ('icefire-island' in export_web.LORE); its mesh (same name) is replaced; the parts glacier,
icicles, stalactites and volcano and 15 steam puffs are made again as its children. The plants are already gone
(icefire_props removed them); any left are removed.

State: the island must be icefire_props' build (round 7 / 12: tagged lava_flow and lava_veins children, the rock's
slots M.icefire_rock / M.icefire_ground), this module's build (rock[icefire_build] == 'r36') or a bare floating rock;
anything else stops the patch. Idempotent: the build is deterministic, so on this build's file it prints 'PATCH
nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- the rock: same name, transform, parent, collections and mesh name; in export_web.LORE; one closed manifold piece
  (every edge in two faces), no face under MIN_AREA, no two vertices within MIN_GAP, one lowest vertex (the tip),
  outward normals (positive volume, the top facing up), within its triangle budget;
- the lava in the rock: molten faces only in the rock and the volcano meshes, no separate lava object; MOLTEN_MIN m2;
  their groove centres sunk (the rock's molten-only vertices sit SUNK_MIN under their faces' rim, on average);
- the parts: each closed, parented to the rock with an identity local transform and tagged, within TRI_CAP; each
  piece starts inside its support (icicles in the cap or the rock, stalactites in the rock, the cap and the volcano
  sunk into the top, the serac shards in the cap): no piece floats;
- the waterfall: nothing of the island crosses its sheets; the rock keeps FALL_GAP from them;
- the bake's decimator (bake_web.capture, Decimator, clean_mesh, export_web.LEVELS): the rock at 12 % down to 0.8 %
  keeps its whole height and DEC_KEEP of its surface within 2 m (DEC_KEEP_LOW at 0.8 %); each part at the level its
  island floor of ISLAND_FLOOR_LO triangles picks keeps PART_KEEP within 2 m;
- the hold: chase.cam at 772, 1600 x 900: rays over the island's screen box: the share of its visible pixels that are
  fire (basalt, scorch, lava, the volcano) and ice (ice, snow, glacier, icicles), at least FIRE_MIN and ICE_MIN, and
  lava at least LAVA_MIN; 974 and 1208 are logged;
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm, each island piece against itself and
  everything near it, before and after the build: the island may not gain more than NEW_MAX m2 in all (12-20 mm and
  back-to-back logged);
- names and counts: objects change by the parts and puffs only, scenes the same, no scratch data left.
Prints 'PATCH CACHES needs audit' (the island's pieces and world boxes change) with the chunks to re-bake, and
'PATCH DIGEST <md5>' of the rock, its parts and puffs (order-free).
"""
import hashlib
import math
import os
import sys
import time
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402  (CAMERA, LORE, LEVELS)
from sect.lib import icefire_island as II  # noqa: E402

ROCK = "scenery.island.009"
OLD_PARTS = ("glacier", "icicles", "stalactites", "volcano", "lava_flow", "lava_veins")
OLD_SLOTS = ["M.icefire_rock", "M.icefire_ground"]
MIN_AREA = 1e-6            # m2: no rock face smaller
MIN_GAP = 1e-3             # m: no two rock vertices nearer (no stacked tip)
MOLTEN_MIN = 250.0         # m2 of lava faces in the rock
SUNK_MIN = 0.15            # m: the rock's molten-only vertices under the plane of their faces' outer ring, on average
FALL_GAP = 0.5             # m: the rock to the waterfall's sheets, at least
DEC_LEVELS = (0.12, 0.06, 0.03, 0.015, 0.008)
DEC_KEEP, DEC_KEEP_LOW = 0.99, 0.97
DEC_Z_TOL = 1.5            # m: a decimated rock's top and tip within this of the source's
ISLAND_FLOOR_LO = 400.0    # bake_web.ISLAND_FLOOR_LO: the stand-in's floor per island piece (triangles)
PART_KEEP = 0.9
HOLD = 772
HOLDS_LOGGED = (974, 1208)
RES = (1600, 900)
RAY_STEP = 3               # px between the hold's rays
FIRE_MIN, ICE_MIN, LAVA_MIN = 0.35, 0.12, 0.02
TRI_CAP = II.TRI_CAP
TOTAL_CAP = 36000          # the rock, its parts together
SCAN_TOL = 0.0055
SCAN_TOL12 = 0.0125
SCAN_TOL20 = 0.0205
SCAN_PAR = 0.985
SCAN_STEP = 0.2            # m between samples (the island is 9,000 m2)
NEW_MAX = 0.05             # m2: same-facing faces within 12 mm the island (all its pieces) may gain
BOX_TOL = 0.01


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
            raise SystemExit("patch_r36_icefire: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
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


def coords(me):
    c = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", c)
    return c.reshape(-1, 3)


def loop_tris(me):
    me.calc_loop_triangles()
    tv = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    tm = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("material_index", tm)
    return tv.reshape(-1, 3), tm


def tri_area(V, T):
    P = V[T]
    return 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)


def faces_sig(me):
    nv = len(me.vertices)
    q = np.round(coords(me) * 1e4).astype(np.int64)
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


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ Vector(c) for c in ob.bound_box]
    return (np.array([min(p[k] for p in pts) for k in range(3)]), np.array([max(p[k] for p in pts) for k in range(3)]))


def components(me):
    """Connected pieces of a mesh: [vertex index arrays]."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen = np.zeros(len(bm.verts), bool)
    out = []
    for v in bm.verts:
        if seen[v.index]:
            continue
        stack, cur = [v], []
        seen[v.index] = True
        while stack:
            x = stack.pop()
            cur.append(x.index)
            for e in x.link_edges:
                o = e.other_vert(x)
                if not seen[o.index]:
                    seen[o.index] = True
                    stack.append(o)
        out.append(np.array(cur))
    bm.free()
    return out


def edge_stats(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    st = dict(open=sum(1 for e in bm.edges if e.is_boundary), nonmanifold=sum(1 for e in bm.edges if not e.is_manifold),
              small=sum(1 for f in bm.faces if f.calc_area() < MIN_AREA))
    vol = bm.calc_volume(signed=True)
    bm.free()
    st["volume"] = vol
    return st


def bvh_of(V, T):
    return BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)


def inside(bvh, p):
    """p inside a closed surface: an odd number of crossings along a fixed direction."""
    o = Vector(tuple(p))
    d = Vector((0.31, 0.93, 0.17)).normalized()
    n = 0
    for _ in range(64):
        hit = bvh.ray_cast(o, d, 1e4)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + d * 1e-4
    return n % 2 == 1


# ------------------------------------------------------------------------------------------------------------ state

def island_state(rock):
    kids = {o.get(II.TAG): o for o in rock.children_recursive if o.get(II.TAG) and o.get(II.TAG) != "steam"}
    slots = [m.name if m else None for m in rock.data.materials]
    if rock.get(II.BUILD_PROP) == II.VERSION and set(kids) == set(II.PARTS):
        return "r36", kids
    if not rock.get(II.BUILD_PROP) and set(kids) == set(OLD_PARTS) and slots == OLD_SLOTS:
        return "r7", kids
    if not kids and not rock.get(II.BUILD_PROP):
        from sect import world as W
        if W.rock_rings(rock.data) is not None:
            return "bare", kids
    return "unknown", kids


def island_objects(rock):
    return [rock] + sorted([o for o in rock.children_recursive if o.get(II.TAG)], key=lambda o: o.name)


def digest(obs):
    h = hashlib.md5()
    for ob in sorted(obs, key=lambda o: o.name):
        h.update(ob.name.encode())
        h.update(np.round(np.array(ob.matrix_basis), 6).tobytes())
        h.update(repr(sorted((k, round(float(ob[k]), 6) if isinstance(ob[k], float) else str(ob[k]))
                             for k in ob.keys() if k in ("glow", "density", II.TAG, II.BUILD_PROP))).encode())
        if ob.type == 'MESH':
            h.update(ob.data.name.encode())
            h.update(faces_sig(ob.data).encode())
            h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
    return h.hexdigest()


# ----------------------------------------------------------------------------------------------------------- checks

def check_rock(rock, before, fail):
    me = rock.data
    if rock.name != ROCK or me.name != before["mesh"]:
        fail.add("rock is %s / mesh %s, want %s / %s" % (rock.name, me.name, ROCK, before["mesh"]))
    if np.abs(np.array(rock.matrix_world) - before["mw"]).max() > 1e-6:
        fail.add("the rock's transform changed")
    if (rock.parent.name if rock.parent else None) != before["parent"] or \
            sorted(c.name for c in rock.users_collection) != before["colls"]:
        fail.add("the rock's parent or collections changed")
    lore = [e for e in EW.LORE if any(ROCK in g for g in e[2])]
    if not lore:
        fail.add("%s is not in export_web.LORE any more" % ROCK)
    st = edge_stats(me)
    comps = components(me)
    V = coords(me)
    zmin = V[:, 2].min()
    lowest = int((V[:, 2] < zmin + 0.05).sum())
    from mathutils import kdtree
    kd = kdtree.KDTree(len(V))
    for i, p in enumerate(V):
        kd.insert(Vector(p), i)
    kd.balance()
    close = sum(1 for i, p in enumerate(V) if len(kd.find_range(Vector(p), MIN_GAP)) > 1)
    T, tm = loop_tris(me)
    A = tri_area(V, T)
    nz = np.cross(V[T][:, 1] - V[T][:, 0], V[T][:, 2] - V[T][:, 0])[:, 2] / np.maximum(2 * A, 1e-12)
    top = np.isin(tm, (II.SNOW, II.CINDER))
    top_up = float((nz[top] * A[top]).sum() / max(A[top].sum(), 1e-9))
    nt = tris(me)
    log("rock %s: %d vertices, %d triangles, %d piece(s); open edges %d, non-manifold %d, faces under %g m2 %d, "
        "vertex pairs within %g m %d; lowest vertex z %.2f (%d within 5 cm); volume %.0f m3; top faces up %.3f; "
        "slots %s" % (rock.name, len(V), nt, len(comps), st["open"], st["nonmanifold"], MIN_AREA, st["small"], MIN_GAP,
                      close, zmin, lowest, st["volume"], top_up, [m.name for m in me.materials]))
    if len(comps) != 1 or st["open"] or st["nonmanifold"] or st["small"] or close or lowest != 1:
        fail.add("rock: not one clean closed piece with a single tip (pieces %d, open %d, non-manifold %d, small %d, "
                 "close pairs %d, lowest %d)" % (len(comps), st["open"], st["nonmanifold"], st["small"], close, lowest))
    if st["volume"] <= 0 or top_up < 0.9:
        fail.add("rock: normals not outward (volume %.0f, top up %.3f)" % (st["volume"], top_up))
    if nt > II.ROCK_TRI_CAP:
        fail.add("rock: %d triangles > %d" % (nt, II.ROCK_TRI_CAP))
    if [m.name for m in me.materials] != ["M." + n for n in II.ROCK_MATS]:
        fail.add("rock: slots %s" % [m.name for m in me.materials])
    # lava: area per material, and how deep the molten-only vertices sit
    names = ("ice", "basalt", "snow", "cinder", "molten", "scorch")
    area_by = {nm: round(float(A[tm == k].sum()), 1) for k, nm in enumerate(names)}
    bm = bmesh.new()
    bm.from_mesh(me)
    depths = []
    for v in bm.verts:
        if v.link_faces and all(f.material_index == II.MOLTEN for f in v.link_faces):
            ring = {o for f in v.link_faces for o in f.verts if o is not v}
            outer = [o for o in ring if any(f.material_index != II.MOLTEN for f in o.link_faces)]
            if len(outer) >= 2:
                c = sum((o.co for o in outer), Vector()) / len(outer)
                n = sum((f.normal for f in v.link_faces), Vector()).normalized()
                depths.append((c - v.co).dot(n))
    bm.free()
    sunk = float(np.mean(depths)) if depths else 0.0
    log("rock areas m2 %s; %d groove vertices next to the rim of their groove sit %.2f m under it on average "
        "(median %.2f)" % (area_by, len(depths), sunk, float(np.median(depths)) if depths else 0.0))
    if area_by["molten"] < MOLTEN_MIN or sunk < SUNK_MIN:
        fail.add("lava: %.0f m2 in the rock, sunk %.2f m (want %.0f m2, %.2f m)" % (area_by["molten"], sunk,
                                                                                   MOLTEN_MIN, SUNK_MIN))
    return area_by


def check_parts(rock, fail):
    """Parts closed, placed, tagged and resting on their support; no other lava object."""
    rV = coords(rock.data)
    rT, _ = loop_tris(rock.data)
    rock_bvh = bvh_of(rV, rT)
    kids = {o.get(II.TAG): o for o in rock.children_recursive if o.get(II.TAG) and o.get(II.TAG) != "steam"}
    if set(kids) != set(II.PARTS):
        fail.add("parts %s, want %s" % (sorted(kids), sorted(II.PARTS)))
        return kids
    for k, ob in kids.items():
        if ob.parent != rock or np.abs(np.array(ob.matrix_local) - np.eye(4)).max() > 1e-6:
            fail.add("%s: not at the rock's frame under it" % ob.name)
        t = tris(ob.data)
        st = edge_stats(ob.data)
        mats = [m.name for m in ob.data.materials]
        log("%s: %d triangles, open edges %d, non-manifold %d, slots %s%s" % (
            ob.name, t, st["open"], st["nonmanifold"], mats, ", glow %.2f" % ob["glow"] if "glow" in ob else ""))
        if t > TRI_CAP or st["open"] or st["nonmanifold"]:
            fail.add("%s: %d triangles (cap %d), open %d, non-manifold %d" % (ob.name, t, TRI_CAP, st["open"],
                                                                               st["nonmanifold"]))
        if any("molten" in m for m in mats) and k != "volcano":
            fail.add("%s carries lava: only the rock and the volcano may" % ob.name)
    lava_obs = [o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(ROCK + ".")
                and o not in kids.values()
                and any(s.material and "molten" in s.material.name for s in o.material_slots)]
    if lava_obs:
        fail.add("separate lava objects left: %s" % lava_obs)
    if kids["volcano"].get("glow") is None or rock.get("glow") is None:
        fail.add("glow missing on the volcano or the rock")
    # support: the glacier's shell in the rock; its shards in the shell; icicles in the shell or the rock; stalactites
    # and the volcano in the rock
    g = kids["glacier"].data
    gV = coords(g)
    gT, _ = loop_tris(g)
    gc = components(g)
    shell = max(gc, key=len)
    sel = np.isin(gT, shell).all(1)
    shell_bvh = bvh_of(gV, gT[sel])
    shell_set = set(shell.tolist())
    res = {}
    for k, ob in kids.items():
        V = coords(ob.data)
        comps = components(ob.data)
        bad = 0
        for c in comps:
            if k == "glacier":
                sups = [rock_bvh] if len(c) == len(shell) and set(c.tolist()) == shell_set else [shell_bvh]
            elif k == "icicles":
                sups = [shell_bvh, rock_bvh]
            else:
                sups = [rock_bvh]
            pts = V[c]
            # the piece's top (icicles and stalactites hang from it), else any of its points (the cap sinks into the
            # top, the shards into the cap, the volcano's foot into the top)
            cand = pts[np.argsort(-pts[:, 2])[:6]] if k in ("icicles", "stalactites") else pts[np.argsort(pts[:, 2])]
            if not any(inside(s, p) for p in cand for s in sups):
                bad += 1
        res[k] = (len(comps), bad)
        if bad:
            fail.add("%s: %d of %d pieces do not start inside their support" % (ob.name, bad, len(comps)))
    log("support: pieces (floating) %s" % {k: "%d (%d)" % v for k, v in res.items()})
    return kids


def check_fall(rock, kids, fail):
    falls = II.falls_of(rock)
    Mi = np.array(rock.matrix_world.inverted())
    rV = coords(rock.data)
    rT, _ = loop_tris(rock.data)
    rb = bvh_of(rV, rT)
    for f in falls:
        fo = bpy.data.objects[f["name"]]
        pts, tri_l = [], []
        off = 0
        for ch in fo.children_recursive:
            if ch.type != 'MESH' or not len(ch.data.polygons):
                continue
            M = Mi @ np.array(ch.matrix_world)
            V = coords(ch.data) @ M[:3, :3].T + M[:3, 3]
            T, _ = loop_tris(ch.data)
            keep = (V[T][:, :, 2] > -II.FALL_DEPTH).any(1)
            pts.append(V)
            tri_l.append(T[keep] + off)
            off += len(V)
        if not pts:
            continue
        V = np.vstack(pts)
        T = np.vstack(tri_l)
        sb = bvh_of(V, T)
        cross = len(sb.overlap(rb))
        for k, ob in kids.items():
            kV = coords(ob.data)
            kT, _ = loop_tris(ob.data)
            cross += len(sb.overlap(bvh_of(kV, kT)))
        sel = V[:, 2] > -II.FALL_DEPTH
        gap = min(rb.find_nearest(Vector(p))[3] for p in V[sel][::3])
        log("waterfall %s at azimuth %.1f deg (+-%.1f): %d crossing triangle pairs with the island; the rock %.2f m "
            "from its sheets" % (f["name"], math.degrees(f["az"]), math.degrees(f["half"]), cross, gap))
        if cross or gap < FALL_GAP:
            fail.add("the island meets the waterfall %s (%d crossings, %.2f m)" % (f["name"], cross, gap))


def check_decimation(rock, kids, fail):
    """The bake's own decimator on the rock (export_web.LEVELS) and on each part at its stand-in floor's level."""
    from sect import bake_web as BW
    sc = bpy.context.scene
    obs = [rock] + [kids[k] for k in II.PARTS]
    caps = BW.capture(["#" + o.name for o in obs])
    dec = BW.Decimator(sc)
    made = []
    try:
        def measure(src, dm):
            V0 = coords(src)
            T0, _ = loop_tris(src)
            A = tri_area(V0, T0)
            C = V0[T0].mean(1)
            V, T = coords(dm), loop_tris(dm)[0]
            if not len(T):
                return 0.0, (0.0, 0.0), 0
            b = bvh_of(V, T)
            d = np.array([b.find_nearest(Vector(tuple(c)))[3] for c in C])
            return float(A[d <= 2.0].sum() / A.sum()), (float(V[:, 2].min()), float(V[:, 2].max())), len(T)
        base = caps["#" + rock.name]
        z0 = (coords(base)[:, 2].min(), coords(base)[:, 2].max())
        for r in DEC_LEVELS:
            dm = dec.get("r36." + rock.name, base, r)
            cm = BW.clean_mesh(dm) or dm
            made += [dm, cm]
            keep, z, n = measure(base, cm)
            need = DEC_KEEP_LOW if r < 0.01 else DEC_KEEP
            log("decimated rock at %g: %d triangles, %.1f%% of the surface within 2 m, z %.1f..%.1f (source %.1f..%.1f)"
                % (r, n, 100 * keep, z[0], z[1], z0[0], z0[1]))
            if keep < need or abs(z[0] - z0[0]) > DEC_Z_TOL or abs(z[1] - z0[1]) > DEC_Z_TOL:
                fail.add("decimated rock at %g keeps %.1f%% within 2 m, z %.1f..%.1f" % (r, 100 * keep, z[0], z[1]))
        lv = sorted(EW.LEVELS)
        for k in II.PARTS:
            ob = kids[k]
            src = caps["#" + ob.name]
            n0 = len(loop_tris(src)[0])
            want = min(1.0, ISLAND_FLOOR_LO / max(n0, 1))
            r = next((x for x in lv if x >= want), 1.0)
            dm = dec.get("r36." + ob.name, src, r)
            cm = BW.clean_mesh(dm) or dm
            made += [dm, cm]
            keep, z, n = measure(src, cm)
            log("decimated %s at %g (its stand-in floor): %d -> %d triangles, %.1f%% within 2 m" % (
                ob.name, r, n0, n, 100 * keep))
            if keep < PART_KEEP:
                fail.add("decimated %s keeps %.1f%% within 2 m" % (ob.name, 100 * keep))
    finally:
        names = {m.name for m in made} | {m.name for m in caps.values()}
        s = bpy.data.scenes.get("web.decimate")
        if s is not None:
            for o in list(s.objects):
                me = o.data
                bpy.data.objects.remove(o, do_unlink=True)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            bpy.data.scenes.remove(s)
        for nm in names:
            m = bpy.data.meshes.get(nm)
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)


def hold_view(sc, cam, rock, kids, frame, fail=None):
    """Rays from chase.cam over the island's screen box at ``frame``: shares of its visible pixels by kind."""
    from bpy_extras.object_utils import world_to_camera_view
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    obs = [rock] + list(kids.values())
    pts = []
    for o in obs:
        M = o.matrix_world
        pts += [M @ Vector(c) for c in o.bound_box]
    ndc = [world_to_camera_view(sc, cam, p) for p in pts]
    if any(v.z <= 0 for v in ndc):
        log("hold %d: the island is (partly) behind the camera" % frame)
    xs = [v.x * RES[0] for v in ndc]
    ys = [(1.0 - v.y) * RES[1] for v in ndc]
    x0, x1 = max(0, int(min(xs))), min(RES[0], int(max(xs)) + 1)
    y0, y1 = max(0, int(min(ys))), min(RES[1], int(max(ys)) + 1)
    if x1 <= x0 or y1 <= y0:
        log("hold %d: the island is off screen (box x %.0f..%.0f, y %.0f..%.0f)" % (frame, min(xs), max(xs), min(ys),
                                                                                 max(ys)))
        if fail is not None:
            fail.add("the island is not on screen at the hold %d" % frame)
        return None
    cw = cam.matrix_world
    origin = cw.translation.copy()
    cd = cam.data
    sx = cd.sensor_width
    fx = cd.lens / sx * RES[0]
    kinds = dict(fire=0, ice=0, lava=0)
    own = {o.name: o for o in obs}
    n_hit = n_ray = 0
    for py in range(y0, y1, RAY_STEP):
        for px in range(x0, x1, RAY_STEP):
            d = Vector(((px + 0.5 - RES[0] / 2) / fx, -(py + 0.5 - RES[1] / 2) / fx, -1.0))
            dw = (cw.to_3x3() @ d).normalized()
            n_ray += 1
            o_ = origin
            for _hop in range(8):                 # through cloud-puff domains (the web draws them as soft sprites)
                hit, loc, nrm, idx, hob, _m = sc.ray_cast(dg, o_, dw, distance=5000.0)
                if not hit or hob is None or not getattr(hob, "original", hob).name.startswith("world.cloud"):
                    break
                o_ = loc + dw * 0.01
            if not hit or hob is None:
                continue
            nm = getattr(hob, "original", hob).name
            if nm not in own:
                continue
            n_hit += 1
            o = own[nm]
            mi = o.data.polygons[idx].material_index if idx < len(o.data.polygons) else 0
            tag = o.get(II.TAG)
            if o is rock:
                k = {II.ICE: "ice", II.SNOW: "ice", II.BASALT: "fire", II.CINDER: "fire", II.SCORCH: "fire",
                     II.MOLTEN: "lava"}[mi]
            elif tag in ("glacier", "icicles"):
                k = "ice"
            elif tag == "volcano":
                k = "lava" if mi == 1 else "fire"
            else:
                k = "ice" if mi == 0 else "fire"
            kinds[k] += 1
    tot = max(1, n_hit)
    sh = {k: v / tot for k, v in kinds.items()}
    log("hold %d: the island's screen box x %d..%d y %d..%d of %dx%d; %d of %d rays meet it; fire %.0f%%, lava %.0f%%, "
        "ice %.0f%% of what shows (fire with lava %.0f%%)" % (frame, x0, x1, y0, y1, RES[0], RES[1], n_hit, n_ray,
                                                             100 * sh["fire"], 100 * sh["lava"], 100 * sh["ice"],
                                                             100 * (sh["fire"] + sh["lava"])))
    if fail is not None:
        if sh["fire"] + sh["lava"] < FIRE_MIN or sh["ice"] < ICE_MIN or sh["lava"] < LAVA_MIN:
            fail.add("the hold %d sees fire %.0f%%, ice %.0f%%, lava %.0f%% (want %.0f / %.0f / %.0f%%)" % (
                frame, 100 * (sh["fire"] + sh["lava"]), 100 * sh["ice"], 100 * sh["lava"], 100 * FIRE_MIN,
                100 * ICE_MIN, 100 * LAVA_MIN))
    return sh


# ------------------------------------------------------------------------------------------------- the coplanar scan

def scan(dg, names, label):
    """{piece: {other: [same <=5 mm, same 5-12 mm, same 12-20 mm, back-to-back <=5 mm]}} m2 of parallel faces sampled
    every SCAN_STEP m on the piece's triangles against itself and every mesh whose box meets its own (patch_r32's
    scan, coarser for a 9,000 m2 island)."""
    t0 = time.time()
    rows = {}
    for nm in names:
        rng = np.random.default_rng(zlib.crc32(nm.encode()))
        ob = bpy.data.objects[nm]
        T0, _ = loop_tris(ob.data)
        V0 = coords(ob.data)
        M = np.array(ob.matrix_world)
        T = (V0 @ M[:3, :3].T + M[:3, 3])[T0]
        lo, hi = T.reshape(-1, 3).min(0) - 0.03, T.reshape(-1, 3).max(0) + 0.03
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
            Lo, _ = loop_tris(o.data)
            if not len(Lo):
                continue
            To = (coords(o.data) @ W[:3, :3].T + W[:3, 3])[Lo]
            keep = ~((To.min(1) > hi).any(1) | (To.max(1) < lo).any(1))
            if keep.any():
                others.append(To[keep])
                oid += [own] * int(keep.sum())
        tn = BVHTree.FromPolygons([Vector(p) for p in np.concatenate(others).reshape(-1, 3)],
                                  [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(sum(len(x) for x in others))],
                                  all_triangles=True) if others else None
        ts = BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                         for i in range(len(T))], all_triangles=True)
        cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        L = np.linalg.norm(cr, axis=1)
        ar = 0.5 * L
        nrm = cr / np.maximum(L, 1e-12)[:, None]
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
                    loc, hn, fi, d = ts.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL20)
                    if loc is not None:
                        hits.append(("<self>", loc, hn))
                    if tn is not None:
                        loc, hn, fi, d = tn.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL20)
                        if loc is not None:
                            hits.append((oid[fi], loc, hn))
                for other, loc, hn in hits:
                    c = hn.dot(n)
                    g = abs((loc - p).dot(n))
                    if abs(c) < SCAN_PAR or g > SCAN_TOL20:
                        continue
                    row = r.setdefault(other, [0.0, 0.0, 0.0, 0.0])
                    if c < 0.0:
                        if g <= SCAN_TOL:
                            row[3] += w
                        continue
                    row[0 if g <= SCAN_TOL else (1 if g <= SCAN_TOL12 else 2)] += w
        tot = [sum(x[i] for x in r.values()) for i in range(4)]
        top = sorted(r.items(), key=lambda kv: -sum(kv[1]))[:5]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2, 12-20 mm %.3f m2; back-to-back within 5 mm "
            "%.3f m2%s" % (label, nm, tot[0], tot[1], tot[2], tot[3], "".join(
                "; %s %.3f + %.3f + %.3f / %.3f" % (o, a, b, c_, d_) for o, (a, b, c_, d_) in top
                if a + b + c_ + d_ >= 0.001)))
    log("scan %s: %d pieces, %.1f s" % (label, len(names), time.time() - t0))
    return rows


# ------------------------------------------------------------------------------------------------------------- main

def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    keep_frame = sc.frame_current
    rock = bpy.data.objects.get(ROCK)
    cam = bpy.data.objects.get(EW.CAMERA)
    if rock is None or rock.type != 'MESH' or cam is None:
        log("NOT SAVED: %s or %s not found: is this out/sect_chase.blend?" % (ROCK, EW.CAMERA))
        raise SystemExit(1)
    state, kids0 = island_state(rock)
    old = II.our_objects(rock)
    mw = rock.matrix_world
    log("island %s: state %s; at %s, turned %.1f deg; %d icefire objects (%d parts, %d puffs); rock mesh %s, %d "
        "triangles, slots %s" % (
            rock.name, state, tuple(round(v, 2) for v in mw.translation), math.degrees(mw.to_euler().z), len(old),
            len(kids0), len(old) - len(kids0), rock.data.name, tris(rock.data),
            [m.name if m else None for m in rock.data.materials]))
    if state == "unknown":
        log("NOT SAVED: the island is neither icefire_props' build, this build nor a bare floating rock")
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    before = dict(mw=np.array(rock.matrix_world), parent=rock.parent.name if rock.parent else None,
                  colls=sorted(c.name for c in rock.users_collection), mesh=rock.data.name)
    boxes0 = {o.name: world_box(o) for o in island_objects(rock) if o.type == 'MESH'}
    dig0 = digest(island_objects(rock) + [o for o in old if o not in island_objects(rock)])
    mats0 = {m.name for m in bpy.data.materials}
    scan0 = None
    if do_scan:
        dg = bpy.context.evaluated_depsgraph_get()
        scan0 = scan(dg, [o.name for o in island_objects(rock) if o.type == 'MESH'], "before")
    # build
    t1 = time.time()
    out = II.build(rock, log=lambda *a: log("build", *a))
    info = out["info"]
    log("built in %.1f s: layout %s" % (time.time() - t1, info["layout"]))
    bpy.context.view_layer.update()
    new = II.our_objects(rock)
    obs = island_objects(rock)
    dig1 = digest(obs + [o for o in new if o not in obs])
    todo = dig1 != dig0
    # checks
    check_rock(rock, before, fail)
    kids = check_parts(rock, fail)
    if set(kids) == set(II.PARTS):
        check_fall(rock, kids, fail)
        check_decimation(rock, kids, fail)
        total = tris(rock.data) + sum(tris(kids[k].data) for k in II.PARTS)
        log("triangles: rock %d + parts %s = %d (cap %d)" % (tris(rock.data), {k: tris(kids[k].data) for k in II.PARTS},
                                                            total, TOTAL_CAP))
        if total > TOTAL_CAP:
            fail.add("island: %d triangles > %d" % (total, TOTAL_CAP))
        rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
        try:
            hold_view(sc, cam, rock, kids, HOLD, fail)
            for f in HOLDS_LOGGED:
                hold_view(sc, cam, rock, kids, f)
        finally:
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
            sc.frame_set(keep_frame)
    steam = [o for o in new if o.name.startswith(II.STEAM_PREFIX)]
    if len(steam) != II.STEAM["plume"] + II.STEAM["snout"] or any(o.parent != rock for o in steam):
        fail.add("steam: %d puffs (want %d), all under the rock" % (len(steam), II.STEAM["plume"] + II.STEAM["snout"]))
    if do_scan and set(kids) == set(II.PARTS):
        dg = bpy.context.evaluated_depsgraph_get()
        rows = scan(dg, [rock.name] + [kids[k].name for k in II.PARTS], "after")
        tot0 = sum(a + b for r in scan0.values() for a, b, _c, _d in r.values())
        tot1 = sum(a + b for r in rows.values() for a, b, _c, _d in r.values())
        b2b0 = sum(d for r in scan0.values() for _a, _b, _c, d in r.values())
        b2b1 = sum(d for r in rows.values() for _a, _b, _c, d in r.values())
        log("scan: the island's same-facing faces within 12 mm %.3f -> %.3f m2 (back-to-back within 5 mm %.3f -> "
            "%.3f m2)" % (tot0, tot1, b2b0, b2b1))
        if tot1 > tot0 + NEW_MAX:
            fail.add("coplanar: the island gains %.3f m2 of same-facing faces within 12 mm (%.3f -> %.3f)" % (
                tot1 - tot0, tot0, tot1))
    # names and counts
    n_obj1 = len(bpy.data.objects)
    if n_obj1 - n_obj0 != len(new) - len(old):
        fail.add("objects %d -> %d, the island's own %d -> %d" % (n_obj0, n_obj1, len(old), len(new)))
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    left = [m.name for m in bpy.data.meshes if m.name.startswith(("~icefire", "r36.")) or m.name.endswith(".cl")]
    left += [o.name for o in bpy.data.objects if o.name.startswith(("web.decimator", "r36."))]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    mats1 = {m.name for m in bpy.data.materials}
    unused = sorted(m.name for m in bpy.data.materials if m.name.startswith("M.icefire_") and m.users == 0)
    log("objects %d -> %d (island %d -> %d); scenes %s; materials added %s; now unused (dropped on save) %s" % (
        n_obj0, n_obj1, len(old), len(new), scenes1, sorted(mats1 - mats0), unused))
    log("DIGEST", dig1)
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    boxes1 = {o.name: world_box(o) for o in island_objects(rock) if o.type == 'MESH'}
    moved = sorted(set(boxes0) ^ set(boxes1)) + sorted(
        n for n in set(boxes0) & set(boxes1) if np.abs(np.concatenate(boxes0[n]) - np.concatenate(boxes1[n])).max() >
        BOX_TOL)
    if moved or todo:
        log("CACHES needs audit: the island's pieces changed (%s) - run export_web.py -- audit --profile full, then "
            "chunks,meta (the icefire-island lore box) and clouds (the steam puffs), then bake_web.py bakefull for the "
            "chunk that holds island.009 (formation today; library if it is forced there) and the backdrop "
            "(proxy.formation, proxy.library), then pack" % ", ".join(moved[:12]))
    else:
        log("CACHES ok: names and world boxes kept; nothing changed")
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
