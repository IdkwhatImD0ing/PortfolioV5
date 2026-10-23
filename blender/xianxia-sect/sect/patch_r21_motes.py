"""Round 21, lane 'motes': the jade slip's and the library's spirit motes come out of an existing out/sect_chase.blend,
so it matches what a fresh build of the current source makes (areas/scroll.py and areas/library.py no longer call
props.spirit_motes). Run on the cloud box, on a copy first, before the next audit and bake, and before the round 15
jade-slip restore (sect/patch_r15_scroll_restore.py refuses a file that still has scroll.motes):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b         E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1         --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r21_motes.py [-- DRY_RUN=1]

Why (owner, 2026-10-23): "Why is there a bunch of random white dots on top of the jade slip". scroll.motes (260 ico
spheres 3-7 cm across, in a 24 x 8 m box up to 19 m over the terrace) and library.motes (260 of 4-9 cm around the
pagoda, up to 4 m under its top) drift with scene time in Blender, but bake_web bakes them where they stand (glow class
'mote', strength 1.6): on the web they were still, near-white, 1-3 px specks spread across the sky over both stops (and
a few strays in the steles and formation chunks). The page already drops the class (client lib/sect/life.ts
isBakedMote, app/sect/experience/prepare.ts) and draws its own rising qi off the jade slip (life.ts relic clusters):
this takes them out at the source, so the next pack carries no '.glow.mote' meshes at all.

Each name is idempotent: a file without it says 'unchanged', and a file without either says 'PATCH nothing changed: not
saving'. Checks (any failure stops before saving; DRY_RUN=1 runs everything and never saves):
- each object found is a props.spirit_motes point instancer (a 'props_instancer' geometry-nodes modifier whose Object
  Info places a prototype in a 'props_mote' material) with no children;
- afterwards no object of those names is left, and the evaluated scene holds no 'props_mote' instance from them. Any
  other owner of a 'props_mote' instance is listed as a WARNING (the web drops every '.glow.mote' face, so it would
  vanish there);
- the object count drops by exactly the objects removed.
Prints 'PATCH DIGEST <md5>' (the two names' state and every props_mote owner left: the same after a first and a second
run) and 'PATCH CACHES ok' (objects removed only, which the export caches ignore; re-bake the scroll, library, steles
and formation chunks, where the motes' specks were).

The round 15 restore (scratchpad r15/PENDING_jade_restore.md) said "rings and motes follow" the scroll: with this, there
are no scroll.motes to move.
"""
import hashlib
import sys
import time

import bpy

NAMES = ("scroll.motes", "library.motes")
MOTE_MAT = "props_mote"


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r21_motes: unknown option %r (DRY_RUN=1)" % a)
    return dry


def mote_proto(ob):
    """The prototype a props.spirit_motes instancer places (its 'props_instancer' group's Object Info), else None."""
    if ob.type != 'MESH':
        return None
    for md in ob.modifiers:
        if md.type != 'NODES' or md.name != "props_instancer" or md.node_group is None:
            continue
        for nd in md.node_group.nodes:
            if nd.bl_idname != "GeometryNodeObjectInfo":
                continue
            proto = nd.inputs["Object"].default_value
            if proto is not None and proto.type == 'MESH' and any(m is not None and MOTE_MAT in m.name
                                                                  for m in proto.data.materials):
                return proto
    return None


def mote_owners():
    """{owner name: instance count} of every evaluated instance drawn in a spirit-mote material."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    owners = {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH' or not any(s.material is not None and MOTE_MAT in s.material.name
                                         for s in ob.material_slots):
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent is not None else ob.original.name
        owners[own] = owners.get(own, 0) + 1
    return owners


def digest(after):
    """md5 of the two names' state (present: its mesh name and modifiers; else 'gone') and of every props_mote owner
    left with its instance count."""
    h = hashlib.md5()
    for nm in NAMES:
        ob = bpy.data.objects.get(nm)
        h.update(("gone:%s;" % nm if ob is None else "%s:%s:%s;" % (
            nm, ob.data.name if ob.data else None, [m.name for m in ob.modifiers])).encode())
    for own, k in sorted(after.items()):
        h.update(("%s=%d;" % (own, k)).encode())
    return h.hexdigest()


def main():
    t0 = time.time()
    dry = options()
    fails = []
    n_obj0 = len(bpy.data.objects)
    before = mote_owners()
    log("mote instances before:", sum(before.values()), before)
    removed = []
    for nm in NAMES:
        ob = bpy.data.objects.get(nm)
        if ob is None:
            log(nm, "unchanged (not in the file)")
            continue
        if mote_proto(ob) is None:
            fails.append("%s is not a props.spirit_motes instancer: left alone" % nm)
            continue
        if len(ob.children):
            fails.append("%s has children %s: left alone" % (nm, [c.name for c in ob.children]))
            continue
        me, groups = ob.data, [md.node_group for md in ob.modifiers if md.type == 'NODES' and md.node_group]
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
        for ng in groups:
            if ng.users == 0:
                bpy.data.node_groups.remove(ng)
        removed.append(nm)
        log(nm, "removed (%d instances)" % before.get(nm, 0))
    after = mote_owners()
    left = [nm for nm in NAMES if bpy.data.objects.get(nm) is not None]
    if left:
        fails.append("still in the file: %s" % left)
    if any(nm in after for nm in NAMES):
        fails.append("mote instances still drawn from %s" % [nm for nm in NAMES if nm in after])
    if after:
        log("WARNING other props_mote instances (the web drops the '.glow.mote' class, so these vanish there):", after)
    log("mote instances after:", sum(after.values()))
    n_obj1 = len(bpy.data.objects)
    if n_obj1 != n_obj0 - len(removed):
        fails.append("objects %d -> %d, expected %+d" % (n_obj0, n_obj1, -len(removed)))
    log("objects %d -> %d (expected %+d)" % (n_obj0, n_obj1, -len(removed)))
    log("DIGEST", digest(after))
    for f in fails:
        log("FAIL", f)
    if fails:
        raise SystemExit("patch_r21_motes: %d check(s) failed, not saving" % len(fails))
    if removed:
        log("CACHES ok: objects removed only %s (the export caches ignore removed names); re-bake the scroll, library, "
            "steles and formation chunks (the motes' specks), then pack" % removed)
    else:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
