"""Far-tree plant lists for the page's crown shells: instances.json -> client/public/sect/full/veg/.

Reads the Blender export blender/xianxia-sect/out/web/full/veg/instances.json (every plant's foot, size,
yaw, sun and family, per chunk) and writes one little-endian binary per chunk, <chunk>.veg, and an
index.json beside them. The page (client/src/lib/sect/veg.ts parseVeg) draws each file's card plants
as lit crown shells on the High tier.

<chunk>.veg:
  16-byte header: b"SVEG", uint32 version (1), uint32 count, uint32 0
  count records of 24 bytes: float32 x, y, z in three.js / glTF coordinates (x = bx, y = bz, z = -by),
  float32 height, float32 radius, uint8 yaw (0-255 = 0-2 pi; the axis swap is a rotation, so Blender's
  yaw about +z is the same angle about three's +y), uint8 sun (0-255 = 0-1), uint8 family (index into
  index.json "families"), uint8 flags (bit 0: the baked files draw it as a near mesh, bit 1: it is part
  of a click target).
index.json: {"version": 1, "families": [...], "chunks": {"<id>": {"file": "<id>.veg", "count": n,
  "cards": n_cards}}}

Only the kinds the page draws go in (pine, shrub, bamboo, blossom); grass, lotus and the rest are
dropped and counted. Stale .veg files in the destination are removed; index.json is written last.

    python blender/xianxia-sect/tools/sect_veg.py [--src <folder or instances.json>] [--dst <folder>]
    python blender/xianxia-sect/tools/sect_veg.py --selftest

Plain Python 3 (no Blender, no third-party modules). Exits non-zero on malformed input.
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                  # blender/xianxia-sect
REPO = os.path.dirname(os.path.dirname(ROOT))
SRC = os.path.join(ROOT, "out", "web", "full", "veg")
DST = os.path.join(REPO, "client", "public", "sect", "full", "veg")

VERSION = 1
KINDS = ("pine", "shrub", "bamboo", "blossom")
REQUIRED = ("x", "y", "z", "yaw", "height", "radius", "sun", "family", "mesh", "hotspot")
HEADER = struct.Struct("<4sIII")
RECORD = struct.Struct("<5f4B")
FLAG_MESH = 1
FLAG_HOTSPOT = 2
CHUNK_ID = re.compile(r"^[a-z0-9_-]+$")


class VegError(Exception):
    """Malformed input."""


def yaw_byte(yaw):
    """Radians about Blender's +z (= three's +y) to 0-255 (256 wraps to 0)."""
    t = (yaw / (2.0 * math.pi)) % 1.0
    return int(round(t * 256.0)) % 256


def sun_byte(sun):
    return int(round(min(max(sun, 0.0), 1.0) * 255.0))


def kind_of(family):
    return family.split(".", 1)[0]


def _num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise VegError("%s: not a finite number (%r)" % (what, v))
    return float(v)


def convert(data):
    """instances.json (parsed) -> ({chunk: bytes}, index dict, [summary rows]). Raises VegError."""
    if not isinstance(data, dict):
        raise VegError("top level: not an object")
    cols = data.get("columns")
    fams = data.get("families")
    chunks = data.get("chunks")
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        raise VegError("columns: not a list of names")
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise VegError("columns: missing %s" % ", ".join(missing))
    if not isinstance(fams, list) or not all(isinstance(f, str) for f in fams):
        raise VegError("families: not a list of names")
    if not isinstance(chunks, dict) or not chunks:
        raise VegError("chunks: not an object of rows")
    at = {c: cols.index(c) for c in REQUIRED}
    width = len(cols)
    keep_fam = [kind_of(f) in KINDS for f in fams]

    # First pass: validate every row, pick the kept ones.
    picked = {}
    used = set()
    summary = []
    for cid in sorted(chunks):
        rows = chunks[cid]
        if not isinstance(cid, str) or not CHUNK_ID.match(cid):
            raise VegError("chunk id %r: use lower-case letters, digits, '-' and '_'" % (cid,))
        if not isinstance(rows, list):
            raise VegError("chunk %s: rows must be a list" % cid)
        kept, dropped = [], {}
        for i, row in enumerate(rows):
            where = "chunk %s row %d" % (cid, i)
            if not isinstance(row, list) or len(row) != width:
                raise VegError("%s: want %d values" % (where, width))
            vals = {c: _num(row[at[c]], "%s %s" % (where, c)) for c in REQUIRED}
            fi = vals["family"]
            if fi != int(fi) or not 0 <= fi < len(fams):
                raise VegError("%s: family %r is not an index into families" % (where, row[at["family"]]))
            fi = int(fi)
            if vals["height"] < 0 or vals["radius"] < 0:
                raise VegError("%s: negative height or radius" % where)
            if not keep_fam[fi]:
                k = kind_of(fams[fi])
                dropped[k] = dropped.get(k, 0) + 1
                continue
            kept.append((vals, fi))
            used.add(fi)
        picked[cid] = kept
        summary.append((cid, len(rows), kept, dropped))

    order = sorted(used)
    if len(order) > 256:
        raise VegError("%d families kept; the family byte holds 256" % len(order))
    remap = {old: new for new, old in enumerate(order)}

    files, index_chunks, report = {}, {}, []
    for cid, n_rows, kept, dropped in summary:
        buf = bytearray(HEADER.pack(b"SVEG", VERSION, len(kept), 0))
        cards = 0
        for v, fi in kept:
            flags = (FLAG_MESH if v["mesh"] != 0 else 0) | (FLAG_HOTSPOT if v["hotspot"] > 0 else 0)
            if not flags & FLAG_MESH:
                cards += 1
            buf += RECORD.pack(v["x"], v["z"], -v["y"], v["height"], v["radius"],
                               yaw_byte(v["yaw"]), sun_byte(v["sun"]), remap[fi], flags)
        files[cid] = bytes(buf)
        index_chunks[cid] = {"file": cid + ".veg", "count": len(kept), "cards": cards}
        report.append(dict(chunk=cid, rows=n_rows, kept=len(kept), cards=cards, mesh=len(kept) - cards,
                           dropped=dropped))
    index = {"version": VERSION, "families": [fams[i] for i in order], "chunks": index_chunks}
    return files, index, report


def load(src):
    path = src if src.lower().endswith(".json") else os.path.join(src, "instances.json")
    if not os.path.isfile(path):
        raise VegError("%s: no such file" % path)
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh), path
        except ValueError as e:
            raise VegError("%s: not JSON (%s)" % (path, e))


def write(dst, files, index):
    """Writes every <chunk>.veg (each through a .part file), removes stale .veg files, then index.json."""
    os.makedirs(dst, exist_ok=True)
    for cid, data in files.items():
        p = os.path.join(dst, cid + ".veg")
        with open(p + ".part", "wb") as fh:
            fh.write(data)
        os.replace(p + ".part", p)
    removed = []
    for fn in sorted(os.listdir(dst)):
        if fn.endswith(".veg") and fn[:-4] not in files:
            os.remove(os.path.join(dst, fn))
            removed.append(fn)
    p = os.path.join(dst, "index.json")
    with open(p + ".part", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
        fh.write("\n")
    os.replace(p + ".part", p)
    return removed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", default=SRC, help="folder holding instances.json, or the file (default: %(default)s)")
    ap.add_argument("--dst", default=DST, help="output folder (default: %(default)s)")
    ap.add_argument("--selftest", action="store_true", help="convert a tiny made-up file and check the bytes")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        data, path = load(a.src)
        files, index, report = convert(data)
    except VegError as e:
        print("sect_veg: %s" % e, file=sys.stderr)
        return 2
    removed = write(a.dst, files, index)
    print("sect_veg: %s -> %s" % (path, a.dst))
    tot = dict(rows=0, kept=0, cards=0, mesh=0)
    drop_all = {}
    for r in report:
        drop = ", ".join("%s %d" % kv for kv in sorted(r["dropped"].items())) or "-"
        print("  %-10s rows %6d  kept %6d  cards %6d  mesh %5d  dropped: %s"
              % (r["chunk"], r["rows"], r["kept"], r["cards"], r["mesh"], drop))
        for k in tot:
            tot[k] += r[k]
        for k, n in r["dropped"].items():
            drop_all[k] = drop_all.get(k, 0) + n
    print("  %-10s rows %6d  kept %6d  cards %6d  mesh %5d  dropped: %s"
          % ("all", tot["rows"], tot["kept"], tot["cards"], tot["mesh"],
             ", ".join("%s %d" % kv for kv in sorted(drop_all.items())) or "-"))
    print("  families kept: %d; sun_missing in the export: %s; removed stale: %s"
          % (len(index["families"]), data.get("sun_missing", "?"), ", ".join(removed) or "nothing"))
    return 0


# ---- selftest ------------------------------------------------------------------------------------------

def selftest():
    cols = ["x", "y", "z", "yaw", "height", "radius", "scale_z", "sun", "family", "mesh", "hotspot", "d"]
    fams = ["bamboo.culm.v0", "grass.v2", "pine.huangshan.v1", "lotus.bud.v0", "shrub.green.v1.low", "blossom.peach.v0"]
    data = {
        "columns": cols,
        "families": fams,
        "hotspots": ["mirror-blossom"],
        "chunks": {
            "gate": [
                [10.0, 20.0, 30.0, math.pi / 2, 12.0, 4.0, 1.0, 0.75, 2, 0, 0, 55.0],    # pine card
                [-5.5, 1.25, 7.0, -math.pi / 2, 3.0, 1.0, 1.0, 1.4, 4, 1, 1, 12.0],     # shrub mesh, click target
                [0.0, 0.0, 0.0, 0.0, 0.4, 0.2, 1.0, 1.0, 1, 0, 0, 3.0],                  # grass: dropped
                [1.0, 2.0, 3.0, 7.0 * math.pi, 9.0, 0.5, 1.0, -0.2, 0, 0, 0, 80.0],      # bamboo card
            ],
            "backdrop": [
                [100.0, -200.0, 50.0, 0.0, 6.0, 3.0, 1.0, 0.5, 5, 0, 0, 900.0],         # blossom card
                [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 3, 0, 0, 900.0],                # lotus: dropped
            ],
        },
        "counts": {},
        "sun_missing": 0,
    }

    def check(ok, what):
        if not ok:
            raise AssertionError(what)

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src")
        dst = os.path.join(tmp, "dst")
        os.makedirs(src)
        os.makedirs(dst)
        with open(os.path.join(dst, "old.veg"), "wb") as fh:
            fh.write(b"stale")
        with open(os.path.join(src, "instances.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        check(main(["--src", src, "--dst", dst]) == 0, "conversion failed")
        with open(os.path.join(dst, "index.json"), encoding="utf-8") as fh:
            index = json.load(fh)
        check(index["version"] == 1, "index version")
        check(index["families"] == ["bamboo.culm.v0", "pine.huangshan.v1", "shrub.green.v1.low", "blossom.peach.v0"],
              "kept families %r" % index["families"])
        check(index["chunks"]["gate"] == {"file": "gate.veg", "count": 3, "cards": 2}, "gate %r" % index["chunks"]["gate"])
        check(index["chunks"]["backdrop"] == {"file": "backdrop.veg", "count": 1, "cards": 1}, "backdrop entry")
        check(not os.path.exists(os.path.join(dst, "old.veg")), "stale file kept")
        with open(os.path.join(dst, "gate.veg"), "rb") as fh:
            raw = fh.read()
        check(len(raw) == 16 + 3 * 24, "gate.veg is %d bytes" % len(raw))
        magic, version, count, zero = HEADER.unpack_from(raw, 0)
        check((magic, version, count, zero) == (b"SVEG", 1, 3, 0), "header %r" % ((magic, version, count, zero),))
        recs = [RECORD.unpack_from(raw, 16 + i * 24) for i in range(3)]
        # Rows keep their order: pine, shrub, bamboo.
        x, y, z, h, r, yaw, sun, fam, flags = recs[0]
        check((x, y, z) == (10.0, 30.0, -20.0), "pine coords %r" % ((x, y, z),))
        check((h, r) == (12.0, 4.0), "pine size")
        check(yaw == 64 and sun == round(0.75 * 255) and fam == 1 and flags == 0, "pine bytes %r" % (recs[0][5:],))
        x, y, z, h, r, yaw, sun, fam, flags = recs[1]
        check((x, y, z) == (-5.5, 7.0, -1.25), "shrub coords %r" % ((x, y, z),))
        check(yaw == 192 and sun == 255 and fam == 2 and flags == FLAG_MESH | FLAG_HOTSPOT, "shrub bytes %r" % (recs[1][5:],))
        yaw, sun, fam, flags = recs[2][5:]
        check(yaw == 128 and sun == 0 and fam == 0 and flags == 0, "bamboo bytes %r" % (recs[2][5:],))
        with open(os.path.join(dst, "backdrop.veg"), "rb") as fh:
            raw = fh.read()
        check(HEADER.unpack_from(raw, 0)[2] == 1 and RECORD.unpack_from(raw, 16)[7] == 3, "backdrop blossom")
        # Malformed input exits non-zero and leaves the output as it was.
        bad = dict(data, chunks={"gate": [[1.0, 2.0]]})
        with open(os.path.join(src, "instances.json"), "w", encoding="utf-8") as fh:
            json.dump(bad, fh)
        check(main(["--src", src, "--dst", dst]) != 0, "short row accepted")
        check(os.path.isfile(os.path.join(dst, "gate.veg")), "output removed by a failed run")
        for broken in (dict(data, columns=cols[:-5]), dict(data, families="x"),
                       dict(data, chunks={"gate": [[0.0] * 8 + [99, 0, 0, 0]]}),
                       dict(data, chunks={"gate": [[float("nan")] + [0.0] * 11]}),
                       dict(data, chunks={"Gate!": []})):
            try:
                convert(broken)
            except VegError:
                continue
            raise AssertionError("malformed input accepted: %r" % (broken,))
        check(main(["--src", os.path.join(tmp, "nowhere"), "--dst", dst]) != 0, "missing file accepted")
    print("sect_veg selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
