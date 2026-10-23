"""Round 30, lane 'flags': the formation's Five Element Banners 五行旗 get the Wu Xing colours (wood jade green, fire
vermilion, earth imperial yellow, metal moon white, water ink black) in an existing out/sect_chase.blend, so it matches
what a fresh build of sect/areas/formation.py makes with the round-30 source change (lib/materials.py registers
lib/element_flags.CLOTH; formation.ELEMENT_FLAGS names those cloths and _flags dresses them with element_flags.TRIM).
Run on the cloud box, on a copy first:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r30_flags.py [-- DRY_RUN=1]

It works with or without the source change applied: lib/element_flags.register checks materials' registry when the
names are there and registers the same cloths when they are not.

Why (owner, 2026-10-23): "The element flags in the formation should have colors corresponding to the element". At the
hold (frame 1208) the wood flag read slate blue, the earth flag a tan copy of the gold trim and the water flag gold;
lib/element_flags.py has the causes (the site's green tame, the palette's gold = the trim's gold, the water flag's
gold flame teeth) and the choice.

What it does: builds the five cloths 'M.flag_<element>' (materials._cloth, element_flags.CLOTH) and points each flag
cloth's material slots 0 (cloth), 1 (flame teeth) and 2 (character and its ring) at the element's cloth and
element_flags.TRIM; slot 3 (the gold fittings) stays. Object-linked slots, as props.banner sets them. No mesh, object,
transform or modifier changes, so the cloth's geometry (the client's FLAG_FLIES, lib/sect/idle.ts) stays exact.

State: each cloth's slots 0-2 must be either the round-6 ones (OLD: the shared banner palette, trim 'auto') or this
round's; anything else stops the patch. A cloth material already in the file must carry this round's colour,
translucency and sheen (else it is rebuilt in place, and logged). Idempotent: on this round's file it prints 'PATCH
nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- the five flags: root 'formation.flag.<element>' (an Empty under formation.root) with one cloth
  'formation.flag.<element>.cloth' (a mesh, four slots, the 'props_wind' Wave modifier);
- after: every cloth's four slots as wanted (object-linked), its mesh, faces, vertex positions, modifier settings,
  transform and world box as before;
- colours: each cloth in its element's family (wood: green leads, hue 120-160; fire: red, hue under 15 or over 345,
  saturation over 0.7; earth: yellow, hue 40-60, CIELAB dE at least EARTH_GOLD_DE_MIN from cloth_gold, the trim;
  metal: value over 0.85, saturation under 0.08; water: value under 0.15), its character at least CHAR_DE_MIN and its
  flame teeth at least TEETH_DE_MIN from the cloth;
- nothing else: the material slots of every other object, the object count, and no material removed; no scratch data.
Prints 'PATCH CACHES ok' (names, meshes and world boxes kept: vis_cache, chunks and the hotspots stay valid) with the
chunks to re-bake (each cloth's chunk from out/web/full/chunks.npz when the box has it: formation for wood, fire and
earth, abode for metal and water), and 'PATCH DIGEST <md5>' of the five cloths and their materials.
"""
import colorsys
import hashlib
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.lib import element_flags as EF  # noqa: E402
from sect.lib import materials as M  # noqa: E402
from sect.lib import util as U  # noqa: E402

KEY = "formation"
ROOT_EMPTY = "formation.root"
# round 6 (areas/formation.py before round 30): banner palette index, then props.banner trim='auto' (ink on the gold
# and moon-white cloths, else gold) on slots 1 and 2
OLD = {
    "wood": ("banner_2", "cloth_gold", "cloth_gold"),
    "fire": ("banner_0", "cloth_gold", "cloth_gold"),
    "earth": ("banner_1", "banner_7", "banner_7"),
    "metal": ("banner_5", "banner_7", "banner_7"),
    "water": ("banner_7", "cloth_gold", "cloth_gold"),
}
WAVE_ATTRS = ("height", "width", "narrowness", "speed", "time_offset", "start_position_x", "start_position_y",
              "use_x", "use_y", "use_normal", "use_cyclic", "vertex_group")
CHUNKS_NPZ = os.path.join(ROOT, "out", "web", "full", "chunks.npz")
KNOWN_CHUNKS = {"wood": "formation", "fire": "formation", "earth": "formation", "metal": "abode", "water": "abode"}
CHAR_DE_MIN = 45.0         # CIELAB dE76 between a cloth and its character (gold on vermilion: 58, the lowest)
TEETH_DE_MIN = 25.0        # and between a cloth and its flame teeth (indigo on ink black: 33)
EARTH_GOLD_DE_MIN = 12.0   # the earth cloth against the gold trim (round 6's imperial gold: 3; round 30: 19)


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
            raise SystemExit("patch_r30_flags: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


# ------------------------------------------------------------------------------------------------------------ helpers

def tag(m):
    """A material's registered name (its sect_material tag, else its name without 'M.')."""
    if m is None:
        return None
    t = m.get(M.TAG)
    if t:
        return t
    return m.name[len(M.PREFIX):] if m.name.startswith(M.PREFIX) else m.name


def slot_tags(ob):
    return [tag(s.material) for s in ob.material_slots]


def cloth_of(key, fail):
    root = bpy.data.objects.get("%s.flag.%s" % (KEY, key))
    if root is None or root.type != 'EMPTY':
        fail.add("%s.flag.%s not found (or not an Empty): is this out/sect_chase.blend?" % (KEY, key))
        return None
    if root.parent is None or root.parent.name != ROOT_EMPTY:
        fail.add("%s's parent is %s, not %s" % (root.name, root.parent.name if root.parent else None, ROOT_EMPTY))
    cl = [c for c in root.children if c.name.startswith(root.name + ".cloth")]
    if len(cl) != 1 or cl[0].type != 'MESH':
        fail.add("%s has %d cloth children (want one mesh)" % (root.name, len(cl)))
        return None
    ob = cl[0]
    if len(ob.material_slots) != 4:
        fail.add("%s has %d material slots (want 4: cloth, teeth, character, gold)" % (ob.name, len(ob.material_slots)))
    if ob.modifiers.get("props_wind") is None or ob.modifiers["props_wind"].type != 'WAVE':
        fail.add("%s has no 'props_wind' Wave modifier" % ob.name)
    return ob


def mesh_sig(me):
    """Vertex positions (0.1 mm), polygons and material indices of a mesh, hashed."""
    nv = len(me.vertices)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    h = hashlib.md5()
    h.update(np.round(co * 1e4).astype(np.int64).tobytes())
    n = len(me.polygons)
    mi = np.empty(n, np.int64)
    me.polygons.foreach_get("material_index", mi)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    vi = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", vi)
    for a in (mi, lt, vi):
        h.update(a.tobytes())
    return h.hexdigest()


def wave_sig(ob):
    w = ob.modifiers.get("props_wind")
    if w is None:
        return None
    return tuple((a, round(getattr(w, a), 6) if isinstance(getattr(w, a), float) else getattr(w, a)) for a in WAVE_ATTRS)


def world_box(ob):
    from mathutils import Vector
    Mw = ob.matrix_world
    pts = [Mw @ Vector(c) for c in ob.bound_box]
    return (np.array([min(p[k] for p in pts) for k in range(3)]), np.array([max(p[k] for p in pts) for k in range(3)]))


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lab(srgb):
    """CIELAB (D65) of an sRGB colour (0-1)."""
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    xyz = (0.4124 * r + 0.3576 * g + 0.1805 * b, 0.2126 * r + 0.7152 * g + 0.0722 * b,
           0.0193 * r + 0.1192 * g + 0.9505 * b)
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in (xyz[0] / 0.95047, xyz[1], xyz[2] / 1.08883)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e(a, b):
    return sum((x - y) ** 2 for x, y in zip(lab(a), lab(b))) ** 0.5


def reg_colour(name):
    """sRGB (0-1) of a registered material's builder colour (the _cloth 'colour' parameter)."""
    _b, params = M._REGISTRY[name]
    return hexrgb(params["colour"])


def mat_sig(m):
    """What this round sets on a cloth material: its viewport colour (= the builder's colour), the translucency mix
    factor and the Principled sheen weight; rounded."""
    tr = sheen = None
    if m.node_tree is not None:
        for n in m.node_tree.nodes:
            if n.bl_idname == "ShaderNodeMixShader" and not n.inputs["Fac"].is_linked:
                tr = round(n.inputs["Fac"].default_value, 4)
            elif n.bl_idname == "ShaderNodeBsdfPrincipled":
                s = n.inputs.get("Sheen Weight")
                if s is not None and not s.is_linked:
                    sheen = round(s.default_value, 4)
    return tuple(round(c, 4) for c in m.diffuse_color[:3]), tr, sheen


def want_sig(key):
    _name, colour, tr, sheen = EF.CLOTH[key]
    return tuple(round(c, 4) for c in M.rgb(colour)[:3]), round(tr, 4) if tr else None, round(sheen, 4)


def sig_ok(have, want, tol=1e-3):
    """mat_sig against want_sig, to ``tol`` (the file stores floats in single precision)."""
    (c0, t0, s0), (c1, t1, s1) = have, want
    if (t0 is None) != (t1 is None) or (s0 is None) != (s1 is None):
        return False
    vals = list(zip(c0, c1)) + ([(t0, t1)] if t0 is not None else []) + ([(s0, s1)] if s0 is not None else [])
    return all(abs(a - b) <= tol for a, b in vals)


def colour_checks(fail):
    """Each cloth in its element's colour family, its character and flame teeth standing out from it."""
    gold = reg_colour("cloth_gold")
    for key in EF.ORDER:
        name, colour, _tr, _sh = EF.CLOTH[key]
        r, g, b = hexrgb(colour)
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h *= 360
        ok = {
            "wood": g > r and g > b and 120 <= h <= 160,
            "fire": (h < 15 or h > 345) and s > 0.7,
            "earth": 40 <= h <= 60 and delta_e((r, g, b), gold) >= EARTH_GOLD_DE_MIN,
            "metal": v > 0.85 and s < 0.08,
            "water": v < 0.15,
        }[key]
        teeth, ink = EF.TRIM[key]
        de_c, de_t = delta_e((r, g, b), reg_colour(ink)), delta_e((r, g, b), reg_colour(teeth))
        log("colour %s %s %s: hue %.0f, saturation %.2f, value %.2f, dE %.0f from the gold trim; character %s dE %.0f, "
            "flame teeth %s dE %.0f" % (key, name, colour, h, s, v, delta_e((r, g, b), gold), ink, de_c, teeth, de_t))
        if not ok:
            fail.add("%s's cloth %s (hue %.0f, s %.2f, v %.2f) is not in the element's colour family" % (
                key, colour, h, s, v))
        if de_c < CHAR_DE_MIN:
            fail.add("%s's character (%s) is dE %.0f from its cloth, want %.0f" % (key, ink, de_c, CHAR_DE_MIN))
        if de_t < TEETH_DE_MIN:
            fail.add("%s's flame teeth (%s) are dE %.0f from its cloth, want %.0f" % (key, teeth, de_t, TEETH_DE_MIN))


def chunks_of(names):
    """{object name: chunk id} from the export's chunk plan (out/web/full/chunks.npz), read only; {} without it."""
    if not os.path.isfile(CHUNKS_NPZ):
        return {}
    try:
        z = np.load(CHUNKS_NPZ, allow_pickle=False)
        ids = [str(s) for s in z["ids"]]
        out = {}
        want = set(names)
        for k, c in zip(z["key"], z["chunk"]):
            k = str(k)
            if k in want:
                out[k] = ids[int(c)] if int(c) >= 0 else "backdrop" if int(c) == -2 else str(int(c))
        return out
    except Exception as e:  # noqa: BLE001
        log("WARN chunks.npz unreadable (%s); using the known chunks" % e)
        return {}


def other_slots():
    """Hash of every object's material slots (name -> slot materials and links), the five cloths left out."""
    skip = {"%s.flag.%s.cloth" % (KEY, k) for k in EF.ORDER}
    h = hashlib.md5()
    n = 0
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.name in skip:
            continue
        h.update(ob.name.encode())
        for s in ob.material_slots:
            h.update(("%s|%s" % (s.link, s.material.name if s.material else "")).encode())
            n += 1
    return h.hexdigest(), n


def digest(cloths):
    h = hashlib.md5()
    for key in EF.ORDER:
        ob = cloths[key]
        h.update(ob.name.encode())
        h.update(ob.data.name.encode())
        h.update(mesh_sig(ob.data).encode())
        h.update(repr([(s.link, s.material.name if s.material else None) for s in ob.material_slots]).encode())
        h.update(repr(wave_sig(ob)).encode())
        m = M.get(EF.CLOTH[key][0])
        h.update(m.name.encode())
        h.update(repr(mat_sig(m)).encode())
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------------- main

def main():
    dry = options()
    t0 = time.time()
    fail = Fail()
    cloths = {}
    for key in EF.ORDER:
        ob = cloth_of(key, fail)
        if ob is not None:
            cloths[key] = ob
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    had = all(M.has(EF.CLOTH[k][0]) for k in EF.ORDER)
    names = EF.register(M)
    log("cloths %s (%s)" % (", ".join("%s %s" % (n, EF.CLOTH[k][1]) for k, n in zip(EF.ORDER, names)),
                            "lib/materials registers them: the source change is applied" if had else
                            "registered here: lib/materials does not have them yet"))
    colour_checks(fail)
    if fail:
        log("NOT SAVED: %d colour checks failed" % len(fail))
        raise SystemExit(1)
    n_obj0 = len(bpy.data.objects)
    mats0 = {m.name for m in bpy.data.materials}
    others0 = other_slots()
    before = {}
    plan = []
    for key in EF.ORDER:
        ob = cloths[key]
        have = slot_tags(ob)
        want = [EF.CLOTH[key][0], EF.TRIM[key][0], EF.TRIM[key][1], "gold"]
        old = list(OLD[key]) + ["gold"]
        state = "new" if have == want else "old" if have == old else "unknown"
        links = [s.link for s in ob.material_slots]
        before[key] = dict(mesh=ob.data.name, sig=mesh_sig(ob.data), wave=wave_sig(ob), mw=np.array(ob.matrix_world),
                           box=world_box(ob), data_mats=[m.name if m else None for m in ob.data.materials])
        log("before %s: %s slots %s (%s), state %s" % (key, ob.name, have, ",".join(links), state))
        if state == "unknown":
            fail.add("%s's slots %s are neither round 6's %s nor round 30's %s" % (ob.name, have, old, want))
        if state == "new" and any(link != 'OBJECT' for link in links[:3]):
            fail.add("%s has data-linked slots %s" % (ob.name, links))
        plan.append((key, ob, want, state))
    if fail:
        log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
        raise SystemExit(1)
    # the cloth materials: build them (M.get), or check the file's against this round's colours
    todo = False
    for key in EF.ORDER:
        name = EF.CLOTH[key][0]
        existed = any(m.get(M.TAG) == name and m.library is None for m in bpy.data.materials)
        m = M.get(name)
        if not existed:
            todo = True
            log("built %s: %s, translucency %s, sheen %s" % (m.name, *EF.CLOTH[key][1:]))
        elif not sig_ok(mat_sig(m), want_sig(key)):
            todo = True
            log("%s had %s, want %s: rebuilt in place" % (m.name, mat_sig(m), want_sig(key)))
            M.rebuild(name)
        else:
            log("%s already in the file as wanted (%d users)" % (m.name, m.users))
        if not sig_ok(mat_sig(m), want_sig(key)):
            fail.add("%s is %s after building, want %s" % (m.name, mat_sig(m), want_sig(key)))
    # dress the cloths
    for key, ob, want, state in plan:
        if state == "new":
            log("%s slots unchanged" % ob.name)
            continue
        for slot in (0, 1, 2):
            U.set_object_material(ob, want[slot], slot)
        todo = True
        log("%s: slots %s -> %s" % (ob.name, list(OLD[key]), want[:3]))
    bpy.context.view_layer.update()
    # checks
    for key, ob, want, _state in plan:
        b = before[key]
        if slot_tags(ob) != want:
            fail.add("%s slots %s, want %s" % (ob.name, slot_tags(ob), want))
        if any(s.link != 'OBJECT' for s in ob.material_slots[:3]):
            fail.add("%s slots 0-2 are not object-linked" % ob.name)
        if ob.data.name != b["mesh"] or mesh_sig(ob.data) != b["sig"]:
            fail.add("%s's mesh changed (%s -> %s)" % (ob.name, b["mesh"], ob.data.name))
        if [m.name if m else None for m in ob.data.materials] != b["data_mats"]:
            fail.add("%s's mesh materials changed" % ob.name)
        if wave_sig(ob) != b["wave"]:
            fail.add("%s's wave modifier changed" % ob.name)
        if np.abs(np.array(ob.matrix_world) - b["mw"]).max() > 1e-6:
            fail.add("%s moved" % ob.name)
        lo, hi = world_box(ob)
        if np.abs(lo - b["box"][0]).max() > 1e-6 or np.abs(hi - b["box"][1]).max() > 1e-6:
            fail.add("%s's world box changed" % ob.name)
    others1 = other_slots()
    if others1 != others0:
        fail.add("material slots of other objects changed (%s, %d slots -> %s, %d)" % (*others0, *others1))
    n_obj1 = len(bpy.data.objects)
    if n_obj1 != n_obj0:
        fail.add("objects %d -> %d" % (n_obj0, n_obj1))
    mats1 = {m.name for m in bpy.data.materials}
    gone = sorted(mats0 - mats1)
    if gone:
        fail.add("materials removed: %s" % gone)
    added = sorted(mats1 - mats0)
    stray = [n for n in added if n not in {"%s%s" % (M.PREFIX, EF.CLOTH[k][0]) for k in EF.ORDER}]
    if stray:
        fail.add("unexpected new materials: %s" % stray)
    left = [m.name for m in bpy.data.materials if "trial" in m.name or "~" in m.name]
    if left:
        fail.add("scratch materials in the file: %s" % left[:8])
    for key in EF.ORDER:
        m = bpy.data.materials.get(M.PREFIX + EF.CLOTH[key][0])
        if m is None or m.users < 1:
            fail.add("%s is not used" % (M.PREFIX + EF.CLOTH[key][0]))
    log("objects %d -> %d; materials added %s; other objects' slots kept (%d slots)" % (n_obj0, n_obj1, added or "none",
                                                                                    others1[1]))
    for key, ob, _w, _s in plan:
        log("after %s: %s slots %s" % (key, ob.name, [s.material.name if s.material else None for s in ob.material_slots]))
    log("DIGEST", digest(cloths))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    owners = chunks_of([ob.name for ob in cloths.values()])
    chunk = {k: owners.get(cloths[k].name, KNOWN_CHUNKS[k]) for k in EF.ORDER}
    rebake = sorted(set(chunk.values()))
    log("chunks: %s (%s)" % (", ".join("%s %s" % (k, chunk[k]) for k in EF.ORDER),
                             "out/web/full/chunks.npz" if owners else "the round-29 plan"))
    log("CACHES ok: names, meshes and world boxes kept (vis_cache, chunks and the hotspots stay valid)%s" % (
        "; re-bake %s and the backdrop, then pack" % ",".join(rebake) if todo else "; nothing changed"))
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
