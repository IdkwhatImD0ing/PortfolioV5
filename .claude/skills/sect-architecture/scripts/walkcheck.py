"""walkcheck.py: can a visitor walk from the gate to every door? (sect-architecture skill)

STATUS: analyse() (the graph part) is tested on synthetic grids by test_walkcheck.py, outside
Blender. The Blender part was first run on the assembled sect (2026-10-10) and rewritten then:
mesh cache, vectorised candidate cells, walls block (horizontal rays), doors clustered per
building, project material names.

Headless only, never against the user's open Blender window:
  blender --background <scene.blend> --python walkcheck.py -- [--start X,Y,Z] \
      [--bounds X0,X1,Y0,Y1] [--step 0.5] [--max-rise 0.45] [--no-hop] [--json out.json]
Prints lines starting with WALKCHECK. --start defaults to the gate plaza (0, 0, 40).

What it does:
 1. Walkable triangles: face within 40 deg of up, material tag (custom prop 'sect_material')
    built (marble*, *paving*, wood / grey / dark stone, jade) or natural (rock, moss, grass,
    soil) on objects that are not world terrain / scenery. Roofs never count.
 2. Every --step m in XY, cast down repeatedly to get every floor layer (a bridge over
    terrain is a separate layer). Drop a sample if solid geometry sits within 2 m above it.
 3. Link 8-neighbour samples whose height differs by <= max rise and where nothing solid
    stands between them (two horizontal rays, 0.35 m and 0.9 m over the higher sample: walls,
    balustrades and parapets block; door leaves do not). Also link across one empty cell
    (plank gaps) when the height differs by <= 1.2 x max rise. Stepping stones (connector
    parts named 'stone'/'stones') also link by hops: <= 1.2 m up and <= 2.4 m across.
 4. Breadth-first search from the start. Report doors with no landing or not reachable,
    connector ends that land on nothing, connectors broken into pieces, and orphan floor
    patches (>= 4 m2, wide enough to stand on) that cannot be reached.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict, deque

BUILT = {"marble_white", "marble_paving", "wood_light", "wood_dark", "wood_soot", "stone_grey",
         "stone_dark", "jade"}
BUILT_PART = ("paving",)                            # area paving variants: steles_paving_grey ...
BUILT_PREFIX = ("marble",)
NATURAL = {"rock_cliff", "moss", "grass", "soil", "nature_soil_moss"}
# not solid for the headroom / wall test (substrings of the material tag)
NON_SOLID = ("rune", "cloth_", "foliage_", "light_beam", "glass_shield", "volume", "water_fall",
             "waterfall", "moon", "cloud", "cirrus", "haze", "mist", "smoke", "foam", "splash",
             "props_beam", "formation_beam", "formation_shield", "mote", "flare", "halo",
             "nature_pine_pad", "nature_pine_needle", "nature_shrub", "nature_blossom", "nature_flower",
             "nature_willow", "nature_bamboo_leaf", "nature_grass_blade", "nature_peach_leaf",
             "nature_lotus", "lotus_leaf", "lotus_flower")
EXCLUDE_OWNER = ("flyer", "chase", "camera", "cam.", "look.")
NATURAL_NOT_WALKABLE = ("world.", "scenery.")      # terrain and islets: not paths ...
NATURAL_WALKABLE = ("world.link.",)                 # ... except connectors (stepping stones)
# connector names: a part from CONN_WORDS, followed only by TAIL_OK parts or numbers, with no
# prop word before it ('arena.banner.002.stones' is a banner's base, 'x.stairs.bal.panels' a
# balustrade, 'x.lang.post' a corridor post). world.link.* parts are connectors except the
# archways and rest pavilions standing on them.
CONN_WORDS = {"stairs", "terrace_stairs", "steps", "bridge", "walk", "walkway", "lang", "corridor", "plank",
              "zhandao", "stone", "stones"}
TAIL_OK = {"steps", "floor", "deck", "body", "tread", "treads", "top", "slab", "walk", "stairs", "boards",
           "planks", "landing"}
PROP_WORDS = {"banner", "landing_banner", "flag", "lantern", "landing_lantern", "post", "posts", "bal",
              "balustrade", "rail", "rails", "railing", "panels", "drums", "col", "roof"}
LINK_DECOR = {"foot_gate", "foot_rail", "rest_pavilion", "rest_rail", "rails", "piers", "arch", "posts", "chains", "rest_pier"}
HOP_RE = re.compile(r"\.(stone|stones)(\.|$)")
DOOR_PROTO_RE = re.compile(r"^arch\.p\.lattice\..*\.door\.")
COS_MAX_SLOPE = math.cos(math.radians(40.0))
HEADROOM = 2.0
WALL_RAYS = (0.35, 0.9)                             # m over the higher of two samples
HOP_RISE, HOP_ACROSS = 1.2, 2.4                     # a comfortable stepping-stone hop
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
FWD4 = [d for d in N8 if d > (0, 0)]                # each neighbour pair once


def group_of(owner):
    """Connector grouping: 'world.link.a_b.stone.004' -> 'world.link.a_b'; else drop '.NNN'."""
    if owner.startswith("world.link."):
        return ".".join(owner.split(".")[:3])
    return re.sub(r"(\.\d{3,})+$", "", owner)


def is_connector(owner):
    parts = owner.split(".")
    if owner.startswith("world.link."):
        return len(parts) < 4 or parts[3] not in LINK_DECOR
    ks = [k for k, p in enumerate(parts) if p in CONN_WORDS]
    if not ks or any(p in PROP_WORDS for p in parts[:ks[-1]]):
        return False
    return all(p.isdigit() or p in TAIL_OK for p in parts[ks[-1] + 1:])


def is_hop(owner):
    return bool(HOP_RE.search(owner)) and is_connector(owner)


# ---------------------------------------------------------------- pure analysis (tested)

def analyse(cells, step, start, doors=(), markers=(), is_conn=is_connector, group=group_of,
            max_rise=0.45, gap_rise=None, min_patch=4.0, open_edge=None, hop=None):
    """cells: {(i, j): [(z, owner), ...]} sampled at x = i*step, y = j*step.
    start: (x, y, z). doors: [(name, x, y, z, fx, fy)] threshold point and outward facing.
    markers: [(name, x, y, z)] viewpoints / landmarks where a walkway may legitimately end.
    open_edge(a, b): optional, a and b are (i, j, k) node keys; False if something solid stands
    between the two samples. hop: optional dict(is_hop=owner -> bool, rise=1.2, across=2.4):
    hop-path nodes (stepping stones) also link to any node within `across` m and `rise` m up."""
    gap_rise = 1.2 * max_rise if gap_rise is None else gap_rise
    nodes, index = [], {}
    for (i, j), layers in cells.items():
        for k, (z, owner) in enumerate(layers):
            index[(i, j, k)] = len(nodes)
            nodes.append((i, j, z, owner))
    adj = [[] for _ in nodes]
    ok_edge = (lambda a, b: True) if open_edge is None else open_edge
    for (i, j, k), a in index.items():
        z = nodes[a][2]
        for di, dj in FWD4:
            for m, (z2, _) in enumerate(cells.get((i + di, j + dj), ())):
                if abs(z2 - z) <= max_rise and ok_edge((i, j, k), (i + di, j + dj, m)):
                    b = index[(i + di, j + dj, m)]
                    adj[a].append(b)
                    adj[b].append(a)
            mid = cells.get((i + di, j + dj), ())
            for m, (z2, _) in enumerate(cells.get((i + 2 * di, j + 2 * dj), ())):
                zm = 0.5 * (z + z2)
                if abs(z2 - z) <= gap_rise and not any(abs(zz - zm) <= max_rise for zz, _ in mid) \
                        and ok_edge((i, j, k), (i + 2 * di, j + 2 * dj, m)):
                    b = index[(i + 2 * di, j + 2 * dj, m)]
                    adj[a].append(b)
                    adj[b].append(a)
    n_hops = 0
    if hop:
        hrise, hacross = hop.get("rise", HOP_RISE), hop.get("across", HOP_ACROSS)
        hp = hop.get("is_hop", is_hop)
        r = int(math.ceil(hacross / step))
        for (i, j, k), a in index.items():
            if not hp(nodes[a][3]):
                continue
            z, own = nodes[a][2], nodes[a][3]
            have = set(adj[a])
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if (di, dj) == (0, 0) or math.hypot(di, dj) * step > hacross:
                        continue
                    for m, (z2, own2) in enumerate(cells.get((i + di, j + dj), ())):
                        if own2 == own or abs(z2 - z) > hrise:
                            continue
                        b = index[(i + di, j + dj, m)]
                        if b in have or (hp(own2) and b < a):
                            continue                  # stone-stone pairs once
                        if not ok_edge((i, j, k), (i + di, j + dj, m)):
                            continue
                        adj[a].append(b)
                        adj[b].append(a)
                        have.add(b)
                        n_hops += 1

    comp = [-1] * len(nodes)
    sizes = []
    for s in range(len(nodes)):
        if comp[s] >= 0:
            continue
        c, q, n = len(sizes), deque([s]), 0
        comp[s] = c
        while q:
            u = q.popleft()
            n += 1
            for v in adj[u]:
                if comp[v] < 0:
                    comp[v] = c
                    q.append(v)
        sizes.append(n)

    def near(x, y, z, r, dz):
        out = []
        ri = int(math.ceil(r / step))
        ci, cj = round(x / step), round(y / step)
        for i in range(ci - ri, ci + ri + 1):
            for j in range(cj - ri, cj + ri + 1):
                if math.hypot(i * step - x, j * step - y) > r:
                    continue
                for k, (zz, _) in enumerate(cells.get((i, j), ())):
                    if abs(zz - z) <= dz:
                        out.append(index[(i, j, k)])
        return out

    def xyz(n):
        i, j, z, _ = nodes[n]
        return (round(i * step, 2), round(j * step, 2), round(z, 2))

    rep = dict(step=step, max_rise=max_rise, nodes=len(nodes), hop_links=n_hops, doors=[], connectors=[],
               orphans=[])
    st = near(start[0], start[1], start[2], 3.0, 2.0)
    if not st:
        rep["error"] = "no walkable surface within 3 m of start %s" % (tuple(start),)
        rep["ok"] = False
        return rep
    main = Counter(comp[n] for n in st).most_common(1)[0][0]
    rep["main_area_m2"] = round(sizes[main] * step * step, 1)
    # for callers: is a point reachable? (used by the W9 runner)
    rep["_reach"] = lambda x, y, z, r=2.0, dz=1.0: any(comp[n] == main for n in near(x, y, z, r, dz))

    door_comps = set()
    for name, x, y, z, fx, fy in doors:
        ln = math.hypot(fx, fy) or 1.0
        land = near(x + fx / ln, y + fy / ln, z, 1.0, 0.3)
        d = dict(name=name, at=(round(x, 2), round(y, 2), round(z, 2)))
        if not land:
            d.update(ok=False, why="no landing in front (opens onto a drop, a wall or a step > 0.3 m)")
        elif any(comp[n] == main for n in land):
            d.update(ok=True)
        else:
            c = Counter(comp[n] for n in land).most_common(1)[0][0]
            door_comps.add(c)
            d.update(ok=False, why="not reachable from start (its floor patch is %.0f m2)" % (sizes[c] * step * step))
        rep["doors"].append(d)

    groups = defaultdict(list)
    for n, (_, _, _, o) in enumerate(nodes):
        if is_conn(o):
            groups[group(o)].append(n)
    for g, members in sorted(groups.items()):
        mset = set(members)
        pieces, seen = [], set()
        for s in members:
            if s in seen:
                continue
            seen.add(s)
            piece, q = [s], deque([s])
            while q:
                u = q.popleft()
                for v in adj[u]:
                    if v in mset and v not in seen:
                        seen.add(v)
                        piece.append(v)
                        q.append(v)
            pieces.append(piece)
        # pieces a person can stand in: one cell with all 8 neighbours in the piece (about 1 m
        # wide); slivers behind bench rails or beside a column are not walkways
        def wide_piece(p):
            ps = set(p)
            for u in p:
                i, j = nodes[u][0], nodes[u][1]
                if all(any(index.get((i + di, j + dj, k)) in ps for k in range(len(cells.get((i + di, j + dj), ()))))
                       for di, dj in N8):
                    return True
            return False
        pieces = [p for p in pieces if len(p) >= 4 and wide_piece(p)] or [p for p in pieces if len(p) >= 4] or pieces
        rc = dict(name=g, pieces=len(pieces), cells=len(members),
                  reached=any(comp[n] == main for n in members),
                  pieces_reached=sum(1 for p in pieces if any(comp[n] == main for n in p)), ends=[])

        def two_ends(piece):
            """Double BFS inside the piece: its two farthest-apart cells."""
            pset, far, ends = set(piece), piece[0], []
            for _ in range(2):
                dist = {far: 0}
                q = deque([far])
                while q:
                    u = q.popleft()
                    for v in adj[u]:
                        if v in pset and v not in dist:
                            dist[v] = dist[u] + 1
                            q.append(v)
                far = max(dist, key=dist.get)
                ends.append(far)
            return ends

        def thin(p, k=400):
            return p if len(p) <= k else p[::int(math.ceil(len(p) / k))]

        if len(pieces) > 1:
            cen = [tuple(sum(c) / len(p) for c in zip(*[xyz(n) for n in p])) for p in pieces]
            a = max(range(len(cen)), key=lambda k: math.dist(cen[k], cen[0]))
            b = max(range(len(cen)), key=lambda k: math.dist(cen[k], cen[a]))
            ax = (cen[b][0] - cen[a][0], cen[b][1] - cen[a][1])
            proj = lambda p3: p3[0] * ax[0] + p3[1] * ax[1]
            order = sorted(range(len(pieces)), key=lambda k: proj(cen[k]))
            worst, worst_at = (0.0, 0.0), None
            for p, q2 in zip(order, order[1:]):
                best = min(((math.dist(xyz(u)[:2], xyz(v)[:2]), abs(xyz(u)[2] - xyz(v)[2]), xyz(u))
                            for u in thin(pieces[p]) for v in thin(pieces[q2])), key=lambda t: t[0] + t[1])
                if best[0] + 2 * best[1] > worst[0] + 2 * worst[1]:
                    worst, worst_at = best[:2], best[2]
            rc.update(ok=False, why="broken into %d pieces; worst hop %.1f m across, %.1f m up"
                      % (len(pieces), worst[0], worst[1]), worst_at=worst_at)
            # only the two outer ends matter; the breaks are reported above
            checks = [(min(two_ends(pieces[order[0]]), key=lambda n: proj(xyz(n))), set(pieces[order[0]])),
                      (max(two_ends(pieces[order[-1]]), key=lambda n: proj(xyz(n))), set(pieces[order[-1]]))]
        else:
            rc["ok"] = True
            checks = [(e, set(pieces[0])) for e in two_ends(pieces[0])]
        for e, pset in checks:
            ex, ey, ez = xyz(e)
            tip = [n for n in near(ex, ey, ez, 1.0, 0.6) if n in pset] or [e]
            landed = any(group(nodes[v][3]) != g for t in tip for v in adj[t])
            mark = any(math.dist((ex, ey, ez), m[1:4]) <= 3.0 for m in markers)
            ok = landed or mark
            rc["ends"].append(dict(at=(ex, ey, ez), ok=ok,
                                   why="" if ok else "ends on nothing (no landing, door or viewpoint)"))
            rc["ok"] = rc["ok"] and ok
        rep["connectors"].append(rc)

    by_comp = defaultdict(list)
    for n, c in enumerate(comp):
        if c != main:
            by_comp[c].append(n)
    for c, members in by_comp.items():
        area = len(members) * step * step
        if area < min_patch or all(is_conn(nodes[n][3]) for n in members):
            continue                                  # tiny, or a connector piece (reported above)
        mine = set(members)
        wide = False
        for n in members:
            i, j, z, _ = nodes[n]
            if all(any(index[(i + di, j + dj, k)] in mine for k in range(len(cells.get((i + di, j + dj), ()))))
                   for di, dj in N8):
                wide = True
                break
        if not wide:
            continue
        pts = [xyz(n) for n in members]
        owners = Counter(group(nodes[n][3]) for n in members).most_common(3)
        rep["orphans"].append(dict(area_m2=round(area, 1), owners=[o for o, _ in owners],
                                   centre=tuple(round(sum(v) / len(v), 1) for v in zip(*pts)),
                                   has_door=c in door_comps,
                                   samples=pts[::max(1, len(pts) // 40)][:40]))
    rep["orphans"].sort(key=lambda o: -o["area_m2"])
    rep["ok"] = (all(d["ok"] for d in rep["doors"]) and all(c["ok"] for c in rep["connectors"])
                 and not rep["orphans"])
    return rep


def print_report(rep, out=print):
    if "error" in rep:
        out("WALKCHECK ERROR " + rep["error"])
        return
    nd = sum(1 for d in rep["doors"] if not d["ok"])
    nc = sum(1 for c in rep["connectors"] if not c["ok"])
    out("WALKCHECK summary: %s | reachable floor %.0f m2 | doors failing %d/%d | connectors failing %d/%d "
        "| orphan patches %d | max rise %.2f m | hop links %d" % (
            "PASS" if rep["ok"] else "FAIL", rep["main_area_m2"], nd, len(rep["doors"]), nc,
            len(rep["connectors"]), len(rep["orphans"]), rep["max_rise"], rep.get("hop_links", 0)))
    for d in rep["doors"]:
        if not d["ok"]:
            out("WALKCHECK door FAIL %s at %s: %s" % (d["name"], d["at"], d["why"]))
    for c in rep["connectors"]:
        if not c["ok"]:
            out("WALKCHECK connector FAIL %s%s" % (c["name"], ": " + c["why"] if c.get("why") else ""))
        for e in c["ends"]:
            if not e["ok"]:
                out("WALKCHECK   end at %s %s" % (e["at"], e["why"]))
        if not c["reached"]:
            out("WALKCHECK connector %s is not reachable from the start" % c["name"])
    for o in rep["orphans"]:
        out("WALKCHECK orphan %.0f m2 at %s owners %s%s" % (o["area_m2"], o["centre"], o["owners"],
                                                           " (has a door: building with no way in)"
                                                           if o["has_door"] else ""))


def clean(rep):
    """The report without its callables (for json)."""
    return {k: v for k, v in rep.items() if not callable(v)}


# ---------------------------------------------------------------- Blender side

def _tag(mat):
    if mat is None:
        return ""
    return mat.get("sect_material") or (mat.name[2:] if mat.name.startswith("M.") else mat.name)


def is_built(tag):
    return tag in BUILT or tag.startswith(BUILT_PREFIX) or any(p in tag for p in BUILT_PART)


def _walk_rule(tag, owner):
    if is_built(tag):
        return "up"
    if tag in NATURAL and (owner.startswith(NATURAL_WALKABLE) or not owner.startswith(NATURAL_NOT_WALKABLE)):
        return "up"
    return None


def _solid_rule(tag, owner):
    return None if any(s in tag for s in NON_SOLID) else "all"


def _is_door_leaf(ob):
    try:
        return any(DOOR_PROTO_RE.match(c.name) for c in ob.original.users_collection)
    except Exception:
        return False


def collect(depsgraph, box=None):
    """One pass over the evaluated scene. Returns dict(walk=(verts, tris, owners),
    solid=(verts, tris)) in world space. walk: faces within 40 deg of up with a walkable tag;
    solid: every face with a solid tag, door leaves left out (doors open).
    box = (x0, x1, y0, y1, z0, z1) culls objects and triangles."""
    import numpy as np
    cache, leaf = {}, {}
    out = dict(wv=[], wt=[], wo=[], sv=[], st=[], wb=0, sb=0)

    def add(kind, co, tv, owners=None):
        if len(tv) == 0:
            return
        used, inv = np.unique(tv.ravel(), return_inverse=True)
        out[kind[0] + "v"].append(co[used])
        out[kind[0] + "t"].append(inv.reshape(-1, 3) + out[kind[0] + "b"])
        out[kind[0] + "b"] += len(used)
        if owners is not None:
            out["wo"].extend(owners)

    for inst in depsgraph.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        owner = inst.parent.name if (inst.is_instance and inst.parent) else ob.name
        if owner.startswith(EXCLUDE_OWNER):
            continue
        tags = [_tag(s.material) for s in ob.material_slots] or [""]
        wr = [_walk_rule(t, owner) for t in tags]
        sr = [_solid_rule(t, owner) for t in tags]
        key_o = ob.original.name if ob.original else ob.name
        if key_o not in leaf:
            leaf[key_o] = _is_door_leaf(ob)
        if leaf[key_o]:
            sr = [None] * len(sr)
        if not any(wr) and not any(sr):
            continue
        M = np.array(inst.matrix_world)
        if box is not None:
            bb = np.array([list(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
            if (bb[:, 0].max() < box[0] or bb[:, 0].min() > box[1] or bb[:, 1].max() < box[2]
                    or bb[:, 1].min() > box[3] or bb[:, 2].max() < box[4] or bb[:, 2].min() > box[5]):
                continue
        me = ob.data
        mk = me.as_pointer()
        hit = cache.get(mk)
        if hit is None:
            try:
                nv, nt = len(me.vertices), len(me.loop_triangles)
                co = np.empty(nv * 3, np.float32)
                me.vertices.foreach_get("co", co)
                tv = np.empty(nt * 3, np.int32)
                me.loop_triangles.foreach_get("vertices", tv)
                mi = np.empty(nt, np.int32)
                me.loop_triangles.foreach_get("material_index", mi)
                hit = (co.reshape(-1, 3).astype(float), tv.reshape(-1, 3), mi)
            except Exception:
                hit = (np.zeros((0, 3)), np.zeros((0, 3), np.int32), np.zeros(0, np.int32))
            cache[mk] = hit
        co, tv, mi = hit
        if len(tv) == 0:
            continue
        cw = co @ M[:3, :3].T + M[:3, 3]
        mi = np.clip(mi, 0, len(tags) - 1)
        p0, p1, p2 = cw[tv[:, 0]], cw[tv[:, 1]], cw[tv[:, 2]]
        if box is not None:
            lo = np.minimum(np.minimum(p0, p1), p2)
            hi = np.maximum(np.maximum(p0, p1), p2)
            inb = ((hi[:, 0] >= box[0]) & (lo[:, 0] <= box[1]) & (hi[:, 1] >= box[2])
                   & (lo[:, 1] <= box[3]) & (hi[:, 2] >= box[4]) & (lo[:, 2] <= box[5]))
        else:
            inb = np.ones(len(tv), bool)
        if any(wr):
            n = np.cross(p1 - p0, p2 - p0)
            if np.linalg.det(M[:3, :3]) < 0:           # mirrored instance: winding flips
                n = -n
            nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
            keep = np.array([r == "up" for r in wr])[mi] & (nz >= COS_MAX_SLOPE) & inb
            sel = np.nonzero(keep)[0]
            add("w", cw, tv[sel], [owner] * len(sel))
        if any(sr):
            keep = np.array([r == "all" for r in sr])[mi] & inb
            add("s", cw, tv[keep])
    walk = None
    if out["wt"]:
        walk = (np.concatenate(out["wv"]), np.concatenate(out["wt"]), out["wo"])
    solid = (np.concatenate(out["sv"]), np.concatenate(out["st"])) if out["st"] else None
    return dict(walk=walk, solid=solid, meshes=len(cache))


def collect_tris(depsgraph, rule, box=None):
    """Kept for old callers: (verts, tris, owners) of the walkable triangles (rule ignored)."""
    return collect(depsgraph, box)["walk"]


def candidate_cells(tri, step):
    """(n, 2) int cell indices under the XY bounding boxes of triangles tri (m, 3, 3)."""
    import numpy as np
    lo = np.ceil(tri[:, :, :2].min(axis=1) / step - 1e-9).astype(np.int64)
    hi = np.floor(tri[:, :, :2].max(axis=1) / step + 1e-9).astype(np.int64)
    ni, nj = hi[:, 0] - lo[:, 0] + 1, hi[:, 1] - lo[:, 1] + 1
    ok = (ni > 0) & (nj > 0)
    small = ok & (ni <= 3) & (nj <= 3)
    parts = []
    for di in range(3):
        for dj in range(3):
            m = small & (di < ni) & (dj < nj)
            parts.append(np.stack([lo[m, 0] + di, lo[m, 1] + dj], axis=1))
    for k in np.nonzero(ok & ~small)[0]:
        I, J = np.meshgrid(np.arange(lo[k, 0], hi[k, 0] + 1), np.arange(lo[k, 1], hi[k, 1] + 1))
        parts.append(np.stack([I.ravel(), J.ravel()], axis=1))
    return np.unique(np.concatenate(parts), axis=0)


def _cull_solid(solid, cells, step, block=4.0, below=1.0, above=HEADROOM + 1.2):
    """Solid triangles near the sampled floor: in a block (dilated by one) that has floor, and
    within the floor's height range there. Triangles larger than a block are kept if they
    overlap the floor's overall height range."""
    import numpy as np
    sv, st = solid
    ij = np.array(list(cells.keys()), np.int64)
    zl = [(min(z for z, _ in v), max(z for z, _ in v)) for v in cells.values()]
    zl = np.array(zl)
    bi = np.floor(ij * step / block).astype(np.int64)
    b0 = bi.min(axis=0) - 2
    shape = tuple(bi.max(axis=0) - b0 + 3)
    zmin = np.full(shape, np.inf)
    zmax = np.full(shape, -np.inf)
    np.minimum.at(zmin, (bi[:, 0] - b0[0], bi[:, 1] - b0[1]), zl[:, 0])
    np.maximum.at(zmax, (bi[:, 0] - b0[0], bi[:, 1] - b0[1]), zl[:, 1])
    dmin, dmax = zmin.copy(), zmax.copy()
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            dmin = np.minimum(dmin, np.roll(np.roll(zmin, di, 0), dj, 1))
            dmax = np.maximum(dmax, np.roll(np.roll(zmax, di, 0), dj, 1))
    tri = sv[st]
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    cen = tri.mean(axis=1)
    big = (hi[:, :2] - lo[:, :2]).max(axis=1) > block
    cb = np.floor(cen[:, :2] / block).astype(np.int64) - b0
    inside = (cb[:, 0] >= 0) & (cb[:, 0] < shape[0]) & (cb[:, 1] >= 0) & (cb[:, 1] < shape[1])
    cbc = np.clip(cb, 0, np.array(shape) - 1)
    bz0, bz1 = dmin[cbc[:, 0], cbc[:, 1]], dmax[cbc[:, 0], cbc[:, 1]]
    keep = inside & (hi[:, 2] >= bz0 - below) & (lo[:, 2] <= bz1 + above)
    gz0, gz1 = zl[:, 0].min(), zl[:, 1].max()
    keep |= big & (hi[:, 2] >= gz0 - below) & (lo[:, 2] <= gz1 + above)
    sel = st[keep]
    used, inv = np.unique(sel.ravel(), return_inverse=True)
    return sv[used], inv.reshape(-1, 3)


class Sampler:
    """Floor samples of a scene plus the solid BVH for headroom and wall tests."""

    def __init__(self, walk, solid, step=0.5, headroom=HEADROOM, max_layers=8, log=print):
        import numpy as np
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        self.step = step
        wv, wt, wo = walk
        wb = BVHTree.FromPolygons(wv.tolist(), wt.tolist(), all_triangles=True)
        cand = candidate_cells(wv[wt], step)
        top, down = float(wv[:, 2].max()) + 5.0, Vector((0, 0, -1))
        raw = {}
        for i, j in cand.tolist():
            x, y, zc, layers = i * step, j * step, top, []
            for _ in range(max_layers):
                loc, _n, idx, _d = wb.ray_cast(Vector((x, y, zc)), down)
                if loc is None:
                    break
                zc = loc.z - 0.03
                if not layers or layers[-1][0] - loc.z > 0.02:
                    layers.append((round(loc.z, 3), wo[idx]))
            if layers:
                raw[(i, j)] = layers
        log("WALKCHECK sampled %d candidate cells, %d with floor" % (len(cand), len(raw)))
        self.sb = None
        if solid is not None and raw:
            sv, st = _cull_solid(solid, raw, step)
            log("WALKCHECK solid triangles kept near the floor: %d" % len(st))
            self.sb = BVHTree.FromPolygons(sv.tolist(), st.tolist(), all_triangles=True)
        up = Vector((0, 0, 1))
        cells = {}
        for key, layers in raw.items():
            x, y = key[0] * step, key[1] * step
            keep = [(z, o) for z, o in layers
                    if self.sb is None or self.sb.ray_cast(Vector((x, y, z + 0.05)), up, headroom - 0.05)[0] is None]
            if keep:
                cells[key] = keep
        self.cells = cells
        self._open = {}
        log("WALKCHECK floor cells after the headroom test: %d" % len(cells))

    def covered(self, x, y, z, up=40.0):
        """True if solid geometry stands over (x, y, z) within `up` m (a roof, or the inside of a
        solid the floor was sampled in)."""
        from mathutils import Vector
        if self.sb is None:
            return False
        return self.sb.ray_cast(Vector((x, y, z + 0.05)), Vector((0, 0, 1)), up)[0] is not None

    def open_edge(self, a, b):
        """No solid between samples a and b (node keys (i, j, k)) at WALL_RAYS over the higher."""
        key = (a, b) if a < b else (b, a)
        hit = self._open.get(key)
        if hit is not None:
            return hit
        from mathutils import Vector
        za, zb = self.cells[a[:2]][a[2]][0], self.cells[b[:2]][b[2]][0]
        s = self.step
        pa = Vector((a[0] * s, a[1] * s, 0.0))
        pb = Vector((b[0] * s, b[1] * s, 0.0))
        d = pb - pa
        dist = d.length
        d.normalize()
        ok = True
        if self.sb is not None:
            for h in WALL_RAYS:
                zr = max(za, zb) + h
                o = Vector((pa.x, pa.y, zr))
                if self.sb.ray_cast(o, d, dist)[0] is not None:
                    ok = False
                    break
        self._open[key] = ok
        return ok


def sample(walk, solid, step, headroom=HEADROOM, max_layers=8):
    """Kept for old callers: the floor cells only (no wall test)."""
    return Sampler(walk, solid, step, headroom, max_layers).cells


def _building_of(ob):
    """Top-level object under an area root ('<key>.root') for an object, else its own name."""
    o = ob
    while o is not None and o.parent is not None and not o.parent.name.endswith(".root"):
        o = o.parent
    return o.name if o is not None else "?"


def find_doors(scene, depsgraph, info=None):
    """Tagged Empties 'door.*' (or custom prop 'door') first; else lattice door leaves, clustered
    per building (leaves within 6 m and 0.5 m of height). info (dict) gets name -> building."""
    from mathutils import Vector
    doors = []
    for ob in scene.objects:
        if ob.name.startswith("door.") or ob.get("door"):
            m = ob.matrix_world
            f = m.to_3x3() @ Vector((0, -1, 0))
            doors.append((ob.name, m.translation.x, m.translation.y, m.translation.z, f.x, f.y))
            if info is not None:
                info[ob.name] = _building_of(ob)
    if doors:
        return doors, "tagged Empties"
    leaves = {}
    is_door = {}
    for inst in depsgraph.object_instances:
        if not inst.is_instance or inst.object.type != 'MESH' or inst.parent is None:
            continue
        nm = inst.object.original.name
        if nm not in is_door:
            is_door[nm] = any(DOOR_PROTO_RE.match(c.name) for c in inst.object.original.users_collection)
        if not is_door[nm]:
            continue
        m = inst.matrix_world
        f = m.to_3x3() @ Vector((0, -1, 0))
        key = (round(m.translation.x, 1), round(m.translation.y, 1), round(m.translation.z, 1))
        par = inst.parent.original if inst.parent.original else inst.parent
        leaves[key] = (_building_of(par), key, (f.x, f.y))
    clusters = []
    for bld, p, f in sorted(leaves.values()):
        for c in clusters:
            if c[0] == bld and abs(p[2] - c[1][0][2]) <= 0.5 and math.dist(p[:2], c[1][0][:2]) <= 6.0:
                c[1].append(p)
                break
        else:
            clusters.append((bld, [p], f))
    count = Counter()
    for bld, ps, f in clusters:
        c = [sum(v) / len(ps) for v in zip(*ps)]
        name = "%s.door%d" % (bld, count[bld])
        count[bld] += 1
        doors.append((name, c[0], c[1], c[2], f[0], f[1]))
        if info is not None:
            info[name] = bld
    return doors, "lattice door leaves"


def scan(step=0.5, box=None, log=print):
    """Collect + sample the open scene. Returns (Sampler, doors, door_info, markers)."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    got = collect(dg, box)
    if got["walk"] is None:
        return None, [], {}, []
    log("WALKCHECK collected %d walkable and %d solid triangles from %d meshes"
        % (len(got["walk"][1]), 0 if got["solid"] is None else len(got["solid"][1]), got["meshes"]))
    smp = Sampler(got["walk"], got["solid"], step, log=log)
    info = {}
    doors, how = find_doors(bpy.context.scene, dg, info)
    markers = [(o.name, *o.matrix_world.translation) for o in bpy.context.scene.objects
               if o.name.startswith(("vista.", "landmark."))]
    log("WALKCHECK %d doors (%s), %d markers" % (len(doors), how, len(markers)))
    return smp, doors, info, markers


def subset(cells, step, bounds):
    """Cells whose sample point lies inside bounds (x0, x1, y0, y1)."""
    x0, x1, y0, y1 = bounds
    return {k: v for k, v in cells.items() if x0 <= k[0] * step <= x1 and y0 <= k[1] * step <= y1}


def main(argv):
    a = dict(start="0,0,40", bounds=None, step="0.5", max_rise="0.45", json=None)
    hop = True
    k = 0
    while k < len(argv):
        if argv[k] == "--no-hop":
            hop = False
            k += 1
            continue
        a[argv[k].lstrip("-").replace("-", "_")] = argv[k + 1]
        k += 2
    step, rise = float(a["step"]), float(a["max_rise"])
    start = tuple(float(v) for v in a["start"].split(","))
    b = [float(v) for v in a["bounds"].split(",")] if a["bounds"] else None
    box = (b[0] - 5, b[1] + 5, b[2] - 5, b[3] + 5, -1e9, 1e9) if b else None
    smp, doors, info, markers = scan(step, box)
    if smp is None:
        print("WALKCHECK ERROR no walkable triangles found")
        return
    cells = subset(smp.cells, step, b) if b else smp.cells
    if b:
        doors = [d for d in doors if b[0] <= d[1] <= b[1] and b[2] <= d[2] <= b[3]]
    rep = analyse(cells, step, start, doors, markers, max_rise=rise, open_edge=smp.open_edge,
                  hop=dict(is_hop=is_hop) if hop else None)
    print_report(rep)
    if a["json"]:
        with open(a["json"], "w", encoding="utf-8") as fh:
            json.dump(clean(rep), fh, indent=1)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
