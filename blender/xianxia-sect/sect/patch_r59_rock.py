"""Round 59: the rock material rebuilt (docs/scene/rock-r59.md) in an existing out/sect_chase.blend, so it matches what
a fresh build of sect/lib/materials.py makes with ROCK_STRUCT on (_rock_r59: world beds, one set of master joints, one
Bump; the drawn joints, stains and mottle bump gone). Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r59_rock.py -- [MODE=inspect|patch] [DRY_RUN=1] \
        [FORCE=1] [PHOTO_SWAP=1] [<CONSTANT>=<python literal> ...]

MODE=inspect: read only, never saves. Per rock tag (every material whose registered builder is materials._rock): its
materials, node count, images, the photo's triplanar Mapping scale and offsets, the Bump nodes (strength, distance), the
round 59 mark and whether its node tree equals what the repo builds today (ROCK_STRUCT False) or with the new graph.
Also how many objects carry nature_top_radius (the beds stay off there), how many floating rocks bake_web.ROCK_FLAT_RE
finds (bake_web flags them rock_flat), and whether any mesh already has a geo_w attribute.

MODE=patch (the default): every material of every rock tag is rebuilt in place under its own name with its own
registered parameters (materials.register(tag, builder, overwrite=True, ...), as patch_rock_life.py does). No object is
touched: no name, vertex, slot or transform changes, so no audit, no chunk plan and no keep-list change.

Options after '--':
- DRY_RUN=1 runs everything and never saves; FORCE=1 rebuilds even when the shipped trees differ from today's repo.
- <CONSTANT>=<python literal> sets an upper-case constant of sect.lib.materials for this run (a tuning pass), e.g.
  ROCK_STRUCT_BUMP=0.6 "ROCK_BED={'hard': 0.22}" "ROCK_JOINT={'master_w': 0.8}". ROCK_BED, ROCK_JOINT and ROCK_CAVITY
  keep the keys an override leaves out. Write a kept value into materials.py too, or a fresh build will differ.
  ROCK_STRUCT=False rebuilds today's graph: the rollback of a patched file.
  An override of ROCK_SCANS replaces the whole dict, so list every key. The scans it names are checked again after
  the overrides: a missing file stops the patch (scan_image would quietly drop that photo).
- PHOTO_SWAP=1 (round 60, docs/scene/rock-r60.md): a trial of another photo for rock_cliff. The photo check below
  then wants the diff file ROCK_SCANS names for rock_cliff's scan key instead of PHOTO, and the run logs 'PATCH PHOTO
  SWAP rock_cliff reads <file>'. The page's detail.webp is still cut from mtn_cliff, so a file patched this
  way is for stills and test bakes only until the page changes too.
- Any override that changes rock_cliff's photo, its tile or ROCK_SCAN_CONTRAST (PHOTO_SWAP or not) logs 'PATCH PAGE
  WARN ...': the page's rock layers follow the repo's values, so such a bake ships only with the page change.

Fingerprint check first (before any override): each material's node tree (every node's type, settings, input values
to 4 decimals, image files, colour ramps, and every link) against a throwaway build of the same tag. State per material:
'old' (the repo's graph of today, exactly), 'new' (marked rock_struct = materials.ROCK_STRUCT_TAG) or 'differs' (not
marked and not today's graph: an earlier patch ran with an override the repo does not record, or Blender's versioning
changed a node). 'differs' stops the patch with the first differences listed, unless FORCE=1, except on the STALE_OK
tags (the forge's tomb and cairn rock and the flute's stone, which no earlier rock patch rebuilt). A file with both old
and new rock materials stops too. A 'new' material whose tree equals the build asked for is left alone (idempotent: a re-run
prints 'nothing changed: not saving' and the same digest); one that differs (another tuning) is rebuilt.

Checks after the rebuild (any failure stops before saving): every rebuilt material equals a throwaway build of the asked
graph and carries the asked mark; rock_cliff still reads PHOTO, mtn_cliff_diff.jpg (the page's rock layers are cut from
it; with PHOTO_SWAP=1 the photo ROCK_SCANS names for it); no object changed its slots, mesh or matrix; no object, scene
or image appeared or vanished; no scratch data left. After the rebuild it logs rock_cliff's photo tile and offsets
('PATCH photo mapping rock_cliff'). Prints 'PATCH DIGEST <md5>' (every rock material's fingerprint) and
'PATCH CACHES needs bakefull gate,mirror,forge,arena,mission,library,steles,scroll,formation,abode,summit,backdrop'
(with --live: every chunk's live maps go with it).
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import world  # noqa: E402,F401  (registers world_rock_under, world_pier_stone)
from sect.lib import materials as M  # noqa: E402
from sect.lib import nature  # noqa: E402,F401  (registers nature_rock_small)
from sect.areas import forge  # noqa: E402,F401  (registers forge_tomb_rock, forge_cairn_rock)
from sect.lib import flute_props  # noqa: E402,F401  (registers flute_qingshi)

EXPECTED = ("rock_cliff", "world_rock_under", "nature_rock_small", "world_pier_stone", "forge_tomb_rock",
            "forge_cairn_rock", "flute_qingshi")
# tags no earlier rock patch rebuilt (patch_rock_life, patch_nature_look and patch_r48_green import only world and
# nature, so these variants were never in their registry): their trees may be older than today's graph. A difference
# there is listed but does not stop the patch; they are rebuilt like the rest
STALE_OK = ("forge_tomb_rock", "forge_cairn_rock", "flute_qingshi")
SCRATCH = "~r59"
PHOTO = "mtn_cliff_diff.jpg"   # rock_cliff's photo: the page's detail.webp is cut from it (keep it)
CHUNKS = ("gate", "mirror", "forge", "arena", "mission", "library", "steles", "scroll", "formation", "abode", "summit",
          "backdrop")
DEC = 4                        # decimals of the fingerprint's numbers
SHOW = 12                      # differences listed per material when a fingerprint does not match
MARK = "rock_struct"
PILLAR_RE = re.compile(r"^world\.peak\.\d{3}$")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    """(mode, dry, force, swap, overrides as [(name, value)]). Overrides are applied later (after the fingerprints of
    today's graph)."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode, dry, force, swap, over = "patch", False, False, False, []
    for a in argv:
        k, eq, v = a.partition("=")
        if not eq:
            raise SystemExit("patch_r59_rock: not KEY=value: %r" % a)
        if k == "MODE":
            mode = v.strip().lower()
            if mode not in ("inspect", "patch"):
                raise SystemExit("patch_r59_rock: MODE must be inspect or patch")
        elif k == "DRY_RUN":
            dry = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "FORCE":
            force = v.strip().lower() not in ("", "0", "false", "no")
        elif k == "PHOTO_SWAP":
            swap = v.strip().lower() not in ("", "0", "false", "no")
        elif k.isupper() and hasattr(M, k):
            over.append((k, ast.literal_eval(v)))
        else:
            raise SystemExit("patch_r59_rock: unknown option %r (MODE=, DRY_RUN=1, FORCE=1, PHOTO_SWAP=1, or an "
                             "upper-case constant of sect.lib.materials)" % a)
    return mode, dry, force, swap, over


def missing_scans():
    """Scan files the module's constants name (as they are now) that are not in SCAN_DIR."""
    return [f for f in M.scan_files() if not os.path.isfile(os.path.join(M.SCAN_DIR, f))]


def cliff_photo(swap):
    """The diff file rock_cliff must read after the rebuild: PHOTO, or with PHOTO_SWAP the one ROCK_SCANS names for
    its registered scan key (None and the reason when that cannot be read)."""
    if not swap:
        return PHOTO, ""
    try:
        key = M._REGISTRY["rock_cliff"][1]["scan"]
        return M.ROCK_SCANS[key]["diff"], ""
    except (KeyError, TypeError) as e:
        return None, "PHOTO_SWAP: no ROCK_SCANS diff for rock_cliff's scan key (%r)" % (e,)


def page_photo():
    """(diff file, tile, ROCK_SCAN_CONTRAST) of rock_cliff's photo as the module holds it now. Taken before the
    overrides, it is what the page's detail.webp is cut from (prep_textures.mjs and detail.ts follow the repo); None
    when it cannot be read. Only compared and logged."""
    try:
        s = M.ROCK_SCANS[M._REGISTRY["rock_cliff"][1]["scan"]]
        return s["diff"], tuple(s["tile"]), M.ROCK_SCAN_CONTRAST
    except (KeyError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------------------------------- fingerprints

_BASE = None


def _r(v):
    """A setting or socket value as a plain, rounded, comparable value."""
    if isinstance(v, bool) or v is None or isinstance(v, (int, str)):
        return v
    if isinstance(v, float):
        return round(v, DEC)
    if isinstance(v, (set, frozenset)):
        return tuple(sorted(str(x) for x in v))
    try:
        return tuple(_r(x) for x in v)
    except TypeError:
        return str(type(v).__name__)


def _settings(n):
    """A node's own settings (operation, data type, dimensions, attribute name...): its RNA properties beyond the
    ones every shader node has; the image by its file name, a colour ramp by its stops."""
    global _BASE
    if _BASE is None:
        _BASE = {p.identifier for p in bpy.types.ShaderNode.bl_rna.properties}
    out = []
    for p in n.bl_rna.properties:
        k = p.identifier
        if k in _BASE or p.type == 'COLLECTION':
            continue
        try:
            v = getattr(n, k)
        except Exception:
            continue
        if p.type == 'POINTER':
            if k == "image":
                v = (os.path.basename(bpy.path.abspath(v.filepath)) or v.name) if v is not None else None
            elif k == "color_ramp" and v is not None:
                v = (v.interpolation, v.color_mode,
                     tuple((round(e.position, DEC), _r(tuple(e.color))) for e in v.elements))
            else:
                continue
        else:
            v = _r(v)
        out.append((k, v))
    return tuple(out)


def fingerprint(mat):
    """[one entry per node in order: (type, settings, input values)] + [sorted links by node index and socket]."""
    nt = mat.node_tree
    if nt is None:
        return [("no node tree",)]
    idx = {n.as_pointer(): i for i, n in enumerate(nt.nodes)}
    out = []
    for n in nt.nodes:
        ins = tuple((s.identifier, None if s.is_linked or not hasattr(s, "default_value") else _r(s.default_value))
                    for s in n.inputs)
        out.append((n.bl_idname, _settings(n), ins))
    links = sorted((idx.get(l.from_node.as_pointer(), -1), l.from_socket.identifier,
                    idx.get(l.to_node.as_pointer(), -1), l.to_socket.identifier) for l in nt.links)
    out.append(("links", tuple(links)))
    return out


def fp_hash(fp):
    return hashlib.md5(repr(fp).encode()).hexdigest()


def fp_diff(a, b):
    """The first differences between two fingerprints, as readable lines."""
    out = []
    if len(a) != len(b):
        out.append("%d nodes against %d" % (len(a) - 1, len(b) - 1))
    for i, (x, y) in enumerate(zip(a, b)):
        if x == y:
            continue
        if x[0] != y[0]:
            out.append("node %d: %s against %s" % (i, x[0], y[0]))
        elif x[0] == "links":
            sx, sy = set(x[1]), set(y[1])
            out.append("links: %d only in the file %s, %d only in the build %s" % (
                len(sx - sy), sorted(sx - sy)[:3], len(sy - sx), sorted(sy - sx)[:3]))
        else:
            for part, px, py in (("settings", x[1], y[1]), ("inputs", x[2], y[2])):
                dx = [kv for kv in px if kv not in py]
                dy = [kv for kv in py if kv not in px]
                if dx or dy:
                    out.append("node %d %s %s: file %s, build %s" % (i, x[0], part, dx[:3], dy[:3]))
        if len(out) >= SHOW:
            break
    return out


def fresh(tag, struct):
    """Fingerprint of a throwaway build of `tag` with ROCK_STRUCT = struct and the module's constants as they are now
    (removed again; images it loads are the file's own: scan_image uses check_existing)."""
    builder, params = M._REGISTRY[tag]
    m = bpy.data.materials.new("%s.fp.%s" % (SCRATCH, tag))
    m[M.TAG] = tag
    was = M.ROCK_STRUCT
    M.ROCK_STRUCT = struct
    try:
        builder(M.Graph(m), **params)
        return fingerprint(m)
    finally:
        M.ROCK_STRUCT = was
        bpy.data.materials.remove(m)


# ---------------------------------------------------------------------------------------------------- the file

def rock_tags():
    """Tags in this file whose registered builder is materials._rock (EXPECTED ones warned when absent)."""
    present = {m.get(M.TAG) for m in bpy.data.materials if m.get(M.TAG) and m.library is None}
    tags = sorted(t for t in present if t in M._REGISTRY and M._REGISTRY[t][0] is M._rock)
    for t in EXPECTED:
        if t not in tags:
            log("WARN no material tagged", t)
    return tags


def tag_materials(tag):
    """The file's own materials of a tag (not the bake's '@' copies, not linked ones)."""
    return [m for m in bpy.data.materials if m.get(M.TAG) == tag and m.library is None and "@" not in m.name]


def images_of(m):
    if m.node_tree is None:
        return []
    return sorted({os.path.basename(bpy.path.abspath(n.image.filepath)) or n.image.name
                   for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image is not None})


def bumps_of(m):
    if m.node_tree is None:
        return []
    out = []
    for n in m.node_tree.nodes:
        if n.bl_idname == "ShaderNodeBump":
            s, d = n.inputs["Strength"], n.inputs["Distance"]
            out.append(("linked" if s.is_linked else round(s.default_value, 3),
                        "linked" if d.is_linked else round(d.default_value, 3)))
    return out


def photo_mapping(m):
    """The triplanar's Mapping nodes that scale world positions by 1 / tile: [(scale x, scale y, location x, y)]."""
    if m.node_tree is None:
        return []
    out = []
    for n in m.node_tree.nodes:
        if n.bl_idname != "ShaderNodeMapping" or n.inputs["Scale"].is_linked:
            continue
        s = tuple(n.inputs["Scale"].default_value)
        loc = tuple(n.inputs["Location"].default_value)
        if abs(s[2] - 1.0) < 1e-6 and 0.02 < s[0] < 0.6 and 0.02 < s[1] < 0.6:   # rock tiles 1.7-50 m, not moss's 1.5
            out.append((round(1.0 / s[0], 3), round(1.0 / s[1], 3), round(loc[0], 3), round(loc[1], 3)))
    return sorted(set(out))


def snapshot():
    """{object: (matrix 5 dp, mesh name, slot material names)} and the image and scene names."""
    obs = {}
    for ob in bpy.data.objects:
        me = ob.data.name if ob.type == 'MESH' and ob.data is not None else ""
        obs[ob.name] = (np.round(np.array(ob.matrix_world), 5).tobytes(), me,
                        tuple(s.material.name if s.material is not None else "" for s in ob.material_slots))
    return obs, sorted(i.name for i in bpy.data.images), sorted(s.name for s in bpy.data.scenes)


def inspect(tags, today, new):
    """MODE=inspect: what the shipped file holds (read only)."""
    for tag in tags:
        for m in tag_materials(tag):
            fp = fingerprint(m)
            st = "today's graph" if fp == today[tag] else ("the new graph" if fp == new[tag] else "neither")
            log("INSPECT %s %s: nodes %d, mark %s, equals %s; images %s; photo tile and offsets %s; bumps "
                "(strength, distance) %s; users %d" % (tag, m.name, len(m.node_tree.nodes) if m.node_tree else 0,
                                                       m.get(MARK), st, images_of(m), photo_mapping(m), bumps_of(m),
                                                       m.users))
            if st == "neither":
                for line in fp_diff(fp, today[tag]):
                    log("INSPECT   against today's build:", line)
    pillars = [o for o in bpy.data.objects if PILLAR_RE.match(o.name)]
    top_r = [o for o in bpy.data.objects if float(o.get("nature_top_radius", 0.0) or 0.0) > 0.0]
    keys = ("nature_top_z", "nature_top_radius", "nature_bottom_radius", "nature_preset", "nature_lod", "nature_dip",
            "r48_peak")
    log("INSPECT pillars world.peak.NNN %d; with each prop: %s; objects with nature_top_radius > 0: %d (%s)" % (
        len(pillars), {k: sum(1 for o in pillars if k in o.keys()) for k in keys}, len(top_r),
        sorted({o.name.split(".")[0] + "." + o.name.split(".")[1] for o in top_r if "." in o.name})[:12]))
    try:
        from sect import bake_web as BW
        flat = [o.name for o in bpy.data.objects if o.type == 'MESH' and BW.ROCK_FLAT_RE.match(o.name)]
        log("INSPECT floating rocks bake_web flags rock_flat: %d %s" % (len(flat), flat[:8]))
    except Exception as e:      # inspect is read only: say so and go on
        log("WARN could not read bake_web.ROCK_FLAT_RE:", e)
    geo = [me.name for me in bpy.data.meshes if me.attributes.get(M.ROCK_GEO_ATTR) is not None]
    log("INSPECT meshes with a %s attribute: %d %s" % (M.ROCK_GEO_ATTR, len(geo), geo[:6]))


def digest(tags):
    h = hashlib.md5()
    for tag in tags:
        for m in sorted(tag_materials(tag), key=lambda x: x.name):
            h.update(("%s|%s|%s|%s" % (tag, m.name, m.get(MARK), fp_hash(fingerprint(m)))).encode())
    return h.hexdigest()


def main():
    mode, dry, force, swap, over = options()
    t0 = time.time()
    if bpy.data.objects.get("world.root") is None or bpy.data.objects.get("world.range") is None:
        log("NOT SAVED: no world.root / world.range: is this out/sect_chase.blend?")
        raise SystemExit(1)
    missing = missing_scans()
    if missing:
        log("NOT SAVED: scans missing in %s: %s" % (M.SCAN_DIR, missing))
        raise SystemExit(1)
    tags = rock_tags()
    if not tags:
        log("NOT SAVED: no rock material found")
        raise SystemExit(1)
    names0 = set(m.name for m in bpy.data.materials)
    # today's graph, from the repo's constants as they are (no override yet), and the new one
    today = {t: fresh(t, False) for t in tags}
    if mode == "inspect":
        new = {t: fresh(t, True) for t in tags}
        inspect(tags, today, new)
        log("inspect done (%.1f s); nothing saved" % (time.time() - t0))
        return
    page = page_photo()     # the repo's rock photo, tile and contrast: what the page's rock layers are cut from
    for k, v in over:
        setattr(M, k, v)
        log("override", k, "=", repr(getattr(M, k)))
    baked = page_photo()
    # again with the overrides: a ROCK_SCANS override may name a file the box does not have
    missing = missing_scans()
    if missing:
        log("NOT SAVED: after the overrides, scans missing in %s: %s" % (M.SCAN_DIR, missing))
        raise SystemExit(1)
    photo, why = cliff_photo(swap)
    if photo is None:
        log("NOT SAVED:", why)
        raise SystemExit(1)
    struct = bool(M.ROCK_STRUCT)
    want = {t: fresh(t, struct) for t in tags}
    log("round 59 rock: ROCK_STRUCT %s; %s" % (struct, json.dumps(
        {k: getattr(M, k) for k in ("ROCK_BED", "ROCK_JOINT", "ROCK_CAVITY", "ROCK_STRUCT_BUMP", "ROCK_STRUCT_VARIANTS",
                                    "ROCK_GEO_FADE", "ROCK_FLAT_PROPS", "ROCK_SCANS", "ROCK_SCAN_CONTRAST",
                                    "ROCK_SCAN_BUMP", "ROCK_SMALL_SCAN_SCALE")}, default=str)))
    # state per material
    states, todo, stop = {}, [], []
    for tag in tags:
        mats = tag_materials(tag)
        if not mats:
            continue
        st = []
        for m in mats:
            fp = fingerprint(m)
            if m.get(MARK) == M.ROCK_STRUCT_TAG:
                s = "new"
            elif fp == today[tag]:
                s = "old"
            else:
                s = "differs"
                lines = fp_diff(fp, today[tag])
                log("DIFFERS %s %s from today's repo build:" % (tag, m.name))
                for line in lines:
                    log("   ", line)
            st.append((m, s, fp == want[tag]))
        states[tag] = st
        log("state %s: %s" % (tag, ", ".join("%s %s%s" % (m.name, s, " (as asked)" if same else "")
                                             for m, s, same in st)))
        if any(s == "differs" for _m, s, _same in st):
            if tag in STALE_OK:
                log("   %s: expected, no earlier patch rebuilt it (STALE_OK); it is rebuilt with the rest" % tag)
            else:
                stop.append(tag)
        if not all(same for _m, _s, same in st):
            todo.append(tag)
    kinds = {s for st in states.values() for _m, s, _same in st}
    if "old" in kinds and "new" in kinds:
        log("NOT SAVED: the file has both old and round 59 rock materials: %s" % {
            t: [s for _m, s, _same in st] for t, st in states.items()})
        raise SystemExit(1)
    if stop and not force:
        log("NOT SAVED: %s differ from what the repo builds today (listed above). Find the override an earlier patch "
            "used and write it into materials.py, or run with FORCE=1 to rebuild them anyway." % stop)
        raise SystemExit(1)
    if stop:
        log("FORCE: rebuilding %s although they differ from today's repo build" % stop)
    if not todo:
        log("DIGEST", digest(tags))
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    obs0, imgs0, scenes0 = snapshot()
    for tag in todo:
        builder, params = M._REGISTRY[tag]
        mats = tag_materials(tag)
        before = sum(len(m.node_tree.nodes) for m in mats if m.node_tree)
        M.register(tag, builder, overwrite=True, **params)
        log("%s rebuilt %d %s nodes %d -> %d images %s bumps %s params %s" % (
            tag, len(mats), [m.name for m in mats][:4], before, sum(len(m.node_tree.nodes) for m in mats if m.node_tree),
            images_of(mats[0]), bumps_of(mats[0]), params))
    cliff = tag_materials("rock_cliff")
    if cliff:
        log("photo mapping rock_cliff %s: tile and offsets %s" % (cliff[0].name, photo_mapping(cliff[0])))
    fail = []
    for tag in tags:
        for m in tag_materials(tag):
            if fingerprint(m) != want[tag]:
                fail.append("%s %s is not the asked build: %s" % (tag, m.name, fp_diff(fingerprint(m), want[tag])[:3]))
            if (m.get(MARK) == M.ROCK_STRUCT_TAG) != struct:
                fail.append("%s %s mark %s with ROCK_STRUCT %s" % (tag, m.name, m.get(MARK), struct))
    if cliff and photo not in images_of(cliff[0]):
        fail.append("rock_cliff lost %s: %s" % (photo, images_of(cliff[0])))
    elif cliff and swap:
        log("PHOTO SWAP rock_cliff reads %s: detail.webp is cut from mtn_cliff; do not ship this bake without "
            "the page change" % photo)
    if cliff and page and baked and baked != page:   # a new tile or contrast leaves the page out of step too
        log("PAGE WARN rock_cliff's photo is %s at %s m, contrast %s; the page's detail.webp is cut from %s at %s m, "
            "contrast %s: do not ship this bake without the page change" % (baked + page))
    obs1, imgs1, scenes1 = snapshot()
    changed = [n for n in obs0 if n in obs1 and obs0[n] != obs1[n]]
    if changed or set(obs0) != set(obs1):
        fail.append("objects changed %s, appeared %s, vanished %s" % (changed[:6], sorted(set(obs1) - set(obs0))[:6],
                                                                      sorted(set(obs0) - set(obs1))[:6]))
    if imgs0 != imgs1:
        fail.append("images appeared %s or vanished %s" % (sorted(set(imgs1) - set(imgs0))[:6],
                                                          sorted(set(imgs0) - set(imgs1))[:6]))
    if scenes0 != scenes1:
        fail.append("scenes changed")
    left = [m.name for m in bpy.data.materials if m.name.startswith(SCRATCH)]
    if left or set(m.name for m in bpy.data.materials) != names0:
        fail.append("materials appeared or vanished: scratch %s, new %s" % (
            left[:4], sorted(set(m.name for m in bpy.data.materials) - names0)[:4]))
    bad = [im.name for im in bpy.data.images
           if os.path.normpath(bpy.path.abspath(im.filepath)).startswith(M.SCAN_DIR) and not im.size[0]]
    if bad:
        fail.append("scans failed to load: %s" % bad)
    log("objects %d, unchanged %d" % (len(obs1), len(obs1) - len(changed)))
    log("DIGEST", digest(tags))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    log("CACHES needs bakefull %s (with --live: then live_calib, live_bounce and sect_live for every area)"
        % ",".join(CHUNKS))
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
