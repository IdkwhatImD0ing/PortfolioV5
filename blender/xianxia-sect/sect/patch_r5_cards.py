"""Turn the mission wall's 7 glowing jade tablets into the lettered white-jade role boards of sect/areas/mission.py
(_role_boards, _wall_rails) in out/sect_chase.blend and save it. Run on the cloud box:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r5_cards.py [-- DRY_RUN=1]

Needs Georgia Bold and Palatino Linotype Bold in the box's font mirror (from the PC's C:/Windows/Fonts):
    tar cf - -C /c/Windows/Fonts georgiab.ttf palab.ttf | ssh -p <port> root@<host> "tar xf - -C '/C:/Windows/Fonts'"
It stops (no save) when either is missing rather than letter the boards in the YaHei fallback.

Why: the owner could not read the tablets ("light blue cards are hard to read"): 1.3 m portrait jade_glow tablets with
random Daoist idioms behind cyan rune halos, washed out by the bloom. Each role now has a 5.2 x 2.2 m white-jade board
with its employer in Georgia Bold ink (the longest name 4.3 m wide, caps ~0.6 m, ~15 px at the 1600 x 900 hold) over
a cinnabar years line flanked by a cinnabar sun disc in a gold ring and a gold crescent moon (日 + 月 = 明). Only a
thin gold rim line glows (the client's idle wave runs along it). Order = the client's role:0..6 (portfolio-data/experience.ts): top row under the beam Pinterest, Scale
AI, RingCentral, Dispatch AI; lower row on a new rail SlugLoop, X-Camp, Hackathons.

What changes in the file (all in the mission wall's collection, parented to 'mission.wall'):
    mission.role_tablet[.001-.006]  same Empties (names = hotspots role:0..6); each now instances mission.role_proto(i)
                                    (prototype 'props.mission.role.<hash>.v4': role.board, role.gold, role.glyphs,
                                    role.glyph_rim, role.cord) and moves to mission.role_slots(); scale 1
    mission.tablet_halo[.001-.006]  removed (the cyan halos)
    mission.wood_tablet*            removed and rebuilt: 8 a rail in the wall's two lower corners (was 40 a rail
                                    across the whole wall, now behind the lower boards)
    mission.wall.rail*              removed and rebuilt as 4 short corner rails (the old two ran the full width and
                                    stopped short of the posts: they floated)
    mission.wall.board_rail         new: the lower row's rail, post to post
    mission.wall.bracket*           new: gold brackets from the rails back to the board
    the tablets' previous prototypes ('props.tablet.*', or an older 'props.mission.role.*') that nothing instances
    any more are deleted with their meshes.
Material 'M.mission_jade_white' (a jade variant registered by mission.py) is added, or rebuilt in place.

Idempotent: role_proto() reuses the prototype it built, the halos are gone, and the corner rails and wooden tablets are
removed and rebuilt under the same names; a second run reports the same objects and boxes.

Web caches: the boards are far bigger than the tablets and objects are added and removed, so the script prints
'PATCH CACHES STALE' (with each changed box): run 'export_web.py -- chunks,meta --profile full' (the audit) before
re-baking the mission chunk (and the backdrop proxy). Checks before saving (stops on failure): the 7 Empties exist
under mission.wall, each prototype holds the 5 parts with non-empty lettering in the right fonts, triangle caps, and
no new object reaches outside the wall's frame box.
"""
import hashlib
import os
import re
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import mission as MI  # noqa: E402
from sect.lib import materials as MAT  # noqa: E402

WALL = MI.K + ".wall"
TABLETS = [MI.K + ".role_tablet" + ("" if i == 0 else ".%03d" % i) for i in range(7)]
REBUILT = (MI.K + ".wood_tablet", MI.K + ".wall.rail", MI.K + ".wall.board_rail", MI.K + ".wall.bracket")
REMOVED = (MI.K + ".tablet_halo",)
PARTS = ("role.board", "role.gold", "role.glyphs", "role.glyph_rim", "role.cord")
TRI_CAP = {"role.glyphs": 40000, "role.board": 4000, "role.gold": 12000, "role.glyph_rim": 2000, "role.cord": 400}
# the wall's frame in its own space (posts at x +-12.5 r 0.42, base / roof): no new piece may reach outside it
WALL_FRAME = ((-13.0, -1.0, 0.0), (13.0, 1.0, 8.5))
DRY = any(a == "DRY_RUN=1" for a in sys.argv)


def log(*a):
    print("PATCH", *a, flush=True)


def family(base):
    pat = re.compile(r"^%s(\.\d{3})?$" % re.escape(base))
    return sorted((o for o in bpy.data.objects if pat.match(o.name)), key=lambda o: o.name)


def corners(ob, M=None):
    """World (or M-space) corners of an object; an instancer gives its instance collection's mesh corners."""
    M = ob.matrix_world if M is None else M
    pts = []
    if ob.type == 'EMPTY' and ob.instance_type == 'COLLECTION' and ob.instance_collection is not None:
        off = Vector(ob.instance_collection.instance_offset)
        for o in ob.instance_collection.all_objects:
            if o.type == 'MESH':
                pts += [M @ (o.matrix_world @ Vector(c) - off) for c in o.bound_box]
    elif ob.type == 'MESH':
        pts = [M @ Vector(c) for c in ob.bound_box]
    return pts


def box(pts):
    if not pts:
        return None
    return (tuple(round(min(p[k] for p in pts), 3) for k in range(3)),
            tuple(round(max(p[k] for p in pts), 3) for k in range(3)))


def inside(b, outer, tol=1e-3):
    return b is not None and outer is not None and all(b[0][k] >= outer[0][k] - tol and b[1][k] <= outer[1][k] + tol
                                                        for k in range(3))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def remove_objects(obs):
    meshes = {o.data for o in obs if o.type == 'MESH'}
    names = [o.name for o in obs]
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    freed = 0
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
            freed += 1
    return names, freed


def main():
    wall = bpy.data.objects.get(WALL)
    if wall is None:
        raise RuntimeError("%s not found; is this out/sect_chase.blend?" % WALL)
    coll = wall.users_collection[0]
    log("wall", WALL, "collection", coll.name, "location", tuple(round(c, 3) for c in wall.matrix_world.translation))
    for f in (MI.ROLE_FONT, MI.ROLE_FONT_YEARS):
        log("font", f, "->", MI._font_path(f))          # raises when missing
    n_obj = len(bpy.data.objects)
    # ---- before: world boxes of everything this touches
    before = {}
    tabs = []
    for nm in TABLETS:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'EMPTY' or ob.instance_type != 'COLLECTION':
            raise RuntimeError("%s missing or not a collection instance" % nm)
        if ob.parent != wall:
            raise RuntimeError("%s parent is %s, not %s" % (nm, ob.parent.name if ob.parent else None, WALL))
        before[nm] = box(corners(ob))
        tabs.append(ob)
    for base in REBUILT + REMOVED:
        for ob in family(base):
            before[ob.name] = box(corners(ob))
    old_protos = {t.instance_collection for t in tabs}
    log("before: tablets", [(t.name, t.instance_collection.name, tuple(round(c, 3) for c in t.location),
                             round(t.scale.x, 4)) for t in tabs])
    log("before: halos", len(family(REMOVED[0])), "wood tablets", len(family(REBUILT[0])), "rails",
        len(family(REBUILT[1])), "board rails", len(family(REBUILT[2])), "brackets", len(family(REBUILT[3])))
    # ---- 1. role boards: same Empties, new prototypes, new places (the jade variant rebuilt with mission.py's
    # current colours when an earlier run already made it)
    if any(m.get(MAT.TAG) == "mission_jade_white" for m in bpy.data.materials):
        MAT.rebuild("mission_jade_white")
        log("rebuilt material M.mission_jade_white")
    scale = MI.role_text_scale()
    log("lettering: %.4f m per font unit (the widest name %.2f m)" % (scale, MI.ROLE_TEXT_W))
    for (i, x, z), ob in zip(MI.role_slots(), tabs):
        pc = MI.role_proto(i, scale)
        if ob.instance_collection is not pc:
            ob.instance_collection = pc
        ob.location = (x, MI.ROLE_Y, z)
        ob.rotation_euler = (0.0, 0.0, 0.0)
        ob.scale = (1.0, 1.0, 1.0)
        log("role:%d" % i, ob.name, MI.ROLE_BOARDS[i], "->", pc.name, "at", (x, MI.ROLE_Y, z))
    # ---- 2. halos out
    names, freed = remove_objects(family(REMOVED[0]))
    if names:
        log("removed", len(names), "halos", names, "freed meshes", freed)
    # ---- 3. rails and wooden tablets: remove, rebuild
    old = [o for base in REBUILT for o in family(base)]
    names, freed = remove_objects(old)
    log("removed", len(names), "rail / bracket / wooden-tablet objects, freed meshes", freed)
    count = MI._wall_rails(coll, wall, board_front=0.45 - 0.25)
    wall["wood_tablets"] = count
    log("rebuilt: wood tablets", len(family(REBUILT[0])), "(wall['wood_tablets'] = %d)" % count, "rails",
        len(family(REBUILT[1])), "board rails", len(family(REBUILT[2])), "brackets", len(family(REBUILT[3])))
    # ---- 4. old prototypes nothing instances any more
    for pc in old_protos:
        if pc is None or pc in {t.instance_collection for t in tabs}:
            continue
        users = [o.name for o in bpy.data.objects if o.instance_collection == pc]
        if users:
            log("keep prototype", pc.name, "still instanced by", users[:4])
            continue
        nm = pc.name
        _, freed = remove_objects(list(pc.all_objects))
        bpy.data.collections.remove(pc)
        log("deleted prototype", nm, "freed meshes", freed)
    bpy.context.view_layer.update()
    # ---- checks
    fonts = sorted(os.path.basename(f.filepath) for f in bpy.data.fonts if f.users or f.filepath)
    log("fonts in the file", fonts)
    Minv = wall.matrix_world.inverted()
    for i, ob in enumerate(tabs):
        pc = ob.instance_collection
        got = {}
        for o in pc.all_objects:
            for p in PARTS:
                if re.match(r"^props\.%s(\.\d{3})?$" % re.escape(p), o.name):
                    got[p] = o
        miss = [p for p in PARTS if p not in got]
        if miss:
            raise RuntimeError("%s: prototype %s lacks %s" % (ob.name, pc.name, miss))
        for p, o in got.items():
            t = tris(o.data)
            if t > TRI_CAP[p] or t == 0:
                raise RuntimeError("%s %s has %d triangles (cap %d)" % (pc.name, o.name, t, TRI_CAP[p]))
        g = got["role.glyphs"]
        mats = [s.material.name if s.material else None for s in g.material_slots]
        idx = [0] * len(g.data.polygons)
        g.data.polygons.foreach_get("material_index", idx)
        if mats != ["M.ink", "M.lacquer_red"] or 0 not in idx or 1 not in idx:
            raise RuntimeError("%s lettering slots %s / indices %s" % (pc.name, mats, sorted(set(idx))))
        lb = box(corners(ob, Minv @ ob.matrix_world))
        if not inside(lb, WALL_FRAME):
            raise RuntimeError("%s reaches outside the wall frame: %s" % (ob.name, lb))
        log("check role:%d" % i, ob.name, "parts", {p: tris(o.data) for p, o in got.items()},
            "rim glow", got["role.glyph_rim"].get("glow"), "wall-space box", lb)
    for base in REBUILT:
        for ob in family(base):
            lb = box(corners(ob, Minv @ ob.matrix_world))
            if not inside(lb, WALL_FRAME):
                raise RuntimeError("%s reaches outside the wall frame: %s" % (ob.name, lb))
    log("objects", n_obj, "->", len(bpy.data.objects))
    # ---- web caches: every touched name, its old and new world box
    after = {}
    for nm in TABLETS:
        after[nm] = box(corners(bpy.data.objects[nm]))
    for base in REBUILT:
        for ob in family(base):
            after[ob.name] = box(corners(ob))
    stale = []
    for nm in sorted(set(before) | set(after)):
        b0, b1 = before.get(nm), after.get(nm)
        if b1 is None:
            stale.append((nm, "removed"))
        elif b0 is None:
            stale.append((nm, "new", b1))
        elif not inside(b1, b0):
            stale.append((nm, "grew", b0, b1))
    for s in stale:
        if s[0] in TABLETS or s[1] != "new":
            log("box", *s)
    if stale:
        log("CACHES STALE: %d names added, removed or grown (%d removed, %d new, %d grew) - run export_web.py -- "
            "chunks,meta --profile full (the audit) before re-baking the mission chunk and the backdrop"
            % (len(stale), sum(s[1] == "removed" for s in stale), sum(s[1] == "new" for s in stale),
               sum(s[1] == "grew" for s in stale)))
    else:
        log("CACHES ok: names unchanged and every world box inside the old one")
    # fingerprint of the result (names, world boxes, prototypes, part triangles): equal on a second run
    rows = ["%s %r %s" % (nm, after[nm], getattr(bpy.data.objects[nm].instance_collection, "name", "")) for nm in
            sorted(after)]
    for t in tabs:
        rows += ["%s %d" % (o.name, tris(o.data)) for o in sorted(t.instance_collection.all_objects,
                                                                    key=lambda o: o.name)]
    log("STATE", hashlib.md5("\n".join(rows).encode("utf-8")).hexdigest(), "over", len(rows), "rows; objects",
        len(bpy.data.objects), "collections", len(bpy.data.collections), "meshes", len(bpy.data.meshes))
    if DRY:
        log("DRY_RUN=1: not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
