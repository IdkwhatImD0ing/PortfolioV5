"""walk_sect.py: the W9 walkability battery for the xianxia sect (blender/xianxia-sect).

Run headless on the assembled scene (out/sect.blend), with walkcheck.py next to this file:
  blender --background out/sect.blend --python walk_sect.py -- [--rises 0.7,0.45] [--json out.json]
          [--areas gate,mirror] [--links gate_mirror] [--no-global]

One scan of the scene, then for each max rise:
- global: from the gate plaza (0, 0, 40); which doors are reachable at all;
- per area: the area's square (footprint + 16 m), from its declared AREA['arrival'] (world);
  doors failing, orphan floor patches, the area's own connectors failing;
- per link: the link's bounding box + 10 m, from the leaving area's AREA['depart']; the link
  in pieces or not, its ends, and whether the next area's AREA['arrival'] is reached.
A door that fails only because it opens onto an upper-storey balcony (the same building has a
reachable door at least 2 m lower) is listed as 'upper' (reached by an inner stair), not failed.
Prints 'W9 ...' lines; --json writes everything.
"""
import importlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import walkcheck as W  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

ORDER = ("gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll", "formation",
         "abode", "summit")


def log(*a):
    print("W9", *a, flush=True)


def project_root():
    p = bpy.data.filepath.replace("\\", "/")
    return os.path.dirname(os.path.dirname(p))


def ports():
    """{key: dict(arrival=(p, h), depart=(p, h), anchor=(x, y, z), fp=footprint)} in world space."""
    root = project_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    out = {}
    for k in ORDER:
        ob = bpy.data.objects.get(k + ".root")
        if ob is None:
            continue
        try:
            area = importlib.import_module("sect.areas." + k).AREA
        except Exception as exc:
            log("WARN area", k, "did not import:", exc)
            continue
        mw = ob.matrix_world
        yaw = mw.to_euler().z
        d = dict(anchor=tuple(mw.translation), fp=float(area.get("footprint", 45.0)))
        for kind in ("arrival", "depart"):
            v = area.get(kind)
            if v is None:
                continue
            p = mw @ Vector(tuple(v[:3]))
            h = float(v[3]) + yaw if len(v) > 3 else None
            d[kind] = (tuple(p), (math.cos(h), math.sin(h)) if h is not None else None)
        out[k] = d
    return out


def _link_bounds(name, pad=10.0, extra=()):
    lo, hi = [1e9, 1e9], [-1e9, -1e9]
    for ob in bpy.data.objects:
        if not (ob.name == name or ob.name.startswith(name + ".")) or ob.type != 'MESH':
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = [min(lo[0], w.x), min(lo[1], w.y)]
            hi = [max(hi[0], w.x), max(hi[1], w.y)]
    for p in extra:
        lo = [min(lo[0], p[0]), min(lo[1], p[1])]
        hi = [max(hi[0], p[0]), max(hi[1], p[1])]
    return (lo[0] - pad, hi[0] + pad, lo[1] - pad, hi[1] + pad)


def _doors_in(doors, b):
    return [d for d in doors if b[0] <= d[1] <= b[1] and b[2] <= d[2] <= b[3]]


def _classify_doors(rep, info):
    """Split failing doors into real fails and upper-storey balcony doors."""
    ok_z = {}
    for d in rep["doors"]:
        if d["ok"]:
            b = info.get(d["name"], "?")
            ok_z[b] = min(ok_z.get(b, 1e9), d["at"][2])
    fails, upper = [], []
    for d in rep["doors"]:
        if d["ok"]:
            continue
        b = info.get(d["name"], "?")
        (upper if d["at"][2] >= ok_z.get(b, 1e9) + 2.0 else fails).append(
            dict(name=d["name"], building=b, at=d["at"], why=d["why"]))
    return fails, upper


def run_area(smp, doors, info, markers, key, P, rise, hop):
    a = P[key]
    ax, ay, _ = a["anchor"]
    R = a["fp"] + 16.0
    b = [ax - R, ax + R, ay - R, ay + R]
    if key == "gate":                       # the grand stair down to its foot
        b[2] = min(b[2], a["arrival"][0][1] - 10.0)
    start = a["arrival"][0] if "arrival" in a else (ax, ay, a["anchor"][2])
    rep = W.analyse(W.subset(smp.cells, smp.step, b), smp.step, start, _doors_in(doors, b), markers,
                    max_rise=rise, open_edge=smp.open_edge, hop=hop)
    if "error" in rep:
        return dict(area=key, rise=rise, error=rep["error"], start=start)
    fails, upper = _classify_doors(rep, info)
    mine = [c for c in rep["connectors"] if c["name"].startswith(key + ".")]
    own = [dict(name=c["name"], why=c.get("why", ""), pieces=c["pieces"], pieces_reached=c["pieces_reached"],
                worst_at=c.get("worst_at"))
           for c in mine if c["pieces_reached"] < c["pieces"]]
    split = [c["name"] for c in mine if not c["ok"] and c["pieces_reached"] == c["pieces"]]
    dep = a.get("depart")
    dep_ok = bool(rep["_reach"](*dep[0], r=2.5, dz=1.0)) if dep else None
    orph = _sort_orphans(smp, rep["orphans"])
    res = dict(area=key, rise=rise, start=[round(v, 2) for v in start], bounds=[round(v, 1) for v in b],
               floor_m2=rep["main_area_m2"], doors=len(rep["doors"]),
               doors_ok=sum(1 for d in rep["doors"] if d["ok"]), door_fails=fails, upper_doors=upper,
               depart_reached=dep_ok, connectors_failing=own, connectors_split_but_reached=split,
               orphans_open=orph["open"][:12], n_orphans_open=len(orph["open"]),
               n_orphans_covered=len(orph["covered"]), n_orphans_rock=len(orph["rock"]),
               orphans_covered=orph["covered"][:12], orphans_rock=orph["rock"][:6])
    return res


ROCK_WORDS = ("ridge", "cliff", "pinnacle", "rock", "boulder", "underside")


def _sort_orphans(smp, orphans):
    """open (sky over most samples: a real patch nobody can reach), covered (under a roof or
    sampled inside a solid) and rock (natural rock: cliffs, ridges)."""
    out = dict(open=[], covered=[], rock=[])
    for o in orphans:
        o = dict(o)
        smpl = o.pop("samples", [])
        cov = sum(1 for p in smpl if smp.covered(*p)) / max(len(smpl), 1)
        o["covered"] = round(cov, 2)
        if all(any(w in ow for w in ROCK_WORDS) for ow in o["owners"]):
            out["rock"].append(o)
        elif cov >= 0.6:
            out["covered"].append(o)
        else:
            out["open"].append(o)
    return out


def run_link(smp, markers, ka, kb, P, rise, hop):
    name = "world.link.%s_%s" % (ka, kb)
    dep, arr = P[ka].get("depart"), P[kb].get("arrival")
    if dep is None or arr is None:
        return dict(link=name, rise=rise, error="no depart / arrival")
    b = _link_bounds(name, extra=(dep[0], arr[0]))
    rep = W.analyse(W.subset(smp.cells, smp.step, b), smp.step, dep[0], (), markers, max_rise=rise,
                    open_edge=smp.open_edge, hop=hop)
    if "error" in rep:
        return dict(link=name, rise=rise, error=rep["error"], start=dep[0])
    c = next((c for c in rep["connectors"] if c["name"] == name), None)
    reach = rep["_reach"]
    hd, ha = dep[1], arr[1]

    def inward(p, h, s):
        return (p[0] + h[0] * s, p[1] + h[1] * s, p[2])

    into_a = any(reach(*inward(dep[0], hd, -s), r=1.5, dz=0.6) for s in (2.0, 3.0, 4.0)) if hd else None
    into_b = any(reach(*inward(arr[0], ha, s), r=1.5, dz=0.6) for s in (2.0, 3.0, 4.0)) if ha else None
    hops = {}
    for cell in W.subset(smp.cells, smp.step, b).values():
        for z, o in cell:
            if W.is_hop(o) and o.startswith(name):
                h = hops.setdefault(o, [0, 0.0])
                h[0] += 1
                h[1] += z
    res = dict(link=name, rise=rise, bounds=[round(v, 1) for v in b],
               stones=sorted((o, n, round(zs / n, 2)) for o, (n, zs) in hops.items()),
               depart=[round(v, 2) for v in dep[0]], arrival=[round(v, 2) for v in arr[0]],
               arrival_reached=bool(reach(*arr[0], r=2.0, dz=0.8)), back_into_depart_area=into_a,
               into_arrival_area=into_b, hop_links=rep.get("hop_links", 0))
    if c is None:
        res.update(pieces=0, ok=False, why="link not found in the floor samples")
    else:
        res.update(pieces=c["pieces"], pieces_reached=c["pieces_reached"], cells=c["cells"],
                   why=c.get("why", ""), ends=c["ends"], worst_at=c.get("worst_at"))
    # pass: the arrival is reached from the depart, the link joins both areas' floors, and every
    # standable piece of the link is reached (a piece can be a side terrace reached through the
    # rest pavilion standing on it; 'pieces' says how many)
    res["ok"] = bool(c is not None and c["pieces_reached"] == c["pieces"] and res["arrival_reached"]
                     and into_a is not False and into_b is not False)
    return res


def run_global(smp, doors, info, markers, rise, hop, P=None):
    rep = W.analyse(smp.cells, smp.step, (0.0, 0.0, 40.0), doors, markers, max_rise=rise,
                    open_edge=smp.open_edge, hop=hop)
    if "error" in rep:
        return dict(rise=rise, error=rep["error"])
    ports_reached = {}
    for k, a in (P or {}).items():
        for kind in ("arrival", "depart"):
            if kind in a:
                ports_reached["%s.%s" % (k, kind)] = bool(rep["_reach"](*a[kind][0], r=2.5, dz=1.0))
    fails, upper = _classify_doors(rep, info)
    by_area = {}
    for d in rep["doors"]:
        k = info.get(d["name"], "?").split(".")[0]
        t = by_area.setdefault(k, [0, 0])
        t[0] += 1
        t[1] += 1 if d["ok"] else 0
    return dict(rise=rise, floor_m2=rep["main_area_m2"], doors=len(rep["doors"]), ports_reached=ports_reached,
                doors_ok=sum(1 for d in rep["doors"] if d["ok"]), by_area=by_area,
                door_fails=fails, upper_doors=upper, n_orphans=len(rep["orphans"]),
                orphans=rep["orphans"][:30])


def main(argv):
    opts = dict(rises="0.7,0.45", json=None, areas=None, links=None, step="0.5")
    flags = set()
    k = 0
    while k < len(argv):
        if argv[k] in ("--no-global", "--no-hop"):
            flags.add(argv[k])
            k += 1
            continue
        opts[argv[k].lstrip("-").replace("-", "_")] = argv[k + 1]
        k += 2
    t0 = time.perf_counter()
    smp, doors, info, markers = W.scan(float(opts["step"]))
    log("scan %.1f s" % (time.perf_counter() - t0))
    P = ports()
    hop = None if "--no-hop" in flags else dict(is_hop=W.is_hop)
    areas = opts["areas"].split(",") if opts["areas"] else [k for k in ORDER if k in P]
    pairs = list(zip(ORDER, ORDER[1:]))
    if opts["links"]:
        want = set(opts["links"].split(","))
        pairs = [p for p in pairs if "%s_%s" % p in want]
    elif opts["areas"]:
        pairs = []
    out = dict(ports={k: {kk: vv for kk, vv in v.items()} for k, v in P.items()}, runs=[])
    for rise in [float(r) for r in opts["rises"].split(",")]:
        if "--no-global" not in flags and not opts["areas"] and not opts["links"]:
            t = time.perf_counter()
            g = run_global(smp, doors, info, markers, rise, hop, P)
            out["runs"].append(dict(kind="global", **g))
            pr = g.get("ports_reached", {})
            log("global rise %.2f: doors %s/%s reachable from the gate plaza (+%d upper-storey), by area %s | "
                "arrival/depart points reached %d/%d %s (%.0f s)"
                % (rise, g.get("doors_ok"), g.get("doors"), len(g.get("upper_doors", [])), json.dumps(g.get("by_area")),
                   sum(pr.values()), len(pr), [k for k, v in pr.items() if not v], time.perf_counter() - t))
        for key in areas:
            r = run_area(smp, doors, info, markers, key, P, rise, hop)
            out["runs"].append(dict(kind="area", **r))
            if "error" in r:
                log("area %s rise %.2f ERROR %s" % (key, rise, r["error"]))
                continue
            log("area %s rise %.2f: doors %d/%d (+%d upper-storey) | depart reached %s | connector pieces unreached %d"
                " (split but reached %d) | orphans open %d, covered %d, rock %d | floor %.0f m2"
                % (key, rise, r["doors_ok"], r["doors"] - len(r["upper_doors"]), len(r["upper_doors"]),
                   r["depart_reached"], len(r["connectors_failing"]), len(r["connectors_split_but_reached"]),
                   r["n_orphans_open"], r["n_orphans_covered"], r["n_orphans_rock"], r["floor_m2"]))
            for d in r["door_fails"]:
                log("   door FAIL %s at %s: %s" % (d["name"], d["at"], d["why"]))
            for c in r["connectors_failing"]:
                log("   connector FAIL %s: %d of %d pieces reached; %s; near %s"
                    % (c["name"], c["pieces_reached"], c["pieces"], c["why"], c["worst_at"]))
            for o in r["orphans_open"][:8]:
                log("   orphan open %.0f m2 at %s %s%s" % (o["area_m2"], o["centre"], o["owners"],
                                                         " HAS DOOR" if o["has_door"] else ""))
        for ka, kb in pairs:
            if ka not in P or kb not in P:
                continue
            r = run_link(smp, markers, ka, kb, P, rise, hop)
            out["runs"].append(dict(kind="link", **r))
            if "error" in r:
                log("link %s rise %.2f ERROR %s" % (r["link"], rise, r["error"]))
                continue
            log("link %s rise %.2f: %s | pieces %s | arrival reached %s | joins depart area %s | joins arrival area %s | %s"
                % (r["link"], rise, "PASS" if r["ok"] else "FAIL", r.get("pieces"), r["arrival_reached"],
                   r["back_into_depart_area"], r["into_arrival_area"], r.get("why", "")))
            for e in r.get("ends", []):
                if not e["ok"]:
                    log("   end at %s %s" % (e["at"], e["why"]))
            if r.get("worst_at"):
                log("   worst break near %s" % (r["worst_at"],))
            if r.get("stones"):
                log("   stones (owner, cells, mean z): %s" % (r["stones"],))
    log("done %.1f s" % (time.perf_counter() - t0))
    if opts["json"]:
        with open(opts["json"], "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
