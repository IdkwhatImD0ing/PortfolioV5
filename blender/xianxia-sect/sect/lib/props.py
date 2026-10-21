"""Props and the magic layer of the Moonlit Sect (spec.md section 5, lib contract).

    from sect.lib import props
    lan = props.lantern_hanging(coll, style='palace', size=1.0, name="gate.lantern",
                                parent=root, location=(4, -6, 7.5))

Every public builder:

- takes the target ``collection`` first, then its own dimensions (meters), and the shared
  keyword arguments ``name`` (root object name, e.g. "gate.lantern"; default "props.<kind>"),
  ``parent``, ``location``, ``rotation`` (XYZ Euler radians) and, for most, ``scale``;
- builds at the local origin with its front facing -Y and returns its root object (an Empty
  or a collection-instance Empty);
- is deterministic (``seed``) and safe to call many times: repeated props are prototypes in
  excluded ``_protos`` collections (built once per parameter set, keyed by size buckets on a
  sqrt(2) grid, the remainder applied as instance scale), placed with collection instances,
  linked duplicates or geometry-node point instancers.

Glow strength of emissive parts is set on the prototype objects (``obj["glow"]``), because the
shared materials read it with an OBJECT attribute, which instancers do not override.

Materials: shared names from materials.py, plus module materials registered here with the
prefix ``props_`` (see ``_register_materials``).
"""

import math
import random
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from . import materials as M
from . import util as U

TAU = 2.0 * math.pi
PREFIX = "props"
_PROTO_TAG = "props_proto"
_VERSION = 4            # bump to invalidate prototypes cached inside an open .blend

__all__ = [
    "lantern_hanging", "lantern_stone", "plaque", "banner", "sunmoon_finial", "sunmoon_medallion",
    "cauldron_ding", "incense_burner", "bell", "drum", "guardian_lion",
    "sword", "artifact", "ARTIFACT_KINDS", "chain", "rope", "jade_tablet", "stele",
    "bamboo_slip_scroll", "floating_scroll", "book_stack",
    "stone_table", "tea_set", "cushion", "wind_chime", "weapon_rack", "anvil", "ore_pile",
    "crane", "koi", "rune_ring", "light_beam", "light_pillar", "spirit_motes", "shield_dome",
    "showcase", "closeups", "CLASSICS", "TABLET_TEXTS", "TRIGRAMS", "BAGUA_ORDER", "LUOPAN_24",
]

# Classical texts used for glyph columns (never English), in traditional characters (ancient
# objects; simplified forms read as modern signage). Dao De Jing ch. 1, 8, 16, 25, 42, Qian Zi Wen,
# Qing Jing Jing. Joined they give about 370 characters, so long scrolls never repeat.
CLASSICS = [
    "道可道非常道名可名非常名無名天地之始有名萬物之母故常無欲以觀其妙常有欲以觀其徼此兩者同出而異名同謂之玄玄之又玄眾妙之門",
    "天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往秋收冬藏閏餘成歲律呂調陽雲騰致雨露結為霜金生麗水玉出崑岡劍號巨闕珠稱夜光",
    "上善若水水善利萬物而不爭處眾人之所惡故幾於道居善地心善淵與善仁言善信正善治事善能動善時夫唯不爭故無尤",
    "大道無形生育天地大道無情運行日月大道無名長養萬物吾不知其名強名曰道夫道者有清有濁有動有靜天清地濁天動地靜",
    "致虛極守靜篤萬物並作吾以觀復夫物芸芸各復歸其根歸根曰靜靜曰復命復命曰常知常曰明不知常妄作凶",
    "人法地地法天天法道道法自然有物混成先天地生寂兮寥兮獨立而不改周行而不殆可以為天下母吾不知其名字之曰道",
    "道生一一生二二生三三生萬物萬物負陰而抱陽沖氣以為和",
    "果珍李柰菜重芥薑海鹹河淡鱗潛羽翔龍師火帝鳥官人皇",
]
CLASSICS_ALL = "".join(CLASSICS)

TABLET_TEXTS = ["道法自然", "上善若水", "天道酬勤", "厚德載物", "寧靜致遠", "抱元守一", "清靜無為",
                "紫氣東來", "劍心通明", "太上忘情"]


# ============================================================ module materials

def _beam_link(g, colour="#1effc0", core="#d8fff4", strength=5.0, speed=0.05):
    """Uniform additive beam along local Z (light links between nodes): soft silhouette fade,
    short fades at both ends (generated Z), energy streaks flowing toward +Z."""
    g.blended(shadows=False)
    facing = g.layer_weight(0.35, "Facing")
    edge_fade = g.math('POWER', g.math('SUBTRACT', 1.0, facing), 1.4)
    z = g.sep(g.coord("generated"))[2]
    ends = g.mul(g.smooth(z, 0.0, 0.06), g.smooth(z, 1.0, 0.94))
    v = g.flow(g.coord("object"), (0, 0, -speed))
    streak = g.noise(g.mapping(v, scale=(4.0, 4.0, 0.25)), 1.0, detail=2.0)
    st = g.maprange(streak, 0.3, 0.75, 0.6, 1.2)
    inten = g.mul(g.mul(edge_fade, ends), st)
    col = g.mix(colour, core, g.mul(edge_fade, edge_fade))
    k = g.obj_prop("glow", 1.0)
    g.viewport(colour, 0.5)
    g.output(g.add_shader(g.transparent(), g.emission(col, g.mul(g.mul(inten, strength), k))))


def _flare(g, colour="#1effc0", core="#e0fff8", strength=3.0):
    """Additive radial glow disc (generated XY), e.g. the foot of a light pillar."""
    g.blended(shadows=False)
    x, y, _z = g.sep(g.coord("generated"))
    cx, cy = g.math('SUBTRACT', x, 0.5), g.math('SUBTRACT', y, 0.5)
    r = g.mul(g.math('SQRT', g.add(g.mul(cx, cx), g.mul(cy, cy))), 2.0)
    f = g.math('POWER', g.smooth(r, 1.0, 0.0), 2.2)
    col = g.mix(colour, core, g.math('POWER', f, 3.0))
    k = g.obj_prop("glow", 1.0)
    g.viewport(colour, 0.5)
    g.output(g.add_shader(g.transparent(), g.emission(col, g.mul(g.mul(f, strength), k))))


def _shell(g, c1="#4e4b45", c2="#3a3834", groove="#1f1d1b", scale=2.2):
    """Dark stone carved into irregular tortoise-shell plates (voronoi scutes with grooves)."""
    v = g.coord("object")
    n1 = g.noise(v, 0.9, detail=6.0, roughness=0.6)
    n2 = g.noise(v, 6.0, detail=4.0, roughness=0.55)
    col = g.ramp(g.add(g.mul(n1, 0.7), g.mul(n2, 0.3)), [(0.3, c2), (0.7, c1)])
    cell = g.voronoi(v, scale, feature='DISTANCE_TO_EDGE', randomness=0.6)
    gm = g.smooth(cell, 0.06, 0.015)
    rim = g.smooth(cell, 0.16, 0.06)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 1.18), g.mul(g.math('SUBTRACT', rim, gm), 0.6))
    col = g.mix(col, groove, g.mul(gm, 0.85))
    col = g.tint_per_object(col, hue=0.008, sat=0.08, val=0.06)
    nrm = g.bump(gm, 0.7, 0.02, invert=True)
    nrm = g.bump(n2, 0.15, 0.004, nrm)
    g.viewport(c1, 0.6)
    g.output(g.principled(base_color=col, roughness=g.maprange(n2, 0.3, 0.7, 0.45, 0.68), normal=nrm))


def _gilt(g, base="#e2a646", dark="#9c6426", lacquer="#6a1d12", rough=(0.30, 0.44), ao=0.08, scale=3.0):
    """Gilded carving (plaque frames): warm gold leaf rubbed through to red lacquer in the
    recesses (ambient occlusion) and faintly on raised wear. Rougher than polished gold, so under a
    blue sky the shadowed side stays warm instead of mirroring the sky olive-green."""
    v = g.coord("object")
    n1 = g.noise(v, 1.6 * scale, detail=5.0, roughness=0.6)
    n2 = g.noise(v, 9.0 * scale, detail=3.0)
    col = g.mix(base, dark, g.mul(g.smooth(n1, 0.45, 0.8), 0.35))
    col = g.tint_per_object(col, hue=0.004, sat=0.04, val=0.05)
    occl = g.ao(ao)
    crev = g.math('SUBTRACT', 1.0, g.maprange(occl, 0.35, 0.95, 0.0, 1.0))
    m = g.smooth(g.add(crev, g.mul(g.math('SUBTRACT', n2, 0.5), 0.3)), 0.42, 0.72)
    col = g.mix(col, lacquer, m)
    r = g.mixf(g.maprange(n1, 0.3, 0.75, rough[0], rough[1]), 0.48, m)
    met = g.math('SUBTRACT', 1.0, m)
    g.viewport(base, rough[0], 1.0)
    g.output(g.principled(base_color=col, metallic=met, roughness=r, normal=g.bump(n2, 0.04, 0.003),
                          specular_tint="#ffd9a0"))


def _rim_glow(g, colour="#ff6a10", hot="#ffb048", strength=4.0):
    """Inner wall of a lit cauldron: dark bronze lit from below, glowing orange near the molten
    surface (generated Z = 0) and fading to nothing toward the rim (Z = 1)."""
    z = g.sep(g.coord("generated"))[2]
    f = g.math('POWER', g.math('SUBTRACT', 1.0, z), 2.2)
    n = g.noise(g.coord("object"), 6.0, detail=3.0)
    col = g.mix(colour, hot, g.mul(f, f))
    k = g.obj_prop("glow", 1.0)
    em = g.mul(g.mul(g.mul(f, g.maprange(n, 0.3, 0.7, 0.7, 1.1)), strength), k)
    g.viewport(colour, 0.5)
    g.output(g.principled(base_color="#24180e", roughness=0.5, metallic=0.6, emission_color=col,
                          emission_strength=em))


def _variant(name, base_name, **params):
    """Like materials.variant, but also works for builders with a parameter called ``base``
    (materials.variant(name, base, **params) cannot pass base=... to _paper/_metal/_marble)."""
    builder, p = M._REGISTRY[base_name]
    merged = dict(p)
    merged.update(params)
    return M.register(name, builder, **merged)


def _register_materials():
    """Register the props_ materials (idempotent; built lazily on first M.get)."""
    R, V = M.register, _variant
    R("props_beam_link", _beam_link)
    R("props_beam_gold", _beam_link, colour="#ffaa2a", core="#fff0c8", strength=4.0)
    R("props_flare", _flare)
    R("props_shell", _shell)
    R("props_gilt", _gilt)
    R("props_rim_glow", _rim_glow)
    # aged bronze: dark brown metal, verdigris only in crevices (no camouflage blotches)
    V("props_bronze_aged", "bronze_verdigris", base="#6f5732", dark="#2e2416", rough=(0.45, 0.65),
      verdigris_amt=0.2, edge_col="#b8935a")
    V("props_mirror", "silver", base="#bfb39a", dark="#8a7d62", rough=(0.07, 0.13), tarnish=0.18,
      edge_col="#e6dcc4")
    V("props_lantern_silk", "lantern_red", paper="#c0301a", glow="#ff5a2a", hot="#ff9050", ribs=1)
    V("props_lantern_panel", "paper_lantern", ribs=1, strength=2.6)
    V("props_rope", "moss", colours=[(0.15, "#5e4a33"), (0.55, "#8a7150"), (0.95, "#ad9470")],
      rough=(0.8, 0.95), sheen=0.25, scale=7.0, bump=0.35)
    V("props_straw", "moss", colours=[(0.15, "#8a6a32"), (0.55, "#b8954e"), (0.95, "#d6bb78")],
      rough=(0.75, 0.9), sheen=0.3, scale=9.0, bump=0.3)
    V("props_feather_white", "cloth_white", colour="#f1efea", translucency=0.18, weave=False,
      sheen=0.55, rough=0.62)
    V("props_feather_black", "cloth_black", colour="#141416", translucency=0.04, weave=False, sheen=0.5)
    V("props_crane_crown", "cloth_red", colour="#d4101c", translucency=0.08, weave=False, sheen=0.2, rough=0.45)
    V("props_horn", "moss", colours=[(0.2, "#6f6b4c"), (0.7, "#9a9470")], rough=(0.32, 0.48), sheen=0.0,
      bump=0.04, scale=4.0)
    V("props_leg", "moss", colours=[(0.2, "#1c1c1c"), (0.8, "#363431")], rough=(0.45, 0.65), sheen=0.1,
      bump=0.15, scale=8.0)
    V("props_fin", "cloth_white", colour="#f6e6d6", translucency=0.6, weave=False, sheen=0.3, rough=0.4)
    V("props_drum_skin", "paper_aged", base="#cdb48a", fibre="#b39a6e", translucency=0.0, aged=0.2)
    V("props_ash", "soil", colours=[(0.2, "#6a6560"), (0.6, "#8f8a83"), (1.0, "#b3ada4")],
      speckle=("#3a3836", 0.12))
    V("props_incense", "moss", colours=[(0.2, "#5a2018"), (0.8, "#7a2c1e")], rough=(0.7, 0.85), sheen=0.0,
      scale=10.0, bump=0.1)
    V("props_zisha", "moss", colours=[(0.2, "#4a2a22"), (0.7, "#6a3c2e"), (1.0, "#7a4836")],
      rough=(0.42, 0.58), sheen=0.15, scale=6.0, bump=0.06)
    # motes: saturated jade-cyan with a pale (not white) core, so AgX keeps the hue (spec: no white blobs)
    V("props_mote", "ember", colour="#2fffc8", hot="#9affe4", strength=3.5)
    V("props_mote_gold", "ember", colour="#ffaa2a", hot="#ffd890", strength=3.5)
    V("props_beam_node", "ember", colour="#1effc0", hot="#c8fff0", strength=6.0)
    V("props_flame", "ember", colour="#ff8a1a", hot="#fff2c4", strength=9.0)
    V("props_gourd", "lacquer_red", c1="#8e5a22", c2="#b8823a", coat=0.55, rough=(0.22, 0.36))
    V("props_jade_white", "jade", deep="#c3cfbb", pale="#f0f2e6", sss=0.8)
    V("props_cover_ochre", "cloth_gold", colour="#7d5f34", translucency=0.0, sheen=0.3)
    V("props_cover_brown", "cloth_red", colour="#4a2a20", translucency=0.0, sheen=0.3)
    V("props_ore", "stone_dark", c1="#3b3936", c2="#25231f", speck="#8a7a5a", rough=(0.35, 0.7), bump=0.4,
      light="#6a6258", light_amt=0.25)
    V("props_lion_bronze", "bronze", base="#a2884e", dark="#4a3c22", tarnish=0.5)
    # forge-ring project artifacts
    V("props_bamboo_slip", "moss", colours=[(0.15, "#9c7a42"), (0.55, "#c4a060"), (0.95, "#dcc084")],
      rough=(0.45, 0.6), sheen=0.15, scale=7.0, bump=0.06)
    V("props_rice", "moss", colours=[(0.2, "#e4dcc8"), (0.7, "#f4efe2"), (1.0, "#fbf8f0")], rough=(0.55, 0.75),
      sheen=0.25, scale=60.0, bump=0.35)
    V("props_peach", "moss", colours=[(0.15, "#c8383c"), (0.45, "#e86a5c"), (0.75, "#f4a678"), (1.0, "#f8d494")],
      rough=(0.5, 0.65), sheen=0.6, scale=2.2, bump=0.03)
    V("props_peach_leaf", "moss", colours=[(0.2, "#2f5a2a"), (0.6, "#3f7a34"), (1.0, "#5e9440")], rough=(0.35, 0.5),
      sheen=0.15, scale=5.0, bump=0.05)
    V("props_paper_red", "paper_aged", base="#b3302a", fibre="#962620", aged=0.2)
    V("props_paper_gold", "paper_aged", base="#d9a842", fibre="#c08f30", aged=0.2)
    V("props_beak", "lacquer_red", c1="#d2641c", c2="#e2802c")
    V("rune_blossom", "rune_cyan", colour="#ff6fa0", core="#ffd6e4")


_register_materials()


def _mat(m):
    """Material from a name, a Material, or an int (banner colour index)."""
    if m is None or isinstance(m, bpy.types.Material):
        return m
    if isinstance(m, int):
        return M.banner_cloth(m)
    return M.get(m)


def _mname(m):
    """Stable name of a material argument (registered name, Material or banner index) for use in
    prototype keys, so passing a Material object never puts a memory address into a name."""
    if m is None:
        return "none"
    if isinstance(m, bpy.types.Material):
        return m.get(M.TAG) or m.name
    if isinstance(m, int):
        return "banner_%d" % (m % len(M.BANNER_COLOURS))
    return str(m)


_EVAL_SCENE = "_props_eval"


def _evaluate_temp(ob):
    """Evaluate a temporary object (text curve, metaball) to new mesh data in a private, empty
    scene, then delete the object. Evaluating in the active scene rebuilds that scene's whole
    depsgraph per call (0.3 s per glyph inside a 6000-object scene); the private scene costs ~3 ms.
    The scene is recreated lazily (look.reset_scene() deletes extra scenes)."""
    sc = bpy.data.scenes.get(_EVAL_SCENE)
    if sc is None:
        sc = bpy.data.scenes.new(_EVAL_SCENE)
    sc.collection.objects.link(ob)
    vl = sc.view_layers[0]
    vl.update()
    dg = vl.depsgraph
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    return me


# ============================================================ small generic helpers

def _v3(s):
    return (s, s, s) if isinstance(s, (int, float)) else tuple(s)


def _bucket(value, nominal, step=math.sqrt(2.0)):
    """Quantise ``value`` to nominal * step**k. Returns (bucket, residual scale)."""
    r = max(float(value), 1e-6) / nominal
    k = round(math.log(r) / math.log(step))
    b = nominal * step ** k
    return b, float(value) / b


def _k(x):
    return ("%.3g" % x).replace(".", "p").replace("-", "m")


def _nm(*parts):
    return U.name(PREFIX, *parts)


def _root(collection, name, default, parent, location, rotation, scale=1.0):
    return U.empty(U.unique_name(name or "%s.%s" % (PREFIX, default)), collection, location=location,
                   parent=parent, rotation=rotation, scale=_v3(scale), display_size=0.5)


def _proto(key, build):
    """Prototype collection ``props.<key>`` (under the excluded ``_protos``), built once by
    ``build(pc)`` and reused while it still has objects (rebuilt after look.reset_scene())."""
    key = "%s.v%d" % (key, _VERSION)
    cname = "%s.%s" % (PREFIX, key)
    pc = bpy.data.collections.get(cname)
    if pc is not None and pc.get(_PROTO_TAG) == key and len(pc.all_objects) > 0:
        return pc
    pc = U.proto_collection(cname)
    for o in list(pc.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    build(pc)
    pc[_PROTO_TAG] = key
    return pc


def _place(pc, collection, name, default, parent, location, rotation, scale):
    return U.collection_instance(pc, U.unique_name(name or "%s.%s" % (PREFIX, default)), collection,
                                 location=location, rotation=rotation, scale=_v3(scale), parent=parent,
                                 display_size=0.5)


def _mk(nm, bm, col, mats, parent=None, smooth=None, bevel=0.0, seg=2, angle=math.radians(30), glow=None,
        **place):
    """BMesh -> object (optional bmesh bevel with edge-wear attribute, optional obj['glow'])."""
    ob = U.mesh_from_bmesh(nm, bm, col, materials=mats, smooth=smooth, parent=parent, **place)
    if bevel > 0:
        U.bevel_mesh(ob, bevel, seg, angle)
    if glow is not None:
        ob["glow"] = float(glow)
    return ob


def _merge(bm, dist=1e-5):
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)


def _xf(bm, matrix, verts):
    """Transform ``verts`` in place (plain Python: bmesh.ops.transform costs O(whole BMesh))."""
    m = Matrix(matrix)
    for v in verts:
        v.co = m @ v.co


def _faces_of(verts):
    """Faces whose vertices are all in ``verts`` (the faces a helper just created)."""
    vs = set(verts)
    out = set()
    for v in vs:
        for f in v.link_faces:
            if f not in out and all(w in vs for w in f.verts):
                out.add(f)
    return out


def _set_mat(verts, index):
    for f in _faces_of(verts):
        f.material_index = index


# Every helper below tracks the vertices it creates. Never rely on BMesh indices: bmesh ops
# such as create_uvsphere delete temporary vertices, and later allocations reuse those slots.

def _lathe(bm, profile, segs=32, rmod=None, zmod=None, cap_start=True, cap_end=True, matrix=None,
           phase=0.0, mat=0):
    """Revolve [(r, z), ...] (bottom to top) around Z with optional modulation:
    rmod(theta, i, r, z) -> r and zmod(theta, i, r, z) -> z (i = profile index).
    Returns the list of rings (lists of BMVerts)."""
    rings, made = [], []
    for i, (r, z) in enumerate(profile):
        if r <= 1e-7:
            v = bm.verts.new((0.0, 0.0, z))
            rings.append([v])
            made.append(v)
            continue
        ring = []
        for j in range(segs):
            a = TAU * j / segs + phase
            rr = rmod(a, i, r, z) if rmod else r
            zz = zmod(a, i, r, z) if zmod else z
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), zz)))
        rings.append(ring)
        made.extend(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(segs):
            j2 = (j + 1) % segs
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[j2], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[j2], b[0]))
            else:
                bm.faces.new((a[j], a[j2], b[j2], b[j]))
    if cap_start and len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end and len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    if matrix is not None:
        _xf(bm, matrix, made)
    if mat:
        _set_mat(made, mat)
    return rings


def _sq_lathe(bm, profile, matrix=None, mat=0):
    """Square-plan lathe: profile [(half_width, z), ...]; sides aligned with X/Y."""
    prof = [(a * math.sqrt(2.0), z) for a, z in profile]
    return _lathe(bm, prof, 4, phase=math.pi / 4, matrix=matrix, mat=mat)


_TEMPLATES = {}


def _template(key, build):
    """Cached (verts, faces) of a unit primitive. bmesh.ops.create_* get slower the bigger the
    target BMesh is, so primitives are built once in a scratch BMesh and copied vertex by vertex."""
    t = _TEMPLATES.get(key)
    if t is None:
        tmp = bmesh.new()
        build(tmp)
        tmp.verts.index_update()
        co = [v.co.copy() for v in tmp.verts]
        faces = [[v.index for v in f.verts] for f in tmp.faces]
        tmp.free()
        # canonical order (bmesh.ops.create_uvsphere returns a different face order per process):
        # vertices sorted by rounded position, each face rotated to start at its smallest index
        # (winding kept), faces sorted
        order = sorted(range(len(co)), key=lambda i: (round(co[i].z, 6), round(co[i].y, 6), round(co[i].x, 6)))
        remap = {old: new for new, old in enumerate(order)}
        co = [co[i] for i in order]
        canon = []
        for f in faces:
            f = [remap[i] for i in f]
            k = f.index(min(f))
            canon.append(f[k:] + f[:k])
        canon.sort()
        t = (co, canon)
        _TEMPLATES[key] = t
    return t


def _stamp(bm, key, build, m, mat=0):
    """Add a copy of template ``key`` transformed by 4x4 ``m``; returns the new verts."""
    co, faces = _template(key, build)
    vs = [bm.verts.new(m @ c) for c in co]
    for f in faces:
        nf = bm.faces.new([vs[i] for i in f])
        if mat:
            nf.material_index = mat
    return vs


def _box(bm, size, center=(0, 0, 0), matrix=None, mat=0):
    """Axis-aligned box (size in meters) at ``center``, then optional ``matrix``."""
    m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*_v3(size), 1.0))
    if matrix is not None:
        m = Matrix(matrix) @ m
    return _stamp(bm, ("box",), lambda t: bmesh.ops.create_cube(t, size=1.0), m, mat)


def _cyl(bm, r, depth, segs=16, center=(0, 0, 0), r_top=None, matrix=None, cap=True, mat=0):
    """Z-aligned cylinder / cone centred at ``center``."""
    rt = r if r_top is None else r_top
    m = Matrix.Translation(Vector(center))
    if matrix is not None:
        m = Matrix(matrix) @ m
    return _lathe(bm, [(r, -depth / 2), (rt, depth / 2)], segs, cap_start=cap, cap_end=cap, matrix=m, mat=mat)


def _sphere(bm, r, center=(0, 0, 0), segs=16, rings=8, scale=(1, 1, 1), matrix=None, mat=0):
    """UV sphere of radius r (optionally scaled per axis) at ``center``, then ``matrix``."""
    m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*(r * c for c in _v3(scale)), 1.0))
    if matrix is not None:
        m = Matrix(matrix) @ m
    return _stamp(bm, ("uv", segs, rings),
                  lambda t: bmesh.ops.create_uvsphere(t, u_segments=segs, v_segments=rings, radius=1.0), m, mat)


def _ico(bm, r, center=(0, 0, 0), subdiv=1, scale=(1, 1, 1), matrix=None, mat=0):
    """Icosphere of radius r at ``center``."""
    m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*(r * c for c in _v3(scale)), 1.0))
    if matrix is not None:
        m = Matrix(matrix) @ m
    return _stamp(bm, ("ico", subdiv), lambda t: bmesh.ops.create_icosphere(t, subdivisions=subdiv, radius=1.0),
                  m, mat)


def _torus(bm, R, r, segs=32, sides=8, matrix=None, mat=0, arc=TAU, scale_xy=(1.0, 1.0)):
    """Torus in the XY plane (ring radius R, tube radius r). ``arc`` < TAU makes an open arc."""
    full = arc >= TAU - 1e-6
    cols = segs if full else segs + 1
    rings = []
    for i in range(cols):
        a = arc * i / segs
        c, s = math.cos(a), math.sin(a)
        ring = []
        for k in range(sides):
            b = TAU * k / sides
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((rr * c * scale_xy[0], rr * s * scale_xy[1], r * math.sin(b))))
        rings.append(ring)
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % cols]
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((a[k], b[k], b[k2], a[k2]))
    if not full:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    vs = [v for ring in rings for v in ring]
    if matrix is not None:
        _xf(bm, matrix, vs)
    if mat:
        _set_mat(vs, mat)
    return vs


def _frames(pts, closed=False):
    """Parallel-transport frames along a polyline: list of (point, tangent, normal, binormal)."""
    cs = [Vector(p[:3]) for p in pts]
    m = len(cs)
    tans = []
    for i in range(m):
        a = cs[(i - 1) % m] if (closed or i > 0) else cs[i]
        b = cs[(i + 1) % m] if (closed or i < m - 1) else cs[i]
        t = b - a
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(ref).normalized()
    out = []
    for i in range(m):
        if i > 0:
            axis = tans[i - 1].cross(tans[i])
            if axis.length > 1e-9:
                nrm = Quaternion(axis.normalized(), tans[i - 1].angle(tans[i])) @ nrm
        out.append((cs[i], tans[i], nrm.copy(), tans[i].cross(nrm).normalized()))
    return out


def _tube(bm, points, radius, sides=8, samples=6, closed=False, caps=True, matrix=None, mat=0,
          smooth_path=True, profile=None):
    """Tube into a BMesh along a Catmull-Rom spline through ``points`` ((x,y,z[,w]); w scales
    the radius). ``profile`` = optional list of (cos, sin) multipliers for a non-round section."""
    path = U.catmull_rom(points, samples, closed) if smooth_path else \
        [tuple(p) + (1.0,) if len(p) == 3 else tuple(p) for p in points]
    fr = _frames(path, closed)
    prof = profile or [(math.cos(TAU * k / sides), math.sin(TAU * k / sides)) for k in range(sides)]
    sides = len(prof)
    rings = []
    for (c, _t, n, b), p in zip(fr, path):
        r = radius * p[3]
        rings.append([bm.verts.new(c + (n * cx + b * sy) * r) for cx, sy in prof])
    m = len(rings)
    for i in range(m if closed else m - 1):
        a, b2 = rings[i], rings[(i + 1) % m]
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((a[k], a[k2], b2[k2], b2[k]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    made = [v for ring in rings for v in ring]
    if matrix is not None:
        _xf(bm, matrix, made)
    if mat:
        _set_mat(made, mat)
    return rings


def _ribbon(bm, pts, width, z=0.0, closed=False, matrix=None, mat=0, thick=0.0):
    """Flat ribbon (in XY at height z) along 2D polyline ``pts`` with mitred joints; optional
    thickness (extruded downward). Used for rune strokes and inlaid lines."""
    n = len(pts)
    if n < 2:
        return []
    P2 = [Vector((p[0], p[1])) for p in pts]
    left, right = [], []
    hw = width * 0.5
    for i in range(n):
        if closed or 0 < i < n - 1:
            a = (P2[i] - P2[(i - 1) % n])
            b = (P2[(i + 1) % n] - P2[i])
            a = a.normalized() if a.length > 1e-9 else b.normalized()
            b = b.normalized() if b.length > 1e-9 else a
            t = (a + b)
            t = t.normalized() if t.length > 1e-9 else a
            nrm = Vector((-t.y, t.x))
            miter = hw / max(0.35, nrm.dot(Vector((-a.y, a.x))))
        else:
            t = (P2[1] - P2[0]) if i == 0 else (P2[-1] - P2[-2])
            t = t.normalized() if t.length > 1e-9 else Vector((1, 0))
            nrm = Vector((-t.y, t.x))
            miter = hw
        left.append(P2[i] + nrm * miter)
        right.append(P2[i] - nrm * miter)
    L = [bm.verts.new((p.x, p.y, z)) for p in left]
    Rr = [bm.verts.new((p.x, p.y, z)) for p in right]
    made = L + Rr
    segs = n if closed else n - 1
    for i in range(segs):
        j = (i + 1) % n
        bm.faces.new((Rr[i], Rr[j], L[j], L[i]))
    if thick > 0:
        L2 = [bm.verts.new((p.x, p.y, z - thick)) for p in left]
        R2 = [bm.verts.new((p.x, p.y, z - thick)) for p in right]
        made += L2 + R2
        for i in range(segs):
            j = (i + 1) % n
            bm.faces.new((L[i], L[j], L2[j], L2[i]))
            bm.faces.new((R2[i], R2[j], Rr[j], Rr[i]))
        if not closed:
            bm.faces.new((L[0], L2[0], R2[0], Rr[0]))
            bm.faces.new((Rr[-1], R2[-1], L2[-1], L[-1]))
    if matrix is not None:
        _xf(bm, matrix, made)
    if mat:
        _set_mat(made, mat)
    return made


def _offset2d(pts, hw, closed=False):
    """Left/right offset polylines (mitred joints) of 2D polyline ``pts`` at half width ``hw``."""
    n = len(pts)
    P2 = [Vector((p[0], p[1])) for p in pts]
    left, right = [], []
    for i in range(n):
        if closed or 0 < i < n - 1:
            a = (P2[i] - P2[(i - 1) % n])
            b = (P2[(i + 1) % n] - P2[i])
            a = a.normalized() if a.length > 1e-9 else b.normalized()
            b = b.normalized() if b.length > 1e-9 else a
            t = (a + b)
            t = t.normalized() if t.length > 1e-9 else a
            nrm = Vector((-t.y, t.x))
            miter = hw / max(0.35, nrm.dot(Vector((-a.y, a.x))))
        else:
            t = (P2[1] - P2[0]) if i == 0 else (P2[-1] - P2[-2])
            t = t.normalized() if t.length > 1e-9 else Vector((1, 0))
            nrm = Vector((-t.y, t.x))
            miter = hw
        left.append(P2[i] + nrm * miter)
        right.append(P2[i] - nrm * miter)
    return left, right


def _relief(bm, pts, width, height, surf, closed=False, taper=0.7, mat=0, sink=0.3):
    """Flat-topped relief line (cast bronze or carved stone) on a parametric surface.
    ``pts``: 2D polyline in the surface parameters (meters); ``surf(u, v, h)`` -> 3D point at
    height h above the surface. Section: a trapezoid ``width`` wide at the base and taper*width on
    top, ``height`` tall, its base sunk sink*height so it never floats. Mitred corners keep key-fret
    spirals crisp. Closed solid (normals fixed by the caller's _outward). Returns the new verts."""
    if len(pts) < 2:
        return []
    L0, R0 = _offset2d(pts, width * 0.5, closed)
    L1, R1 = _offset2d(pts, width * 0.5 * taper, closed)
    z0 = -sink * height
    bl = [bm.verts.new(surf(p.x, p.y, z0)) for p in L0]
    br = [bm.verts.new(surf(p.x, p.y, z0)) for p in R0]
    tl = [bm.verts.new(surf(p.x, p.y, height)) for p in L1]
    tr = [bm.verts.new(surf(p.x, p.y, height)) for p in R1]
    n = len(pts)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        bm.faces.new((tr[i], tr[j], tl[j], tl[i]))
        bm.faces.new((tl[i], tl[j], bl[j], bl[i]))
        bm.faces.new((br[i], br[j], tr[j], tr[i]))
        bm.faces.new((bl[i], bl[j], br[j], br[i]))
    if not closed:
        bm.faces.new((bl[0], br[0], tr[0], tl[0]))
        bm.faces.new((tl[-1], tr[-1], br[-1], bl[-1]))
    made = bl + br + tl + tr
    if mat:
        _set_mat(made, mat)
    return made


def _boss(bm, surf, u, v, r, height, segs=12, rings=4, mat=0, aspect=1.0):
    """Rounded boss (eye, nipple, stud) on a parametric surface: a dome of base radius ``r``
    (``aspect`` stretches it along u) standing ``height`` off the surface, base sunk slightly."""
    made = []
    rows = []
    for j in range(rings + 1):
        t = j / rings
        rr = r * math.cos(t * math.pi / 2)
        h = height * math.sin(t * math.pi / 2) if j else -0.25 * height
        if j == rings:
            v_ = bm.verts.new(surf(u, v, height))
            rows.append([v_])
            made.append(v_)
            break
        row = [bm.verts.new(surf(u + rr * aspect * math.cos(TAU * k / segs), v + rr * math.sin(TAU * k / segs), h))
               for k in range(segs)]
        rows.append(row)
        made.extend(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for k in range(segs):
            k2 = (k + 1) % segs
            if len(b) == 1:
                bm.faces.new((a[k], a[k2], b[0]))
            else:
                bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(rows[0])))
    if mat:
        _set_mat(made, mat)
    return made


def _rbox(bm, half, center=(0, 0, 0), matrix=None, p=4.0, segs=16, rings=10, mat=0):
    """Rounded box (superellipsoid |x|^p + |y|^p + |z|^p = 1 scaled by ``half`` sizes): crisp
    planes with soft edges, for carved blocks such as a lion's nose or a dragon's snout."""
    vs = _sphere(bm, 1.0, (0, 0, 0), segs, rings, mat=mat)
    m = Matrix.Translation(Vector(center))
    if matrix is not None:
        m = Matrix(matrix) @ m
    hx, hy, hz = _v3(half)
    for v in vs:
        d = v.co
        s = (abs(d.x) ** p + abs(d.y) ** p + abs(d.z) ** p) ** (-1.0 / p)
        v.co = m @ Vector((d.x * s * hx, d.y * s * hy, d.z * s * hz))
    return vs


def _revolve_surf(r_of_z, theta0=0.0, r_ref=None, dr=0.0):
    """Parametric surface map for _relief/_boss on a surface of revolution r_of_z(z):
    (u, z, h) -> 3D, where u is arc length (m) around the axis from angle theta0 measured at
    radius r_ref (default the local radius). ``dr`` pushes the base outward."""
    def surf(u, z, h):
        r = r_of_z(z) + dr
        rr = r_ref if r_ref else r
        a = theta0 + u / max(rr, 1e-6)
        e = 1e-3
        slope = (r_of_z(z + e) - r_of_z(z - e)) / (2 * e)
        n = Vector((math.cos(a), math.sin(a), -slope)).normalized()
        return Vector((r * math.cos(a), r * math.sin(a), z)) + n * h
    return surf


def _plane_surf(matrix):
    """Parametric map for a plane: (u, v, h) -> matrix @ (u, v, h) (u right, v up, h out)."""
    m = Matrix(matrix)
    return lambda u, v, h: m @ Vector((u, v, h))


_FRET_SPIRAL = [(0.1, 0.1), (0.1, 0.9), (0.9, 0.9), (0.9, 0.22), (0.32, 0.22), (0.32, 0.68), (0.68, 0.68),
                (0.68, 0.45), (0.5, 0.45)]


def _leiwen_fill(bm, surf, u0, u1, v0, v1, cell, width, height, mask=None, mat=0):
    """Fill the (u, v) rectangle with low key-fret (lei wen) spirals, alternately mirrored: the
    'thunder pattern' ground of Shang/Zhou bronzes. ``mask(u, v)`` -> True skips a cell (keeps the
    ground clear under a main motif)."""
    nu = max(1, int((u1 - u0) / cell))
    nv = max(1, int((v1 - v0) / cell))
    cu, cv = (u1 - u0) / nu, (v1 - v0) / nv
    for j in range(nv):
        for i in range(nu):
            uc, vc = u0 + (i + 0.5) * cu, v0 + (j + 0.5) * cv
            if mask is not None and mask(uc, vc):
                continue
            flip = (i + j) % 2
            pts = [(uc + ((0.5 - sx) if flip else (sx - 0.5)) * cu * 0.86, vc + (sy - 0.5) * cv * 0.86)
                   for sx, sy in _FRET_SPIRAL]
            _relief(bm, pts, width, height, surf, taper=0.8, mat=mat)


def _arc_pts(r, a0, a1, n, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def _annulus(bm, r_in, r_out, segs=64, z=0.0, a0=0.0, a1=TAU, matrix=None, mat=0):
    """Flat ring band (or arc band) in XY at height z. Returns the new verts."""
    full = (a1 - a0) >= TAU - 1e-6
    cols = segs if full else segs + 1
    inner, outer = [], []
    for i in range(cols):
        a = a0 + (a1 - a0) * i / segs
        c, s = math.cos(a), math.sin(a)
        inner.append(bm.verts.new((r_in * c, r_in * s, z)))
        outer.append(bm.verts.new((r_out * c, r_out * s, z)))
    for i in range(segs):
        j = (i + 1) % cols
        bm.faces.new((inner[i], outer[i], outer[j], inner[j]))
    made = inner + outer
    if matrix is not None:
        _xf(bm, matrix, made)
    if mat:
        _set_mat(made, mat)
    return made


def _prism(bm, outline, depth, matrix=None, mat=0, y0=0.0):
    """Extrude a 2D outline [(x, z), ...] through Y from y0 (front, toward -Y) to y0 + depth.
    Returns the new verts."""
    front = [bm.verts.new((x, y0, z)) for x, z in outline]
    back = [bm.verts.new((x, y0 + depth, z)) for x, z in outline]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[j], front[i], back[i], back[j]))
    vs = front + back
    if matrix is not None:
        _xf(bm, matrix, vs)
    if mat:
        _set_mat(vs, mat)
    return vs


def _outward(bm):
    """Recalculate normals so they point outward (closed or near-closed parts)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def _catenary(p0, p1, sag, n=64):
    """Points on a catenary-like curve between p0 and p1 dropping ``sag`` m below the chord
    midpoint (exact catenary across the chord, gravity along -Z)."""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    pts = []
    if sag <= 1e-6 or L < 1e-6:
        return [p0.lerp(p1, i / n) for i in range(n + 1)]
    lo, hi = L * 1e-3, L * 1e4
    for _ in range(80):                     # solve s = a (cosh(L/2a) - 1)
        a = math.sqrt(lo * hi)
        s = a * (math.cosh(min(L / (2 * a), 50.0)) - 1.0)
        if s > sag:
            lo = a
        else:
            hi = a
    a = math.sqrt(lo * hi)
    ch = math.cosh(min(L / (2 * a), 50.0))
    for i in range(n + 1):
        t = i / n
        d = a * (math.cosh(min((t - 0.5) * L / a, 50.0)) - ch)
        pts.append(p0.lerp(p1, t) + Vector((0, 0, d)))
    return pts


def _resample(pts, step):
    """Walk a polyline at fixed arc-length ``step``; returns (positions, tangents)."""
    pts = [Vector(p) for p in pts]
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg)
    out_p, out_t = [], []
    s, i, acc = step * 0.5, 0, 0.0
    while s < total and i < len(seg):
        while i < len(seg) and acc + seg[i] < s:
            acc += seg[i]
            i += 1
        if i >= len(seg):
            break
        t = (s - acc) / max(seg[i], 1e-9)
        out_p.append(pts[i].lerp(pts[i + 1], t))
        out_t.append((pts[i + 1] - pts[i]).normalized())
        s += step
    return out_p, out_t


# ============================================================ text -> mesh

def _text_mesh(body, size=1.0, res=2, extrude=0.0, bevel=0.0, spacing=1.0, line=1.0, vertical=False,
               font=None):
    """Mesh (cached) of ``body`` set in KaiTi, lying in XY (readable from +Z, glyph up = +Y),
    centred on its bounding box. vertical=True stacks characters top to bottom."""
    font = font or U.FONT_KAITI
    sig = "%s|%r|%d|%r|%r|%r|%r|%d|%s" % (body, size, res, extrude, bevel, spacing, line, vertical, font)
    key = "props.txt.%08x" % (zlib.crc32(sig.encode("utf-8")) & 0xFFFFFFFF)
    me = bpy.data.meshes.get(key)
    if me is not None and me.get("props_txt") == key:
        return me
    cu = bpy.data.curves.new("props_tmp_text", 'FONT')
    cu.body = "\n".join(body) if vertical else body
    f = U.load_font(font)
    if f is not None:
        cu.font = f
    cu.size = size
    cu.resolution_u = res
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1 if bevel else 0
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.space_character = spacing
    cu.space_line = line
    ob = bpy.data.objects.new("props_tmp_text", cu)
    me = _evaluate_temp(ob)
    bpy.data.curves.remove(cu)
    if len(me.vertices):
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0)))
    me.name = key
    me["props_txt"] = key
    return me


def _mesh_dims(me):
    if not len(me.vertices):
        return Vector((0, 0, 0))
    cs = [v.co for v in me.vertices]
    return Vector((max(c.x for c in cs) - min(c.x for c in cs), max(c.y for c in cs) - min(c.y for c in cs),
                   max(c.z for c in cs) - min(c.z for c in cs)))


def _add_mesh(bm, me, matrix, mat=0):
    """Append a transformed copy of mesh data ``me`` to ``bm`` (all faces get material ``mat``,
    flat shading)."""
    tmp = me.copy()
    tmp.transform(Matrix(matrix))
    n = len(tmp.polygons)
    if n:
        tmp.polygons.foreach_set("material_index", [mat] * n)
        tmp.polygons.foreach_set("use_smooth", [False] * n)
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)


def _text_columns(bm, text, n_cols, n_rows, cell, origin, right_to_left=True, res=2, mat=0,
                  basis=None, offset=0):
    """Lay out ``text`` in vertical columns (top to bottom, columns right to left) as flat glyph
    meshes. ``origin`` = top-left corner of the block in the basis plane; ``basis`` = 3x3 matrix
    whose columns are (right, up, normal) world directions (default: XZ plane facing -Y)."""
    basis = basis or Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))   # right=X, up=Z, normal=-Y
    if not text:
        return
    k = offset
    o = Vector(origin)
    for c in range(n_cols):
        ci = (n_cols - 1 - c) if right_to_left else c
        for r in range(n_rows):
            ch = text[k % len(text)]
            k += 1
            me = _text_mesh(ch, cell * 0.86, res)
            x = (ci + 0.5) * cell
            z = -(r + 0.5) * cell
            pos = o + basis @ Vector((x, z, 0.0))
            m = Matrix.Translation(pos) @ basis.to_4x4()
            _add_mesh(bm, me, m, mat)
    return k


# ============================================================ geometry-node instancers

def _gn_group(proto_obj, drift=None):
    """Geometry-node group instancing ``proto_obj`` on the points of the modified mesh, with
    per-point attributes ``rot`` (quaternion) and ``scl`` (vector). With ``drift``
    (dict rise, height, wobble, speed) the points also move with scene time: they rise and wrap
    every ``height`` m (fading in and out, for sparks) and wobble with 4D noise (motes).
    The object and values are baked into the group, one small group per prototype and parameter
    set. (In Blender 5.2 ``mod['Socket_N'] = v`` raises 'id properties not supported';
    ``mod.properties.inputs['Socket_N'].value = v`` does work, but baked groups keep every
    instancer self-contained.)"""
    d = drift or {}
    sig = "%s|%s" % (proto_obj.name, ",".join("%s=%.4g" % kv for kv in sorted(d.items())))
    gname = "props.gn.%08x" % (zlib.crc32(sig.encode("utf-8")) & 0xFFFFFFFF)
    ng = bpy.data.node_groups.get(gname)
    if ng is not None and ng.get("props_gn") == sig:
        # the prototype may have been deleted and rebuilt under the same name: re-point the group
        for nd in ng.nodes:
            if nd.bl_idname == "GeometryNodeObjectInfo" and nd.inputs["Object"].default_value != proto_obj:
                nd.inputs["Object"].default_value = proto_obj
        return ng
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng["props_gn"] = sig
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, Lk = ng.nodes, ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    oi = N.new("GeometryNodeObjectInfo")
    oi.transform_space = 'ORIGINAL'
    oi.inputs["As Instance"].default_value = True
    oi.inputs["Object"].default_value = proto_obj
    rot = N.new("GeometryNodeInputNamedAttribute")
    rot.data_type = 'QUATERNION'
    rot.inputs["Name"].default_value = "rot"
    scl = N.new("GeometryNodeInputNamedAttribute")
    scl.data_type = 'FLOAT_VECTOR'
    scl.inputs["Name"].default_value = "scl"
    iop = N.new("GeometryNodeInstanceOnPoints")
    Lk.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    Lk.new(rot.outputs["Attribute"], iop.inputs["Rotation"])
    pts = gi.outputs["Geometry"]
    scale_out = scl.outputs["Attribute"]
    if drift:
        def math_(op, a, b=None):
            n = N.new("ShaderNodeMath")
            n.operation = op
            for idx, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[idx].default_value = float(v)
                else:
                    Lk.new(v, n.inputs[idx])
            return n.outputs[0]
        rise, height = float(d.get("rise", 0.0)), max(1e-4, float(d.get("height", 1.0)))
        wobble, speed = float(d.get("wobble", 0.0)), float(d.get("speed", 0.2))
        t = N.new("GeometryNodeInputSceneTime").outputs["Seconds"]
        ph = N.new("GeometryNodeInputNamedAttribute")
        ph.data_type = 'FLOAT'
        ph.inputs["Name"].default_value = "phase"
        up = N.new("ShaderNodeCombineXYZ")
        fade = None
        if rise > 0:
            fr = math_('FRACT', math_('ADD', ph.outputs["Attribute"], math_('MULTIPLY', t, rise / height)))
            Lk.new(math_('MULTIPLY', fr, height), up.inputs["Z"])
            fade = math_('POWER', math_('SINE', math_('MULTIPLY', fr, math.pi)), 0.7)
        pos = N.new("GeometryNodeInputPosition")
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = '4D'
        nz.inputs["Scale"].default_value = 0.6
        nz.inputs["Detail"].default_value = 1.0
        Lk.new(pos.outputs["Position"], nz.inputs["Vector"])
        Lk.new(math_('ADD', math_('MULTIPLY', t, speed), math_('MULTIPLY', ph.outputs["Attribute"], 7.0)),
               nz.inputs["W"])
        cen = N.new("ShaderNodeVectorMath")
        cen.operation = 'SUBTRACT'
        Lk.new(nz.outputs["Color"], cen.inputs[0])
        cen.inputs[1].default_value = (0.5, 0.5, 0.5)
        wob = N.new("ShaderNodeVectorMath")
        wob.operation = 'SCALE'
        Lk.new(cen.outputs["Vector"], wob.inputs[0])
        wob.inputs["Scale"].default_value = 2.0 * wobble
        off = N.new("ShaderNodeVectorMath")
        off.operation = 'ADD'
        Lk.new(wob.outputs["Vector"], off.inputs[0])
        Lk.new(up.outputs["Vector"], off.inputs[1])
        sp = N.new("GeometryNodeSetPosition")
        Lk.new(pts, sp.inputs["Geometry"])
        Lk.new(off.outputs["Vector"], sp.inputs["Offset"])
        pts = sp.outputs["Geometry"]
        if fade is not None:
            sc = N.new("ShaderNodeVectorMath")
            sc.operation = 'SCALE'
            Lk.new(scl.outputs["Attribute"], sc.inputs[0])
            Lk.new(fade, sc.inputs["Scale"])
            scale_out = sc.outputs["Vector"]
    Lk.new(pts, iop.inputs["Points"])
    Lk.new(scale_out, iop.inputs["Scale"])
    Lk.new(iop.outputs["Instances"], go.inputs["Geometry"])
    return ng


def _point_instancer(nm, collection, proto_obj, points, rots=None, scales=None, phases=None, parent=None,
                     location=(0, 0, 0), rotation=(0, 0, 0), drift=None):
    """One object instancing ``proto_obj`` on ``points`` through geometry nodes.
    rots: Quaternions / Euler tuples / matrices; scales: floats or 3-vectors; phases: floats 0-1;
    drift: dict(rise, height, wobble, speed) to animate (embers rise and fade, motes wobble)."""
    me = bpy.data.meshes.new(nm)
    me.vertices.add(len(points))
    me.vertices.foreach_set("co", [c for p in points for c in tuple(p)[:3]])
    q = me.attributes.new("rot", 'QUATERNION', 'POINT')
    s = me.attributes.new("scl", 'FLOAT_VECTOR', 'POINT')
    qs, ss = [], []
    for i in range(len(points)):
        r = rots[i] if rots is not None else Quaternion()
        if isinstance(r, Matrix):
            r = r.to_quaternion()
        elif not isinstance(r, Quaternion):
            r = Euler(r, 'XYZ').to_quaternion()
        qs.extend((r.w, r.x, r.y, r.z))
        ss.extend(_v3(scales[i] if scales is not None else 1.0))
    q.data.foreach_set("value", qs)
    s.data.foreach_set("vector", ss)
    ph = me.attributes.new("phase", 'FLOAT', 'POINT')
    ph.data.foreach_set("value", list(phases) if phases is not None else [0.0] * len(points))
    me.update()
    ob = U.object_from_mesh(nm, me, collection, location=location, rotation=rotation, parent=parent)
    mod = ob.modifiers.new("props_instancer", 'NODES')
    mod.node_group = _gn_group(proto_obj, drift)
    return ob


def _proto_object(key, build):
    """Single-object prototype (for point instancers): returns the object, built once."""
    pc = _proto(key, build)
    return sorted(pc.all_objects, key=lambda o: o.name)[0]



def _mesh(key, build_bm, mats, smooth=None, bevel=0.0, seg=2, angle=math.radians(30)):
    """Shared mesh data cached by ``key`` (version-tagged): build_bm() -> BMesh, then materials,
    smoothing (None keeps the BMesh flags, False flat, True smooth, float = auto-smooth angle)
    and an optional bmesh bevel are applied once."""
    key = "%s.v%d" % (key, _VERSION)

    def build():
        bm = build_bm()
        me = bpy.data.meshes.new(key)
        bm.to_mesh(me)
        bm.free()
        if smooth is True:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        elif smooth is False:
            U.shade_flat(me)
        elif isinstance(smooth, (int, float)):
            U.auto_smooth(me, float(smooth))
        U.set_materials(me, mats)
        if bevel > 0:
            U.bevel_mesh(me, bevel, seg, angle)
        return me

    return U.shared_mesh(key, build)


def _obj(nm, me, collection, parent=None, glow=None, **place):
    ob = U.object_from_mesh(nm, me, collection, parent=parent, **place)
    if glow is not None:
        ob["glow"] = float(glow)
    return ob


# ============================================================ lanterns

def _hang_cord(bm, length, r=0.007):
    if length > 1e-3:
        _tube(bm, [(0, 0, 0), (0, 0, -length * 0.5), (0, 0, -length)], r, sides=6, samples=2)


def _tassel(bm, top, length, r0, r1, flutes=12, head=True, matrix=None):
    """Chinese tassel hanging from ``top``: a knot head and a flared, fluted skirt of strands
    (optional extra ``matrix`` applied afterwards)."""
    x, y, z = top
    M0 = Matrix(matrix) if matrix is not None else Matrix.Identity(4)
    T = Matrix.Translation
    if head:
        hl = 0.125 * length
        _lathe(bm, [(0.0, -hl), (r0 * 0.9, -hl), (r0 * 1.2, -hl * 0.55), (r0 * 0.9, -hl * 0.08), (0.0, 0.0)],
               12, matrix=M0 @ T((x, y, z)))
        z -= hl
        length -= hl
    prof = [(r1 * 0.85, -length), (r1, -length * 0.94), (r1 * 0.8, -length * 0.5), (r0 * 0.75, -length * 0.05),
            (0.0, 0.0)]
    _lathe(bm, prof, flutes * 2, rmod=lambda a, i, r, zz: r * (1.0 + 0.09 * math.cos(flutes * a)) if i < 3 else r,
           matrix=M0 @ T((x, y, z)))


def _build_round_lantern(pc, s, cord):
    """Red silk round lantern (deng long): pleated oblate body, lacquer caps, gold bands, tassel."""
    zt = -cord - 0.06 * s
    h, R = 0.50 * s, 0.31 * s
    zc = zt - 0.05 * s - h / 2
    bm = bmesh.new()
    prof = []
    for i in range(15):
        z = zc - h / 2 + h * i / 14.0
        e = (z - zc) / (h / 2)
        prof.append((max(0.125 * s, R * math.sqrt(max(0.0, 1 - e * e)) ** 0.9), z))
    _lathe(bm, prof, 64, rmod=lambda a, i, r, z: r * (0.968 + 0.032 * abs(math.sin(8 * a))),
           cap_start=False, cap_end=False)
    body = _mk(_nm("lantern_round.body"), bm, pc, ["props_lantern_silk"], smooth=True, glow=1.4)
    bm = bmesh.new()
    for sign, zz in ((1, zc + h / 2), (-1, zc - h / 2)):
        p = [(0.0, 0.0), (0.135 * s, 0.0), (0.145 * s, 0.012 * s), (0.14 * s, 0.05 * s), (0.11 * s, 0.06 * s),
             (0.0, 0.06 * s)]
        _lathe(bm, p, 32, matrix=Matrix.Translation((0, 0, zz)) @ Matrix.Diagonal((1, 1, sign, 1)))
    _outward(bm)
    _mk(_nm("lantern_round.caps"), bm, pc, ["lacquer_black"], smooth=math.radians(40))
    bm = bmesh.new()
    for zz in (zc + h / 2 + 0.008 * s, zc - h / 2 - 0.008 * s):
        _torus(bm, 0.143 * s, 0.011 * s, 32, 6, matrix=Matrix.Translation((0, 0, zz)))
    _torus(bm, 0.028 * s, 0.006 * s, 16, 6,
           matrix=Matrix.Translation((0, 0, zt + 0.028 * s)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    _sphere(bm, 0.03 * s, (0, 0, zc - h / 2 - 0.085 * s), 12, 6)
    _mk(_nm("lantern_round.gold"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    _hang_cord(bm, cord + 0.006 * s, 0.0065 * s)
    _tassel(bm, (0, 0, zc - h / 2 - 0.11 * s), 0.42 * s, 0.03 * s, 0.075 * s, 12)
    _mk(_nm("lantern_round.tassel"), bm, pc, ["cloth_red"], smooth=True)
    return body


def _build_palace_lantern(pc, s, cord):
    """Hexagonal palace lantern (gong deng): rosewood frame, glowing panels, crown with six
    upswept gold dragon-head hooks carrying small tassels, gold trim, big bottom tassel."""
    ap = math.pi / 6                  # hex corners at 30, 90, ... -> a flat side faces -Y
    z0 = -cord

    def sc(prof):
        return [(r * s, z0 + z * s) for r, z in prof]
    bm = bmesh.new()
    _lathe(bm, sc([(0.0, -0.215), (0.30, -0.215), (0.355, -0.19), (0.34, -0.17), (0.24, -0.12), (0.17, -0.085),
                   (0.18, -0.065), (0.11, -0.04), (0.075, -0.012), (0.0, -0.012)]), 6, phase=ap)
    _lathe(bm, sc([(0.0, -0.255), (0.30, -0.255), (0.305, -0.215), (0.0, -0.215)]), 6, phase=ap)
    _lathe(bm, sc([(0.0, -0.86), (0.07, -0.86), (0.12, -0.82), (0.24, -0.765), (0.31, -0.725), (0.305, -0.685),
                   (0.0, -0.685)]), 6, phase=ap)
    rc = 0.283 * s
    for k in range(6):
        a = ap + TAU * k / 6
        _box(bm, (0.034 * s, 0.034 * s, 0.47 * s), (rc * math.cos(a), rc * math.sin(a), z0 - 0.47 * s))
    _outward(bm)
    _mk(_nm("lantern_palace.frame"), bm, pc, ["wood_dark"], smooth=False, bevel=0.004 * s)
    bm = bmesh.new()
    _lathe(bm, [(0.262 * s, z0 - 0.685 * s), (0.262 * s, z0 - 0.255 * s)], 6, phase=ap,
           cap_start=False, cap_end=False)
    _mk(_nm("lantern_palace.panels"), bm, pc, ["props_lantern_panel"], smooth=False, glow=1.6)
    bm = bmesh.new()
    apo = 0.262 * s * math.cos(math.pi / 6)
    for k in range(6):
        a = TAU * k / 6 + ap + math.pi / 6            # outward normal of side k
        m = Matrix.Translation((apo * math.cos(a), apo * math.sin(a), 0)) @ Matrix.Rotation(a + math.pi / 2, 4, 'Z')
        zc = z0 - 0.47 * s
        hw, hh, t = 0.262 * s * 0.40, 0.17 * s, 0.009 * s
        for cx, cz, sx, sz in ((0, hh, 2 * hw, t), (0, -hh, 2 * hw, t), (hw, 0, t, 2 * hh), (-hw, 0, t, 2 * hh)):
            _box(bm, (sx, 0.008 * s, sz), (cx, -0.006 * s, zc + cz), matrix=m)
        for sx_ in (-1, 1):
            _box(bm, (0.05 * s, 0.008 * s, 0.012 * s), (sx_ * (hw - 0.025 * s), -0.006 * s, zc + hh - 0.03 * s),
                 matrix=m)
    for zz, rr in ((-0.214, 0.355), (-0.686, 0.31)):
        _torus(bm, rr * s, 0.008 * s, 6, 4, matrix=Matrix.Translation((0, 0, z0 + zz * s)) @ Matrix.Rotation(ap, 4, 'Z'))
    for k in range(6):
        a = ap + TAU * k / 6
        ca, sa = math.cos(a), math.sin(a)
        pts = [(0.33, -0.175, 1.0), (0.40, -0.15, 1.0), (0.455, -0.10, 0.9), (0.47, -0.05, 0.8), (0.445, -0.025, 0.9)]
        _tube(bm, [(r * s * ca, r * s * sa, z0 + z * s, w) for r, z, w in pts], 0.012 * s, 6, 4)
        _sphere(bm, 0.02 * s, (0.445 * s * ca, 0.445 * s * sa, z0 - 0.03 * s), 8, 4, scale=(1.3, 1.3, 1.0))
    _lathe(bm, [(0.0, z0 - 0.012 * s), (0.04 * s, z0 - 0.012 * s), (0.05 * s, z0 + 0.005 * s),
                (0.02 * s, z0 + 0.02 * s), (0.0, z0 + 0.025 * s)], 12)
    _sphere(bm, 0.035 * s, (0, 0, z0 - 0.88 * s), 12, 6)
    _torus(bm, 0.03 * s, 0.006 * s, 12, 6, matrix=Matrix.Translation((0, 0, z0 + 0.05 * s)) @
           Matrix.Rotation(math.pi / 2, 4, 'X'))
    _mk(_nm("lantern_palace.gold"), bm, pc, ["gold"], smooth=math.radians(40))
    bm = bmesh.new()
    _hang_cord(bm, cord + 0.02 * s, 0.006 * s)
    for k in range(6):
        a = ap + TAU * k / 6
        top = (0.445 * s * math.cos(a), 0.445 * s * math.sin(a), z0 - 0.05 * s)
        _tube(bm, [top, (top[0], top[1], top[2] - 0.08 * s)], 0.004 * s, 4, 1)
        _tassel(bm, (top[0], top[1], top[2] - 0.08 * s), 0.26 * s, 0.016 * s, 0.032 * s, 8)
    _tassel(bm, (0, 0, z0 - 0.91 * s), 0.55 * s, 0.035 * s, 0.085 * s, 14)
    _mk(_nm("lantern_palace.tassels"), bm, pc, ["cloth_red"], smooth=True)


def lantern_hanging(collection, style='palace', size=1.0, cord=0.25, name=None, parent=None,
                    location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Hanging lantern. The origin is the suspension point; the lantern hangs below it in -Z.

    style 'palace': hexagonal rosewood palace lantern with glowing panels, a crown of six upswept
    gold dragon-head hooks with little tassels and a big red bottom tassel (about 1.4*size m long
    below the cord, 0.95*size m wide). style 'round': red silk deng long with vertical pleats, black
    lacquer caps, gold bands and a red tassel (about 1.05*size m below the cord, 0.62*size m wide).
    ``cord``: cord length above the lantern (m). Returns a collection-instance Empty."""
    if style not in ("palace", "round"):
        raise ValueError("lantern_hanging style must be 'palace' or 'round'")
    b, res = _bucket(size, 1.0)
    cq = round(cord / size / 0.05) * 0.05
    key = "lantern_%s.%s.c%s" % (style, _k(b), _k(cq))
    builder = _build_palace_lantern if style == "palace" else _build_round_lantern
    pc = _proto(key, lambda pc: builder(pc, b, cq * b))
    return _place(pc, collection, name, "lantern_" + style, parent, location, rotation,
                  tuple(res * c for c in _v3(scale)))


def _arch_wall(bm, w, h, t, hole_w, hole_h, sill, matrix, segs=10):
    """Wall panel (XZ plane, thickness t along Y, base at z=0, centred on x) with a round-arched
    opening ``hole_w`` wide and ``hole_h`` tall starting ``sill`` above the base; transformed by
    ``matrix``. Coincident verts are merged by the caller (one _merge at the end)."""
    hw = hole_w / 2
    straight = max(0.0, hole_h - hw)
    half = [(0.0, sill), (hw, sill), (hw, sill + straight)]
    for i in range(1, segs + 1):
        a = math.pi / 2 * i / segs
        half.append((hw * math.cos(a), sill + straight + hw * math.sin(a)))
    half[-1] = (0.0, half[-1][1])
    made = []
    for side in (1, -1):
        hp = [(side * x, z) for x, z in half]
        poly = [(0.0, h), (side * w / 2, h), (side * w / 2, 0.0), (0.0, 0.0)] + hp
        for y in (-t / 2, t / 2):
            ring = [bm.verts.new((x, y, z)) for x, z in poly]
            made.extend(ring)
            bm.faces.new(ring)

    def strip(pts):
        a = [bm.verts.new((x, -t / 2, z)) for x, z in pts]
        b = [bm.verts.new((x, t / 2, z)) for x, z in pts]
        made.extend(a + b)
        for i in range(len(pts) - 1):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    strip([(-x, z) for x, z in half[::-1]] + half[1:])
    strip([(-w / 2, 0.0), (-w / 2, h), (w / 2, h), (w / 2, 0.0), (-w / 2, 0.0)])
    _xf(bm, matrix, made)


_OCT = 1.0 / math.cos(math.pi / 8)        # octagon circumradius / apothem


def _oct_lathe(bm, profile, matrix=None, mat=0):
    """Octagonal-plan lathe: profile [(apothem, z), ...]; a flat side faces -Y."""
    return _lathe(bm, [(a * _OCT, z) for a, z in profile], 8, phase=math.pi / 8, matrix=matrix, mat=mat)


def _oct_point(a, side, t):
    """Point on an octagon of apothem ``a`` (flat side toward -Y): ``side`` 0-7 counter-clockwise
    from the corner at 22.5 deg, ``t`` 0-1 along the side. Returns (x, y, corner weight 0-1)."""
    c0 = math.pi / 8 + side * math.pi / 4
    c1 = c0 + math.pi / 4
    R = a * _OCT
    p0 = Vector((R * math.cos(c0), R * math.sin(c0)))
    p1 = Vector((R * math.cos(c1), R * math.sin(c1)))
    p = p0.lerp(p1, t)
    return p.x, p.y, abs(2.0 * t - 1.0) ** 6


def _oct_roof(bm, rings, n_side=6, flare=0.06):
    """Closed octagonal roof slab lofted through ``rings`` [(apothem, z, lift, lift_factor), ...]
    (bottom/inside first, ridge last): eave corners rise by lift*lift_factor and flare outward.
    Returns the ring coordinates (lists of Vectors) for placing ridges and ribs."""
    loops, coords = [], []
    for a, z, lift, lf in rings:
        ring, cr = [], []
        for side in range(8):
            for i in range(n_side):
                x, y, w = _oct_point(a, side, i / n_side)
                k = 1.0 + flare * w * lf
                co = Vector((x * k, y * k, z + lift * w * lf))
                ring.append(bm.verts.new(co))
                cr.append(co)
        loops.append(ring)
        coords.append(cr)
    m = len(loops[0])
    for a_, b_ in zip(loops[:-1], loops[1:]):
        for i in range(m):
            bm.faces.new((a_[i], a_[(i + 1) % m], b_[(i + 1) % m], b_[i]))
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[-1])
    return coords


def _build_stone_lantern(pc, H, material, lit):
    """Tang/Song octagonal stone lantern (shi deng), designed 2.44 units tall, scaled to H."""
    k = H / 2.44
    S = Matrix.Diagonal((k, k, k, 1.0))
    # ---- base: octagonal xumizuo, downturned lotus, shaft with a lotus band, upturned lotus capital
    bm = bmesh.new()
    _oct_lathe(bm, [(0, 0), (0.40, 0), (0.40, 0.08), (0.375, 0.10), (0.355, 0.13), (0.30, 0.155), (0.30, 0.27),
                    (0.35, 0.295), (0.37, 0.325), (0.385, 0.355), (0.385, 0.40), (0, 0.40)], matrix=S)
    _lathe(bm, [(0.33, 0.40), (0.335, 0.425), (0.29, 0.47), (0.21, 0.505), (0.17, 0.515), (0, 0.515)], 64,
           rmod=lambda a, i, r, z: r * (1 + (0.075 if 0 < i < 4 else 0.0) * abs(math.cos(8 * a)) ** 0.6),
           zmod=lambda a, i, r, z: z + (0.014 if i in (1, 2) else 0) * abs(math.cos(8 * a)), matrix=S)
    _oct_lathe(bm, [(0, 0.50), (0.19, 0.50), (0.19, 0.53), (0.165, 0.55), (0.157, 0.56), (0.157, 1.135),
                    (0.175, 1.145), (0, 1.145)], matrix=S)
    _lathe(bm, [(0.15, 0.775), (0.20, 0.79), (0.215, 0.815), (0.20, 0.835), (0.215, 0.855), (0.20, 0.88),
                (0.15, 0.895)], 48, rmod=lambda a, i, r, z: r * (1 + (0.06 if i in (2, 4) else 0) *
                                                                    abs(math.cos(8 * a)) ** 0.8),
           cap_start=False, cap_end=False, matrix=S)
    _lathe(bm, [(0.0, 1.13), (0.17, 1.13), (0.20, 1.16), (0.27, 1.205), (0.33, 1.245), (0.355, 1.275),
                (0.33, 1.28), (0.0, 1.28)], 64,
           rmod=lambda a, i, r, z: r * (1 + (0.07 if i in (3, 4, 5) else 0) * (abs(math.cos(8 * a)) ** 0.7 - 0.5)),
           zmod=lambda a, i, r, z: z + (0.028 if i in (4, 5) else 0.0) * abs(math.cos(8 * a)) ** 3, matrix=S)
    _oct_lathe(bm, [(0, 1.275), (0.315, 1.275), (0.325, 1.295), (0.315, 1.33), (0, 1.33)], matrix=S)
    _outward(bm)
    base = _mk(_nm("stone_lantern.base"), bm, pc, [material], smooth=math.radians(35), bevel=0.007 * k)
    # ---- octagonal lamp chamber: corner posts, arched openings on the four cardinal faces,
    # blind relief windows (vertical-bar lattice, zhi ling chuang) on the four diagonal faces
    zc0, ch, ap, t = 1.33, 0.52, 0.27, 0.05
    side_len = 2 * ap * math.tan(math.pi / 8)
    bm = bmesh.new()
    for i in range(8):
        R = Matrix.Rotation(i * math.pi / 4, 4, 'Z')
        if i % 2 == 0:
            _arch_wall(bm, side_len, ch, t, 0.125, 0.30, 0.09,
                       S @ R @ Matrix.Translation((0, -(ap - t / 2), zc0)))
        else:
            _box(bm, (side_len, t, ch), (0, -(ap - t / 2), zc0 + ch / 2), matrix=S @ R)
            fw, fh, zw = 0.125, 0.25, zc0 + 0.09 + 0.125
            for cx, cz, sx, sz in ((0, fh / 2, fw + 0.03, 0.025), (0, -fh / 2, fw + 0.03, 0.025),
                                   (fw / 2, 0, 0.025, fh), (-fw / 2, 0, 0.025, fh)):
                _box(bm, (sx, 0.022, sz), (cx, -ap - 0.004, zw + cz), matrix=S @ R)
            for b in range(4):
                _box(bm, (0.014, 0.014, fh), (-fw / 2 + fw * (b + 0.5) / 4, -ap + 0.002, zw), matrix=S @ R)
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        R0 = ap * _OCT - 0.01
        _oct_lathe(bm, [(0, zc0), (0.03, zc0), (0.03, zc0 + ch), (0, zc0 + ch)],
                   matrix=S @ Matrix.Translation((R0 * math.cos(a), R0 * math.sin(a), 0)))
    _oct_lathe(bm, [(0, zc0 + ch), (0.29, zc0 + ch), (0.30, zc0 + ch + 0.02), (0.30, zc0 + ch + 0.05),
                    (0.0, zc0 + ch + 0.05)], matrix=S)
    _merge(bm, 1e-6)
    _outward(bm)
    _mk(_nm("stone_lantern.chamber"), bm, pc, [material], smooth=False, bevel=0.005 * k)
    # ---- octagonal roof: soffit, stepped fascia, thick eave edge, concave slopes, lifted corners
    z_e = zc0 + ch + 0.05                       # 1.90
    rings = [(0.29, z_e, 0.05, 0.0), (0.38, z_e, 0.05, 1.0), (0.38, z_e + 0.03, 0.05, 1.0),
             (0.395, z_e + 0.03, 0.05, 1.0), (0.395, z_e + 0.09, 0.05, 1.0)]
    nr = 7
    for r_i in range(1, nr + 1):
        s = r_i / nr
        rings.append((0.395 + (0.06 - 0.395) * s, z_e + 0.09 + 0.19 * s ** 1.6, 0.05, (1 - s) ** 2))
    bm = bmesh.new()
    coords = _oct_roof(bm, rings, n_side=6)
    _xf(bm, S, bm.verts[:])
    _outward(bm)
    _mk(_nm("stone_lantern.roof"), bm, pc, [material], smooth=math.radians(32))
    # hip ridges with upturned tips, tile ribs, round tile ends along the eave, lotus-ring-pearl finial
    bm = bmesh.new()
    top = coords[4:]                            # eave-edge top ring, then the slope rings
    ns = 6
    for c in range(8):
        pts = [tuple(S @ (ring[c * ns] + Vector((0, 0, 0.014)))) for ring in top]
        tip = Vector(pts[0])
        d = Vector((tip.x, tip.y, 0)).normalized()
        pts.insert(0, tuple(tip + d * 0.022 * k + Vector((0, 0, 0.03 * k))))
        _tube(bm, [p + (1.0 - 0.35 * i / len(pts),) for i, p in enumerate(pts)], 0.019 * k, 6, 3)
        for jj in (2, 4):                       # two tile ribs per face
            rib = [tuple(S @ (ring[c * ns + jj] + Vector((0, 0, 0.004)))) for ring in top[:-1]]
            _tube(bm, rib, 0.009 * k, 5, 2)
            e = S @ top[0][c * ns + jj]
            dd = Vector((e.x, e.y, 0)).normalized()
            _cyl(bm, 0.017 * k, 0.012 * k, 10, matrix=Matrix.Translation(e + dd * 0.004 * k -
                                                                         Vector((0, 0, 0.02 * k))) @
                 U.align_z(dd).to_4x4())
    fz = z_e + 0.28
    _lathe(bm, [(0.0, fz - 0.02), (0.07, fz - 0.02), (0.085, fz + 0.01), (0.07, fz + 0.035), (0.05, fz + 0.045),
                (0.0, fz + 0.045)], 32, rmod=lambda a, i, r, z: r * (1 + (0.12 if i in (2, 3) else 0) *
                                                                      (abs(math.cos(4 * a)) ** 0.7 - 0.4)),
           matrix=S)
    for j, (rr, zz) in enumerate(((0.042, 0.06), (0.036, 0.087), (0.03, 0.111))):
        _torus(bm, rr, 0.012, 20, 8, matrix=S @ Matrix.Translation((0, 0, fz + zz)))
    _lathe(bm, [(0.0, fz + 0.045), (0.022, fz + 0.045), (0.022, fz + 0.125), (0.0, fz + 0.125)], 10, matrix=S)
    _sphere(bm, 0.05, (0, 0, fz + 0.165), 16, 10, matrix=S)
    _lathe(bm, [(0.0, fz + 0.2), (0.022, fz + 0.205), (0.0, fz + 0.255)], 10, matrix=S)
    _mk(_nm("stone_lantern.crown"), bm, pc, [material], smooth=math.radians(45))
    if lit:
        bm = bmesh.new()
        _oct_lathe(bm, [(0, zc0 + 0.06), (0.205, zc0 + 0.06), (0.205, zc0 + ch - 0.05), (0, zc0 + ch - 0.05)],
                   matrix=S)
        _mk(_nm("stone_lantern.light"), bm, pc, ["paper_screen_lit"], smooth=False, glow=2.4)
    return base


def lantern_stone(collection, height=2.4, material="stone_grey", lit=True, name=None, parent=None,
                  location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Chinese octagonal stone lantern (Tang/Song shi deng), ``height`` m tall (0.33*height wide):
    octagonal xumizuo base with a waist, downturned lotus cushion, octagonal shaft with a lotus band,
    upturned lotus capital, octagonal lamp chamber with arched openings on the four cardinal faces
    and blind vertical-bar windows on the four diagonals (a glowing paper core when lit=True), a
    thick octagonal roof with a stepped fascia, concave slopes, eight hip ridges with lifted tips,
    tile ribs and round tile ends, and a lotus-seat / three-ring / pearl finial.
    Origin at the ground centre, a flat face toward -Y. Collection instance."""
    b, res = _bucket(height, 2.4)
    key = "stone_lantern.%s.%s.%d" % (_k(b), _mname(material), int(bool(lit)))
    pc = _proto(key, lambda pc: _build_stone_lantern(pc, b, material, lit))
    return _place(pc, collection, name, "stone_lantern", parent, location, rotation,
                  tuple(res * c for c in _v3(scale)))


# ============================================================ plaque

def _frame_sweep(bm, W, H, profile):
    """Rectangular moulded frame in the XZ plane, outer size W x H, sweeping ``profile``
    [(inset, y), ...] from the outer back edge inward (front = -Y). Closed solid."""
    loops = []
    for inset, y in profile:
        hw, hh = W / 2 - inset, H / 2 - inset
        loops.append([bm.verts.new((x, y, z)) for x, z in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))])
    for a, b in zip(loops, loops[1:] + loops[:1]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return loops


def _corner_bracket(A):
    """Corner bracket outline (jiao ya): legs of length A along +x and +z, concave curved hypotenuse."""
    pts = [(0.0, 0.0), (A, 0.0)]
    for i in range(1, 10):
        t = math.pi / 2 * i / 10
        pts.append((A - A * math.sin(t), A - A * math.cos(t)))
    pts.append((0.0, A))
    return pts


def _frame_fret(bm, W, H, u0, u1, y, height, matrix=None):
    """Raised key-fret (hui wen) square spirals along a rectangular frame band between insets
    u0 and u1 (in the XZ plane, band surface at ``y``, relief toward -Y by ``height``)."""
    bw = u1 - u0
    uc = (u0 + u1) / 2
    unit = bw * 1.05
    spiral = [(0.1, 0.1), (0.1, 0.9), (0.9, 0.9), (0.9, 0.22), (0.32, 0.22), (0.32, 0.68), (0.68, 0.68),
              (0.68, 0.45), (0.5, 0.45)]
    stroke = bw * 0.11
    for side in range(4):
        length, off = (W - 2 * uc, H / 2 - uc) if side % 2 == 0 else (H - 2 * uc, W / 2 - uc)
        n = max(2, int((length - bw) / unit))
        step = (length - bw) / n
        R = Matrix.Rotation((0.0, -math.pi / 2, math.pi, math.pi / 2)[side], 4, 'Y')
        # local frame: s along +X, t across the band (+Z = inward), relief along -Y
        base = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
        for i in range(n):
            x0 = -length / 2 + bw / 2 + step * (i + 0.5) - unit * 0.45
            flip = i % 2
            pts = [((sx if not flip else 1 - sx) * unit * 0.9 + x0, (sy - 0.5) * bw * 0.86) for sx, sy in spiral]
            m = R @ Matrix.Translation((0, y - 0.0005, -off)) @ base
            if matrix is not None:
                m = Matrix(matrix) @ m
            _ribbon(bm, pts, stroke, z=height, thick=height, matrix=m)


def plaque(collection, text_zh, width=3.0, vertical=False, rtl=False, tilt=math.radians(8),
           board="plaque_board", frame="gold", text_material="gold", name=None, parent=None,
           location=(0, 0, 0), rotation=(0, 0, 0)):
    """Hanging plaque (bian e): dark blue lacquered board, carved gold frame (rounded outer bead,
    cove, a band of gold pearls, raised inner lip, curved corner brackets) and raised gold KaiTi
    characters with bevelled edges. ``width`` is the outer width; the height follows the text
    (3 characters horizontal: height = width / 2.6). vertical=True stacks the characters top to
    bottom (height about (1.06 n + 0.95) * width / 1.66) and adds a cloud crest on top.
    rtl=True writes a horizontal plaque right to left (classical). Origin = board centre; the top
    leans forward by ``tilt``; front faces -Y. Returns the root Empty (plaques are unique)."""
    chars = list(text_zh)
    n = max(1, len(chars))
    if vertical:
        cs = width / 1.66
        W, Hh = width, n * cs * 1.06 + 0.95 * cs
    else:
        cs = width / (n * 1.12 + 0.95)
        W, Hh = width, cs * 1.66
    fw = 0.32 * cs
    d = 0.16 * cs
    root = _root(collection, name, "plaque", parent, location, rotation)
    pivot = U.empty(U.unique_name(root.name + ".pivot"), collection, parent=root, rotation=(tilt, 0, 0),
                    display_size=0.2)
    pn = root.name
    bm = bmesh.new()
    _box(bm, (W - 2 * fw, d, Hh - 2 * fw), (0, d / 2, 0))
    _mk(U.unique_name(pn + ".board"), bm, collection, [board], parent=pivot, smooth=False, bevel=0.004 * cs)
    # frame moulding: outer bead, flat fret band, bead ridge, pearl channel, inner lip
    bm = bmesh.new()
    prof = [(0.0, d), (0.0, -0.22 * fw), (0.04 * fw, -0.32 * fw), (0.10 * fw, -0.36 * fw), (0.16 * fw, -0.32 * fw),
            (0.18 * fw, -0.26 * fw), (0.52 * fw, -0.26 * fw), (0.56 * fw, -0.33 * fw), (0.62 * fw, -0.36 * fw),
            (0.68 * fw, -0.30 * fw), (0.72 * fw, -0.22 * fw), (0.84 * fw, -0.22 * fw), (0.88 * fw, -0.28 * fw),
            (0.93 * fw, -0.25 * fw), (0.97 * fw, -0.10 * fw), (1.0 * fw, -0.04 * fw), (1.0 * fw, d)]
    _frame_sweep(bm, W, Hh, prof)
    A = 1.1 * fw
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx, cz = sx * (W / 2 - fw), sz * (Hh / 2 - fw)
            outline = [(cx - sx * px, cz - sz * pz) for px, pz in _corner_bracket(A)]
            if sx * sz < 0:
                outline = outline[::-1]
            _prism(bm, outline, 0.05 * fw, y0=-0.05 * fw - 0.002)
    if vertical:
        cw, chh = W * 0.62, W * 0.2
        pts = []
        for i in range(25):
            t = math.pi * i / 24
            r = 1.0 + 0.10 * math.cos(6 * t) ** 2
            pts.append((-math.cos(t) * cw / 2 * r, Hh / 2 - fw * 0.3 + math.sin(t) * chh * r))
        _prism(bm, pts[::-1], d * 0.8, y0=-0.2 * fw)
    _outward(bm)
    _mk(U.unique_name(pn + ".frame"), bm, collection, [frame], parent=pivot, smooth=math.radians(35),
        bevel=0.012 * fw)
    # carved relief (not bevelled): key-fret spirals on the flat band, pearls in the channel
    bm = bmesh.new()
    _frame_fret(bm, W, Hh, 0.18 * fw, 0.52 * fw, -0.26 * fw, 0.035 * fw)
    uc = 0.78 * fw
    for side in range(4):
        length, off = (W - 2 * uc, Hh / 2 - uc) if side % 2 == 0 else (Hh - 2 * uc, W / 2 - uc)
        n_p = max(4, int(length / (0.30 * fw)))
        R = Matrix.Rotation((0.0, -math.pi / 2, math.pi, math.pi / 2)[side], 4, 'Y')
        for i in range(n_p + 1):
            x = -length / 2 + length * i / n_p
            _sphere(bm, 0.075 * fw, (x, -0.22 * fw, -off), 8, 4, scale=(1, 0.7, 1), matrix=R)
    if vertical:
        _sphere(bm, 0.18 * W * 0.2, (0, -0.3 * fw, Hh / 2 + W * 0.2 * 0.55), 16, 8, scale=(1, 0.6, 1))
    _mk(U.unique_name(pn + ".relief"), bm, collection, [frame], parent=pivot, smooth=math.radians(50))
    body = "".join(reversed(chars)) if (rtl and not vertical) else "".join(chars)
    ex, bv = 0.02 * cs, 0.008 * cs
    me = _text_mesh(body, cs * 0.80, 4, extrude=ex, bevel=bv, spacing=1.12, line=1.05, vertical=vertical)
    dims = _mesh_dims(me)
    f = min(1.0, (W - 2 * fw) * 0.86 / max(dims.x, 1e-6), (Hh - 2 * fw) * 0.88 / max(dims.y, 1e-6))
    bm = bmesh.new()
    m = Matrix.Translation((0, -(ex + bv) * f - 0.001, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X') @ \
        Matrix.Diagonal((f, f, f, 1))
    _add_mesh(bm, me, m)
    _mk(U.unique_name(pn + ".text"), bm, collection, [text_material], parent=pivot, smooth=math.radians(40))
    return root


# ============================================================ banner

def _cloth_rows(bm, rows, matfn):
    """Quad grid through ``rows`` (lists of (x, y) points, equal length, top row first) in the
    z = 0 plane, normals +Z; face material matfn(i, j) (i column, j row). Returns the verts."""
    vs = [[bm.verts.new((x, y, 0.0)) for x, y in row] for row in rows]
    for j in range(len(rows) - 1):
        for i in range(len(rows[0]) - 1):
            f = bm.faces.new((vs[j][i], vs[j + 1][i], vs[j + 1][i + 1], vs[j][i + 1]))
            f.material_index = matfn(i, j)
    return [v for row in vs for v in row]


def _crescent(bm, cx, cy, R, mat, ring=True, z=0.0, n=20):
    """Flat crescent moon (horns toward +x) inside an optional thin ring, centred at (cx, cy)."""
    made = []
    a0, a1 = math.radians(55), math.radians(305)
    off = 0.42 * R
    outer = [(cx + R * math.cos(a0 + (a1 - a0) * i / n), cy + R * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    p_top, p_bot = Vector(outer[0]), Vector(outer[-1])
    c2 = Vector((cx + off, cy))
    b0 = math.atan2(p_top.y - c2.y, p_top.x - c2.x)
    b1 = math.atan2(p_bot.y - c2.y, p_bot.x - c2.x) + TAU
    r2 = (p_top - c2).length
    inner = [(c2.x + r2 * math.cos(b0 + (b1 - b0) * i / n), c2.y + r2 * math.sin(b0 + (b1 - b0) * i / n))
             for i in range(n + 1)]
    vo = [bm.verts.new((x, y, z)) for x, y in outer]
    vi = [bm.verts.new((x, y, z)) for x, y in inner]
    made += vo + vi
    for i in range(n):
        f = bm.faces.new((vo[i], vo[i + 1], vi[i + 1], vi[i]))
        f.material_index = mat
    if ring:
        made += _annulus(bm, R * 1.22, R * 1.32, 48, z, matrix=Matrix.Translation((cx, cy, 0)), mat=mat)
    return made


# ---- the Ming Sect's sun-and-moon emblem 日月 (明 = 日 sun + 月 moon)
# One design everywhere (banner roundels, the gate's ridge finial and plaque medallions): a crescent moon with its
# horns up, the lead (bigger, silver / moon-white), cradling a rayed sun disc (gold) that rises out of its cup, the
# way a Tibetan stupa's spire carries the sun in the moon. Unit coordinates: the roundel's ring has inner radius 1,
# y up. The whole sun (rays included) lies inside the moon's cut circle, so the two never overlap (flat cloth faces
# cannot z-fight) and a thin gap of sky / cloth shows between them.
SM_MOON = ((0.0, -0.10), 0.86, (0.0, 0.24), 0.74)   # outer circle (centre, radius), cut circle (centre, radius)
SM_SUN = ((0.0, 0.14), 0.34, 0.56, 12)              # centre, disc radius, ray tip radius, number of rays
SM_RAY_BASE = 0.5                                   # ray base as a fraction of the ray pitch
SM_RING = (1.0, 1.08)                               # the roundel ring on banners (inner, outer)
SM_MATS = dict(ring=2, moon=4, sun=5)               # banner cloth slots (0 cloth, 1 trim, 2 text/ring, 3 gold)


def _sm_tips():
    """The crescent's two horn tips (right, left) and the circles' data, unit coordinates."""
    (c1x, c1y), r1, (c2x, c2y), r2 = SM_MOON
    d = math.hypot(c2x - c1x, c2y - c1y)
    ux, uy = (c2x - c1x) / d, (c2y - c1y) / d
    a = (d * d + r1 * r1 - r2 * r2) / (2.0 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    px, py = c1x + a * ux, c1y + a * uy
    return (px + h * uy, py - h * ux), (px - h * uy, py + h * ux)


def sm_moon_shape(n=24):
    """The emblem's crescent as a 2D shape (points, faces, boundary loop) in unit coordinates: faces are
    counter-clockwise index tuples (normal +Z in an XY plane), the loop runs once round the outline."""
    (c1x, c1y), r1, (c2x, c2y), r2 = SM_MOON
    tr, tl = _sm_tips()
    ar, al = math.atan2(tr[1] - c1y, tr[0] - c1x), math.atan2(tl[1] - c1y, tl[0] - c1x)
    br, bl = math.atan2(tr[1] - c2y, tr[0] - c2x), math.atan2(tl[1] - c2y, tl[0] - c2x)
    if al < ar:
        al += TAU
    if bl < br:
        bl += TAU
    sa, sb = TAU - (al - ar), TAU - (bl - br)        # the long way round, away from the cut circle's centre
    outer = [(c1x + r1 * math.cos(ar - sa * i / n), c1y + r1 * math.sin(ar - sa * i / n)) for i in range(n + 1)]
    inner = [(c2x + r2 * math.cos(br - sb * i / n), c2y + r2 * math.sin(br - sb * i / n)) for i in range(1, n)]
    pts = outer + inner
    O = list(range(n + 1))
    I = [0] + [n + 1 + k for k in range(n - 1)] + [n]  # the tips are shared
    faces = []
    for i in range(n):
        q = [O[i], I[i], I[i + 1], O[i + 1]]
        q = [v for k, v in enumerate(q) if v not in q[:k]]
        faces.append(tuple(q))
    loop = O + I[1:n][::-1]
    return pts, _sm_ccw_faces(pts, faces), loop


def sm_sun_shape(arc=2):
    """The emblem's rayed sun as a 2D shape (points, faces, loop): a fan from the centre (index 0) to an outline of
    ray tips with ``arc`` + 1 points of the disc's rim between each pair of rays. Unit coordinates."""
    (cx, cy), rs, rt, k = SM_SUN
    pitch = TAU / k
    hb = 0.5 * SM_RAY_BASE * pitch
    rim = []
    for j in range(k):
        t = math.pi / 2 + j * pitch                    # one ray points straight up
        rim.append((cx + rt * math.cos(t), cy + rt * math.sin(t)))
        for q in range(arc + 1):
            b = t + hb + (pitch - 2 * hb) * q / arc
            rim.append((cx + rs * math.cos(b), cy + rs * math.sin(b)))
    pts = [(cx, cy)] + rim
    m = len(rim)
    faces = [(0, 1 + i, 1 + (i + 1) % m) for i in range(m)]
    return pts, faces, list(range(1, m + 1))


def _sm_ccw_faces(pts, faces):
    """Faces turned counter-clockwise (normal +Z)."""
    out = []
    for f in faces:
        area = sum(pts[f[i]][0] * pts[f[(i + 1) % len(f)]][1] - pts[f[(i + 1) % len(f)]][0] * pts[f[i]][1]
                   for i in range(len(f)))
        out.append(tuple(f) if area >= 0 else tuple(reversed(f)))
    return out


def _sm_place(shape, scale=1.0, offset=(0.0, 0.0), rot=0.0, centre=(0.0, 0.0)):
    """Shape moved: about ``centre`` (unit coordinates) rotated by ``rot`` (radians, CCW), scaled, then offset."""
    pts, faces, loop = shape
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for x, y in pts:
        x, y = x - centre[0], y - centre[1]
        out.append((offset[0] + scale * (c * x - s * y), offset[1] + scale * (s * x + c * y)))
    return out, faces, loop


def _sm_faces(bm, shape, z=0.0, back=False, mat=0):
    """A 2D shape as flat faces in the plane z, facing +Z (back=True: facing -Z). Returns the verts."""
    pts, faces, _loop = shape
    vs = [bm.verts.new((x, y, z)) for x, y in pts]
    for f in faces:
        fv = [vs[i] for i in f]
        face = bm.faces.new(fv[::-1] if back else fv)
        face.material_index = mat
    return vs


def _sm_slab(bm, shape, z0, z1, mat=0):
    """A 2D shape extruded from z0 to z1 (z1 > z0): front cap at z1 facing +Z, back cap at z0, side walls along
    the loop; closed and outward. Returns the verts."""
    pts, faces, loop = shape
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    made = []
    for f in faces:
        made.append(bm.faces.new([top[i] for i in f]))
        made.append(bm.faces.new([bot[i] for i in reversed(f)]))
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        made.append(bm.faces.new((bot[a], bot[b], top[b], top[a])))
    bmesh.ops.recalc_face_normals(bm, faces=made)
    for f in made:
        f.material_index = mat
    return top + bot


def _sunmoon_flat(bm, cx, cy, R, z=0.0, back=False, ring=True, mats=SM_MATS):
    """The sun-and-moon roundel as flat faces in the plane z (banner cloth), unit radius ``R`` (the ring's inner
    radius), centred at (cx, cy): ring (slot mats['ring']), crescent (mats['moon']), rayed sun (mats['sun']).
    Faces +Z (back=True: -Z, for the cloth's back face). Returns the verts."""
    made = []
    made += _sm_faces(bm, _sm_place(sm_moon_shape(20), R, (cx, cy)), z, back, mats["moon"])
    made += _sm_faces(bm, _sm_place(sm_sun_shape(2), R, (cx, cy)), z, back, mats["sun"])
    if ring:
        rv = _annulus(bm, R * SM_RING[0], R * SM_RING[1], 48, z, matrix=Matrix.Translation((cx, cy, 0)),
                      mat=mats["ring"])
        for f in _faces_of(rv):
            f.normal_update()
            if (f.normal.z < 0) != back:
                f.normal_flip()
        made += rv
    return made


def sunmoon_materials(cloth):
    """(moon, sun) materials for a sun-and-moon roundel on banner cloth ``cloth`` (index, name or Material):
    moon-white silk and gold thread on dark cloth; ink and vermilion on the light gold / moon-white cloths."""
    if _mname(cloth) in _LIGHT_BANNERS:
        return M.get("banner_7"), M.get("banner_0")
    return M.get("banner_5"), M.get("cloth_gold")


def _orient_up(bm, verts):
    """Make the faces of ``verts`` face +Z (flat cloth pieces built in the z=0 plane)."""
    for f in _faces_of(verts):
        if f.normal.z < 0:
            f.normal_flip()


def _banner_cloth_mesh(W, L, seed, wind, style, text, emblem, fresh=False):
    """Banner cloth in local XY (normal +Z = the front). 'fan': hangs from its apex at the origin
    down -Y: triangular head, gold stiffener rod, body divided by cross-bands into sections (one
    character per section, or the emblem roundel), two side streamers and three tapered tails.
    'qi': a flag whose hoist edge runs down the Y axis and flies out along +X, with flame-tooth
    borders on its three free edges and one big character (or the emblem) in a ring.
    ``emblem``: 'sunmoon' (the sect's sun-and-moon roundel, _sunmoon_flat), 'moon' (the older
    crescent roundel) or None. Static wind deformation is baked in; per-vertex weights for the
    wave modifier are stored in me['props_weights']. Materials: 0 cloth, 1 trim, 2 text/emblem
    ring, 3 gold fittings, 4 moon and 5 sun ('sunmoon' only). fresh=True builds a new mesh even
    when the shared one exists (patch scripts compare against the file's)."""
    tkey = "%08x" % (zlib.crc32((text or "").encode("utf-8")) & 0xFFFFFFFF)
    key = "props.banner_cloth.%s.%s.%s.%d.%s.%s.%s.v%d" % (style, _k(W), _k(L), seed % 4, _k(wind), tkey,
                                                         emblem or "none", _VERSION)

    def build():
        r = U.rng(seed % 4, "banner", style)
        ph, ph2, ph3 = r.uniform(0, TAU), r.uniform(0, TAU), r.uniform(0, TAU)
        swing = r.uniform(0.7, 1.0)
        bm = bmesh.new()
        rest = []

        def take(n0, fn):
            bm.verts.ensure_lookup_table()
            for v in bm.verts[n0:]:
                rest.append(v.co.copy())
                v.co = fn(v.co)

        if style == "qi":
            Wq, Hq = W, L

            def dq(co, extra=0.0):
                u = max(0.0, co.x / Wq)
                v = -co.y / Hq
                z = wind * Wq * (0.07 * u * math.sin(TAU * (1.05 * u - 0.1 * v) + ph)
                                 + 0.035 * u * u * math.sin(TAU * (2.1 * u + 0.4 * v) + ph2) + extra * u)
                return Vector((co.x * (1.0 - 0.05 * wind * u), co.y - wind * 0.10 * Hq * u * u, z + co.z))
            # body
            xs = [Wq * i / 12 for i in range(13)]
            ys = [-Hq * j / 8 for j in range(9)]
            n0 = len(bm.verts)
            vs = _cloth_rows(bm, [[(x, y) for x in xs] for y in ys],
                             lambda i, j: 1 if (j == 0 or j == 7 or i == 11) else 0)
            _orient_up(bm, vs)
            take(n0, dq)
            # flame-tooth border on the top, the fly (outer) edge and the bottom
            th, tw = 0.16 * Hq, 0.14 * Hq
            n0 = len(bm.verts)
            teeth = []
            nt = max(3, int(Wq / tw))
            for k in range(nt):
                x0, x1 = Wq * k / nt, Wq * (k + 1) / nt
                for sgn, ye in ((1, 0.0), (-1, -Hq)):
                    base = [(x0, ye), (x1, ye)]
                    tip = (x0 + 0.85 * (x1 - x0), ye + sgn * th)
                    mid = (x0 + 0.35 * (x1 - x0), ye + sgn * th * 0.55)
                    teeth.append([base[0], base[1], tip, mid] if sgn > 0 else [base[1], base[0], mid, tip])
            ntv = max(3, int(Hq / tw))
            for k in range(ntv):
                y0, y1 = -Hq * k / ntv, -Hq * (k + 1) / ntv
                tip = (Wq + th, y0 + 0.85 * (y1 - y0))
                mid = (Wq + th * 0.55, y0 + 0.35 * (y1 - y0))
                teeth.append([(Wq, y0), (Wq, y1), tip, mid][::-1])
            for poly in teeth:
                vv = [bm.verts.new((x, y, 0.0)) for x, y in poly]
                f = bm.faces.new(vv)
                f.material_index = 1
                if f.normal.z < 0:
                    f.normal_flip()
            take(n0, dq)
            cx, cy, R = Wq * 0.55, -Hq * 0.5, 0.36 * min(Wq, Hq)
            n0 = len(bm.verts)
            if text:
                me = _text_mesh(text[0], 1.0, 3)
                dm = _mesh_dims(me)
                f = 1.15 * R / max(dm.x, dm.y, 1e-6)
                for zo, mir in ((0.004, 1), (-0.004, -1)):
                    _add_mesh(bm, me, Matrix.Translation((cx, cy, zo)) @ Matrix.Diagonal((f * mir, f, f, 1)), 2)
                for zo in (0.003, -0.003):
                    _annulus(bm, R * 1.0, R * 1.08, 48, zo, matrix=Matrix.Translation((cx, cy, 0)), mat=2)
            elif emblem == "sunmoon":
                for zo in (0.003, -0.003):
                    _sunmoon_flat(bm, cx, cy, R * 0.8 * 1.22, z=zo, back=zo < 0)
            elif emblem:
                for zo in (0.003, -0.003):
                    _crescent(bm, cx, cy, R * 0.8, 2, z=zo)
            take(n0, dq)
            weights = [min(1.0, max(0.0, c.x / Wq)) ** 1.2 for c in rest]
        else:
            hh = 0.42 * W                         # head triangle height
            Lb = max(0.5 * W, (L - hh) / 1.26)    # body length; tails are 0.26 of it
            tail_L = 0.26 * Lb
            Lt = hh + Lb + tail_L

            def df(co, extra=0.0, rigid=False):
                x, y = (0.0 if rigid else co.x), co.y
                v = min(1.0, max(0.0, -y / Lt))
                xc = max(-0.75, min(0.75, x / W))
                u = xc + 0.5
                z = wind * W * (0.16 * math.cos(math.pi * xc) * v ** 0.8
                                + 0.10 * v * math.sin(TAU * (1.3 * v + 0.35 * u) + ph)
                                + 0.05 * v * v * math.sin(TAU * (2.1 * v - 0.6 * u) + ph2)
                                + 0.03 * (1 - math.cos(math.pi * min(1.0, max(0.0, u)))) * v
                                + extra * v * math.sin(TAU * 1.6 * v + ph3))
                dx = wind * swing * Lt * 0.05 * v * v
                dy = wind * Lt * 0.01 * v * v
                return Vector((co.x + dx, co.y + dy, z + co.z))
            # head triangle (fan tou): trim border on the slopes and the base
            n0 = len(bm.verts)
            rows = []
            for j in range(6):
                t = j / 5
                hw_ = 0.05 * W + (0.52 * W - 0.05 * W) * t
                rows.append([(-hw_ + 2 * hw_ * i / 6, -hh * t) for i in range(7)])
            _cloth_rows(bm, rows, lambda i, j: 1 if (i in (0, 5) or j == 4) else 0)
            take(n0, df)
            # body: side borders, cross-bands between sections
            nsec = max(1, min(6, len(text))) if text else 3
            bh = 0.07 * W
            hs = (Lb - (nsec + 1) * bh) / nsec
            y = -hh
            ys, kinds = [y], []
            for s_ in range(nsec):
                ys.append(y - bh)
                kinds.append(1)
                y -= bh
                nsub = max(2, int(round(hs / (0.22 * W))))
                for q in range(1, nsub + 1):
                    ys.append(y - hs * q / nsub)
                    kinds.append(0)
                y -= hs
            ys.append(y - bh)
            kinds.append(1)
            y -= bh
            bw = 0.075 * W
            xs = [-W / 2, -W / 2 + bw] + [-W / 2 + bw + (W - 2 * bw) * q / 6 for q in range(1, 6)] + [W / 2 - bw, W / 2]
            n0 = len(bm.verts)
            _cloth_rows(bm, [[(x, yy) for x in xs] for yy in ys],
                        lambda i, j: 1 if (i == 0 or i == len(xs) - 2 or kinds[j]) else 0)
            take(n0, df)
            body_bottom = y
            # three tapered tails (fan zu)
            gap = 0.025 * W
            tw = (W - 2 * gap) / 3
            for q in range(3):
                x0 = -W / 2 + q * (tw + gap)
                cxq = x0 + tw / 2
                lq = tail_L * (1.0 if q == 1 else 0.86)
                rows = []
                for j in range(7):
                    t = j / 6
                    half = tw / 2 * (1 - 0.92 * t ** 1.3)
                    rows.append([(cxq - half + 2 * half * i / 2, body_bottom + 0.01 * W - lq * t) for i in range(3)])
                n0 = len(bm.verts)
                _cloth_rows(bm, rows, lambda i, j: 1 if j >= 5 else 0)
                take(n0, lambda co: df(co, extra=0.06 * W))
            # side streamers (fan shou) hanging from the rod ends
            for sx in (-1, 1):
                cxs = sx * (W / 2 + 0.085 * W)
                sw_ = 0.09 * W
                ls = 0.62 * Lb
                rows = []
                for j in range(13):
                    t = j / 12
                    half = sw_ / 2 * (1 - 0.7 * max(0.0, t - 0.75) / 0.25)
                    rows.append([(cxs - half + 2 * half * i / 2, -hh - 0.02 * W - ls * t) for i in range(3)])
                n0 = len(bm.verts)
                _cloth_rows(bm, rows, lambda i, j: 1 if j >= 10 else 0)
                take(n0, lambda co, sx=sx: df(co, extra=0.10 * W))
            # stiffener rod with knobs at the head base (rigid: moved with the cloth, not bent)
            n0 = len(bm.verts)
            rl = W / 2 + 0.13 * W
            _tube(bm, [(-rl, -hh, 0.0), (rl, -hh, 0.0)], 0.02 * W, 8, 1, mat=3)
            for sx in (-1, 1):
                _sphere(bm, 0.035 * W, (sx * (rl + 0.02 * W), -hh, 0.0), 10, 6, mat=3)
            take(n0, lambda co: df(co, rigid=True))
            # text, one character per section, both faces; or a crescent roundel in the first section
            n0 = len(bm.verts)
            y = -hh - bh
            for s_ in range(nsec):
                yc = y - hs / 2
                if text:
                    me = _text_mesh(text[s_], 1.0, 3)
                    dm = _mesh_dims(me)
                    f = min(0.66 * W, 0.78 * hs) / max(dm.x, dm.y, 1e-6)
                    for zo, mir in ((0.005, 1), (-0.005, -1)):
                        _add_mesh(bm, me, Matrix.Translation((0, yc, zo)) @ Matrix.Diagonal((f * mir, f, f, 1)), 2)
                elif emblem == "sunmoon" and s_ == 0:
                    for zo in (0.004, -0.004):
                        _sunmoon_flat(bm, 0.0, yc, 1.22 * min(0.26 * W, 0.3 * hs), z=zo, back=zo < 0)
                elif emblem and s_ == 0:
                    for zo in (0.004, -0.004):
                        _crescent(bm, 0.0, yc, min(0.26 * W, 0.3 * hs), 2, z=zo)
                y -= hs + bh
            take(n0, df)
            weights = [min(1.0, max(0.0, -c.y / Lt)) ** 1.2 for c in rest]
        me = bpy.data.meshes.new(key)
        bm.to_mesh(me)
        bm.free()
        mats = [p.material_index for p in me.polygons]
        smooth = [m_ in (0, 1, 3) for m_ in mats]
        me.polygons.foreach_set("use_smooth", smooth)
        me["props_weights"] = weights
        me.update()
        return me

    return build() if fresh else U.shared_mesh(key, build)


def _banner_pole_meshes(H, W, style):
    """Shared pole, clamping stones and gold fittings (finial; 'fan': a long arm with a
    cloud-scroll end, brace and hook; 'qi': hoist rings)."""
    La = 0.75 + 0.6 * W                         # arm reach: the cloth hangs centred under its end

    def pole():
        bm = bmesh.new()
        _lathe(bm, [(0, 0), (0.07, 0), (0.065, H * 0.5), (0.05, H - 0.02), (0.0, H - 0.02)], 16)
        return bm

    def stones():
        bm = bmesh.new()
        _sq_lathe(bm, [(0, 0), (0.34, 0), (0.34, 0.10), (0.31, 0.13), (0, 0.13)])
        outline = [(0.19, 0.13)] + [(0.19 * math.cos(math.pi * i / 12), 0.62 + 0.12 * math.sin(math.pi * i / 12))
                                    for i in range(13)] + [(-0.19, 0.13)]
        for sx in (-1, 1):
            vs = _prism(bm, outline, 0.12, y0=-0.06)
            _xf(bm, Matrix.Translation((sx * 0.135, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Z'), vs)
        _outward(bm)
        return bm

    def gold():
        bm = bmesh.new()
        _lathe(bm, [(0.0, H - 0.03), (0.062, H - 0.03), (0.07, H), (0.05, H + 0.04), (0.08, H + 0.11),
                    (0.05, H + 0.18), (0.022, H + 0.21), (0.045, H + 0.30), (0.03, H + 0.40), (0.0, H + 0.52)], 16)
        if style == "qi":
            for z in (H - 0.34 - 0.25 * W * q for q in range(4)):
                _torus(bm, 0.075, 0.012, 16, 6, matrix=Matrix.Translation((0, 0, z)))
            return bm
        za = H - 0.35
        _lathe(bm, [(0.0, za - 0.04), (0.078, za - 0.04), (0.078, za + 0.04), (0.0, za + 0.04)], 16)
        _tube(bm, [(0.0, 0, za), (La * 0.5, 0, za + 0.012), (La, 0, za)], 0.03, 8, 3)
        curl = [(La, 0, za), (La + 0.09, 0, za + 0.012), (La + 0.17, 0, za - 0.025), (La + 0.175, 0, za - 0.09),
                (La + 0.12, 0, za - 0.125), (La + 0.075, 0, za - 0.095), (La + 0.09, 0, za - 0.055),
                (La + 0.125, 0, za - 0.06)]
        _tube(bm, [p + (1.0 - 0.55 * i / (len(curl) - 1),) for i, p in enumerate(curl)], 0.034, 8, 3)
        _tube(bm, [(La + 0.02, 0, za + 0.01), (La + 0.08, 0, za + 0.07), (La + 0.15, 0, za + 0.06),
                   (La + 0.17, 0, za + 0.02)], 0.016, 6, 3)
        _tube(bm, [(0.0, 0, za - 0.55), (0.25, 0, za - 0.28), (0.5, 0, za - 0.02)], 0.018, 6, 3)
        _torus(bm, 0.022, 0.006, 12, 6, matrix=Matrix.Translation((La, 0, za - 0.045)) @
               Matrix.Rotation(math.pi / 2, 4, 'X'))
        return bm

    return (_mesh("props.banner_pole.%s" % _k(H), pole, ["lacquer_red"], smooth=math.radians(40)),
            _mesh("props.banner_stones", stones, ["stone_grey"], smooth=False, bevel=0.012),
            _mesh("props.banner_gold.%s.%s.%s" % (style, _k(H), _k(W)), gold, ["gold"], smooth=math.radians(40)),
            La)


_LIGHT_BANNERS = ("banner_1", "banner_5")     # gold and moon-white cloth take ink-black trim


def banner(collection, height=6.0, width=1.0, material=0, pole=True, seed=0, length=None, trim="auto",
           wind=1.0, animate=True, pole_material="lacquer_red", style="fan", text_zh=None, emblem="sunmoon",
           name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Chinese sect banner. Front faces -Y; origin at the pole foot (pole=False: at the hook).

    style 'fan' (default; a temple/sect fan): a ``width`` m wide cloth hanging from the end of a
    long gold arm (0.75 + 0.6*width m from the pole, so the cloth is well clear of it): a
    triangular head (fan tou) on a gold stiffener rod, a body divided by gold cross-bands into
    sections, two side streamers and three tapered tails. ``text_zh`` puts one character per
    section (up to 6, both faces); without text the first section carries the sect's emblem in a
    ring: ``emblem='sunmoon'`` (default; the Ming Sect's 明 = 日 + 月: a crescent moon cradling a
    rayed sun, moon-white and gold on dark cloth, ink and vermilion on gold / white cloth, see
    sunmoon_materials), 'moon' (the older crescent alone) or None (plain). ``length`` = cloth
    length from the hook (default 0.6*height, clamped so the tails stay 0.4 m above the ground).
    style 'qi' (a flag): flies out from rings on the pole top, ``width`` m out and ``length``
    (default 0.8*width) tall, flame-tooth borders on its three free edges, one big character
    (``text_zh[0]``) or the emblem in a ring.
    Trim (``trim``; 'auto' = gold, or ink black on gold/white cloth) borders, bands and text.
    ``material``: banner colour index (int, materials.banner_cloth), a name or a Material.
    Static seeded billow, plus (animate=True) a Wave modifier sending ripples down (fan) or out
    (qi) the cloth over the frames. pole=False: the fan alone hanging from a hook at the origin
    (eaves, beams). Meshes are shared (pole/stones/fittings per height, cloth per size, seed % 4,
    text). Returns the root Empty."""
    if style not in ("fan", "qi"):
        raise ValueError("banner style must be 'fan' or 'qi'")
    if style == "qi" and not pole:
        raise ValueError("banner style 'qi' needs pole=True")
    main = _mat(material)
    if trim == "auto":
        trim = "banner_7" if _mname(material) in _LIGHT_BANNERS else "cloth_gold"
    root = _root(collection, name, "banner", parent, location, rotation, scale)
    pn = root.name
    za = height - 0.35
    if style == "qi":
        L = length or 0.8 * width
        L = max(0.3, min(L, height - 1.2))
    else:
        L = length or height * 0.6
        if pole:
            L = max(0.8, min(L, za - 0.06 - 0.4))
        L = max(0.5 * width + 0.3, L)
    if pole:
        pme, sme, gme, La = _banner_pole_meshes(height, width, style)
        po = _obj(U.unique_name(pn + ".pole"), pme, collection, parent=root)
        if pole_material != "lacquer_red":
            U.set_object_material(po, pole_material, 0)
        _obj(U.unique_name(pn + ".stones"), sme, collection, parent=root)
        _obj(U.unique_name(pn + ".gold"), gme, collection, parent=root)
        top = Vector((0.07, 0.0, height - 0.32)) if style == "qi" else Vector((La, 0.0, za - 0.06))
    else:
        def hook():
            bm = bmesh.new()
            _torus(bm, 0.022, 0.006, 12, 6, matrix=Matrix.Translation((0, 0, -0.03)) @
                   Matrix.Rotation(math.pi / 2, 4, 'X'))
            _tube(bm, [(0, 0, 0.0), (0, 0, -0.01)], 0.008, 6, 1)
            return bm
        hme = _mesh("props.banner_hook", hook, ["gold"], smooth=True)
        _obj(U.unique_name(pn + ".hook"), hme, collection, parent=root)
        top = Vector((0.0, 0.0, -0.06))
    cme = _banner_cloth_mesh(width, L, seed, wind, style, text_zh, emblem)
    cl = U.object_from_mesh(U.unique_name(pn + ".cloth"), cme, collection, parent=root, location=top,
                            rotation=(math.pi / 2, 0, 0))
    tm = _mat(trim)
    for slot, m in enumerate((main, tm, tm, M.get("gold"))):
        U.set_object_material(cl, m, slot)
    if emblem == "sunmoon" and not text_zh:
        moon_m, sun_m = sunmoon_materials(material)
        U.set_object_material(cl, moon_m, SM_MATS["moon"])
        U.set_object_material(cl, sun_m, SM_MATS["sun"])
    if animate:
        vg = cl.vertex_groups.get("flutter")
        if vg is None:                          # vertex groups live on the (shared) mesh in 5.x
            vg = cl.vertex_groups.new(name="flutter")
            for i, w in enumerate(cme.get("props_weights", [])):
                if w > 0:
                    vg.add([i], float(w), 'REPLACE')
        wv = cl.modifiers.new("props_wind", 'WAVE')
        wv.use_cyclic = True
        wv.use_normal = True
        wv.use_normal_x, wv.use_normal_y, wv.use_normal_z = False, False, True
        wv.start_position_x, wv.start_position_y = 0.0, 0.0
        span = width if style == "qi" else L
        wv.use_x, wv.use_y = (True, False) if style == "qi" else (False, True)
        wv.height = 0.15 * width * wind
        wv.width = max(0.3, span * 0.22)
        wv.narrowness = 1.8 / wv.width          # Gaussian floor exp(-(w*n)^2) ~ 0: full height
        wv.speed = 0.022 * span / 4.0
        wv.time_offset = -400.0 - (U.seed_from(seed, "wave") % 97)
        wv.vertex_group = "flutter"
    return root


# ============================================================ sun-and-moon emblem in the round

_XZ = Matrix.Rotation(math.pi / 2, 4, 'X')      # a shape drawn in XY (y up, +Z front) stood up facing -Y
SM_FIN_SINK = 0.30                               # finial: tenon buried this far (x R) into the ridge
SM_FIN_TENON = 0.07                              # finial: tenon radius (x R), thinner than a ridge roll's crest, so
                                                 # it never shows through the ridge's faces (0.21 R poked 8 cm out
                                                 # of each face of the gate's 0.39 m ridge as a gold stub)


def _sm_upright(bm, shape, t, mat, z_up):
    """A 2D emblem shape (metres, y up) as a slab ``t`` thick centred on y = 0, standing at height z_up, facing -Y."""
    vs = _sm_slab(bm, _sm_place(shape, 1.0, (0.0, z_up)), -t / 2, t / 2, mat)
    _xf(bm, _XZ, vs)
    return vs


def sunmoon_finial(collection, R=1.3, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Gilt sun-and-moon ridge finial 日月宝顶 for the middle of a main ridge: the sect's emblem in the round. Origin
    on the ridge top, Z up, front -Y. A lotus base on a vase neck seated on the ridge's crest, held by a thin tenon
    (SM_FIN_TENON * R) sunk SM_FIN_SINK * R into the ridge; a stem; the
    crescent (silver, horns up, 0.16 R thick) and the rayed sun (gold, 0.12 R thick, a boss on each face) held in its
    cup by the stem, which shows only in the thin gap between them. ``R`` = the emblem's unit radius (m): the moon is
    1.72 R wide and the finial stands about 2.0 R above the ridge. Returns the root Empty; children '.gold' (base,
    stem, sun) and '.moon' (crescent)."""
    root = _root(collection, name, "sunmoon_finial", parent, location, rotation, scale)
    pn = root.name
    (_c1, r1, _c2, _r2) = SM_MOON
    (scx, scy), rs, rt, _k_ = SM_SUN
    cup = 0.27 * R
    z_e = cup + (r1 - SM_MOON[0][1]) * R - 0.07 * R     # emblem centre: the moon's foot sits 0.07 R into the cup
    z_sun = z_e + scy * R

    bm = bmesh.new()
    s = -SM_FIN_SINK * R
    tn = SM_FIN_TENON * R
    prof = [(0.0, s), (tn, s), (tn, -0.01 * R), (0.28 * R, 0.0), (0.28 * R, 0.035 * R),
            (0.18 * R, 0.085 * R), (0.13 * R, 0.125 * R), (0.17 * R, 0.165 * R), (0.29 * R, 0.235 * R),
            (0.32 * R, cup), (0.0, cup - 0.01 * R)]
    _lathe(bm, prof, 24, rmod=lambda th, i, r, z: r * (1.0 + 0.07 * abs(math.cos(4 * th))) if i in (8, 9) else r)
    _lathe(bm, [(0.0, cup - 0.02 * R), (0.05 * R, cup - 0.02 * R), (0.05 * R, z_sun), (0.0, z_sun)], 12)
    _sm_upright(bm, _sm_place(sm_sun_shape(3), R), 0.12 * R, 0, z_e)
    _sphere(bm, 0.17 * R, (0.0, 0.0, z_sun), 16, 8, scale=(1.0, 0.55, 1.0))
    _outward(bm)
    _mk(U.unique_name(pn + ".gold"), bm, collection, ["gold"], parent=root, smooth=math.radians(35))

    bm = bmesh.new()
    _sm_upright(bm, _sm_place(sm_moon_shape(28), R), 0.16 * R, 0, z_e)
    _mk(U.unique_name(pn + ".moon"), bm, collection, ["silver"], parent=root, smooth=math.radians(35))
    return root


def sunmoon_medallion(collection, radius=1.0, part="both", depth=0.10, moon_rot=math.pi / 2, name=None, parent=None,
                      location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Wall medallion with the sect's emblem in relief. Origin at the centre of its back on the wall, front -Y (the
    back sinks 0.02 m into the wall). A lacquered disc (plaque_board, ``radius`` m, ``depth`` m thick), a gilt
    rope rim, and in relief: part 'both' the full emblem, 'sun' the rayed sun alone (gold), 'moon' the crescent
    alone (silver) turned by ``moon_rot`` (default: horns toward -X). Returns the root Empty; children '.disc',
    '.gold' (rim and sun) and '.moon' (crescent; not for 'sun')."""
    if part not in ("both", "sun", "moon"):
        raise ValueError("medallion part must be 'both', 'sun' or 'moon'")
    root = _root(collection, name, "sunmoon_medallion", parent, location, rotation, scale)
    pn = root.name
    r, d = radius, depth
    # the relief: a slab 0.05 r proud of the disc face (0.01 r sunk into it)
    z0, z1 = d - 0.01 * r, d + 0.05 * r
    (c1x, c1y), r1, _c2, _r2 = SM_MOON
    (scx, scy), _rs, rt, _k_ = SM_SUN
    if part == "both":
        moon = _sm_place(sm_moon_shape(28), 0.80 * r)
        sun = _sm_place(sm_sun_shape(3), 0.80 * r)
    elif part == "sun":
        moon, sun = None, _sm_place(sm_sun_shape(3), 0.74 * r / rt, centre=(scx, scy))
    else:
        cy = c1y - 0.20                                   # the crescent's bounding-box centre (horns up)
        reach = r1 + abs(c1y - cy)
        moon, sun = _sm_place(sm_moon_shape(28), 0.76 * r / reach, rot=moon_rot, centre=(c1x, cy)), None

    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.02), (r, -0.02), (r, 0.7 * d), (0.97 * r, d), (0.0, d)], 48, matrix=_XZ)
    _mk(U.unique_name(pn + ".disc"), bm, collection, ["plaque_board"], parent=root, smooth=math.radians(35))

    bm = bmesh.new()
    _torus(bm, 0.925 * r, 0.045 * r, 48, 8, matrix=_XZ @ Matrix.Translation((0, 0, d)))
    if sun is not None:
        vs = _sm_slab(bm, sun, z0, z1)
        _xf(bm, _XZ, vs)
        (sx, sy) = sun[0][0]
        _sphere(bm, 0.15 * r if part == "sun" else 0.11 * r, (sx, -z1 + 0.01 * r, sy), 16, 8, scale=(1.0, 0.45, 1.0))
    _outward(bm)
    _mk(U.unique_name(pn + ".gold"), bm, collection, ["gold"], parent=root, smooth=math.radians(35))

    if moon is not None:
        bm = bmesh.new()
        vs = _sm_slab(bm, moon, z0, z1)
        _xf(bm, _XZ, vs)
        _mk(U.unique_name(pn + ".moon"), bm, collection, ["silver"], parent=root, smooth=math.radians(35))
    return root


# ============================================================ more shared helpers

def _add_mesh_fn(bm, me, fn, mat=0, smooth=False):
    """Append mesh data ``me`` to ``bm`` with every vertex mapped by fn(Vector) -> Vector
    (non-linear placement: glyphs bent onto cylinders, scrolls, bells)."""
    tmp = bmesh.new()
    tmp.from_mesh(me)
    for v in tmp.verts:
        v.co = fn(v.co.copy())
    for f in tmp.faces:
        f.material_index = mat
        f.smooth = smooth
    m2 = bpy.data.meshes.new("props_tmp_add")
    tmp.to_mesh(m2)
    tmp.free()
    bm.from_mesh(m2)
    bpy.data.meshes.remove(m2)


def _prof_r(prof, z):
    """Radius of a (r, z) profile (z increasing) at height z (linear interpolation)."""
    pts = sorted([(zz, r) for r, zz in prof])
    if z <= pts[0][0]:
        return pts[0][1]
    for (z0, r0), (z1, r1) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / max(z1 - z0, 1e-9)
            return r0 + (r1 - r0) * t
    return pts[-1][1]


def _strip(bm, path, widths, twist=0.0, up=(0, 0, 1)):
    """Flat ribbon along 3D ``path`` (list of Vectors), width per point, rotating ``twist``
    radians in total about the path (curling smoke, cords, streamers)."""
    fr = _frames([tuple(p) for p in path])
    n = len(path)
    L, R = [], []
    for i, ((c, t, nrm, b), w) in enumerate(zip(fr, widths)):
        a = twist * i / max(n - 1, 1)
        d = nrm * math.cos(a) + b * math.sin(a)
        L.append(bm.verts.new(c + d * w * 0.5))
        R.append(bm.verts.new(c - d * w * 0.5))
    for i in range(n - 1):
        bm.faces.new((L[i], R[i], R[i + 1], L[i + 1]))
    return L + R


def _smoke_wisp(g, colour="#d8d4cc", opacity=0.5):
    """Soft transparent smoke ribbon: fades in at the bottom and out toward the top (generated Z),
    broken up by drifting noise. Blended, casts no shadow."""
    g.blended(shadows=False)
    z = g.sep(g.coord("generated"))[2]
    fade = g.mul(g.smooth(z, 0.0, 0.06), g.math('POWER', g.math('SUBTRACT', 1.0, z), 1.4))
    v = g.flow(g.coord("object"), (0, 0, -0.004))
    n = g.noise(g.mapping(v, scale=(5.0, 5.0, 1.6)), 1.0, detail=3.0, roughness=0.55)
    br = g.smooth(n, 0.32, 0.62)
    a = g.mul(g.mul(fade, br), opacity)
    g.viewport(colour, 1.0)
    g.output(g.principled(base_color=colour, roughness=1.0, alpha=a, specular_ior_level=0.0))


def _molten_fine(g, strength=5.0, speed=0.01, scale=2.6):
    """Molten metal like materials 'molten' but with ``scale`` x finer crust cells and a deeper
    orange ramp (keeps its colour under AgX at moderate strength)."""
    v = g.coord("object", scale=scale)
    w = g.node("ShaderNodeValue")
    g.frame_driven(w.outputs[0], "frame*%r" % speed)
    t = w.outputs[0]
    heat = g.noise(v, 1.4, detail=5.0, roughness=0.55, distortion=0.6, dims='4D', w=t)
    crust = g.voronoi(v, 2.2, feature='DISTANCE_TO_EDGE', dims='4D', w=t, randomness=0.9)
    crust_m = g.mul(g.smooth(crust, 0.02, 0.12), g.smooth(heat, 0.55, 0.38))
    temp = g.mul(g.math('SUBTRACT', 1.0, crust_m), g.maprange(heat, 0.25, 0.8, 0.45, 1.0))
    col = g.ramp(temp, [(0.0, "#1a0501"), (0.3, "#a02402"), (0.55, "#ff6206"), (0.8, "#ffa018"), (1.0, "#ffd050")])
    k = g.obj_prop("glow", 1.0)
    em = g.mul(g.mul(g.math('POWER', temp, 1.5), strength), k)
    g.viewport("#ff5a0a", 0.4)
    g.output(g.principled(base_color="#1a0c06", roughness=g.mixf(0.25, 0.85, crust_m),
                          emission_color=col, emission_strength=em, normal=g.bump(crust_m, 0.4, 0.02)))


M.register("props_smoke_wisp", _smoke_wisp)
M.register("props_molten", _molten_fine)
_variant("props_heat", "light_beam", colour="#ff5a0a", core="#ffb060", strength=0.55, speed=0.01)


def _proto_ember(key="ember", material="ember", r=0.012, glow=1.0):
    """Tiny emissive icosphere prototype for point instancers."""
    def build(pc):
        bm = bmesh.new()
        _ico(bm, r, subdiv=2)
        _mk(_nm(key), bm, pc, [material], smooth=True, glow=glow)
    return _proto_object("pt.%s.%s" % (key, _k(r)), build)


def _taotie(bm, theta, z, r, s, mat=0):
    """Stylised taotie mask relief on a round surface (radius r at height z, around angle theta,
    scale s): oval eye bosses, curled brows, a nose ridge and horn curls."""
    def P(da, dz, dr=0.0):
        a = theta + da / r
        return (math.cos(a) * (r + dr), math.sin(a) * (r + dr), z + dz)
    out = Vector((math.cos(theta), math.sin(theta), 0))
    tang = Vector((-math.sin(theta), math.cos(theta), 0))
    for side in (-1, 1):
        c = Vector(P(side * 0.075 * s, 0.0, 0.008 * s))
        m = Matrix((tang, out, Vector((0, 0, 1)))).transposed().to_4x4()
        _sphere(bm, 0.022 * s, (0, 0, 0), 10, 6, scale=(1.5, 0.55, 1.0), matrix=Matrix.Translation(c) @ m, mat=mat)
        brow = [P(side * da * s, dz * s, 0.004 * s) for da, dz in ((0.02, 0.03), (0.07, 0.042), (0.12, 0.035),
                                                                    (0.15, 0.015), (0.135, 0.0))]
        _tube(bm, brow, 0.007 * s, 6, 3, mat=mat)
        horn = [P(side * da * s, dz * s, 0.004 * s) for da, dz in ((0.17, -0.03), (0.21, -0.005), (0.22, 0.03),
                                                                    (0.19, 0.045), (0.17, 0.025))]
        _tube(bm, horn, 0.006 * s, 6, 3, mat=mat)
    _tube(bm, [P(0, -0.04 * s, 0.004 * s), P(0, 0.0, 0.006 * s), P(0, 0.04 * s, 0.004 * s)], 0.008 * s, 6, 2, mat=mat)


def _notched_fin(r_of_z, z0, z1, depth, thick, notch=0.075, notch_d=0.28):
    """Outline (x = radial, z) of a vertical flange (fei leng) following a surface radius
    r_of_z, protruding ``depth`` with castellated notches every ``notch``."""
    pts_out, pts_in = [], []
    n = max(2, int((z1 - z0) / (notch / 2)))
    for i in range(n + 1):
        z = z0 + (z1 - z0) * i / n
        rs = r_of_z(z)
        notch_on = (i % 2 == 1) and 0 < i < n
        pts_out.append((rs + depth * (1 - notch_d if notch_on else 1.0), z))
        pts_in.append((rs - 0.004, z))
    return pts_in + pts_out[::-1]


# ============================================================ cauldron (ding)

def _ding_round(pc, s, lit, material, sparks, light, smoke):
    S = Matrix.Diagonal((s, s, s, 1.0))
    outer = [(0.0, 0.27), (0.18, 0.275), (0.30, 0.31), (0.37, 0.38), (0.40, 0.47), (0.395, 0.56), (0.38, 0.64),
             (0.372, 0.70), (0.386, 0.705), (0.386, 0.765), (0.372, 0.77), (0.378, 0.782), (0.41, 0.797),
             (0.415, 0.81), (0.392, 0.815), (0.362, 0.80), (0.352, 0.76), (0.345, 0.70), (0.0, 0.70)]
    bm = bmesh.new()
    _lathe(bm, outer, 64, cap_start=False, cap_end=False, matrix=S)
    r_of_z = lambda z: _prof_r(outer[1:8], z)
    for k in range(6):                                     # flanges between the masks
        th = TAU * k / 6
        vs = _prism(bm, _notched_fin(r_of_z, 0.40, 0.77, 0.032, 0.012), 0.014, y0=-0.007)
        _xf(bm, S @ Matrix.Rotation(th, 4, 'Z'), vs)
    for k in range(6):                                     # taotie masks on the neck band
        _taotie(bm, TAU * k / 6 + math.pi / 6, 0.735 * s, 0.386 * s, s)
    for zz in (0.45, 0.62):                                # belly ridges with a wave band between
        pts = []
        for i in range(97):
            a = TAU * i / 96
            rr = _prof_r(outer[1:8], zz) + 0.004
            pts.append((rr * math.cos(a) * s, rr * math.sin(a) * s, zz * s))
        _tube(bm, pts[:-1], 0.006 * s, 6, 1, closed=True, smooth_path=False)
    wave = []
    for i in range(193):
        a = TAU * i / 192
        zz = 0.535 + 0.045 * math.sin(6 * a + math.pi / 2)
        rr = _prof_r(outer[1:8], zz) + 0.004
        wave.append((rr * math.cos(a) * s, rr * math.sin(a) * s, zz * s))
    _tube(bm, wave[:-1], 0.009 * s, 6, 1, closed=True, smooth_path=False)
    for side in (-1, 1):                                   # upright ears, opening facing the front
        _arch_wall(bm, 0.15, 0.20, 0.04, 0.085, 0.125, 0.012,
                   S @ Matrix.Translation((side * 0.392, 0, 0.795)) @ Matrix.Rotation(side * 0.12, 4, 'Y'))
    for k in range(3):                                     # hoof legs with mask bulges
        th = math.pi / 2 + TAU * k / 3
        m = S @ Matrix.Translation((0.27 * math.cos(th), 0.27 * math.sin(th), 0.0)) @ \
            Matrix.Rotation(0.06, 4, Vector((-math.sin(th), math.cos(th), 0)))
        _lathe(bm, [(0.0, 0.0), (0.072, 0.0), (0.076, 0.02), (0.056, 0.05), (0.043, 0.10), (0.040, 0.18),
                    (0.052, 0.24), (0.078, 0.29), (0.07, 0.335), (0.0, 0.36)], 20, matrix=m)
    _merge(bm, 1e-6)
    _outward(bm)
    body = _mk(_nm("ding.body"), bm, pc, [material], smooth=math.radians(40), bevel=0.003 * s, angle=math.radians(50))
    _ding_fill(pc, s, lit, 0.355, 0.752, sparks, light, smoke)
    return body


def _ding_fill(pc, s, lit, r_in, z_top, sparks, light, smoke):
    """Molten (lit) or ash (unlit) surface, heat aura, rising embers and an optional light."""
    bm = bmesh.new()
    _lathe(bm, [(r_in * s, (z_top - 0.012) * s), (r_in * 0.7 * s, (z_top - 0.004) * s), (0.0, z_top * s)], 48,
           cap_start=True)
    _mk(_nm("ding.molten" if lit else "ding.ash"), bm, pc, ["props_molten" if lit else "props_ash"], smooth=True,
        glow=1.0 if lit else None)
    if not lit:
        return
    bm = bmesh.new()
    _lathe(bm, [(r_in * 0.92 * s, (z_top - 0.03) * s), (r_in * 0.55 * s, (z_top + 0.75) * s)], 32,
           cap_start=False, cap_end=False)
    heat = _mk(_nm("ding.heat"), bm, pc, ["props_heat"], smooth=True)
    U.set_visibility(heat, shadow=False)
    if sparks:
        r = U.rng("ding_sparks", s)
        ember = _proto_ember("ember", "ember", 0.008 * s, 1.0)
        pts, scl, ph = [], [], []
        for i in range(70):
            a, rr = r.uniform(0, TAU), r_in * 0.8 * math.sqrt(r.random())
            pts.append((rr * math.cos(a) * s, rr * math.sin(a) * s, z_top * s))
            scl.append(r.uniform(0.5, 1.3))
            ph.append(r.random())
        _point_instancer(_nm("ding.sparks"), pc, ember, pts, scales=scl, phases=ph,
                         drift=dict(rise=0.45 * s, height=1.3 * s, wobble=0.12 * s, speed=0.4))
    if smoke:
        bm = bmesh.new()
        _cyl(bm, 0.42 * s, 2.4 * s, 16, (0, 0, (z_top + 1.25) * s))
        sm = _mk(_nm("ding.smoke"), bm, pc, ["smoke_volume"], smooth=False)
        sm["density"] = 2.0
    if light:
        ld = bpy.data.lights.new(_nm("ding.light"), 'POINT')
        ld.color = (1.0, 0.45, 0.12)
        ld.energy = 260.0 * s * s
        ld.shadow_soft_size = 0.3 * s
        lo = bpy.data.objects.new(_nm("ding.light"), ld)
        pc.objects.link(lo)
        lo.location = (0, 0, (z_top + 0.25) * s)


def _ding_square(pc, s, lit, material, sparks, light, smoke):
    S = Matrix.Diagonal((s, s, s, 1.0))
    bm = bmesh.new()
    hx0, hy0, hx1, hy1 = 0.30, 0.235, 0.32, 0.25           # bottom / top half sizes (slight taper)
    z0, z1 = 0.33, 0.76
    # outer box (tapered), lip, inner wall
    def rect(hx, hy, z):
        return [bm.verts.new(S @ Vector(p)) for p in ((-hx, -hy, z), (hx, -hy, z), (hx, hy, z), (-hx, hy, z))]
    loops = [rect(hx0 - 0.02, hy0 - 0.02, z0 - 0.02), rect(hx0, hy0, z0), rect(hx1, hy1, z1 - 0.03),
             rect(hx1 + 0.02, hy1 + 0.02, z1), rect(hx1 + 0.02, hy1 + 0.02, z1 + 0.018),
             rect(hx1 - 0.015, hy1 - 0.015, z1 + 0.018), rect(hx1 - 0.02, hy1 - 0.02, z1 - 0.04)]
    for a, b in zip(loops, loops[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[-1])
    # nipple bosses (ru ding): U-shaped bands on each face; taotie in the centre field
    for face in range(4):
        th = face * math.pi / 2
        half_w = hx1 if face % 2 == 0 else hy1
        dist = hy1 if face % 2 == 0 else hx1
        R = Matrix.Rotation(th, 4, 'Z')
        def onface(u, z, dr=0.0):
            # u along the face (local x), z up; the face's outward normal is -Y before rotation
            d = dist - (dist - (hy0 if face % 2 == 0 else hx0)) * (z1 - z) / (z1 - z0)
            return R @ Vector((u, -(d + dr), z))
        cols = 3
        for row in range(3):
            for i in range(cols):
                for sgn in (-1, 1):
                    u = sgn * (half_w - 0.05 - 0.04 * i)
                    z = 0.42 + 0.09 * row
                    _lathe(bm, [(0.014, 0.0), (0.011, 0.012), (0.0, 0.02)], 10,
                           matrix=S @ Matrix.Translation(onface(u, z)) @ R @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        for i in range(int((2 * half_w - 0.30) / 0.04) + 1):
            u = -half_w + 0.15 + 0.04 * i
            _lathe(bm, [(0.014, 0.0), (0.011, 0.012), (0.0, 0.02)], 10,
                   matrix=S @ Matrix.Translation(onface(u, 0.375)) @ R @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        # taotie: two eye bosses + brows in the centre field
        for sgn in (-1, 1):
            e = onface(sgn * 0.06, 0.60, 0.006)
            _sphere(bm, 0.022, (0, 0, 0), 10, 6, scale=(1.5, 0.55, 1.0),
                    matrix=S @ Matrix.Translation(e) @ R)
            brow = [onface(sgn * du, 0.6 + dz, 0.004) for du, dz in ((0.02, 0.035), (0.07, 0.05), (0.12, 0.04),
                                                                      (0.14, 0.015))]
            _tube(bm, [tuple(S @ p) for p in brow], 0.007 * s, 6, 3)
        _tube(bm, [tuple(S @ onface(0.0, z, 0.006)) for z in (0.53, 0.60, 0.67)], 0.008 * s, 6, 2)
    # corner + mid flanges
    for cx, cy, ang in ((hx1, hy1, math.pi / 4), (-hx1, hy1, 3 * math.pi / 4), (-hx1, -hy1, -3 * math.pi / 4),
                        (hx1, -hy1, -math.pi / 4), (0, -hy1, -math.pi / 2), (0, hy1, math.pi / 2),
                        (hx1, 0, 0.0), (-hx1, 0, math.pi)):
        outline = _notched_fin(lambda z: -0.025 * (z1 - z) / (z1 - z0), z0 + 0.02, z1 - 0.03, 0.035, 0.012)
        vs = _prism(bm, outline, 0.014, y0=-0.007)
        _xf(bm, S @ Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(ang, 4, 'Z'), vs)
    for side in (-1, 1):
        _arch_wall(bm, 0.15, 0.20, 0.04, 0.085, 0.125, 0.012,
                   S @ Matrix.Translation((side * (hx1 + 0.005), 0, z1 + 0.01)) @ Matrix.Rotation(side * 0.1, 4, 'Y'))
    for sx in (-1, 1):
        for sy in (-1, 1):
            _lathe(bm, [(0.0, 0.0), (0.062, 0.0), (0.06, 0.03), (0.05, 0.06), (0.05, 0.20), (0.066, 0.26),
                        (0.07, 0.31), (0.06, 0.345), (0.0, 0.35)], 20,
                   matrix=S @ Matrix.Translation((sx * (hx0 - 0.07), sy * (hy0 - 0.06), 0)))
    _merge(bm, 1e-6)
    _outward(bm)
    body = _mk(_nm("ding4.body"), bm, pc, [material], smooth=math.radians(40), bevel=0.003 * s, angle=math.radians(50))
    # molten surface: a rectangle
    bm = bmesh.new()
    _box(bm, (2 * (hx1 - 0.02) * s, 2 * (hy1 - 0.02) * s, 0.01 * s), (0, 0, (z1 - 0.008) * s))
    _mk(_nm("ding4.molten" if lit else "ding4.ash"), bm, pc, ["props_molten" if lit else "props_ash"], smooth=False,
        glow=1.0 if lit else None)
    if lit:
        _ding_fill_extras(pc, s, (hx1 - 0.03, hy1 - 0.03), z1, sparks, light, smoke)
    return body


def _ding_fill_extras(pc, s, half, z_top, sparks, light, smoke):
    bm = bmesh.new()
    _sq_lathe(bm, [(min(half) * 0.95 * s, (z_top - 0.03) * s), (min(half) * 0.55 * s, (z_top + 0.75) * s)])
    for f in list(bm.faces):
        if abs(f.normal.z) > 0.9:
            bm.faces.remove(f)
    bm.faces.ensure_lookup_table()
    _xf(bm, Matrix.Diagonal((half[0] / min(half), half[1] / min(half), 1.0, 1.0)), bm.verts[:])
    heat = _mk(_nm("ding4.heat"), bm, pc, ["props_heat"], smooth=True)
    U.set_visibility(heat, shadow=False)
    if sparks:
        r = U.rng("ding4_sparks", s)
        ember = _proto_ember("ember", "ember", 0.008 * s, 1.0)
        pts, scl, ph = [], [], []
        for i in range(60):
            pts.append((r.uniform(-half[0], half[0]) * 0.8 * s, r.uniform(-half[1], half[1]) * 0.8 * s, z_top * s))
            scl.append(r.uniform(0.5, 1.3))
            ph.append(r.random())
        _point_instancer(_nm("ding4.sparks"), pc, ember, pts, scales=scl, phases=ph,
                         drift=dict(rise=0.45 * s, height=1.3 * s, wobble=0.12 * s, speed=0.4))


def cauldron_ding(collection, size=1.6, lit=True, legs=3, material="bronze_verdigris", sparks=True,
                  light=False, smoke=False, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0),
                  scale=1.0):
    """Bronze ding cauldron, ``size`` m tall to the top of its ears (about 0.83*size wide).

    legs=3: round ding on three hoof legs, two upright ears on the rim (openings facing the
    front), a neck band of six taotie masks between notched flanges, a wave band on the belly.
    legs=4: square fang ding on four column legs with nipple-boss bands, taotie faces, corner and
    centre flanges. lit=True: churning molten surface, a warm heat aura above the rim and rising
    ember sparks (geometry-node instances animated with scene time); lit=False: grey ash.
    light=True adds a warm point light above the molten metal (counts toward an area's 8 lights);
    smoke=True adds a smoke column. Origin at the ground centre. Collection instance."""
    if legs not in (3, 4):
        raise ValueError("cauldron_ding legs must be 3 or 4")
    b, res = _bucket(size, 1.6)
    key = "ding%d.%s.%s.%d%d%d%d" % (legs, _k(b), material, lit, sparks, light, smoke)
    fn = _ding_round if legs == 3 else _ding_square
    pc = _proto(key, lambda pc: fn(pc, b, lit, material, sparks, light, smoke))
    return _place(pc, collection, name, "ding", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ incense burner

def _build_incense(pc, s, smoke):
    S = Matrix.Diagonal((s, s, s, 1.0))
    bm = bmesh.new()
    _lathe(bm, [(0, 0), (0.36, 0), (0.36, 0.08), (0.31, 0.11), (0.26, 0.14), (0.26, 0.32), (0.31, 0.35),
                (0.34, 0.38), (0.34, 0.44), (0, 0.44)], 6, phase=math.pi / 6, matrix=S)
    _outward(bm)
    _mk(_nm("incense.pedestal"), bm, pc, ["stone_grey"], smooth=False, bevel=0.01 * s)
    bm = bmesh.new()
    body = [(0.0, 0.54), (0.16, 0.545), (0.26, 0.58), (0.30, 0.64), (0.295, 0.70), (0.26, 0.75), (0.25, 0.77),
            (0.30, 0.80), (0.305, 0.815), (0.28, 0.815), (0.24, 0.785), (0.235, 0.76), (0.0, 0.76)]
    _lathe(bm, body, 48, matrix=S)
    for zz in (0.62, 0.69):
        rr = _prof_r(body[1:6], zz) + 0.003
        _torus(bm, rr * s, 0.006 * s, 48, 6, matrix=Matrix.Translation((0, 0, zz * s)))
    for k in range(4):
        _taotie(bm, math.pi / 2 * k - math.pi / 2, 0.655 * s, 0.302 * s, 0.75 * s)
    for side in (-1, 1):                                   # crown ears rising from the rim
        pts = [(0.265, -0.065, 0.80), (0.29, -0.065, 0.87), (0.335, -0.05, 0.935), (0.36, 0.0, 0.955),
               (0.335, 0.05, 0.935), (0.29, 0.065, 0.87), (0.265, 0.065, 0.80)]
        _tube(bm, [(side * x * s, y * s, z * s) for x, y, z in pts], 0.016 * s, 8, 4)
    for k in range(3):                                     # elephant-trunk legs
        th = -math.pi / 2 + TAU * k / 3
        c, sn = math.cos(th), math.sin(th)
        pts = [(0.17, 0.58, 1.0), (0.22, 0.53, 1.0), (0.25, 0.49, 0.9), (0.245, 0.455, 1.15), (0.25, 0.445, 1.3)]
        _tube(bm, [(r * c * s, r * sn * s, z * s, w) for r, z, w in pts], 0.03 * s, 10, 4)
    _merge(bm, 1e-6)
    _outward(bm)
    _mk(_nm("incense.censer"), bm, pc, ["bronze_verdigris"], smooth=math.radians(45))
    bm = bmesh.new()
    _cyl(bm, 0.236 * s, 0.01 * s, 32, (0, 0, 0.775 * s))
    _mk(_nm("incense.ash"), bm, pc, ["props_ash"], smooth=False)
    bm = bmesh.new()
    tips = []
    for i, (x, tilt) in enumerate(((-0.05, -0.08), (0.0, 0.0), (0.05, 0.08))):
        base = Vector((x * s, 0.0, 0.775 * s))
        d = Vector((math.sin(tilt), 0.0, math.cos(tilt)))
        top = base + d * 0.30 * s
        _tube(bm, [tuple(base - d * 0.02 * s), tuple(top)], 0.004 * s, 6, 1)
        tips.append(top)
    _mk(_nm("incense.sticks"), bm, pc, ["props_incense"], smooth=True)
    bm = bmesh.new()
    for t in tips:
        _sphere(bm, 0.0065 * s, tuple(t), 8, 4)
    _mk(_nm("incense.embers"), bm, pc, ["ember"], smooth=True, glow=0.6)
    if smoke:
        bm = bmesh.new()
        r = U.rng("incense_smoke", s)
        for i, t in enumerate(tips):
            ph = r.uniform(0, TAU)
            path, widths = [], []
            n = 40
            for j in range(n + 1):
                u = j / n
                h = 1.5 * u
                sway = 0.06 * u + 0.30 * u * u
                path.append(Vector((t.x + (sway * math.sin(TAU * 1.2 * u + ph)) * s,
                                    (sway * math.cos(TAU * 0.9 * u + ph * 1.3)) * s, t.z + h * s)))
                widths.append((0.008 + 0.30 * u ** 1.6) * s)
            _strip(bm, path, widths, twist=r.uniform(4.0, 7.0))
        sm = _mk(_nm("incense.smoke"), bm, pc, ["props_smoke_wisp"], smooth=True)
        U.set_visibility(sm, shadow=False)


def incense_burner(collection, size=1.0, smoke=True, name=None, parent=None, location=(0, 0, 0),
                   rotation=(0, 0, 0), scale=1.0):
    """Courtyard incense burner, about 1.1*size m to the stick tips: hexagonal stone pedestal,
    bronze tripod censer with elephant-trunk legs, flaring crown ears, ridges and taotie masks,
    grey ash, three incense sticks with glowing tips and (smoke=True) three thin curling smoke
    ribbons rising about 1.5*size m. Origin at the ground centre. Collection instance."""
    b, res = _bucket(size, 1.0)
    pc = _proto("incense.%s.%d" % (_k(b), smoke), lambda pc: _build_incense(pc, b, smoke))
    return _place(pc, collection, name, "incense", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ bell

def _build_bell(pc, s, material, frame):
    """Chinese temple bell (fan zhong), designed 1 unit tall incl. hanger, scaled by s."""
    z_off = 0.22 if frame else 0.0
    if not frame:
        pc.instance_offset = (0.0, 0.0, 1.03 * s)          # hanger top = instance origin
    S = Matrix.Translation((0, 0, z_off * s)) @ Matrix.Diagonal((s, s, s, 1.0))
    prof = [(0.0, 0.80), (0.28, 0.76), (0.31, 0.60), (0.33, 0.10), (0.35, 0.0), (0.40, 0.0), (0.40, 0.04),
            (0.37, 0.06), (0.36, 0.12), (0.345, 0.40), (0.335, 0.62), (0.33, 0.72), (0.31, 0.78), (0.25, 0.83),
            (0.15, 0.855), (0.0, 0.86)]
    bm = bmesh.new()
    _lathe(bm, prof, 64, zmod=lambda a, i, r, z: z - (0.035 * abs(math.sin(4 * a)) if i in (4, 5, 6) else 0.0),
           cap_start=False, cap_end=False, matrix=S)
    outer = prof[6:13]
    for zz in (0.09, 0.30, 0.64, 0.70):
        rr = _prof_r(outer, zz) + 0.003
        _torus(bm, rr, 0.008, 64, 6, matrix=S @ Matrix.Translation((0, 0, zz)))
    for k in range(4):                                     # vertical bands dividing the panels
        a = math.pi / 4 + k * math.pi / 2
        pts = [((_prof_r(outer, z) + 0.003) * math.cos(a), (_prof_r(outer, z) + 0.003) * math.sin(a), z)
               for z in (0.30, 0.47, 0.64)]
        _tube(bm, pts, 0.008, 6, 2, matrix=S)
    for k in range(4):                                     # lotus striking seats
        a = -math.pi / 2 + k * math.pi / 2
        rr = _prof_r(outer, 0.19)
        m = S @ Matrix.Translation((rr * math.cos(a), rr * math.sin(a), 0.19)) @ \
            Matrix.Rotation(a + math.pi / 2, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
        _sphere(bm, 0.045, (0, 0, 0), 16, 8, scale=(1, 1, 0.35), matrix=m)
        _torus(bm, 0.055, 0.008, 24, 6, matrix=m)
        for p in range(8):
            pa = TAU * p / 8
            _sphere(bm, 0.014, (0.075 * math.cos(pa), 0.075 * math.sin(pa), 0.0), 8, 4, scale=(1.4, 1.0, 0.5),
                    matrix=m @ Matrix.Rotation(pa, 4, 'Z'))
    # pu lao dragon hanger: arched body with a spiny ridge, head and claws gripping the crown
    arch = [(-0.13, 0, 0.845), (-0.12, 0, 0.92), (-0.07, 0, 0.985), (0.0, 0, 1.0), (0.07, 0, 0.985),
            (0.12, 0, 0.92), (0.13, 0, 0.845)]
    _tube(bm, arch, 0.034, 10, 5, matrix=S)
    path = [Vector(p[:3]) for p in U.catmull_rom(arch, 6)]
    for i in range(3, len(path) - 3, 2):
        p = path[i]
        d = Vector((p.x, 0, p.z - 0.86)).normalized()
        _lathe(bm, [(0.012, 0.0), (0.0, 0.03)], 6, matrix=S @ Matrix.Translation(p + d * 0.028) @
               U.align_z(d).to_4x4())
    _sphere(bm, 0.05, (-0.15, 0.0, 0.875), 12, 8, scale=(1.3, 0.9, 0.9), matrix=S)
    _sphere(bm, 0.03, (-0.205, 0.0, 0.86), 10, 6, scale=(1.2, 0.8, 0.7), matrix=S)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _tube(bm, [(sx * 0.12, 0, 0.86), (sx * 0.15, sy * 0.06, 0.845), (sx * 0.17, sy * 0.09, 0.835)], 0.013, 6, 3,
                  matrix=S)
    _merge(bm, 1e-6)
    body = _mk(_nm("bell.body"), bm, pc, [material], smooth=math.radians(40))
    # inscription: relief characters on the front upper panel, bent onto the bell
    bm = bmesh.new()
    text = CLASSICS[2]
    cell = 0.05
    for c in range(4):
        for r_ in range(5):
            ch = text[(c * 5 + r_) % len(text)]
            me = _text_mesh(ch, cell * 0.85, 2, extrude=0.004)
            x0 = (1.5 - c) * cell
            z0 = 0.585 - (r_ + 0.5) * cell

            def fn(co, x0=x0, z0=z0):
                x, y, z = co.x + x0, co.y + z0, co.z
                rr = _prof_r(outer, y) + 0.004 + z
                a = -math.pi / 2 + x / rr
                return S @ Vector((rr * math.cos(a), rr * math.sin(a), y))
            _add_mesh_fn(bm, me, fn)
    _mk(_nm("bell.inscription"), bm, pc, [material], smooth=False)
    if frame:
        bm = bmesh.new()
        for sx in (-1, 1):
            _box(bm, (0.09, 0.09, 1.42), (sx * 0.56, 0, 0.71), matrix=Matrix.Diagonal((s, s, s, 1)))
            _box(bm, (0.12, 0.5, 0.06), (sx * 0.56, 0, 0.03), matrix=Matrix.Diagonal((s, s, s, 1)))
            for sy in (-1, 1):
                _tube(bm, [(sx * 0.56, sy * 0.22, 0.06), (sx * 0.56, sy * 0.04, 0.40)], 0.022, 6, 1,
                      matrix=Matrix.Diagonal((s, s, s, 1)))
        _box(bm, (1.36, 0.11, 0.11), (0, 0, 1.40), matrix=Matrix.Diagonal((s, s, s, 1)))
        _mk(_nm("bell.frame"), bm, pc, ["lacquer_red_worn"], smooth=False, bevel=0.008 * s)
        bm = bmesh.new()
        _tube(bm, [(0, 0, 1.35 * s), (0, 0, (z_off + 1.0) * s)], 0.012 * s, 6, 1)
        for sx in (-1, 1):
            _sphere(bm, 0.06 * s, (sx * 0.70 * s, 0, 1.40 * s), 12, 6, scale=(1.4, 0.9, 0.9))
        _torus(bm, 0.035 * s, 0.01 * s, 16, 6, matrix=Matrix.Translation((0, 0, 1.0 * s + z_off * s)) @
               Matrix.Rotation(math.pi / 2, 4, 'Y'))
        _mk(_nm("bell.fittings"), bm, pc, ["gold"], smooth=True)
        bm = bmesh.new()                                    # striking log on two ropes
        _lathe(bm, [(0.0, 0.0), (0.05, 0.0), (0.055, 0.02), (0.055, 0.58), (0.05, 0.60), (0.0, 0.60)], 12,
               matrix=Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation((0.0, -1.05, z_off + 0.19)) @
               Matrix.Rotation(-math.pi / 2, 4, 'X'))
        _mk(_nm("bell.log"), bm, pc, ["wood_light"], smooth=math.radians(40))
        bm = bmesh.new()
        for y in (-0.95, -0.55):
            for x in (-0.03, 0.03):
                _tube(bm, [(x * s, y * s, (z_off + 0.24) * s), (x * 4 * s, (y * 0.5) * s, 1.0 * s),
                           (x * 8 * s, -0.04 * s, 1.35 * s)], 0.006 * s, 5, 4)
        _mk(_nm("bell.ropes"), bm, pc, ["props_rope"], smooth=True)
    return body


def bell(collection, size=1.6, material="bronze_verdigris", frame=False, name=None, parent=None,
         location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Chinese bronze temple bell (fan zhong), ``size`` m tall including its dragon hanger
    (0.8*size wide): eight-lobed scalloped lip, horizontal and vertical relief bands, four lotus
    striking seats, a relief inscription on the front panel, a pu-lao dragon loop on the crown.
    frame=False: origin at the top of the hanger (the bell hangs below it in -Z).
    frame=True: on a red lacquered post-and-beam frame (1.42*size tall) with a striking log on
    ropes in front; origin at the ground centre. Collection instance."""
    b, res = _bucket(size, 1.6)
    pc = _proto("bell.%s.%s.%d" % (_k(b), material, frame), lambda pc: _build_bell(pc, b, material, frame))
    return _place(pc, collection, name, "bell", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ drum

def _build_drum(pc, D, stand):
    s = D
    zc = 0.85 if stand else 0.0
    S = Matrix.Diagonal((s, s, s, 1.0))
    A = S @ Matrix.Translation((0, 0, zc)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')   # lathe Z -> world -Y.. +Y
    prof = [(0.0, -0.405), (0.49, -0.405), (0.50, -0.42), (0.53, -0.32), (0.555, -0.15), (0.565, 0.0),
            (0.555, 0.15), (0.53, 0.32), (0.50, 0.42), (0.49, 0.405), (0.0, 0.405)]
    bm = bmesh.new()
    _lathe(bm, prof[1:-1], 48, cap_start=False, cap_end=False, matrix=A)
    _outward(bm)
    _mk(_nm("drum.body"), bm, pc, ["lacquer_red"], smooth=math.radians(40))
    bm = bmesh.new()
    for sgn in (-1, 1):
        _lathe(bm, [(0.495, 0.0), (0.3, 0.006), (0.0, 0.009)], 48, cap_start=False,
               matrix=A @ Matrix.Translation((0, 0, sgn * 0.408)) @ Matrix.Diagonal((1, 1, sgn, 1)))
    _mk(_nm("drum.heads"), bm, pc, ["props_drum_skin"], smooth=True)
    bm = bmesh.new()
    for sgn in (-1, 1):
        for row, (z, rr) in enumerate(((0.385, 0.507), (0.345, 0.522))):
            n = 44
            for i in range(n):
                a = TAU * (i + 0.5 * row) / n
                c = A @ Vector((rr * math.cos(a), rr * math.sin(a), sgn * z))
                _sphere(bm, 0.011 * s, tuple(c), 8, 4, scale=(1, 1, 1))
        _torus(bm, 0.503, 0.008, 48, 6, matrix=A @ Matrix.Translation((0, 0, sgn * 0.415)))
    for z in (-0.12, 0.12):
        _torus(bm, _prof_r([(r, z_) for r, z_ in prof[2:9]], z) + 0.002, 0.007, 48, 6,
               matrix=A @ Matrix.Translation((0, 0, z)))
    for sx in (-1, 1):                                       # ring pulls on the sides
        _sphere(bm, 0.03, (sx * 0.57, 0, 0), 10, 6, scale=(0.5, 1, 1), matrix=S @ Matrix.Translation((0, 0, zc)))
        _torus(bm, 0.06, 0.009, 20, 6, matrix=S @ Matrix.Translation((sx * 0.585, 0, zc - 0.06)) @
               Matrix.Rotation(math.pi / 2, 4, 'Y'))
    _mk(_nm("drum.studs"), bm, pc, ["gold"], smooth=True)
    if stand:
        bm = bmesh.new()
        W = Matrix.Diagonal((s, s, s, 1.0))
        for sx in (-1, 1):
            x = sx * 0.64
            _box(bm, (0.08, 0.08, zc + 0.08), (x, 0, (zc + 0.08) / 2), matrix=W)
            _box(bm, (0.10, 0.90, 0.08), (x, 0, 0.04), matrix=W)
            for sy in (-1, 1):
                _tube(bm, [(x, sy * 0.40, 0.08), (x, sy * 0.04, 0.48)], 0.028, 4, 1, matrix=W)
            _box(bm, (0.12, 0.16, 0.06), (x, 0, zc - 0.10), matrix=W)
        _box(bm, (1.36, 0.07, 0.07), (0, 0, 0.16), matrix=W)
        _mk(_nm("drum.stand"), bm, pc, ["wood_dark"], smooth=False, bevel=0.008 * s)
        bm = bmesh.new()
        for i, y in enumerate((-0.05, 0.05)):
            _tube(bm, [(-0.45, y - 0.30, 0.19), (0.05, y - 0.32, 0.215)], 0.016, 8, 1, matrix=W)
            _sphere(bm, 0.035, (0.07, y - 0.32, 0.215), 10, 6, matrix=W)
        _mk(_nm("drum.sticks"), bm, pc, ["lacquer_red_worn"], smooth=True)


def drum(collection, size=1.2, stand=True, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0),
         scale=1.0):
    """Chinese barrel drum (tang gu), heads ``size`` m across facing -Y/+Y, 0.84*size deep: red
    lacquered body with gold bands, two rows of brass studs at each head, side ring pulls, tan skin
    heads. stand=True: on a rosewood stand (drum centre 0.85*size above the ground) with two
    drumsticks resting on the stretcher; origin at the ground centre. stand=False: origin at the
    drum centre. Collection instance."""
    b, res = _bucket(size, 1.2)
    pc = _proto("drum.%s.%d" % (_k(b), stand), lambda pc: _build_drum(pc, b, stand))
    return _place(pc, collection, name, "drum", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ organic forms (metaballs)

_MB_COUNT = [0]


def _mb(kind, co, R, size=(1, 1, 1), rot=None, stiff=2.0, neg=False):
    """Metaball element spec. ``R`` = surface radius of the element on its own (ELLIPSOID: per
    axis R*size; CAPSULE: size[0] is the half length of its segment along local X)."""
    return (kind, tuple(co), R, tuple(size), rot, stiff, neg)


def _capsule(p0, p1, R, stiff=2.0):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    rot = Vector((1, 0, 0)).rotation_difference(d.normalized()) if d.length > 1e-9 else None
    return _mb('CAPSULE', (p0 + p1) / 2, R, (d.length / 2, 1, 1), rot, stiff)


def _mb_mesh(elements, res, thr=0.6):
    """Polygonise metaball ``elements`` (see _mb) into new mesh data (smoothly blended forms)."""
    _MB_COUNT[0] += 1
    fam = "propsmb%d" % _MB_COUNT[0]          # unique family name: metaballs of one family merge
    mb = bpy.data.metaballs.new(fam)
    mb.resolution = res
    mb.render_resolution = res
    mb.threshold = thr
    for kind, co, R, size, rot, stiff, neg in elements:
        el = mb.elements.new(type=kind)
        el.co = co
        el.radius = R / math.sqrt(1.0 - (thr / stiff) ** (1.0 / 3.0))
        el.stiffness = stiff
        if kind != 'BALL':
            el.size_x, el.size_y, el.size_z = size
        if rot is not None:
            el.rotation = rot
        el.use_negative = neg
    ob = bpy.data.objects.new(fam, mb)
    me = _evaluate_temp(ob)
    bpy.data.metaballs.remove(mb)
    return me


def _smooth_mesh(me, iterations=6, factor=0.5):
    """Laplacian-smooth mesh data in place (removes marching-cube facets)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=factor, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    bm.to_mesh(me)
    bm.free()


def _surface_points(me, origin, dirs, offset=0.0):
    """Ray-cast from ``origin`` along each direction onto mesh ``me``; returns (point, normal)
    pairs (None where nothing is hit). Used to seat curls, scales and claws on organic forms."""
    from mathutils.bvhtree import BVHTree
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    out = []
    o = Vector(origin)
    for d in dirs:
        d = Vector(d).normalized()
        hit = tree.ray_cast(o + d * 10.0, -d)              # from outside inward: outermost surface
        if hit[0] is None:
            out.append(None)
        else:
            n = hit[1] if hit[1].dot(d) > 0 else -hit[1]
            out.append((hit[0] + n * offset, n))
    return out


def _curl(bm, p, n, r, mat=0, turns=1.6):
    """A carved snail-shell curl (mane, tail, clouds): flattened knob plus a spiral ridge,
    sitting on point ``p`` with normal ``n``."""
    rot = U.align_z(n).to_4x4()
    m = Matrix.Translation(p) @ rot
    _sphere(bm, r, (0, 0, r * 0.15), 8, 4, scale=(1, 1, 0.55), matrix=m, mat=mat)
    pts = []
    for i in range(10):
        t = i / 9
        a = TAU * turns * t
        rr = r * (1.05 - 0.75 * t)
        pts.append((rr * math.cos(a), rr * math.sin(a), r * (0.25 + 0.3 * t)))
    _tube(bm, pts, r * 0.17, 5, 1, matrix=m, mat=mat)


# ============================================================ guardian lion

def _xumizuo(bm, hx, hy, h, matrix=None):
    """Rectangular stepped xumizuo pedestal (half sizes hx, hy, height h) with a waist."""
    k = hy / hx
    prof = [(0, 0), (1.0, 0), (1.0, 0.16), (0.93, 0.21), (0.89, 0.26), (0.78, 0.31), (0.78, 0.69),
            (0.89, 0.74), (0.93, 0.79), (0.98, 0.85), (0.98, 1.0), (0, 1.0)]
    m = Matrix.Diagonal((1.0, k, 1.0, 1.0))
    if matrix is not None:
        m = Matrix(matrix) @ m
    return _sq_lathe(bm, [(a * hx, z * h) for a, z in prof], matrix=m)


def _fib_dirs(n):
    """``n`` evenly spread unit directions (Fibonacci sphere)."""
    ga = math.pi * (3.0 - math.sqrt(5.0))
    out = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        out.append(Vector((r * math.cos(ga * i), r * math.sin(ga * i), z)))
    return out


_LION_HEAD = Vector((0.0, -0.16, 1.30))


def _lion_elements(female):
    sx = 1.0 if not female else -1.0           # male: lion's right paw (-X) on the ball
    E, B = 'ELLIPSOID', 'BALL'
    hc = _LION_HEAD
    els = [
        _mb(E, (0, -0.06, 0.80), 0.31, (0.95, 0.85, 1.25)),
        _mb(E, (0, 0.12, 0.56), 0.30, (1.0, 1.1, 0.9)),
        _mb(E, (0, 0.30, 0.37), 0.30, (1.0, 0.95, 0.85)),
        _mb(E, (0.22, 0.18, 0.32), 0.22, (0.85, 1.4, 1.05)),
        _mb(E, (-0.22, 0.18, 0.32), 0.22, (0.85, 1.4, 1.05)),
        _mb(E, (0.31, -0.03, 0.065), 0.09, (1.0, 1.7, 0.7)),
        _mb(E, (-0.31, -0.03, 0.065), 0.09, (1.0, 1.7, 0.7)),
        _mb(E, (0, -0.11, 1.06), 0.26, (1.0, 1.0, 1.0)),
        _mb(B, tuple(hc), 0.31),
        _mb(E, (0, -0.40, 1.20), 0.17, (1.5, 0.85, 0.8)),
        _mb(B, (0.17, -0.34, 1.17), 0.12),
        _mb(B, (-0.17, -0.34, 1.17), 0.12),
        _mb(E, (0, -0.39, 1.40), 0.10, (2.5, 0.8, 0.7)),
        _mb(E, (0, -0.535, 1.26), 0.075, (1.6, 0.85, 0.85)),
        _mb(E, (0, -0.38, 1.03), 0.12, (1.5, 1.0, 0.65)),
        _mb(E, (0, -0.53, 1.115), 0.08, (2.0, 1.1, 0.5), neg=True),
        _mb(E, (0.27, -0.14, 1.44), 0.065, (0.8, 0.45, 1.3)),
        _mb(E, (-0.27, -0.14, 1.44), 0.065, (0.8, 0.45, 1.3)),
    ]
    els.append(_capsule((sx * 0.16, -0.21, 0.66), (sx * 0.16, -0.26, 0.12), 0.095))
    els.append(_mb(E, (sx * 0.16, -0.32, 0.07), 0.095, (1.15, 1.45, 0.75)))
    lift = 0.32 if not female else 0.22
    els.append(_capsule((-sx * 0.16, -0.21, 0.66), (-sx * 0.19, -0.37, lift + 0.03), 0.095))
    els.append(_mb(E, (-sx * 0.19, -0.41, lift), 0.095, (1.15, 1.45, 0.75)))
    if female:                                   # cub lying on its back under the paw
        cx = -sx * 0.20
        els += [_mb(E, (cx, -0.39, 0.075), 0.08, (1.0, 1.7, 0.75)),
                _mb(B, (cx + 0.02, -0.53, 0.10), 0.075),
                _capsule((cx - 0.05, -0.33, 0.10), (cx - 0.07, -0.31, 0.19), 0.03),
                _capsule((cx + 0.06, -0.34, 0.10), (cx + 0.09, -0.31, 0.18), 0.03)]
    return els, sx


def _build_lion(pc, s, female, material, plinth_material):
    S = Matrix.Diagonal((s, s, s, 1.0))
    top = 0.63
    bm = bmesh.new()
    _xumizuo(bm, 0.50, 0.60, 0.60, matrix=S @ Matrix.Translation((0, 0.03, 0)))
    _box(bm, (1.02, 1.22, 0.03), (0, 0.03, 0.615), matrix=S)
    for cx in (-0.5, 0.5):
        for cy in (-0.57, 0.63):
            _lathe(bm, [(0.0, -0.13), (0.035, -0.11), (0.03, -0.03), (0.015, 0.0), (0.0, 0.0)], 10,
                   matrix=S @ Matrix.Translation((cx, cy, 0.60)))
    _outward(bm)
    _mk(_nm("lion.plinth"), bm, pc, [plinth_material], smooth=math.radians(35), bevel=0.012 * s)
    els, sx = _lion_elements(female)
    me = _mb_mesh(els, 0.02)
    _smooth_mesh(me, 4, 0.5)
    bm = bmesh.new()
    bm.from_mesh(me)
    hc = _LION_HEAD
    # bulging eyes with lids, curled brows
    for side in (-1, 1):
        c = Vector((side * 0.115, -0.49, 1.34))
        _sphere(bm, 0.064, tuple(c), 16, 8, scale=(1.0, 0.75, 0.9))
        _torus(bm, 0.064, 0.013, 20, 6, matrix=Matrix.Translation(c + Vector((0, 0.01, 0))) @
               Matrix.Rotation(math.pi / 2, 4, 'X') @ Matrix.Diagonal((1.0, 0.9, 1.0, 1.0)))
        brow = [(side * 0.03, -0.545, 1.43), (side * 0.11, -0.535, 1.455), (side * 0.19, -0.50, 1.45),
                (side * 0.24, -0.45, 1.42), (side * 0.25, -0.42, 1.375)]
        _tube(bm, [p + (1.0 - 0.4 * i / 4,) for i, p in enumerate(brow)], 0.026, 8, 4)
        _curl(bm, Vector((side * 0.245, -0.44, 1.37)), Vector((side * 0.6, -0.8, 0.0)).normalized(), 0.034)
    # grin: a row of upper teeth, fangs, lower fangs, curled tongue
    for i in range(6):
        u = (i - 2.5) / 2.5
        _sphere(bm, 0.016, (u * 0.08, -0.56 + 0.03 * u * u, 1.143), 8, 4, scale=(0.9, 0.8, 1.15))
    for side in (-1, 1):
        _lathe(bm, [(0.02, 0.0), (0.0, -0.06)], 8, matrix=Matrix.Translation((side * 0.115, -0.535, 1.15)))
        _lathe(bm, [(0.018, 0.0), (0.0, 0.05)], 8, matrix=Matrix.Translation((side * 0.10, -0.53, 1.06)))
    _sphere(bm, 0.05, (0, -0.50, 1.085), 12, 6, scale=(1.4, 1.0, 0.45))
    # mane: snail curls over the head (not the face), sideburns, chin beard
    dirs = []
    for d in _fib_dirs(250):
        face = d.y < -0.32 and abs(d.x) < 0.78 and d.z < 0.60
        if face or d.z < -0.62:
            continue
        dirs.append(d)
    for h in _surface_points(me, hc, dirs, 0.0):
        if h is not None:
            _curl(bm, h[0], h[1], 0.056)
    dirs = [d for d in _fib_dirs(180) if d.y > 0.0 and -0.35 < d.z < 0.8]
    for h in _surface_points(me, (0, -0.04, 0.92), dirs, 0.0):
        if h is not None and 0.70 < h[0].z < 1.25:
            _curl(bm, h[0], h[1], 0.05)
    dirs = [d for d in _fib_dirs(160) if d.z < -0.55 and d.y < -0.25]
    for h in _surface_points(me, (0, -0.30, 1.10), dirs, 0.0):
        if h is not None:
            _curl(bm, h[0], h[1], 0.04)
    # hip spirals, elbow tufts, toes
    for side in (-1, 1):
        h = _surface_points(me, (0, 0.18, 0.34), [Vector((side, 0.15, 0.25))], 0.0)[0]
        if h is not None:
            _curl(bm, h[0], h[1], 0.085, turns=2.2)
        for z in (0.40, 0.48):
            h = _surface_points(me, (side * 0.16, -0.18, z), [Vector((side * 0.4, 1.0, 0.0))], 0.0)[0]
            if h is not None:
                _curl(bm, h[0], h[1], 0.035)
    paws = [(sx * 0.16, -0.32, 0.07), (-sx * 0.19, -0.41, 0.32 if not female else 0.22),
            (0.31, -0.03, 0.065), (-0.31, -0.03, 0.065)]
    for i, (px, py, pz) in enumerate(paws):
        ylen = 0.14 if i < 2 else 0.15
        for k in range(4):
            u = (k - 1.5) / 1.5
            _sphere(bm, 0.03, (px + u * 0.065, py - ylen + 0.012 * abs(u), pz - 0.02), 10, 6, scale=(1.0, 1.25, 0.8))
    # collar, bell
    _torus(bm, 0.235, 0.026, 40, 8, matrix=Matrix.Translation((0, -0.11, 0.97)) @ Matrix.Rotation(0.42, 4, 'X')
           @ Matrix.Diagonal((1.0, 0.95, 1.0, 1.0)))
    _sphere(bm, 0.07, (0, -0.35, 0.84), 16, 8)
    _torus(bm, 0.072, 0.009, 24, 6, matrix=Matrix.Translation((0, -0.35, 0.84)))
    _torus(bm, 0.022, 0.009, 12, 6, matrix=Matrix.Translation((0, -0.35, 0.915)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    # flame tail: a fan of five curling locks on the rump
    for a in (-0.9, -0.45, 0.0, 0.45, 0.9):
        pts = [(0.0, 0.50, 0.40), (0.06 * a, 0.62, 0.52), (0.16 * a, 0.67, 0.68 - 0.06 * abs(a)),
               (0.24 * a, 0.62, 0.80 - 0.08 * abs(a)), (0.21 * a, 0.56, 0.76 - 0.08 * abs(a))]
        _tube(bm, [p + (1.0 - 0.35 * i / 4,) for i, p in enumerate(pts)], 0.04, 8, 4)
        _curl(bm, Vector((0.22 * a, 0.575, 0.775 - 0.08 * abs(a))), Vector((0.4 * a, 0.5, 1.0)).normalized(), 0.045)
    if not female:                                # embroidered ball with ribbons
        bc = Vector((-sx * 0.21, -0.42, 0.155))
        _sphere(bm, 0.155, tuple(bc), 24, 12)
        for rot in (Matrix.Rotation(0.4, 4, 'X'), Matrix.Rotation(-0.6, 4, 'Y') @ Matrix.Rotation(1.2, 4, 'X'),
                    Matrix.Rotation(1.1, 4, 'Y')):
            _torus(bm, 0.157, 0.015, 40, 6, matrix=Matrix.Translation(bc) @ rot)
        _curl(bm, bc + Vector((0.0, -0.1, 0.12)), Vector((0, -0.6, 0.8)).normalized(), 0.04)
    bmesh.ops.transform(bm, matrix=S @ Matrix.Translation((0, 0, top)), verts=bm.verts[:])
    lion = _mk(_nm("lion.body"), bm, pc, [material], smooth=True)
    U.auto_smooth(lion, math.radians(60))
    bpy.data.meshes.remove(me)
    return lion


def guardian_lion(collection, size=1.0, mirror=False, material="marble_white", plinth_material=None,
                  name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Chinese guardian lion (shi shi) seated on a xumizuo plinth with a draped brocade, facing -Y.
    Stylised from blended forms: big round head with heavy brows, bulging eyes, broad snub nose,
    open grin with fangs, rows of snail-curl mane down the nape, collar with a bell, flame tail.
    mirror=False: the male, right paw on an embroidered ball (on the -X side).
    mirror=True: its partner, the female, left paw on a cub (on the +X side).
    About 2.2*size m tall (plinth 0.63*size), 1.0*size wide, 1.2*size deep. Origin at the ground
    centre. Collection instance."""
    b, res = _bucket(size, 1.0)
    pm = plinth_material or material
    key = "lion.%s.%d.%s.%s" % (_k(b), mirror, material, pm)
    pc = _proto(key, lambda pc: _build_lion(pc, b, mirror, material, pm))
    return _place(pc, collection, name, "lion", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ stele on a bixi turtle

def _build_turtle(pc, s, material):
    """Bixi dragon-turtle base (designed for a 4 m stele), returns the socket top height."""
    S = Matrix.Diagonal((s, s, s, 1.0))
    E = 'ELLIPSOID'
    els = [
        _mb(E, (0, 0.05, 0.26), 0.5, (1.35, 2.05, 0.48)),
        _capsule((0, -0.85, 0.36), (0, -1.22, 0.58), 0.17),
        _mb(E, (0, -1.38, 0.66), 0.19, (1.05, 1.45, 0.85)),
        _mb(E, (0, -1.60, 0.62), 0.12, (1.2, 1.25, 0.8)),
        _mb(E, (0, -1.47, 0.79), 0.08, (2.2, 0.8, 0.6)),
        _mb(E, (0, -1.56, 0.53), 0.09, (1.3, 1.0, 0.55)),
        _mb(E, (0, -1.66, 0.575), 0.05, (2.0, 1.0, 0.5), neg=True),
        _capsule((0, 1.05, 0.22), (0, 1.38, 0.12), 0.08),
    ]
    for sx in (-1, 1):
        for y in (-0.62, 0.72):
            els.append(_mb(E, (sx * 0.66, y, 0.20), 0.19, (1.0, 1.25, 1.05)))
            els.append(_mb(E, (sx * 0.74, y - 0.10, 0.07), 0.13, (1.1, 1.3, 0.55)))
    me = _mb_mesh(els, 0.042)
    _smooth_mesh(me, 4, 0.5)
    bm = bmesh.new()
    bm.from_mesh(me)
    for sx in (-1, 1):                               # eyes, claws, horn nubs
        _sphere(bm, 0.05, (sx * 0.12, -1.55, 0.75), 12, 6, scale=(1, 0.8, 0.9))
        _torus(bm, 0.05, 0.01, 16, 6, matrix=Matrix.Translation((sx * 0.12, -1.545, 0.75)) @
               Matrix.Rotation(math.pi / 2, 4, 'X'))
        _lathe(bm, [(0.035, 0.0), (0.0, 0.10)], 8, matrix=Matrix.Translation((sx * 0.10, -1.38, 0.82)) @
               Matrix.Rotation(-0.7, 4, 'X') @ Matrix.Rotation(sx * 0.4, 4, 'Y'))
        for y in (-0.62, 0.72):
            for k in range(3):
                a = (k - 1) * 0.35 + (math.pi if y > 0 else 0.0)
                c = Vector((sx * 0.74 + 0.08 * math.sin(a), y - 0.10 - 0.13 * math.cos(a) * (1 if y < 0 else -1), 0.03))
                _sphere(bm, 0.035, tuple(c), 8, 4, scale=(1, 1.4, 0.8))
    for side in (-1, 1):                             # teeth
        _lathe(bm, [(0.016, 0.0), (0.0, -0.035)], 6, matrix=Matrix.Translation((side * 0.06, -1.68, 0.62)))
    _xf(bm, S, bm.verts[:])
    _mk(_nm("turtle.body"), bm, pc, [material], smooth=True)
    bpy.data.meshes.remove(me)
    # shell with rim and scutes (props_shell)
    bm = bmesh.new()
    prof = [(1.0, 0.0), (1.04, 0.025), (1.0, 0.06), (0.93, 0.17), (0.80, 0.33), (0.60, 0.46), (0.34, 0.55),
            (0.0, 0.58)]
    _lathe(bm, prof, 48, matrix=S @ Matrix.Translation((0, 0.05, 0.30)) @ Matrix.Diagonal((0.78, 1.18, 0.82, 1)))
    _mk(_nm("turtle.shell"), bm, pc, ["props_shell"], smooth=True)
    # socket block on the shell, and the ground slab
    bm = bmesh.new()
    _sq_lathe(bm, [(0, 0.66), (0.38, 0.66), (0.38, 0.82), (0.40, 0.84), (0.40, 0.88), (0, 0.88)],
              matrix=S @ Matrix.Translation((0, 0.05, 0)) @ Matrix.Diagonal((1.85, 0.62, 1.0, 1)))
    _sq_lathe(bm, [(0, -0.01), (1.0, -0.01), (1.0, 0.04), (0.97, 0.07), (0, 0.07)],
              matrix=S @ Matrix.Diagonal((1.05, 1.75, 1.0, 1)))
    _outward(bm)
    _mk(_nm("turtle.socket"), bm, pc, [material], smooth=False, bevel=0.01 * s)
    return 0.88 * s


def _build_stele(pc, H, glyph_mat, turtle, seed, material):
    s = H / 4.0
    if turtle:
        z0 = _build_turtle(pc, s, material)
    else:
        bm = bmesh.new()
        _xumizuo(bm, 0.85 * s, 0.42 * s, 0.50 * s)
        _mk(_nm("stele.base"), bm, pc, [material], smooth=False, bevel=0.01 * s)
        z0 = 0.50 * s
    W, T = 1.25 * s, 0.32 * s
    zc = 3.3 * s                                      # crown base
    bm = bmesh.new()
    _box(bm, (W, T, zc - z0 + 0.02 * s), (0, 0, (z0 + zc) / 2 - 0.01 * s))
    _mk(_nm("stele.slab"), bm, pc, [material], smooth=False, bevel=0.012 * s)
    # carved border: key-fret band on both faces (relief)
    bm = bmesh.new()
    Hs = zc - z0
    for face in (1, -1):
        m = Matrix.Translation((0, -face * T / 2, (z0 + zc) / 2)) @ (Matrix.Identity(4) if face == 1 else
                                                                    Matrix.Rotation(math.pi, 4, 'Z'))
        _frame_fret(bm, W - 0.04 * s, Hs - 0.04 * s, 0.03 * s, 0.13 * s, 0.0, 0.012 * s, matrix=m)
    _mk(_nm("stele.border"), bm, pc, [material], smooth=False)
    # crown: arched top with two coiling dragons holding a pearl, title panel
    bm = bmesh.new()
    cw, ch = 1.36 * s, 0.70 * s
    outline = [(-cw / 2, 0.0), (cw / 2, 0.0), (cw / 2, ch * 0.45)]
    for i in range(1, 24):
        a = math.pi * i / 24
        outline.append((cw / 2 * math.cos(a), ch * 0.45 + ch * 0.55 * math.sin(a)))
    outline.append((-cw / 2, ch * 0.45))
    vs = _prism(bm, outline, 0.38 * s, y0=-0.19 * s)
    _xf(bm, Matrix.Translation((0, 0, zc)), vs)
    for face in (1, -1):
        yf = -face * 0.19 * s
        for side in (-1, 1):
            pts = []
            for i in range(12):
                t = i / 11
                a = math.pi * (0.05 + 0.42 * t)
                rr = 0.45 * s - 0.06 * s * math.sin(math.pi * t)
                x = side * rr * math.cos(a) * 1.25
                z = zc + 0.25 * s + rr * math.sin(a) * 0.80 - 0.05 * s * math.sin(TAU * t)
                pts.append((x, yf - face * 0.03 * s, z, 1.0 - 0.45 * t))
            _tube(bm, pts, 0.06 * s, 8, 3)
            hp = Vector(pts[0][:3])
            _sphere(bm, 0.09 * s, tuple(hp + Vector((side * 0.02 * s, -face * 0.02 * s, -0.04 * s))), 12, 8,
                    scale=(0.9, 0.8, 1.2))
            _curl(bm, hp + Vector((side * 0.04 * s, -face * 0.06 * s, 0.07 * s)),
                  Vector((side * 0.3, -face * 1.0, 0.4)).normalized(), 0.04 * s)
        _sphere(bm, 0.085 * s, (0, yf - face * 0.05 * s, zc + 0.62 * s), 16, 8)
        # recessed-looking title panel frame
        for (cx, cz, sx_, sz_) in ((0, 0.13, 0.36, 0.03), (0, 0.53, 0.36, 0.03), (-0.165, 0.33, 0.03, 0.43),
                                   (0.165, 0.33, 0.03, 0.43)):
            _box(bm, (sx_ * s, 0.03 * s, sz_ * s), (cx * s, yf - face * 0.01 * s, zc + cz * s))
    _outward(bm)
    _mk(_nm("stele.crown"), bm, pc, [material], smooth=math.radians(40), bevel=0.006 * s)
    # glowing glyphs: columns of classical text (right to left) on the front, title in the crown
    bm = bmesh.new()
    r = U.rng(seed, "stele")
    text = CLASSICS[seed % len(CLASSICS)]
    cols = 6
    cell = (W - 0.36 * s) / cols
    rows = int((Hs - 0.42 * s) / cell)
    origin = Vector((-cols * cell / 2, -T / 2 - 0.003 * s, zc - 0.2 * s))
    _text_columns(bm, text, cols, rows, cell, origin, offset=r.randrange(len(text)))
    back = CLASSICS[(seed + 3) % len(CLASSICS)]
    basis_back = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))     # right = -X, up = Z, normal = +Y
    _text_columns(bm, back, cols - 2, rows - 3, cell, Vector(((cols - 2) * cell / 2, T / 2 + 0.003 * s, zc - 0.35 * s)),
                  basis=basis_back, offset=r.randrange(len(back)))
    title = "玄天宝录"
    _text_columns(bm, title, 2, 2, 0.15 * s, Vector((-0.15 * s, -0.19 * s - 0.004 * s, zc + 0.48 * s)))
    g = _mk(_nm("stele.glyphs"), bm, pc, [glyph_mat], smooth=False, glow=1.3)
    U.set_visibility(g, shadow=False)


def stele(collection, height=4.0, glyph_mat="rune_cyan", turtle_base=True, seed=0, material="stone_dark",
          name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Stone stele (bei), ``height`` m tall in all (default 4 m; 1.36/4*height wide): a dark stone
    slab with a key-fret border, columns of glowing classical text (``glyph_mat``: rune_cyan,
    rune_gold, rune_silver or any emissive material) read top to bottom, right to left, a few
    columns on the back, an arched crown with two coiling relief dragons holding a pearl and a
    four-character title panel. turtle_base=True: it stands on a bixi dragon-turtle (scute shell,
    raised dragon head, clawed feet) on a ground slab, 3.6/4*height long; else on a xumizuo base.
    ``seed`` picks the text. Origin at the ground centre, front faces -Y. Collection instance."""
    b, res = _bucket(height, 4.0)
    gm = glyph_mat if isinstance(glyph_mat, str) else glyph_mat.name
    key = "stele.%s.%s.%d.%d.%s" % (_k(b), gm, turtle_base, seed % 6, material)
    pc = _proto(key, lambda pc: _build_stele(pc, b, glyph_mat, turtle_base, seed % 6, material))
    return _place(pc, collection, name, "stele", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ swords

def _blade_section(w, t, n_edge=2):
    """Diamond-ish blade section points (x across, y thickness) going around."""
    return [(w / 2, 0.0), (w * 0.22, -t * 0.42), (0.0, -t / 2), (-w * 0.22, -t * 0.42), (-w / 2, 0.0),
            (-w * 0.22, t * 0.42), (0.0, t / 2), (w * 0.22, t * 0.42)]


def _loft(bm, sections, mat=0, cap_start=True, tip=None):
    """Loft closed sections [(z, [(x, y), ...]), ...] (same point count) bottom to top; optional
    tip point (x, y, z) closing the top. Returns the verts."""
    rings = [[bm.verts.new((x, y, z)) for x, y in pts] for z, pts in sections]
    made = [v for r in rings for v in r]
    n = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    if tip is not None:
        t = bm.verts.new(tip)
        made.append(t)
        for i in range(n):
            bm.faces.new((rings[-1][i], rings[-1][(i + 1) % n], t))
    else:
        bm.faces.new(rings[-1])
    if mat:
        _set_mat(made, mat)
    return made


def _build_sword(pc, L, style, glow, blade_mat, fitting_mat):
    """Sword designed with blade tip at z=0.74*L, guard at z=0, pommel at -0.235*L."""
    s = L
    S = Matrix.Diagonal((s, s, s, 1.0))
    bm = bmesh.new()
    if style == "dao":
        secs = []
        for i in range(17):
            t = i / 16
            z = 0.02 + 0.70 * t
            w = 0.040 + 0.012 * t
            if t > 0.86:
                w *= max(0.05, 1 - (t - 0.86) / 0.14)
            off = 0.07 * t ** 2
            back_t = 0.0075
            pts = [(off + w / 2, 0.0), (off + w * 0.1, -back_t * 0.6), (off - w / 2, -back_t / 2),
                   (off - w / 2, back_t / 2), (off + w * 0.1, back_t * 0.6)]
            secs.append((z, pts))
        vs = _loft(bm, secs, tip=None)
    elif style == "great":
        secs = []
        for i in range(9):
            t = i / 8
            z = 0.02 + 0.66 * t
            w = 0.085 - 0.01 * t
            secs.append((z, _blade_section(w, 0.014)))
        vs = _loft(bm, secs, tip=(0.0, 0.0, 0.76))
    else:
        secs = []
        for i in range(9):
            t = i / 8
            z = 0.02 + 0.66 * t
            w = 0.036 - 0.006 * t
            secs.append((z, _blade_section(w, 0.0075)))
        vs = _loft(bm, secs, tip=(0.0, 0.0, 0.74))
    _xf(bm, S, vs)
    _mk(_nm("sword.blade"), bm, pc, [blade_mat], smooth=math.radians(25))
    bm = bmesh.new()
    if style == "dao":
        _lathe(bm, [(0.0, -0.006), (0.05, -0.006), (0.052, 0.0), (0.05, 0.006), (0.0, 0.006)], 24, matrix=S)
    else:
        gw = 0.11 if style == "jian" else 0.16
        outline = [(-gw / 2, 0.0), (-gw * 0.45, 0.018), (-gw * 0.2, 0.03), (0.0, 0.034), (gw * 0.2, 0.03),
                   (gw * 0.45, 0.018), (gw / 2, 0.0), (gw * 0.28, -0.012), (0.0, -0.024), (-gw * 0.28, -0.012)]
        vs = _prism(bm, outline[::-1], 0.03, y0=-0.015)
        _xf(bm, S, vs)
    pom = [(0.0, -0.238), (0.020, -0.236), (0.026, -0.226), (0.022, -0.212), (0.016, -0.204), (0.0, -0.2)]
    _lathe(bm, pom, 16, matrix=S)
    _torus(bm, 0.012, 0.0035, 12, 6, matrix=S @ Matrix.Translation((0, 0, -0.245)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    _outward(bm)
    _mk(_nm("sword.fittings"), bm, pc, [fitting_mat], smooth=math.radians(40), bevel=0.0015 * s)
    bm = bmesh.new()                                   # cord-wrapped grip (oval section)
    prof = [(0.0, -0.205)] + [(0.0145 * (1 + 0.08 * abs(math.sin(i * math.pi / 2))), -0.205 + 0.2 * i / 32)
                              for i in range(33)] + [(0.0, -0.005)]
    _lathe(bm, prof, 12, matrix=S @ Matrix.Diagonal((1.0, 0.78, 1.0, 1.0)))
    _mk(_nm("sword.grip"), bm, pc, ["cloth_black"], smooth=True)
    bm = bmesh.new()
    _tube(bm, [(0, 0, -0.245), (0.004, 0, -0.27), (0.0, 0, -0.29)], 0.003, 5, 3, matrix=S)
    _tassel(bm, (0, 0, -0.29 * s), 0.17 * s, 0.008 * s, 0.022 * s, 8)
    _mk(_nm("sword.tassel"), bm, pc, ["cloth_red"], smooth=True)
    if glow:
        bm = bmesh.new()
        if style != "dao":
            for face in (-1, 1):
                z0_, z1_ = 0.08, 0.60
                t = 0.0075 if style == "jian" else 0.014
                pts = [(0.0, z) for z in (z0_, (z0_ + z1_) / 2, z1_)]
                _ribbon(bm, [(x, z) for x, z in pts], 0.0035 if style == "jian" else 0.006, z=0.0,
                        matrix=S @ Matrix.Translation((0, face * (t / 2 + 0.0004), 0)) @
                        Matrix.Rotation(math.pi / 2, 4, 'X'))
        else:
            for face in (-1, 1):
                pts = [(0.07 * (0.1 + 0.6 * t) ** 2 + 0.006, 0.06 + 0.6 * t) for t in [i / 8 for i in range(9)]]
                _ribbon(bm, pts, 0.004, z=0.0, matrix=S @ Matrix.Translation((0, face * 0.0042, 0)) @
                        Matrix.Rotation(math.pi / 2, 4, 'X'))
        _sphere(bm, 0.009, (0, -0.016, 0.012), 10, 6, scale=(1, 0.5, 1), matrix=S)
        _sphere(bm, 0.009, (0, 0.016, 0.012), 10, 6, scale=(1, 0.5, 1), matrix=S)
        g = _mk(_nm("sword.glow"), bm, pc, ["rune_cyan"], smooth=False, glow=1.2)
        U.set_visibility(g, shadow=False)


def sword(collection, length=1.0, style="jian", glow=True, blade_material="steel", fitting_material="gold",
          name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Sword, ``length`` m from blade tip to pommel (plus a 0.2*length red tassel), pointing +Z with
    the flat of the blade facing -Y. style 'jian': straight double-edged with a diamond section,
    bow-shaped guard, cord-wrapped grip, mushroom pommel. 'dao': curved single-edged sabre with a
    disc guard. 'great': broad heavy sword. glow=True adds a jade-cyan line along the blade ridge
    and jade gems on the guard. Origin at the guard. Collection instance."""
    if style not in ("jian", "dao", "great"):
        raise ValueError("sword style must be 'jian', 'dao' or 'great'")
    L = length / 0.978
    b, res = _bucket(L, 1.0)
    key = "sword.%s.%s.%d.%s.%s" % (style, _k(b), glow, blade_material, fitting_material)
    pc = _proto(key, lambda pc: _build_sword(pc, b, style, glow, blade_material, fitting_material))
    return _place(pc, collection, name, "sword", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ artifacts (fa bao)

ARTIFACT_KINDS = ("sword", "bell", "mirror", "orb", "fan", "seal", "gourd", "pagoda_treasure", "ruyi",
                  "bead_string", "flag", "spear", "lotus_lamp", "compass", "jade_disc",
                  # made for the forge ring's projects (areas/forge.py FORGE_ARTIFACTS)
                  "command_flag", "treasure_bowl", "bamboo_slips", "fire_wheel", "spirit_brush", "paper_cranes",
                  "duck_censer", "immortal_peaches", "blossom_fan")

TRIGRAMS = {          # bottom line first (1 = solid yang, 0 = broken yin); Fu Xi (early heaven) order
    "qian": (1, 1, 1), "dui": (1, 1, 0), "li": (1, 0, 1), "zhen": (1, 0, 0),
    "xun": (0, 1, 1), "kan": (0, 1, 0), "gen": (0, 0, 1), "kun": (0, 0, 0),
}
BAGUA_ORDER = ("qian", "xun", "kan", "gen", "kun", "zhen", "li", "dui")

LUOPAN_24 = "壬子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥"

ROT_XZ = Matrix.Rotation(math.pi / 2, 4, 'X')        # XY-plane construction -> XZ plane facing -Y


def _normalize_proto(pc, target=1.0):
    """Scale/centre all mesh data in prototype ``pc`` so its bounding box is centred on the origin
    with the largest dimension = ``target``."""
    obs = [o for o in pc.all_objects if o.type == 'MESH' and len(o.data.vertices)]
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in obs:
        for v in o.data.vertices:
            c = o.matrix_basis @ v.co
            lo = Vector((min(lo.x, c.x), min(lo.y, c.y), min(lo.z, c.z)))
            hi = Vector((max(hi.x, c.x), max(hi.y, c.y), max(hi.z, c.z)))
    size = max(hi - lo)
    k = target / max(size, 1e-6)
    m = Matrix.Diagonal((k, k, k, 1.0)) @ Matrix.Translation(-(lo + hi) / 2)
    done = set()
    for o in obs:
        if o.data.name in done:
            continue
        done.add(o.data.name)
        o.data.transform(o.matrix_basis.inverted() @ m @ o.matrix_basis)
    for o in pc.all_objects:
        if o.type != 'MESH':
            o.location = m @ o.location


def _rotate_meshes(pc, m):
    """Transform all mesh data of prototype ``pc`` by ``m`` (e.g. to pose an artifact diagonally)."""
    for me in {o.data for o in pc.all_objects if o.type == 'MESH'}:
        me.transform(m)


def _trigram_bars(bm, lines, w, bar_h, gap, matrix, depth=0.0):
    """Three trigram bars (bottom line first) stacked upward in a local XZ-like 2D frame given by
    ``matrix`` (local x across, local y up); yin lines have a centre gap."""
    for i, yang in enumerate(lines):
        y = i * (bar_h + gap)
        if yang:
            segs = [(-w / 2, w / 2)]
        else:
            segs = [(-w / 2, -w * 0.08), (w * 0.08, w / 2)]
        for a, b in segs:
            pts = [(a, y + bar_h / 2), (b, y + bar_h / 2)]
            _ribbon(bm, pts, bar_h, z=depth, thick=depth, matrix=matrix)


def _art_sword(pc):
    _build_sword(pc, 1.0, "jian", True, "steel", "gold")


def _art_bell(pc):
    bm = bmesh.new()
    prof = [(0.0, 0.36), (0.13, 0.25), (0.15, 0.0), (0.17, 0.0), (0.165, 0.03), (0.15, 0.12), (0.14, 0.26),
            (0.12, 0.34), (0.08, 0.40), (0.0, 0.42)]
    _lathe(bm, prof, 40, zmod=lambda a, i, r, z: z - (0.025 * abs(math.sin(2 * a)) if i in (2, 3, 4) else 0.0),
           cap_start=False, cap_end=False)
    _lathe(bm, [(0.0, 0.40), (0.025, 0.40), (0.022, 0.80), (0.0, 0.80)], 12)
    for z in (0.47, 0.58, 0.69):
        _torus(bm, 0.027, 0.008, 16, 6, matrix=Matrix.Translation((0, 0, z)))
    _box(bm, (0.16, 0.025, 0.025), (0, 0, 0.80))
    for x, h in ((-0.07, 0.12), (0.0, 0.18), (0.07, 0.12)):
        _lathe(bm, [(0.0, 0.80), (0.014, 0.80), (0.012, 0.80 + h * 0.7), (0.0, 0.80 + h)], 8,
               matrix=Matrix.Translation((x, 0, 0)))
    _sphere(bm, 0.03, (0, 0, 0.06), 12, 6)
    _tube(bm, [(0, 0, 0.36), (0, 0, 0.09)], 0.005, 6, 1)
    _mk(_nm("art.bell.body"), bm, pc, ["bronze"], smooth=math.radians(40))
    bm = bmesh.new()
    _torus(bm, 0.152, 0.012, 40, 6, matrix=Matrix.Translation((0, 0, 0.14)))
    _torus(bm, 0.136, 0.008, 40, 6, matrix=Matrix.Translation((0, 0, 0.27)))
    _sphere(bm, 0.035, (0, 0, 0.765), 12, 6)
    _mk(_nm("art.bell.jade"), bm, pc, ["jade_glow"], smooth=True, glow=2.5)


def _art_mirror(pc):
    bm = bmesh.new()
    _lathe(bm, [(0.30, -0.03), (0.48, -0.03), (0.48, 0.03), (0.46, 0.04), (0.32, 0.04), (0.30, 0.03)], 8,
           phase=math.pi / 8, cap_start=False, cap_end=False, matrix=ROT_XZ)
    _lathe(bm, [(0.0, 0.035), (0.30, 0.035), (0.30, 0.02), (0.0, 0.02)], 48, matrix=ROT_XZ)
    _tube(bm, [(0, 0, -0.48), (0, 0, -0.53)], 0.008, 6, 1)
    _mk(_nm("art.mirror.frame"), bm, pc, ["bronze"], smooth=math.radians(30), bevel=0.004)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.30, 0.0), (0.30, 0.02), (0.24, 0.03), (0.12, 0.04), (0.0, 0.045)], 48,
           matrix=ROT_XZ)
    _mk(_nm("art.mirror.face"), bm, pc, ["silver"], smooth=True)
    bm = bmesh.new()
    _torus(bm, 0.305, 0.012, 64, 6, matrix=Matrix.Translation((0, -0.035, 0)) @ ROT_XZ)
    apo = 0.39
    for k, name in enumerate(BAGUA_ORDER):
        a = math.pi / 2 - TAU * k / 8
        m = Matrix.Translation((apo * math.cos(a), -0.042, apo * math.sin(a))) @ ROT_XZ @ \
            Matrix.Rotation(a - math.pi / 2, 4, 'Z') @ Matrix.Translation((0, -0.045, 0))
        _trigram_bars(bm, TRIGRAMS[name], 0.13, 0.018, 0.012, m, depth=0.006)
    g = _mk(_nm("art.mirror.glow"), bm, pc, ["rune_cyan"], smooth=False, glow=1.0)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    _tassel(bm, (0, 0, -0.53), 0.30, 0.02, 0.05, 10)
    _mk(_nm("art.mirror.tassel"), bm, pc, ["cloth_red"], smooth=True)


def _art_orb(pc):
    bm = bmesh.new()
    _sphere(bm, 0.24, (0, 0, 0.08), 32, 16)
    _mk(_nm("art.orb.core"), bm, pc, ["jade_glow"], smooth=True, glow=2.8)
    bm = bmesh.new()
    for rot in (Matrix.Rotation(0.6, 4, 'X'), Matrix.Rotation(-0.6, 4, 'X') @ Matrix.Rotation(1.1, 4, 'Z')):
        _torus(bm, 0.34, 0.014, 64, 8, matrix=Matrix.Translation((0, 0, 0.08)) @ rot)
    _torus(bm, 0.40, 0.009, 64, 6, matrix=Matrix.Translation((0, 0, 0.08)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    for k in range(8):
        a = TAU * k / 8
        _sphere(bm, 0.02, (0.40 * math.cos(a), 0.0, 0.08 + 0.40 * math.sin(a)), 10, 6)
    for k in range(8):                                      # lotus cradle below
        a = TAU * k / 8
        pts = [(0.03 * math.cos(a), 0.03 * math.sin(a), -0.30), (0.12 * math.cos(a), 0.12 * math.sin(a), -0.22),
               (0.17 * math.cos(a), 0.17 * math.sin(a), -0.12), (0.15 * math.cos(a), 0.15 * math.sin(a), -0.07)]
        _tube(bm, [p + (1.0 - 0.5 * i / 3,) for i, p in enumerate(pts)], 0.022, 6, 3)
    _lathe(bm, [(0.0, -0.36), (0.06, -0.36), (0.07, -0.33), (0.035, -0.29), (0.0, -0.28)], 16)
    _mk(_nm("art.orb.gold"), bm, pc, ["gold"], smooth=math.radians(40))


def _art_fan(pc, painting="moon"):
    """Open folding fan; ``painting`` 'moon' (glowing crescent and wave line) or 'blossom' (ink peach-blossom
    branch with glowing pink flowers: peach blossom stands for luck in love)."""
    n = 15
    a0, a1 = math.radians(-78), math.radians(78)
    R0, R1, Rr = 0.20, 0.62, 0.66
    bm = bmesh.new()
    for i in range(n):
        a = a0 + (a1 - a0) * i / (n - 1)
        d = Vector((math.sin(a), 0.0, math.cos(a)))
        w = 0.022 if i in (0, n - 1) else 0.012
        m = U.align_z(d).to_4x4()
        _box(bm, (w, 0.004 if 0 < i < n - 1 else 0.008, Rr), (0, 0, Rr / 2), matrix=m)
    _cyl(bm, 0.022, 0.03, 16, (0, 0, 0), matrix=ROT_XZ)
    _mk(_nm("art.fan.ribs"), bm, pc, ["wood_light"], smooth=False)
    bm = bmesh.new()                                        # pleated leaf (accordion folds)
    steps = (n - 1) * 2
    rows = 4
    grid = []
    for j in range(rows + 1):
        r = R0 + (R1 - R0) * j / rows
        row = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            y = 0.012 * (1 if i % 2 else -1) * (0.4 + 0.6 * j / rows)
            row.append(bm.verts.new((r * math.sin(a), y, r * math.cos(a))))
        grid.append(row)
    for j in range(rows):
        for i in range(steps):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    _mk(_nm("art.fan.leaf"), bm, pc, ["paper_aged"], smooth=False)
    if painting == "blossom":
        _fan_blossoms(pc)
    else:
        bm = bmesh.new()                                    # glowing painted crescent moon and wave line
        pts = []
        for i in range(41):
            a = a0 * 0.85 + (a1 - a0) * 0.85 * i / 40
            r = 0.42 + 0.035 * math.sin(i * 0.9)
            pts.append((r * math.sin(a), r * math.cos(a)))
        _ribbon(bm, pts, 0.012, z=0.0, matrix=Matrix.Translation((0, -0.017, 0)) @ ROT_XZ)
        moon = [(0.12 + 0.06 * math.cos(t), 0.53 + 0.06 * math.sin(t))
                for t in [math.radians(x) for x in range(60, 301, 15)]]
        _ribbon(bm, moon, 0.012, z=0.0, matrix=Matrix.Translation((0, -0.018, 0)) @ ROT_XZ)
        g = _mk(_nm("art.fan.glow"), bm, pc, ["rune_cyan"], smooth=False, glow=1.0)
        U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    _ico(bm, 0.035, (0, 0, -0.08), 2, scale=(1, 0.5, 1))
    _mk(_nm("art.fan.jade"), bm, pc, ["jade_glow"], smooth=True, glow=2.5)
    bm = bmesh.new()
    _tube(bm, [(0, 0, -0.01), (0, 0, -0.05)], 0.004, 5, 1)
    _tassel(bm, (0, 0, -0.115), 0.24, 0.016, 0.04, 8)
    _mk(_nm("art.fan.tassel"), bm, pc, ["cloth_red"], smooth=True)


def _art_seal(pc):
    tilt = Matrix.Rotation(-0.55, 4, 'X')                    # tipped so the glowing seal face shows
    bm = bmesh.new()
    _box(bm, (0.42, 0.42, 0.24), (0, 0, 0.12), matrix=tilt)
    _mk(_nm("art.seal.body"), bm, pc, ["jade"], smooth=False, bevel=0.02)
    bm = bmesh.new()                                         # coiled chi dragon knob
    pts = []
    for i in range(40):
        t = i / 39
        a = TAU * 1.35 * t
        r = 0.13 - 0.05 * t
        pts.append((r * math.cos(a), r * math.sin(a), 0.27 + 0.13 * t, 1.0 - 0.45 * t))
    _tube(bm, pts, 0.045, 10, 2)
    _sphere(bm, 0.06, (0.045, -0.06, 0.42), 12, 8, scale=(1.0, 1.4, 0.9))
    for side in (-1, 1):
        _lathe(bm, [(0.015, 0.0), (0.0, 0.06)], 6, matrix=Matrix.Translation((0.045 + side * 0.035, -0.03, 0.46)) @
               Matrix.Rotation(0.5, 4, 'X'))
    _xf(bm, tilt, bm.verts[:])
    _mk(_nm("art.seal.knob"), bm, pc, ["gold"], smooth=math.radians(45))
    bm = bmesh.new()
    for k, ch in enumerate("受命于天"):
        col, row = divmod(k, 2)
        me = _text_mesh(ch, 0.15, 2)
        x = (0.5 - col) * 0.17
        z = (0.5 - row) * 0.17
        m = tilt @ Matrix.Translation((x, z, -0.003)) @ Matrix.Diagonal((-1, 1, 1, 1)) @ Matrix.Rotation(math.pi, 4, 'X')
        _add_mesh(bm, me, m)
    _ribbon(bm, [(-0.19, -0.19), (0.19, -0.19), (0.19, 0.19), (-0.19, 0.19)], 0.014, z=0.003, closed=True,
            matrix=tilt @ Matrix.Rotation(math.pi, 4, 'X'))
    g = _mk(_nm("art.seal.glyphs"), bm, pc, ["rune_gold"], smooth=False, glow=1.5)
    U.set_visibility(g, shadow=False)


def _art_gourd(pc):
    prof = [(0.0, 0.0), (0.17, 0.02), (0.235, 0.12), (0.25, 0.22), (0.225, 0.32), (0.14, 0.42), (0.085, 0.47),
            (0.10, 0.52), (0.15, 0.61), (0.155, 0.67), (0.12, 0.75), (0.065, 0.80), (0.045, 0.835), (0.052, 0.86),
            (0.0, 0.86)]
    prof = [prof[0]] + [(p[0], p[1]) for p in U.catmull_rom(prof[1:-1], 4)] + [prof[-1]]
    bm = bmesh.new()
    _lathe(bm, prof, 48)
    _mk(_nm("art.gourd.body"), bm, pc, ["props_gourd"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.85), (0.042, 0.85), (0.05, 0.88), (0.045, 0.92), (0.0, 0.94)], 16)
    _torus(bm, 0.098, 0.012, 32, 6, matrix=Matrix.Translation((0, 0, 0.485)))
    _mk(_nm("art.gourd.jade"), bm, pc, ["jade_glow"], smooth=True, glow=2.5)
    bm = bmesh.new()
    _torus(bm, 0.09, 0.009, 32, 6, matrix=Matrix.Translation((0, 0, 0.47)))
    _tube(bm, [(0.08, -0.04, 0.47), (0.13, -0.08, 0.42), (0.15, -0.09, 0.34)], 0.006, 6, 3)
    _tassel(bm, (0.15, -0.09, 0.34), 0.22, 0.016, 0.04, 8)
    _mk(_nm("art.gourd.cord"), bm, pc, ["cloth_red"], smooth=True)
    bm = bmesh.new()                                         # a curl of spirit qi leaving the mouth
    pts = []
    for i in range(30):
        t = i / 29
        a = TAU * 1.2 * t
        pts.append((0.06 * t * math.cos(a) + 0.04 * t, 0.06 * t * math.sin(a), 0.95 + 0.18 * t, 1.0 - 0.8 * t))
    _tube(bm, pts, 0.012, 6, 2)
    g = _mk(_nm("art.gourd.qi"), bm, pc, ["rune_cyan"], smooth=True, glow=0.8)
    U.set_visibility(g, shadow=False)


def _hex_r(r, a, phase=math.pi / 6):
    """Radius of a hexagon (circumradius r, corners at phase + k*60deg) along angle a."""
    t = ((a - phase) % (math.pi / 3)) - math.pi / 6
    return r * math.cos(math.pi / 6) / math.cos(t)


def _art_pagoda(pc):
    bm_g = bmesh.new()
    bm_j = bmesh.new()
    corner = lambda a: abs(math.cos(3 * (a - math.pi / 6))) ** 10
    z = 0.0
    _lathe(bm_g, [(0.0, 0.0), (0.20, 0.0), (0.22, 0.03), (0.19, 0.06), (0.15, 0.08), (0.0, 0.08)], 48,
           rmod=lambda a, i, r, zz: r * (1 + 0.08 * abs(math.cos(8 * a))) if i in (2, 3) else r)
    z = 0.08
    tiers = 7
    for k in range(tiers):
        t = k / (tiers - 1)
        rb = 0.13 - 0.055 * t
        hb = 0.075 - 0.012 * t
        re = rb + 0.065 - 0.012 * t
        _lathe(bm_j, [(rb, z), (rb, z + hb)], 24, rmod=lambda a, i, r, zz: _hex_r(r, a), cap_start=False,
               cap_end=False)
        ze = z + hb
        _lathe(bm_g, [(rb * 0.95, ze - 0.004), (re, ze - 0.012), (re * 1.02, ze - 0.004), (rb * 0.85, ze + 0.028),
                      (0.0, ze + 0.028)], 24,
               rmod=lambda a, i, r, zz: _hex_r(r, a), zmod=lambda a, i, r, zz: zz + (0.035 * corner(a) if i < 3 else 0.0))
        for c in range(6):                                   # bells at the eave corners
            a = math.pi / 6 + c * math.pi / 3
            _sphere(bm_g, 0.008, (re * 1.04 * math.cos(a), re * 1.04 * math.sin(a), ze + 0.015), 8, 4)
        z = ze + 0.028
    _lathe(bm_g, [(0.0, z), (0.03, z), (0.012, z + 0.02), (0.012, z + 0.16), (0.0, z + 0.17)], 12)
    for i in range(5):
        _torus(bm_g, 0.025 - 0.003 * i, 0.006, 16, 6, matrix=Matrix.Translation((0, 0, z + 0.03 + 0.025 * i)))
    _sphere(bm_g, 0.025, (0, 0, z + 0.19), 12, 6)
    _mk(_nm("art.pagoda.gold"), bm_g, pc, ["gold"], smooth=math.radians(35))
    _mk(_nm("art.pagoda.jade"), bm_j, pc, ["jade_glow"], smooth=False, glow=2.4)


def _art_ruyi(pc):
    bm = bmesh.new()
    path = [(0.0, -0.36), (0.035, -0.22), (0.02, -0.05), (-0.02, 0.10), (-0.005, 0.24), (0.03, 0.30)]
    prof = [(math.cos(TAU * k / 10) * 1.0, math.sin(TAU * k / 10) * 0.55) for k in range(10)]
    _tube(bm, [(x, 0.0, z, 1.0 - 0.25 * abs(z)) for x, z in path], 0.032, samples=6, profile=prof)
    lobes = []                                                # lingzhi head: three cloud lobes
    for i in range(48):
        t = TAU * i / 48
        r = 0.15 * (1.0 + 0.24 * math.cos(3 * t + math.pi / 2)) * (1.0 - 0.22 * max(0.0, -math.sin(t)) ** 3)
        lobes.append((r * math.cos(t) * 1.15, r * math.sin(t)))
    head = Matrix.Translation((0.03, 0.0, 0.38)) @ Matrix.Rotation(-0.45, 4, 'X')
    vs = _prism(bm, [(x, z) for x, z in lobes], 0.05, y0=-0.025)
    _xf(bm, head, vs)
    vs = _prism(bm, [(x * 0.5, z * 0.5) for x, z in lobes], 0.04, y0=-0.02)
    _xf(bm, Matrix.Translation((0.0, 0.0, -0.40)), vs)
    vs = _prism(bm, [(x * 0.45, z * 0.45) for x, z in lobes], 0.05, y0=-0.025)
    _xf(bm, Matrix.Translation((0.012, 0.0, -0.03)), vs)
    _outward(bm)
    _mk(_nm("art.ruyi.body"), bm, pc, ["jade"], smooth=math.radians(35), bevel=0.008)
    bm = bmesh.new()
    for m, r in ((head @ Matrix.Translation((0, -0.03, 0)), 0.045),
                 (Matrix.Translation((0.012, -0.029, -0.03)), 0.028),
                 (Matrix.Translation((0.0, -0.022, -0.40)), 0.025)):
        _sphere(bm, r, (0, 0, 0), 16, 8, scale=(1, 0.45, 1), matrix=m)
    _mk(_nm("art.ruyi.gems"), bm, pc, ["jade_glow"], smooth=True, glow=3.0)
    bm = bmesh.new()
    _tassel(bm, (0.0, 0.0, -0.44), 0.22, 0.016, 0.04, 8)
    _mk(_nm("art.ruyi.tassel"), bm, pc, ["cloth_red"], smooth=True)
    _rotate_meshes(pc, Matrix.Rotation(0.5, 4, 'Y'))


def _art_beads(pc):
    bm_w, bm_j = bmesh.new(), bmesh.new()
    n, R = 18, 0.30
    for i in range(n):
        a = -math.pi / 2 + TAU * (i + 0.5) / n
        c = (R * math.cos(a), 0.0, R * math.sin(a))
        if i % 6 == 2:
            _sphere(bm_j, 0.05, c, 16, 8)
        else:
            _sphere(bm_w, 0.042, c, 16, 8)
    _sphere(bm_j, 0.06, (0.0, 0.0, -R - 0.05), 16, 8)
    _mk(_nm("art.beads.wood"), bm_w, pc, ["jade"], smooth=True)
    _mk(_nm("art.beads.jade"), bm_j, pc, ["jade_glow"], smooth=True, glow=2.6)
    bm = bmesh.new()
    _torus(bm, R, 0.005, 72, 5, matrix=ROT_XZ)
    _tassel(bm, (0.0, 0.0, -R - 0.11), 0.26, 0.018, 0.045, 10)
    _mk(_nm("art.beads.cord"), bm, pc, ["cloth_red"], smooth=True)


def _art_flag(pc, glyph=None):
    """Array pennant on a staff; the glowing sign is the qian trigram, or ``glyph`` in gold (令: a command flag)."""
    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.5), (0.014, -0.5), (0.012, 0.42), (0.0, 0.42)], 10)
    _mk(_nm("art.flag.staff"), bm, pc, ["lacquer_black"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.40), (0.022, 0.40), (0.025, 0.44), (0.012, 0.47), (0.024, 0.52), (0.0, 0.64)], 12)
    _lathe(bm, [(0.0, -0.53), (0.02, -0.53), (0.018, -0.48), (0.0, -0.48)], 12)
    _mk(_nm("art.flag.gold"), bm, pc, ["gold"], smooth=math.radians(40))
    bm = bmesh.new()                                         # waving triangular pennant with flame teeth
    nu, nv, L, Hf = 14, 6, 0.55, 0.40
    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        for i in range(nu + 1):
            u = i / nu
            hh = Hf * (1 - u) + 0.03
            zt = 0.40 - (1 - v) * 0.0 - v * hh
            tooth = 0.03 * (1 - abs(((u * 5) % 1.0) * 2 - 1)) if j == nv else 0.0
            x = 0.012 + u * L
            y = 0.04 * u * math.sin(TAU * (u * 1.3 - 0.1)) + 0.015 * v * u
            row.append(bm.verts.new((x, y, zt - tooth)))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.material_index = 1 if (j == nv - 1 or j == 0) else 0
    _mk(_nm("art.flag.cloth"), bm, pc, ["banner_7", "cloth_gold"], smooth=True)
    bm = bmesh.new()
    if glyph:
        _add_mesh(bm, _text_mesh(glyph, 0.17, 2), Matrix.Translation((0.17, -0.008, 0.25)) @ ROT_XZ)
        g = _mk(_nm("art.flag.glyph"), bm, pc, ["rune_gold"], smooth=False, glow=1.5)
    else:
        m = Matrix.Translation((0.16, -0.012, 0.28)) @ ROT_XZ @ Matrix.Translation((0, 0, 0))
        _trigram_bars(bm, TRIGRAMS["qian"], 0.12, 0.018, 0.012, m)
        g = _mk(_nm("art.flag.glow"), bm, pc, ["rune_cyan"], smooth=False, glow=1.2)
    U.set_visibility(g, shadow=False)


def _art_spear(pc):
    bm = bmesh.new()
    secs = []
    for i in range(11):
        t = i / 10
        w = 0.075 * math.sin(math.pi * min(1.0, 0.12 + 0.88 * t)) ** 0.8 + 0.01
        secs.append((0.36 + 0.21 * t, _blade_section(w, 0.011)))
    _loft(bm, secs, tip=(0.0, 0.0, 0.62))
    _mk(_nm("art.spear.head"), bm, pc, ["steel"], smooth=math.radians(25))
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.30), (0.018, 0.30), (0.022, 0.33), (0.016, 0.35), (0.012, 0.365), (0.0, 0.365)], 12)
    _lathe(bm, [(0.0, -0.48), (0.016, -0.48), (0.014, -0.44), (0.0, -0.44)], 12)
    _mk(_nm("art.spear.gold"), bm, pc, ["gold"], smooth=math.radians(40))
    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.44), (0.012, -0.44), (0.012, 0.30), (0.0, 0.30)], 10)
    _mk(_nm("art.spear.shaft"), bm, pc, ["lacquer_red"], smooth=True)
    bm = bmesh.new()
    _tassel(bm, (0.0, 0.0, 0.305), 0.14, 0.02, 0.055, 18, head=False)
    _mk(_nm("art.spear.tassel"), bm, pc, ["cloth_red"], smooth=True)
    bm = bmesh.new()
    for face in (-1, 1):
        _ribbon(bm, [(0.0, 0.38), (0.0, 0.54)], 0.006, z=0.0,
                matrix=Matrix.Translation((0, face * 0.0062, 0)) @ ROT_XZ)
    _sphere(bm, 0.016, (0, 0, 0.335), 10, 6, scale=(1.4, 1.4, 0.6))
    _mk(_nm("art.spear.glow"), bm, pc, ["jade_glow"], smooth=False, glow=2.5)
    _rotate_meshes(pc, Matrix.Rotation(-0.35, 4, 'Y'))


def _petal(bm, length, width, cup, curl, matrix, nu=4, nv=6):
    """Curved lotus petal (spoon shape): base at the origin, growing along +Z, cupped toward -Y."""
    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        half = width / 2 * math.sin(math.pi * min(1.0, 0.12 + 0.88 * v)) ** 0.7 * (1 - 0.6 * v ** 6)
        for i in range(nu + 1):
            u = -1 + 2 * i / nu
            x = u * half
            y = cup * (1 - u * u) * math.sin(math.pi * v) - curl * v * v
            z = v * length
            row.append(bm.verts.new(Matrix(matrix) @ Vector((x, y, z))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))


def _art_lotus_lamp(pc):
    bm_o, bm_i = bmesh.new(), bmesh.new()
    for ring, (n, L, Wd, tilt, bmx) in enumerate(((9, 0.26, 0.15, 1.05, bm_o), (9, 0.24, 0.13, 0.65, bm_o),
                                                  (7, 0.20, 0.11, 0.30, bm_i))):
        for k in range(n):
            a = TAU * (k + 0.5 * ring) / n
            m = Matrix.Translation((0.04 * math.cos(a), 0.04 * math.sin(a), 0.06 + 0.02 * ring)) @ \
                Matrix.Rotation(a - math.pi / 2, 4, 'Z') @ Matrix.Rotation(-tilt, 4, 'X')
            _petal(bmx, L, Wd, 0.03, -0.05, m)
    _mk(_nm("art.lotus.outer"), bm_o, pc, ["props_jade_white"], smooth=True)
    _mk(_nm("art.lotus.inner"), bm_i, pc, ["jade_glow"], smooth=True, glow=2.2)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.05), (0.07, 0.06), (0.075, 0.10), (0.06, 0.115), (0.0, 0.115)], 20)
    for k in range(7):
        a = TAU * k / 7
        _sphere(bm, 0.012, (0.035 * math.cos(a), 0.035 * math.sin(a), 0.115), 8, 4)
    _mk(_nm("art.lotus.pod"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.30, 0.03), (0.33, 0.05), (0.28, 0.06), (0.0, 0.07)], 32,
           rmod=lambda a, i, r, z: r * (1 + 0.06 * math.sin(7 * a)))
    _mk(_nm("art.lotus.pad"), bm, pc, ["jade"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.12), (0.035, 0.15), (0.03, 0.20), (0.012, 0.25), (0.0, 0.29)], 16)
    _mk(_nm("art.lotus.flame"), bm, pc, ["props_flame"], smooth=True, glow=1.0)


def _art_compass(pc):
    tilt = Matrix.Rotation(0.95, 4, 'X')                     # face tipped up toward the viewer
    bm = bmesh.new()
    _sq_lathe(bm, [(0.0, -0.05), (0.40, -0.05), (0.41, -0.03), (0.40, -0.01), (0.0, -0.01)], matrix=tilt)
    _mk(_nm("art.compass.base"), bm, pc, ["lacquer_red_worn"], smooth=False, bevel=0.004)
    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.01), (0.355, -0.01), (0.36, 0.035), (0.35, 0.045), (0.06, 0.045), (0.05, 0.03),
                (0.0, 0.03)], 64, matrix=tilt)
    _mk(_nm("art.compass.disc"), bm, pc, ["wood_light"], smooth=math.radians(30))
    bm = bmesh.new()
    z = 0.0465
    for r in (0.06, 0.11, 0.17, 0.24, 0.30, 0.345):
        _annulus(bm, r - 0.003, r + 0.003, 96, z, matrix=tilt)
    for k in range(72):
        a = TAU * k / 72
        _ribbon(bm, [(0.30 * math.cos(a), 0.30 * math.sin(a)), (0.345 * math.cos(a), 0.345 * math.sin(a))], 0.003,
                z=z, matrix=tilt)
    for k, name in enumerate(BAGUA_ORDER):
        a = math.pi / 2 - TAU * k / 8
        m = tilt @ Matrix.Translation((0.115 * math.cos(a), 0.115 * math.sin(a), z)) @ \
            Matrix.Rotation(a - math.pi / 2, 4, 'Z')
        _trigram_bars(bm, TRIGRAMS[name], 0.032, 0.008, 0.0055, m)
    for k, ch in enumerate(LUOPAN_24):
        a = math.pi / 2 - TAU * k / 24
        me = _text_mesh(ch, 0.04, 1)
        m = tilt @ Matrix.Translation((0.205 * math.cos(a), 0.205 * math.sin(a), z)) @ \
            Matrix.Rotation(a - math.pi / 2, 4, 'Z')
        _add_mesh(bm, me, m)
    g = _mk(_nm("art.compass.glow"), bm, pc, ["rune_gold"], smooth=False, glow=1.2)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    _box(bm, (0.012, 0.09, 0.004), (0, 0.0, 0.034), matrix=tilt)
    _mk(_nm("art.compass.needle"), bm, pc, ["steel"], smooth=False)
    bm = bmesh.new()
    for a in (0.0, math.pi / 2):
        d = Vector((math.cos(a), math.sin(a), 0))
        _tube(bm, [tuple(tilt @ (d * -0.40 + Vector((0, 0, 0.048)))), tuple(tilt @ (d * 0.40 + Vector((0, 0, 0.048))))],
              0.0025, 5, 1)
    _mk(_nm("art.compass.threads"), bm, pc, ["cloth_red"], smooth=True)
    bm = bmesh.new()
    _sphere(bm, 0.05, (0, 0, 0.0), 16, 8, scale=(1, 1, 0.3), matrix=tilt @ Matrix.Translation((0, 0, 0.035)))
    _mk(_nm("art.compass.pool"), bm, pc, ["jade_glow"], smooth=True, glow=2.0)


def _art_jade_disc(pc):
    bm = bmesh.new()
    _lathe(bm, [(0.11, -0.025), (0.40, -0.025), (0.405, -0.015), (0.405, 0.015), (0.40, 0.025), (0.11, 0.025),
                (0.105, 0.015), (0.105, -0.015), (0.11, -0.025)], 72, cap_start=False, cap_end=False, matrix=ROT_XZ)
    _merge(bm, 1e-6)
    # raised grain (gu wen) bumps on both faces, on a hex grid inside the band
    for face in (-1, 1):
        rows = 14
        for j in range(-rows, rows + 1):
            for i in range(-rows, rows + 1):
                x = (i + 0.5 * (j % 2)) * 0.052
                z = j * 0.045
                r = math.hypot(x, z)
                if 0.15 < r < 0.365:
                    _sphere(bm, 0.017, (x, face * 0.026, z), 8, 4, scale=(1, 0.55, 1))
    _mk(_nm("art.disc.body"), bm, pc, ["jade_glow"], smooth=math.radians(50), glow=1.6)
    bm = bmesh.new()
    _torus(bm, 0.40, 0.006, 96, 5, matrix=Matrix.Translation((0, -0.026, 0)) @ ROT_XZ)
    _torus(bm, 0.11, 0.006, 48, 5, matrix=Matrix.Translation((0, -0.026, 0)) @ ROT_XZ)
    g = _mk(_nm("art.disc.glow"), bm, pc, ["rune_cyan"], smooth=False, glow=1.0)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    _tube(bm, [(0, -0.005, 0.10), (0, -0.01, 0.16), (0.0, 0.0, 0.40), (0.0, 0.0, 0.52)], 0.006, 6, 4)
    _tube(bm, [(0, 0.005, -0.10), (0, 0.0, -0.40), (0.0, 0.0, -0.46)], 0.006, 6, 4)
    _tassel(bm, (0.0, 0.0, -0.46), 0.24, 0.018, 0.045, 10)
    _mk(_nm("art.disc.cord"), bm, pc, ["cloth_red"], smooth=True)


# ---- project artifacts: the forge ring's objects that stand for one portfolio project each

def _slab(bm, pts, t):
    """Planar polygon ``pts`` (3D, in order) with thickness ``t`` along its normal (folded paper)."""
    P3 = [Vector(p) for p in pts]
    n = (P3[1] - P3[0]).cross(P3[2] - P3[0])
    n = n.normalized() * (t / 2) if n.length > 1e-12 else Vector((0, 0, t / 2))
    top = [bm.verts.new(p + n) for p in P3]
    bot = [bm.verts.new(p - n) for p in P3]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    k = len(P3)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return top + bot


def _disc2d(bm, cx, cy, r, n, matrix):
    """Flat n-gon of radius ``r`` at (cx, cy) in the XY plane (normal +Z), then ``matrix``."""
    m = Matrix(matrix)
    vs = [bm.verts.new(m @ Vector((cx + r * math.cos(TAU * k / n), cy + r * math.sin(TAU * k / n), 0.0)))
          for k in range(n)]
    bm.faces.new(vs)
    return vs


def _yuanbao(bm, s, matrix):
    """Gold ingot (yuan bao) ``s`` long along X: a boat whose ends curl up, a dome in the middle."""
    vs = _sphere(bm, 1.0, (0, 0, 0), 20, 10, scale=(0.5 * s, 0.3 * s, 0.16 * s))
    for v in vs:
        v.co.z += 0.28 * s * (v.co.x / (0.5 * s)) ** 4
    vs += _sphere(bm, 1.0, (0, 0, 0.09 * s), 16, 8, scale=(0.2 * s, 0.17 * s, 0.17 * s))
    _xf(bm, matrix, vs)
    return vs


def _coin(bm, r, t, matrix, segs=24):
    """Round cash coin with a square hole (fang kong qian) in the XY plane, radius ``r``, thickness ``t``."""
    h = 0.3 * r
    of, ob, inf, ib = [], [], [], []
    for k in range(segs):
        a = math.pi / 4 + TAU * k / segs
        c, s = math.cos(a), math.sin(a)
        q = h / max(abs(c), abs(s))                          # the square hole's edge along this angle
        for lst, rr, z in ((of, r, t / 2), (ob, r, -t / 2), (inf, q, t / 2), (ib, q, -t / 2)):
            lst.append(bm.verts.new((rr * c, rr * s, z)))
    for k in range(segs):
        j = (k + 1) % segs
        bm.faces.new((inf[k], of[k], of[j], inf[j]))
        bm.faces.new((ib[j], ob[j], ob[k], ib[k]))
        bm.faces.new((of[j], of[k], ob[k], ob[j]))
        bm.faces.new((inf[k], inf[j], ib[j], ib[k]))
    made = of + ob + inf + ib
    _xf(bm, matrix, made)
    return made


def _art_treasure_bowl(pc):
    """Treasure bowl (ju bao pen): red lacquer basin heaped with copper cash, gold ingots and coins, a glowing
    pearl on top, 招财进宝 in gold on the band; tipped toward the viewer so the heap shows."""
    tilt = Matrix.Rotation(0.35, 4, 'X')
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.01), (0.17, 0.01), (0.17, 0.0), (0.21, 0.0), (0.21, 0.035), (0.30, 0.07), (0.38, 0.11),
                (0.405, 0.14), (0.405, 0.205), (0.44, 0.235), (0.455, 0.255), (0.44, 0.27), (0.41, 0.26),
                (0.37, 0.215), (0.30, 0.14), (0.16, 0.10), (0.0, 0.095)], 64, cap_start=False, cap_end=False,
           matrix=tilt)
    _mk(_nm("art.bowl.basin"), bm, pc, ["lacquer_red"], smooth=math.radians(40))

    def mound(x, y):
        return 0.21 + 0.11 * math.sqrt(max(0.0, 1.0 - (x * x + y * y) / 0.39 ** 2))

    bm = bmesh.new()                                         # the heap under the gold: copper cash
    vs = _sphere(bm, 1.0, (0, 0, 0.21), 40, 16, scale=(0.39, 0.39, 0.11))
    for v in vs:
        if v.co.z > 0.215:
            v.co.z += 0.012 * math.sin(17 * v.co.x) * math.sin(13 * v.co.y)
    _xf(bm, tilt, vs)
    _mk(_nm("art.bowl.cash"), bm, pc, ["bronze"], smooth=True)
    bm = bmesh.new()
    for R_, r_, z_ in ((0.445, 0.014, 0.258), (0.21, 0.01, 0.035), (0.407, 0.006, 0.14), (0.407, 0.006, 0.205)):
        _torus(bm, R_, r_, 64, 6, matrix=tilt @ Matrix.Translation((0, 0, z_)))
    for x, y, yaw, roll, s, lift in ((0.0, -0.01, 0.0, 0.0, 0.27, 0.06), (-0.20, -0.10, 0.55, 0.18, 0.22, 0.03),
                                     (0.21, -0.08, -0.45, -0.15, 0.22, 0.03), (-0.06, 0.20, 0.25, 0.1, 0.22, 0.03),
                                     (0.17, 0.16, -1.0, 0.0, 0.2, 0.03), (-0.23, 0.12, 1.25, 0.12, 0.2, 0.03)):
        _yuanbao(bm, s, tilt @ Matrix.Translation((x, y, mound(x, y) + lift)) @ Matrix.Rotation(yaw, 4, 'Z') @
                 Matrix.Rotation(roll, 4, 'X'))
    rnd = random.Random(11)
    for k, (x, y) in enumerate(((-0.08, -0.22), (0.07, -0.25), (0.29, 0.02), (-0.30, 0.0), (0.0, 0.27),
                                (-0.13, -0.05), (0.11, 0.04), (0.25, -0.18), (-0.27, -0.17))):
        m = tilt @ Matrix.Translation((x, y, mound(x, y) + 0.012)) @ Matrix.Rotation(rnd.uniform(-0.4, 0.4), 4, 'X') @ \
            Matrix.Rotation(rnd.uniform(-0.4, 0.4), 4, 'Y') @ Matrix.Rotation(rnd.uniform(0, TAU), 4, 'Z')
        cv = _coin(bm, 0.055, 0.01, m)
        if k % 3 == 2:
            _set_mat(cv, 1)
    _mk(_nm("art.bowl.gold"), bm, pc, ["gold", "bronze"], smooth=math.radians(40))
    bm = bmesh.new()                                         # luminous pearl on the top ingot
    _sphere(bm, 0.055, (0.0, -0.01, mound(0.0, -0.01) + 0.06 + 0.07 + 0.05), 20, 10, matrix=tilt)
    _mk(_nm("art.bowl.pearl"), bm, pc, ["jade_glow"], smooth=True, glow=2.8)
    bm = bmesh.new()                                         # 招财进宝 on the band, left to right
    for k, ch in enumerate("招财进宝"):
        th = -math.pi / 2 + (k - 1.5) * 0.28
        pos = (0.409 * math.cos(th), 0.409 * math.sin(th), 0.172)
        _add_mesh(bm, _text_mesh(ch, 0.062, 2), tilt @ Matrix.Translation(pos) @
                  Matrix.Rotation(th + math.pi / 2, 4, 'Z') @ ROT_XZ)
    for x0, y0, z0, turn in ((-0.12, 0.05, 0.40, 1.0), (0.14, 0.02, 0.38, -1.0)):   # curls of gold qi
        pts = []
        for i in range(24):
            t = i / 23
            a = TAU * 1.1 * t * turn
            pts.append((x0 + 0.05 * t * math.cos(a), y0 + 0.05 * t * math.sin(a), z0 + 0.22 * t, 1.0 - 0.75 * t))
        _tube(bm, [tuple(tilt @ Vector(p[:3])) + (p[3],) for p in pts], 0.008, 6, 2)
    g = _mk(_nm("art.bowl.glow"), bm, pc, ["rune_gold"], smooth=False, glow=1.5)
    U.set_visibility(g, shadow=False)


def _art_bamboo_slips(pc):
    """Bamboo-slip book (zhu jian), half unrolled on a shallow arc with the rest rolled up at the end, bound
    with red cord. Analects 1.1 runs down the slips right to left; the first two columns (the lesson being
    taught now) glow."""
    W, T, H, step = 0.07, 0.012, 0.66, 0.078
    n_open, R_arc = 9, 1.1
    cols = ("子曰學而時習之", "不亦說乎", "有朋自遠方來", "不亦樂乎", "人不知而不慍", "不亦君子乎")
    slips = []                                               # (centre, yaw): yaw turns the front (-Y) normal
    for i in range(n_open):                                  # right to left
        phi = ((n_open - 1) / 2 - i) * step / R_arc
        slips.append((Vector((R_arc * math.sin(phi), -R_arc * (1 - math.cos(phi)), 0.0)), -phi))
    last_c, last_yaw = slips[-1]
    roll_c = last_c + Vector((-0.115, 0.075, 0.0))
    roll = []
    for layer_r, n in ((0.085, 7), (0.05, 4)):
        for k in range(n):
            psi = math.radians(-20) + TAU * k / n
            roll.append((roll_c + Vector((layer_r * math.cos(psi), layer_r * math.sin(psi), 0.0)), psi + math.pi / 2))
    bm = bmesh.new()
    rnd = random.Random(5)
    for c, yaw in slips + roll:
        _box(bm, (W, T, H + rnd.uniform(-0.012, 0.004)), (0, 0, rnd.uniform(-0.006, 0.006)),
             matrix=Matrix.Translation(c) @ Matrix.Rotation(yaw, 4, 'Z'))
    _mk(_nm("art.slips.bamboo"), bm, pc, ["props_bamboo_slip"], smooth=False, bevel=0.003)

    def front(c, yaw):
        return Vector((math.sin(yaw), -math.cos(yaw), 0.0))

    bm = bmesh.new()                                         # cords near the ends, over and under each slip
    for z in (0.29, -0.29):
        pts = []
        for i, (c, yaw) in enumerate(slips):
            pts.append(tuple(c + front(c, yaw) * ((T / 2 + 0.004) * (1 if i % 2 == 0 else -1)) + Vector((0, 0, z))))
        pts.append(tuple(roll_c + Vector((0.0, -0.098, z))))
        _tube(bm, pts, 0.004, 6, 4)
        _torus(bm, 0.085 + T / 2 + 0.004, 0.004, 40, 6, matrix=Matrix.Translation(roll_c + Vector((0, 0, z))))
    _mk(_nm("art.slips.cord"), bm, pc, ["cloth_red"], smooth=True)
    bm_glow, bm_ink = bmesh.new(), bmesh.new()
    for i, col in enumerate(cols):
        c, yaw = slips[i]
        for j, ch in enumerate(col):
            pos = c + front(c, yaw) * (T / 2 + 0.0015) + Vector((0, 0, 0.235 - j * 0.07))
            _add_mesh(bm_glow if i < 2 else bm_ink, _text_mesh(ch, 0.052, 2),
                      Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, 'Z') @ ROT_XZ)
    _mk(_nm("art.slips.ink"), bm_ink, pc, ["ink"], smooth=False)
    g = _mk(_nm("art.slips.glow"), bm_glow, pc, ["rune_cyan"], smooth=False, glow=1.2)
    U.set_visibility(g, shadow=False)


def _art_fire_wheel(pc):
    """Wind Fire Wheel (feng huo lun, Nezha's): gold rims and spokes round a red lacquer band, flame tongues
    swept back round the rim (fire), glowing wind swirls round a jade hub (wind); upright, facing -Y."""
    bm = bmesh.new()
    _torus(bm, 0.34, 0.028, 72, 10, matrix=ROT_XZ)
    _torus(bm, 0.20, 0.016, 56, 8, matrix=ROT_XZ)
    _torus(bm, 0.075, 0.016, 32, 8, matrix=ROT_XZ)
    for k in range(8):
        a = TAU * k / 8 + math.pi / 8
        _tube(bm, [(0.08 * math.cos(a), 0.0, 0.08 * math.sin(a)), (0.33 * math.cos(a), 0.0, 0.33 * math.sin(a))],
              0.011, 6, 1)
    for k in range(16):
        a = TAU * k / 16
        for side in (-1, 1):
            _sphere(bm, 0.014, (0.265 * math.cos(a), side * 0.016, 0.265 * math.sin(a)), 8, 4)
    _mk(_nm("art.wheel.gold"), bm, pc, ["gold"], smooth=math.radians(40))
    bm = bmesh.new()
    prof = [(0.205, -0.012), (0.325, -0.012), (0.325, 0.012), (0.205, 0.012), (0.205, -0.012)]
    _lathe(bm, prof, 72, cap_start=False, cap_end=False, matrix=ROT_XZ)
    _merge(bm)
    _outward(bm)
    _mk(_nm("art.wheel.band"), bm, pc, ["lacquer_red"], smooth=False)
    bm = bmesh.new()
    _sphere(bm, 0.055, (0, 0, 0), 20, 10, scale=(1.0, 0.6, 1.0))
    _mk(_nm("art.wheel.hub"), bm, pc, ["jade_glow"], smooth=True, glow=2.6)
    bm = bmesh.new()                                         # flame tongues, swept back as the wheel spins
    prof = [(math.cos(TAU * k / 8), 0.45 * math.sin(TAU * k / 8)) for k in range(8)]
    for k in range(12):
        a = TAU * k / 12
        pts = []
        for t in (0.0, 0.3, 0.6, 1.0):
            r = 0.33 + 0.17 * t
            aa = a - 0.45 * t ** 1.4
            pts.append((r * math.cos(aa), r * math.sin(aa), 0.0, max(0.05, (1.0 - t) ** 0.7)))
        _tube(bm, pts, 0.045, samples=4, profile=prof, matrix=ROT_XZ)
    _mk(_nm("art.wheel.flame"), bm, pc, ["props_flame"], smooth=True, glow=1.0)
    bm = bmesh.new()                                         # wind: three swirls in front of the spokes
    for k in range(3):
        a0 = TAU * k / 3
        pts = [((0.09 + 0.1 * t) * math.cos(a0 + 1.6 * t), (0.09 + 0.1 * t) * math.sin(a0 + 1.6 * t))
               for t in [i / 16 for i in range(17)]]
        _ribbon(bm, pts, 0.016, z=0.0, matrix=Matrix.Translation((0, -0.03, 0)) @ ROT_XZ)
    g = _mk(_nm("art.wheel.wind"), bm, pc, ["rune_cyan"], smooth=False, glow=1.0)
    U.set_visibility(g, shadow=False)


def _art_spirit_brush(pc):
    """Magic brush (shen bi) filling in a form by itself: a sheet leaning back, titled 開戶 (open an account),
    rows 姓名 / 住址 / 簽名 in ink with the answers in glowing gold, the brush writing the last one, a red
    seal in the corner and a curl of gold qi round the brush tip."""
    PW, PH, PT = 0.62, 0.44, 0.008
    MP = Matrix.Translation((0.0, 0.0, 0.2)) @ Matrix.Rotation(-0.45, 4, 'X') @ ROT_XZ   # paper XY, front +Z
    zf = PT / 2 + 0.0015
    bm = bmesh.new()
    _box(bm, (PW, PH, PT), (0, 0, 0), matrix=MP)
    _mk(_nm("art.brush.paper"), bm, pc, ["paper_aged"], smooth=False)
    bm_ink, bm_gold = bmesh.new(), bmesh.new()
    _add_mesh(bm_ink, _text_mesh("開戶", 0.075, 2), MP @ Matrix.Translation((0.0, 0.15, zf)))
    for y, label, value in ((0.05, "姓名", "李白"), (-0.05, "住址", "長安"), (-0.15, "簽名", "李")):
        _add_mesh(bm_ink, _text_mesh(label, 0.05, 2), MP @ Matrix.Translation((-0.19, y, zf)))
        _add_mesh(bm_gold, _text_mesh(value, 0.056, 2), MP @ Matrix.Translation((0.06 if len(value) > 1 else 0.02,
                                                                                  y, zf)))
        _ribbon(bm_ink, [(-0.06, y - 0.036), (0.24, y - 0.036)], 0.004, z=zf, matrix=MP)
    _ribbon(bm_ink, [(-0.29, -0.2), (0.29, -0.2), (0.29, 0.2), (-0.29, 0.2)], 0.005, z=zf, closed=True, matrix=MP)
    _mk(_nm("art.brush.ink"), bm_ink, pc, ["ink"], smooth=False)
    bm = bmesh.new()
    _box(bm, (0.05, 0.05, 0.002), (0.22, -0.155, zf), matrix=MP)
    _mk(_nm("art.brush.seal"), bm, pc, ["lacquer_red"], smooth=False)
    # the brush: tip on the paper just after 李, handle rising toward the viewer
    tip = MP @ Vector((0.08, -0.15, PT / 2))
    B = Matrix.Translation(tip) @ U.align_z(Vector((0.35, -0.55, 0.76)).normalized()).to_4x4()
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.008, 0.012), (0.019, 0.04), (0.025, 0.07), (0.024, 0.095), (0.02, 0.105),
                (0.0, 0.105)], 16, matrix=B)
    _mk(_nm("art.brush.hair"), bm, pc, ["ink"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.10), (0.024, 0.10), (0.026, 0.11), (0.026, 0.135), (0.02, 0.14), (0.0, 0.14)], 16, matrix=B)
    _mk(_nm("art.brush.ferrule"), bm, pc, ["gold"], smooth=math.radians(40))
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.14), (0.019, 0.14), (0.017, 0.52), (0.0, 0.52)], 14, matrix=B)
    _mk(_nm("art.brush.handle"), bm, pc, ["lacquer_red"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.52), (0.02, 0.52), (0.024, 0.55), (0.018, 0.57), (0.0, 0.58)], 14, matrix=B)
    _mk(_nm("art.brush.cap"), bm, pc, ["jade"], smooth=True)
    bm = bmesh.new()
    _torus(bm, 0.02, 0.004, 16, 6, matrix=B @ Matrix.Translation((0, 0, 0.6)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    _mk(_nm("art.brush.loop"), bm, pc, ["cloth_red"], smooth=True)
    _sphere(bm_gold, 0.012, (0, 0, 0), 12, 6, matrix=B)
    pts = []
    for i in range(30):
        t = i / 29
        a = 3 * math.pi * t
        r = 0.05 + 0.03 * t
        pts.append((r * math.cos(a), r * math.sin(a), 0.02 + 0.3 * t, 1.0 - 0.8 * t))
    _tube(bm_gold, [tuple(B @ Vector(p[:3])) + (p[3],) for p in pts], 0.006, 6, 2)
    g = _mk(_nm("art.brush.glow"), bm_gold, pc, ["rune_gold"], smooth=False, glow=1.5)
    U.set_visibility(g, shadow=False)


def _crane(bm, s, matrix):
    """Origami paper crane ``s`` m long flying along +X, wings up in a V. Returns its verts."""
    def P(x, y, z):
        return (x * s, y * s, z * s)
    t = 0.012 * s
    F, B, T, D = P(0.22, 0, 0.06), P(-0.22, 0, 0.06), P(0, 0, 0.17), P(0, 0, -0.06)
    L, Rr = P(0, 0.10, 0.05), P(0, -0.10, 0.05)
    body = [bm.verts.new(p) for p in (F, B, T, D, L, Rr)]
    f, b, tp, d, l, r = body
    for tri in ((f, tp, l), (tp, b, l), (b, d, l), (d, f, l), (tp, f, r), (b, tp, r), (d, b, r), (f, d, r)):
        bm.faces.new(tri)
    vs = list(body)
    vs += _slab(bm, (P(0.16, 0, 0.08), P(0.08, 0, 0.13), P(0.40, 0, 0.34), P(0.42, 0, 0.31)), t)     # neck
    vs += _slab(bm, (P(0.38, 0, 0.33), P(0.42, 0, 0.345), P(0.48, 0, 0.27)), t)                     # head
    vs += _slab(bm, (P(-0.12, 0, 0.12), P(-0.20, 0, 0.07), P(-0.44, 0, 0.30), P(-0.42, 0, 0.33)), t)  # tail
    for side in (1, -1):                                                                             # wings
        vs += _slab(bm, (P(0.12, side * 0.02, 0.15), P(-0.14, side * 0.02, 0.15), P(-0.10, side * 0.42, 0.36)), t)
    _xf(bm, matrix, vs)
    return vs


def _art_paper_cranes(pc):
    """A flock of paper cranes (zhi he, messengers) circling a bowl heaped with rice, each trailing a thread of
    jade qi: a swarm with no leader carrying food where it is needed."""
    big = Matrix.Diagonal((1.2, 1.2, 1.2, 1.0))
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.07, 0.0), (0.075, 0.015), (0.07, 0.02), (0.11, 0.05), (0.16, 0.10), (0.18, 0.14),
                (0.17, 0.145), (0.15, 0.11), (0.10, 0.065), (0.0, 0.05)], 48, cap_start=False, cap_end=False,
           matrix=big)
    _mk(_nm("art.cranes.bowl"), bm, pc, ["props_jade_white"], smooth=math.radians(40))
    bm = bmesh.new()
    _torus(bm, 0.176, 0.006, 48, 6, matrix=big @ Matrix.Translation((0, 0, 0.143)))
    _mk(_nm("art.cranes.rim"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    vs = _ico(bm, 1.0, (0, 0, 0), 3, scale=(0.155, 0.155, 0.07))
    for v in vs:
        v.co.z = max(v.co.z, -0.02) + 0.003 * math.sin(97 * v.co.x) * math.cos(83 * v.co.y)
        v.co.z += 0.105
    _xf(bm, big, vs)
    _mk(_nm("art.cranes.rice"), bm, pc, ["props_rice"], smooth=True)
    bm = bmesh.new()
    bm_q = bmesh.new()

    def path(th):
        return Vector((0.29 * math.cos(th), 0.29 * math.sin(th), 0.34 + 0.07 * math.sin(2 * th + 1.0)))

    for k in range(5):
        th = -math.pi / 2 + 0.3 + TAU * k / 5
        m = Matrix.Translation(path(th)) @ Matrix.Rotation(th + math.pi / 2, 4, 'Z') @ \
            Matrix.Rotation(-0.3, 4, 'X') @ Matrix.Rotation(0.12 * math.sin(3 * k), 4, 'Y') @ \
            Matrix.Translation((0, 0, -0.03))
        cv = _crane(bm, 0.38, m)
        if k % 3:
            _set_mat(cv, k % 3)
        pts = [tuple(path(th - 0.16 - 0.6 * u)) + (1.0 - 0.85 * u,) for u in [i / 12 for i in range(13)]]
        _tube(bm_q, pts, 0.007, 6, 2)
    _outward(bm)
    _mk(_nm("art.cranes.paper"), bm, pc, ["props_paper_red", "paper_aged", "props_paper_gold"], smooth=False)
    g = _mk(_nm("art.cranes.qi"), bm_q, pc, ["rune_cyan"], smooth=True, glow=1.0)
    U.set_visibility(g, shadow=False)


def _art_duck_censer(pc):
    """Golden duck censer (jin ya, the duck-shaped incense burner of Song poems) floating on a jade dish with
    glowing ripples, a curl of qi rising from its beak as if it were talking; seen side on, head to +X."""
    zc = 0.12
    bm = bmesh.new()
    vs = _sphere(bm, 1.0, (0, 0, zc), 32, 16, scale=(0.27, 0.19, 0.16))
    for v in vs:
        x, z = v.co.x, v.co.z
        tx = max(0.0, (-x - 0.08) / 0.19)                    # tail: rises and narrows to a point
        v.co.z += 0.16 * tx ** 2
        v.co.y *= 1.0 - 0.45 * tx
        if z < zc:
            v.co.z = zc + (z - zc) * 0.7 + (v.co.z - z)      # flatter belly
    _tube(bm, [(0.15, 0, zc + 0.05), (0.19, 0, zc + 0.15), (0.205, 0, zc + 0.22)], 0.065, 12, 3)
    _sphere(bm, 0.088, (0.215, 0.0, zc + 0.27), 24, 12, scale=(1.12, 0.92, 1.0))
    for side in (-1, 1):                                     # wings, tips raised toward the tail
        _sphere(bm, 1.0, (0, 0, 0), 20, 10, scale=(0.15, 0.035, 0.075),
                matrix=Matrix.Translation((-0.04, side * 0.16, zc + 0.04)) @ Matrix.Rotation(0.35, 4, 'Y') @
                Matrix.Rotation(side * 0.12, 4, 'Z'))
    _sphere(bm, 0.022, (-0.03, 0.0, zc + 0.165), 12, 6)   # lid knob on the back
    _torus(bm, 0.035, 0.008, 20, 6, matrix=Matrix.Translation((-0.03, 0.0, zc + 0.15)))
    _mk(_nm("art.duck.body"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    _sphere(bm, 1.0, (0.30, 0.0, zc + 0.255), 16, 8, scale=(0.075, 0.045, 0.024))
    _mk(_nm("art.duck.beak"), bm, pc, ["props_beak"], smooth=True)
    bm = bmesh.new()
    for side in (-1, 1):
        _sphere(bm, 0.016, (0.255, side * 0.07, zc + 0.29), 12, 6)
    _mk(_nm("art.duck.eyes"), bm, pc, ["jade_glow"], smooth=True, glow=2.6)
    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.03), (0.22, -0.03), (0.28, -0.01), (0.30, 0.02), (0.29, 0.03), (0.0, 0.03)], 48)
    _mk(_nm("art.duck.dish"), bm, pc, ["jade"], smooth=math.radians(40))
    bm = bmesh.new()
    for r in (0.20, 0.255):
        _annulus(bm, r - 0.005, r + 0.005, 64, 0.0315)
    pts = [(0.375, 0, zc + 0.26), (0.43, 0, zc + 0.30), (0.44, 0, zc + 0.37), (0.40, 0, zc + 0.42),
           (0.36, 0, zc + 0.47), (0.38, 0, zc + 0.53), (0.43, 0, zc + 0.56)]
    _tube(bm, [p + (1.0 - 0.65 * i / (len(pts) - 1),) for i, p in enumerate(pts)], 0.013, 8, 4)
    g = _mk(_nm("art.duck.qi"), bm, pc, ["rune_cyan"], smooth=True, glow=1.0)
    U.set_visibility(g, shadow=False)


def _peach(bm, r, matrix, segs=28):
    """Peach of immortality: round, pointed tip up (bent a little), a crease down the front (-Y)."""
    prof = [(0.0, -0.95), (0.45, -0.88), (0.8, -0.6), (0.98, -0.15), (0.97, 0.25), (0.8, 0.62), (0.5, 0.92),
            (0.2, 1.12), (0.0, 1.22)]
    prof = [prof[0]] + [(p[0], p[1]) for p in U.catmull_rom(prof[1:-1], 3)] + [prof[-1]]

    def crease(a, i, rr, z):
        d = math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))
        return rr * (1.0 - 0.10 * math.exp(-(d / 0.28) ** 2))
    rings = _lathe(bm, [(x * r, z * r) for x, z in prof], segs, rmod=crease)
    vs = [v for ring in rings for v in ring]
    for v in vs:
        if v.co.z > 0.6 * r:
            v.co.x += 0.12 * r * ((v.co.z / r - 0.6) / 0.6) ** 2
    _xf(bm, matrix, vs)
    return vs


def _art_immortal_peaches(pc):
    """Peaches of immortality (pan tao): four on a celadon plate with a gold rim and a glowing jade ring, green
    leaves fanned out underneath; tipped toward the viewer."""
    tilt = Matrix.Rotation(0.3, 4, 'X')
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.13, 0.0), (0.14, 0.012), (0.30, 0.03), (0.365, 0.058), (0.375, 0.07), (0.36, 0.074),
                (0.30, 0.05), (0.13, 0.035), (0.0, 0.035)], 56, matrix=tilt)
    _mk(_nm("art.peach.plate"), bm, pc, ["ceramic_celadon"], smooth=math.radians(40))
    bm = bmesh.new()
    _torus(bm, 0.37, 0.007, 56, 6, matrix=tilt @ Matrix.Translation((0, 0, 0.071)))
    _mk(_nm("art.peach.rim"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    _torus(bm, 0.315, 0.006, 56, 6, matrix=tilt @ Matrix.Translation((0, 0, 0.047)))
    g = _mk(_nm("art.peach.ring"), bm, pc, ["jade_glow"], smooth=True, glow=2.0)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    for x, y, z, r, yaw in ((-0.13, 0.07, 0.16, 0.13, 0.4), (0.13, 0.07, 0.16, 0.13, -0.3),
                            (0.0, -0.12, 0.165, 0.135, 0.0), (0.0, 0.01, 0.345, 0.12, 0.15)):
        _peach(bm, r, tilt @ Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, 'Z'))
    _mk(_nm("art.peach.fruit"), bm, pc, ["props_peach"], smooth=True)
    bm = bmesh.new()
    for w in (-2.1, -1.05, 0.25, 1.3, 2.5):
        base = Vector((0.12 * math.cos(w), 0.12 * math.sin(w), 0.05))
        _petal(bm, 0.21, 0.085, 0.015, -0.03, tilt @ Matrix.Translation(base) @
               Matrix.Rotation(w + math.pi / 2, 4, 'Z') @ Matrix.Rotation(1.2, 4, 'X'))
    _mk(_nm("art.peach.leaves"), bm, pc, ["props_peach_leaf"], smooth=True)


def _fan_blossoms(pc):
    """The blossom fan's painting: an ink branch across the leaf with glowing pink five-petal flowers."""
    M2 = Matrix.Translation((0, -0.016, 0)) @ ROT_XZ
    bm = bmesh.new()
    _ribbon(bm, [(-0.52, 0.30), (-0.36, 0.40), (-0.18, 0.45), (0.0, 0.50), (0.16, 0.52), (0.30, 0.47)], 0.014,
            matrix=M2)
    _ribbon(bm, [(-0.18, 0.45), (-0.14, 0.50), (-0.10, 0.55)], 0.009, matrix=M2)
    _ribbon(bm, [(0.16, 0.52), (0.19, 0.545), (0.22, 0.56)], 0.009, matrix=M2)
    _mk(_nm("art.fan.branch"), bm, pc, ["ink"], smooth=False)
    bm, bm_c = bmesh.new(), bmesh.new()
    M3 = Matrix.Translation((0, -0.019, 0)) @ ROT_XZ
    for i, (cx, cy) in enumerate(((-0.36, 0.41), (-0.12, 0.53), (-0.02, 0.47), (0.10, 0.535), (0.22, 0.56),
                                  (0.31, 0.45), (-0.27, 0.36))):
        rot = 0.7 * i
        for k in range(5):
            a = rot + TAU * k / 5
            _disc2d(bm, cx + 0.019 * math.cos(a), cy + 0.019 * math.sin(a), 0.017, 7, M2)
        _disc2d(bm_c, cx, cy, 0.008, 6, M3)
    for cx, cy in ((0.12, 0.33), (0.28, 0.30), (-0.05, 0.28)):   # falling petals
        _disc2d(bm, cx, cy, 0.015, 7, M2)
    g = _mk(_nm("art.fan.blossom"), bm, pc, ["rune_blossom"], smooth=False, glow=1.2)
    U.set_visibility(g, shadow=False)
    g = _mk(_nm("art.fan.stamens"), bm_c, pc, ["rune_gold"], smooth=False, glow=1.2)
    U.set_visibility(g, shadow=False)


_ARTIFACT_BUILDERS = {
    "sword": _art_sword, "bell": _art_bell, "mirror": _art_mirror, "orb": _art_orb, "fan": _art_fan,
    "seal": _art_seal, "gourd": _art_gourd, "pagoda_treasure": _art_pagoda, "ruyi": _art_ruyi,
    "bead_string": _art_beads, "flag": _art_flag, "spear": _art_spear, "lotus_lamp": _art_lotus_lamp,
    "compass": _art_compass, "jade_disc": _art_jade_disc,
    "command_flag": lambda pc: _art_flag(pc, glyph="令"), "treasure_bowl": _art_treasure_bowl,
    "bamboo_slips": _art_bamboo_slips, "fire_wheel": _art_fire_wheel, "spirit_brush": _art_spirit_brush,
    "paper_cranes": _art_paper_cranes, "duck_censer": _art_duck_censer, "immortal_peaches": _art_immortal_peaches,
    "blossom_fan": lambda pc: _art_fan(pc, painting="blossom"),
}


def artifact(collection, kind, size=1.0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Floating cultivation artifact (fa bao), ``size`` m in its largest dimension, centred on the
    origin, front facing -Y, each with jade-glow accents. ``kind`` is one of ARTIFACT_KINDS:
    sword (flying jian, glowing ridge), bell (Taoist handbell with a three-prong handle), mirror
    (octagonal bagua mirror, glowing trigrams), orb (glowing jade pearl in gold rings on a lotus
    cradle), fan (open folding fan with a glowing painted moon), seal (jade seal with a coiled
    dragon knob, glowing script face tipped toward the viewer), gourd (calabash with a jade stopper,
    red cord and a curl of qi), pagoda_treasure (seven-tier gold pagoda with glowing jade storeys),
    ruyi (jade sceptre with a cloud head), bead_string (ring of prayer beads with jade spacers),
    flag (array pennant on a staff with a glowing trigram), spear (leaf head, red horsehair tassel),
    lotus_lamp (jade lotus with a flame), compass (luopan with glowing rings, trigrams and the 24
    mountains, tipped up), jade_disc (bi disc with grain bumps, cord and tassel).
    Returns a collection-instance Empty (one prototype per kind, scaled)."""
    if kind not in _ARTIFACT_BUILDERS:
        raise ValueError("unknown artifact kind %r; valid: %s" % (kind, ", ".join(ARTIFACT_KINDS)))

    def build(pc):
        _ARTIFACT_BUILDERS[kind](pc)
        _normalize_proto(pc, 1.0)
    pc = _proto("art.%s" % kind, build)
    return _place(pc, collection, name, "artifact_" + kind, parent, location, rotation, size)


# ============================================================ chain and rope

def _link_proto(material):
    """Unit chain link (outer length 1 along Z, width 0.62, wire radius 0.1) prototype object."""
    def build(pc):
        bm = bmesh.new()
        pts = []
        for i in range(4):
            pts.append((0.21, 0.0, -0.19 + 0.38 * i / 3))
        for i in range(1, 8):
            a = math.pi * i / 8
            pts.append((0.21 * math.cos(a), 0.0, 0.19 + 0.21 * math.sin(a)))
        for i in range(4):
            pts.append((-0.21, 0.0, 0.19 - 0.38 * i / 3))
        for i in range(1, 8):
            a = math.pi + math.pi * i / 8
            pts.append((0.21 * math.cos(a), 0.0, -0.19 + 0.21 * math.sin(a)))
        _tube(bm, pts, 0.1, 7, 1, closed=True, smooth_path=False)
        _mk(_nm("chain_link"), bm, pc, [material], smooth=True)
    return _proto_object("link.%s" % material, build)


def chain(collection, p0, p1, link_size=0.3, sag=None, material="iron", name=None, parent=None):
    """Iron chain from ``p0`` to ``p1`` (in the parent's space) hanging along a catenary that
    drops ``sag`` m below the chord midpoint (default 8 % of the span). Links are ``link_size`` m
    long, interlocking (alternately rotated 90 deg) and placed by a geometry-node point instancer
    (one object, one shared link mesh). Returns the instancer object."""
    p0, p1 = Vector(p0), Vector(p1)
    span = (p1 - p0).length
    sag = span * 0.08 if sag is None else sag
    pts = _catenary(p0, p1, sag, 128)
    pos, tans = _resample(pts, link_size * 0.6)
    rots = []
    for i, t in enumerate(tans):
        q = U.align_z(t).to_quaternion() @ Quaternion((0, 0, 1), (math.pi / 2) * (i % 2))
        rots.append(q)
    link = _link_proto(material)
    return _point_instancer(U.unique_name(name or PREFIX + ".chain"), collection, link, pos, rots,
                            [link_size] * len(pos), parent=parent)


def rope(collection, p0, p1, sag=None, radius=0.03, material="props_rope", strands=3, name=None, parent=None):
    """Twisted rope from ``p0`` to ``p1`` (parent space) along a catenary dropping ``sag`` m
    (default 5 % of the span). ``strands`` helical strands (0 = plain tube; long thin ropes fall
    back to a plain tube to stay light). Returns the rope object."""
    p0, p1 = Vector(p0), Vector(p1)
    span = (p1 - p0).length
    sag = span * 0.05 if sag is None else sag
    nm = U.unique_name(name or PREFIX + ".rope")
    pitch = radius * 7.0
    n = int(span / (pitch / 8.0)) + 2
    if strands and n > 2400:
        strands = 0
    if not strands:
        pts = _catenary(p0, p1, sag, max(16, min(256, int(span / (radius * 4)))))
        return U.tube_mesh(nm, [tuple(p) for p in pts], radius, collection, material=material, sides=8,
                           samples_per_segment=1, parent=parent)
    path = _catenary(p0, p1, sag, n)
    fr = _frames([tuple(p) for p in path])
    bm = bmesh.new()
    seglen = span / n
    for k in range(strands):
        pts = []
        for i, (c, _t, nr, b) in enumerate(fr):
            phi = TAU * (i * seglen) / pitch + TAU * k / strands
            pts.append(tuple(c + (nr * math.cos(phi) + b * math.sin(phi)) * radius * 0.45))
        _tube(bm, pts, radius * 0.58, 6, 1, smooth_path=False)
    return _mk(nm, bm, collection, [material], parent=parent, smooth=True)


# ============================================================ jade tablet

def _knot(bm, c, s):
    """Simplified Chinese knot (pan chang): a woven diamond lattice of cord with four corner ears."""
    cx, cy, cz = c
    h = s * 0.5
    q = 1.0 / math.sqrt(2.0)

    def P(u, v, dy=0.0):
        return (cx + (u - v) * q, cy + dy, cz + (u + v) * q)
    for k in range(4):
        o = (k - 1.5) * h * 0.5
        dy = s * 0.012 * (1 if k % 2 else -1)
        _tube(bm, [P(o, -h, dy), P(o, h, dy)], s * 0.035, 5, 1)
        _tube(bm, [P(-h, o, -dy), P(h, o, -dy)], s * 0.035, 5, 1)
    for u, v in ((h, h), (-h, -h), (h, -h), (-h, h)):
        x, y, z = P(u * 1.25, v * 1.25)
        _torus(bm, s * 0.12, s * 0.035, 12, 5, matrix=Matrix.Translation((x, y, z)) @ ROT_XZ)


def _tablet_outline(w, h):
    pts = [(-w / 2 + 0.03 * w, 0.0), (w / 2 - 0.03 * w, 0.0), (w / 2, 0.03 * w), (w / 2, 0.76 * h),
           (w / 2 * 0.90, 0.79 * h)]
    for i in range(1, 20):
        a = math.pi * i / 20
        pts.append((w / 2 * 0.90 * math.cos(a), 0.79 * h + 0.21 * h * math.sin(a) * (1 + 0.08 * math.sin(3 * a) ** 2)))
    pts += [(-w / 2 * 0.90, 0.79 * h), (-w / 2, 0.76 * h), (-w / 2, 0.03 * w)]
    return pts


def _build_tablet(pc, h, glow, cord, text):
    w, t = 0.5 * h, 0.07 * h
    z0 = -cord - h
    bm = bmesh.new()
    vs = _prism(bm, _tablet_outline(w, h), t, y0=-t / 2)
    _xf(bm, Matrix.Translation((0, 0, z0)), vs)
    _mk(_nm("tablet.body"), bm, pc, ["jade_glow" if glow else "jade"], smooth=False, bevel=0.012 * h,
        glow=1.0 if glow else None)
    bm = bmesh.new()
    inner = [(x * 0.84, z * 0.88 + 0.05 * h) for x, z in _tablet_outline(w, h)]
    for face in (-1, 1):
        _ribbon(bm, [(x, z) for x, z in inner], 0.018 * h, z=0.004 * h, thick=0.004 * h, closed=True,
                matrix=Matrix.Translation((0, face * t / 2, z0)) @ (ROT_XZ if face < 0 else
                                                                    Matrix.Rotation(math.pi, 4, 'Z') @ ROT_XZ))
    _torus(bm, 0.045 * h, 0.012 * h, 16, 6, matrix=Matrix.Translation((0, 0, z0 + h + 0.03 * h)) @ ROT_XZ)
    _mk(_nm("tablet.gold"), bm, pc, ["gold"], smooth=True)
    bm = bmesh.new()
    chars = text or TABLET_TEXTS[0]
    cell = min(w * 0.42, h * 0.78 / max(1, len(chars)))
    n = len(chars)
    _text_columns(bm, chars, 1, n, cell, Vector((-cell / 2, -t / 2 - 0.004 * h, z0 + 0.5 * h + n * cell / 2)))
    g = _mk(_nm("tablet.glyphs"), bm, pc, ["rune_gold" if glow else "gold"], smooth=False, glow=1.5 if glow else None)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    top = z0 + h + 0.075 * h
    _tube(bm, [(0, 0, 0.0), (-0.03 * h, 0, -cord * 0.5), (-0.012 * h, 0, top + 0.01 * h), (0, 0, top - 0.02 * h)],
          0.009 * h, 6, 4)
    _tube(bm, [(0, 0, 0.0), (0.03 * h, 0, -cord * 0.5), (0.012 * h, 0, top + 0.01 * h), (0, 0, top - 0.02 * h)],
          0.009 * h, 6, 4)
    _tube(bm, [(0, 0, z0), (0, 0, z0 - 0.06 * h)], 0.009 * h, 6, 1)
    _knot(bm, (0, 0, z0 - 0.16 * h), 0.18 * h)
    _tube(bm, [(0, 0, z0 - 0.27 * h), (0, 0, z0 - 0.30 * h)], 0.009 * h, 6, 1)
    _tassel(bm, (0, 0, z0 - 0.30 * h), 0.55 * h, 0.03 * h, 0.07 * h, 14)
    _mk(_nm("tablet.cord"), bm, pc, ["cloth_red"], smooth=True)


def jade_tablet(collection, height=0.6, glow=True, cord=0.5, text=None, seed=0, name=None, parent=None,
                location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Hanging jade tablet (ling pai): a ``height`` m tall, 0.5*height wide jade plaque with a
    cloud-arched top, a raised gold border on both faces, a gold ring, a column of glowing gold
    characters (``text``, default chosen by ``seed`` from TABLET_TEXTS), and a red cord running up
    ``cord`` m to the suspension point, with a Chinese knot and a long red tassel below.
    glow=True uses jade_glow. Origin = suspension point (the tablet hangs below it). Instanced."""
    b, res = _bucket(height, 0.6)
    txt = text or TABLET_TEXTS[seed % len(TABLET_TEXTS)]
    cq = round(cord / height / 0.1) * 0.1
    key = "tablet.%s.%d.%s.%08x" % (_k(b), glow, _k(cq), zlib.crc32(txt.encode("utf-8")))
    pc = _proto(key, lambda pc: _build_tablet(pc, b, glow, cq * b, txt))
    return _place(pc, collection, name, "jade_tablet", parent, location, rotation, tuple(res * c for c in _v3(scale)))


# ============================================================ scrolls and books

def bamboo_slip_scroll(collection, width=3.0, height=1.2, curve=0.25, glow=True, seed=0, rolled=True,
                       text_material=None, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Unrolled bamboo-slip scroll (zhu jian) of jade slips: ``width`` x ``height`` m, bowed in plan
    so its ends come ``curve``*width toward the viewer (-Y), slips bound by two red silk cords
    woven over and under, each slip carrying a column of glowing classical script (text_material,
    default rune_gold on glowing jade; glow=False: plain jade with ink), and (rolled=True) a tight
    roll of slips at the left end. Origin at the centre, front faces -Y. Returns the root Empty
    (unique: every slip carries different text)."""
    root = _root(collection, name, "slip_scroll", parent, location, rotation)
    pn = root.name
    r = U.rng(seed, "slips")
    N = max(8, int(round(width / (height * 0.075))))
    pitch = width / N
    sw, st = pitch * 0.88, pitch * 0.16
    d = max(1e-4, curve * width)
    R = (width * width / 4 + d * d) / (2 * d)
    half_ang = math.asin(min(1.0, width / 2 / R))
    tm = text_material or ("rune_gold" if glow else "ink")

    def frame_at(i_f):
        a = -half_ang + 2 * half_ang * (i_f + 0.5) / N
        c = Vector((R * math.sin(a), -R + R * math.cos(a), 0.0))
        return c, a
    bm = bmesh.new()
    bt = bmesh.new()
    text = CLASSICS[seed % len(CLASSICS)]
    k = r.randrange(len(text))
    cell = sw * 0.80
    rows = int(height * 0.84 / cell)
    for i in range(N):
        c, a = frame_at(i)
        rot = Matrix.Rotation(-a, 4, 'Z')
        m = Matrix.Translation(c) @ rot
        _box(bm, (sw, st, height), (0, 0, 0), matrix=m)
        basis = rot.to_3x3() @ Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
        origin = c + rot.to_3x3() @ Vector((-cell / 2, -st / 2 - 0.0015 * height, rows * cell / 2))
        col_txt = "".join(text[(k + j) % len(text)] for j in range(rows))
        k += rows
        _text_columns(bt, col_txt, 1, rows, cell, origin, basis=basis.to_3x3(), res=1 if cell < 0.15 else 2)
    if rolled:
        c0, a0 = frame_at(-0.5)
        axis = c0 + Vector((-pitch * 1.4, -pitch * 0.6, 0))
        for j in range(12):
            th = 0.6 * j
            rr = pitch * 0.55 + pitch * 0.13 * th
            p = axis + Vector((rr * math.cos(th + 0.6), rr * math.sin(th + 0.6), 0))
            _box(bm, (sw, st, height), (0, 0, 0), matrix=Matrix.Translation(p) @ Matrix.Rotation(th + 0.6 + math.pi / 2, 4, 'Z'))
    _mk(U.unique_name(pn + ".slips"), bm, collection, ["jade_slip" if glow else "jade"], parent=root,
        smooth=False, bevel=st * 0.25, glow=0.7 if glow else None)
    g = _mk(U.unique_name(pn + ".script"), bt, collection, [tm], parent=root, smooth=False, glow=1.1 if glow else None)
    U.set_visibility(g, shadow=False)
    bm = bmesh.new()
    for zc in (-height * 0.32, height * 0.32):
        pts = []
        for i in range(N * 4 + 1):
            f = i / 4.0 - 0.5
            c, a = frame_at(f)
            nrm = Vector((-math.sin(a), math.cos(a), 0))
            off = math.cos(math.pi * (i / 4.0)) * st * 0.9
            pts.append(tuple(c - nrm * off + Vector((0, 0, zc))))
        _tube(bm, pts, st * 0.42, 6, 1, smooth_path=True)
    _mk(U.unique_name(pn + ".cords"), bm, collection, ["cloth_red"], parent=root, smooth=True)
    return root


def _build_scroll(pc, w, opened, glow, seed):
    h = w * 0.36
    r = U.rng(seed, "scroll")
    ph = r.uniform(0, TAU)

    def wave(x):
        return 0.03 * w * math.sin(TAU * x / w * 1.1 + ph)
    if opened:
        bm = bmesh.new()
        nu, nv = 32, 3
        grid = []
        for j in range(nv + 1):
            z = -h / 2 + h * j / nv
            row = []
            for i in range(nu + 1):
                x = -w / 2 + w * i / nu
                row.append(bm.verts.new((x, wave(x), z)))
            grid.append(row)
        for j in range(nv):
            for i in range(nu):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        _mk(_nm("scroll.paper"), bm, pc, ["paper_aged"], smooth=True)
        bm = bmesh.new()
        for x, rr in ((-w / 2, 0.035 * w), (w / 2, 0.018 * w)):
            _cyl(bm, rr, h + 0.02 * w, 20, (x, wave(x) + rr * 0.6, 0))
        _mk(_nm("scroll.rollers"), bm, pc, ["wood_dark"], smooth=True)
        bm = bmesh.new()
        for x, rr in ((-w / 2, 0.035 * w), (w / 2, 0.018 * w)):
            for sz in (-1, 1):
                _lathe(bm, [(0.0, 0.0), (rr * 1.05, 0.0), (rr * 1.2, 0.02 * w), (rr * 0.8, 0.045 * w), (0.0, 0.05 * w)],
                       16, matrix=Matrix.Translation((x, wave(x) + rr * 0.6, sz * (h / 2 + 0.01 * w))) @
                       Matrix.Diagonal((1, 1, sz, 1)))
        _outward(bm)
        _mk(_nm("scroll.knobs"), bm, pc, ["jade_glow" if glow else "jade"], smooth=True, glow=1.5 if glow else None)
        bm = bmesh.new()
        text = CLASSICS[seed % len(CLASSICS)]
        cell = h * 0.11
        cols = int(w * 0.80 / (cell * 1.25))
        rows = int(h * 0.80 / cell)
        k = r.randrange(len(text))
        for c in range(cols):
            x0 = w * 0.40 - (c + 0.5) * cell * 1.25
            for j in range(rows):
                ch = text[(k + c * rows + j) % len(text)]
                me = _text_mesh(ch, cell * 0.85, 2)
                z0 = h * 0.40 - (j + 0.5) * cell

                def fn(co, x0=x0, z0=z0):
                    x = x0 + co.x
                    return Vector((x, wave(x) - 0.002, z0 + co.y))
                _add_mesh_fn(bm, me, fn)
        g = _mk(_nm("scroll.text"), bm, pc, ["rune_gold" if glow else "ink"], smooth=False, glow=0.9 if glow else None)
        U.set_visibility(g, shadow=False)
        bm = bmesh.new()
        xs = w * 0.40 - (cols + 0.3) * cell * 1.25
        _box(bm, (cell * 1.1, 0.002, cell * 1.1), (xs, wave(xs) - 0.0025, h * 0.40 - cell * (rows - 1.2)))
        _mk(_nm("scroll.seal"), bm, pc, ["lacquer_red"], smooth=False)
    else:
        bm = bmesh.new()
        L = h + 0.02 * w
        _lathe(bm, [(0.0, -L / 2), (0.045 * w, -L / 2), (0.05 * w, -L / 2 + 0.01 * w), (0.05 * w, L / 2 - 0.01 * w),
                    (0.045 * w, L / 2), (0.0, L / 2)], 24, matrix=Matrix.Rotation(math.pi / 2, 4, 'Y'))
        _mk(_nm("scroll.roll"), bm, pc, ["paper_aged"], smooth=math.radians(40))
        bm = bmesh.new()
        for sx in (-1, 1):
            _lathe(bm, [(0.0, 0.0), (0.03 * w, 0.0), (0.036 * w, 0.02 * w), (0.024 * w, 0.045 * w), (0.0, 0.05 * w)], 16,
                   matrix=Matrix.Translation((sx * L / 2, 0, 0)) @ Matrix.Rotation(sx * math.pi / 2, 4, 'Y'))
        _mk(_nm("scroll.knobs"), bm, pc, ["jade_glow" if glow else "jade"], smooth=True, glow=1.5 if glow else None)
        bm = bmesh.new()
        _torus(bm, 0.052 * w, 0.006 * w, 24, 6, matrix=Matrix.Rotation(math.pi / 2, 4, 'Y'))
        _tube(bm, [(0.0, -0.05 * w, 0.0), (0.02 * w, -0.06 * w, -0.06 * w), (0.0, -0.055 * w, -0.14 * w)], 0.008 * w, 6, 4)
        _mk(_nm("scroll.tie"), bm, pc, ["cloth_teal"], smooth=True)


def floating_scroll(collection, width=1.2, open=True, glow=True, seed=0, name=None, parent=None,
                    location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Hand scroll (juan zhou), ``width`` m. open=True: a gently S-waving aged-paper sheet
    (0.36*width tall) between a thick left roller (the unread part) and a thin right roller, jade
    knobs, columns of classical script read right to left (glowing gold if glow, else ink) and a
    red seal stamp. open=False: a closed roll with jade end knobs and a teal silk tie.
    Origin at the centre, front -Y. Collection instance (seed % 3 variants)."""
    b, res = _bucket(width, 1.2)
    key = "scroll.%s.%d.%d.%d" % (_k(b), open, glow, seed % 3)
    pc = _proto(key, lambda pc: _build_scroll(pc, b, open, glow, seed % 3))
    return _place(pc, collection, name, "scroll", parent, location, rotation, tuple(res * c for c in _v3(scale)))


_BOOK_COVERS = ["banner_4", "cloth_teal", "props_cover_ochre", "props_cover_brown"]


def _build_books(pc, n, seed):
    r = U.rng(seed, "books")
    mats = ["paper_aged"] + _BOOK_COVERS + ["cloth_white", "ink"]
    bm = bmesh.new()
    z = 0.0
    for i in range(n):
        w, d = 0.18 + r.uniform(-0.01, 0.01), 0.26 + r.uniform(-0.012, 0.012)
        t = r.uniform(0.016, 0.028)
        m = Matrix.Translation((r.uniform(-0.012, 0.012), r.uniform(-0.012, 0.012), z)) @ \
            Matrix.Rotation(r.uniform(-0.14, 0.14), 4, 'Z')
        cov = 1 + r.randrange(len(_BOOK_COVERS))
        _box(bm, (w - 0.004, d - 0.004, t - 0.003), (0, 0, t / 2), matrix=m)
        for zz in (0.00075, t - 0.00075):
            _box(bm, (w, d, 0.0015), (0, 0, zz), matrix=m, mat=cov)
        for k in range(4):                                  # side stitching on the spine (+X edge)
            y = -d / 2 + d * (k + 0.5) / 4
            _box(bm, (0.026, 0.003, t + 0.0012), (w / 2 - 0.012, y, t / 2), matrix=m, mat=5)
        _box(bm, (0.032, 0.13, 0.0006), (-w / 2 + 0.03, 0.03, t + 0.0003), matrix=m, mat=5)
        for k in range(3):
            _box(bm, (0.012, 0.014, 0.0004), (-w / 2 + 0.03, 0.075 - k * 0.03, t + 0.0008), matrix=m, mat=6)
        z += t
    _mk(_nm("books"), bm, pc, mats, smooth=False, bevel=0.0012)


def book_stack(collection, n=4, seed=0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Stack of ``n`` thread-bound books (xian zhuang shu), 0.18 x 0.26 m each, 16-28 mm thick,
    indigo / teal / ochre / brown cloth covers, side stitching on the spine, white title slips with
    ink marks, each slightly rotated. Origin at the bottom centre. Collection instance (seed % 4)."""
    key = "books.%d.%d" % (n, seed % 4)
    pc = _proto(key, lambda pc: _build_books(pc, n, seed % 4))
    return _place(pc, collection, name, "books", parent, location, rotation, scale)


# ============================================================ furniture and small props

def _build_stone_table(pc, D, stools, material):
    bm = bmesh.new()
    R = D / 2
    _lathe(bm, [(0.0, 0.70), (R * 0.97, 0.70), (R, 0.715), (R, 0.765), (R * 0.98, 0.78), (0.0, 0.78)], 64)
    _lathe(bm, [(0.0, 0.0), (0.30 * D + 0.05, 0.0), (0.30 * D + 0.05, 0.05), (0.2 * D + 0.04, 0.09),
                (0.13 * D + 0.03, 0.16), (0.12 * D + 0.03, 0.30), (0.15 * D + 0.03, 0.42), (0.13 * D + 0.03, 0.55),
                (0.18 * D + 0.03, 0.66), (0.25 * D + 0.03, 0.70), (0.0, 0.70)], 32,
           rmod=lambda a, i, r, z: r * (1 + 0.05 * abs(math.cos(4 * a))) if i in (5, 6, 7) else r)
    for k in range(stools):
        a = math.pi / 4 + TAU * k / stools
        c = Vector(((R + 0.33) * math.cos(a), (R + 0.33) * math.sin(a), 0))
        _lathe(bm, [(0.0, 0.0), (0.15, 0.0), (0.17, 0.03), (0.205, 0.15), (0.21, 0.24), (0.205, 0.33), (0.17, 0.43),
                    (0.155, 0.45), (0.0, 0.45)], 28, matrix=Matrix.Translation(c))
        for zz, rr in ((0.07, 0.185), (0.39, 0.19)):
            for j in range(16):
                b = TAU * j / 16
                _sphere(bm, 0.014, (c.x + rr * math.cos(b), c.y + rr * math.sin(b), zz), 8, 4)
        for j in range(4):                                      # carved oval panels (raised rims)
            b = TAU * j / 4 + math.pi / 4
            _torus(bm, 0.06, 0.008, 16, 5, matrix=Matrix.Translation((c.x + 0.208 * math.cos(b), c.y + 0.208 * math.sin(b), 0.235))
                   @ Matrix.Rotation(b + math.pi / 2, 4, 'Z') @ ROT_XZ @ Matrix.Diagonal((0.75, 1.1, 1.0, 1.0)))
    _outward(bm)
    _mk(_nm("stone_table"), bm, pc, [material], smooth=math.radians(40))


def stone_table(collection, diameter=1.0, stools=4, material="marble_white", name=None, parent=None,
                location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Round stone garden table (0.78 m high, ``diameter`` m top on a carved vase pedestal) with
    ``stools`` drum stools (gu dun, 0.45 m, rows of studs, oval panels) around it. Origin at the
    ground centre. Collection instance."""
    key = "stone_table.%s.%d.%s" % (_k(diameter), stools, material)
    pc = _proto(key, lambda pc: _build_stone_table(pc, diameter, stools, material))
    return _place(pc, collection, name, "stone_table", parent, location, rotation, scale)


def _build_tea(pc):
    bm = bmesh.new()
    _box(bm, (0.42, 0.28, 0.012), (0, 0, 0.006))
    for (cx, cy, sx, sy) in ((0, -0.135, 0.42, 0.01), (0, 0.135, 0.42, 0.01), (-0.205, 0, 0.01, 0.28), (0.205, 0, 0.01, 0.28)):
        _box(bm, (sx, sy, 0.025), (cx, cy, 0.0125))
    _mk(_nm("tea.tray"), bm, pc, ["lacquer_black"], smooth=False, bevel=0.002)
    bm = bmesh.new()
    T = Matrix.Translation((-0.07, 0.02, 0.012))
    _lathe(bm, [(0.0, 0.0), (0.045, 0.0), (0.065, 0.02), (0.072, 0.045), (0.066, 0.07), (0.045, 0.085), (0.04, 0.09),
                (0.0, 0.09)], 32, matrix=T)
    _lathe(bm, [(0.0, 0.088), (0.043, 0.088), (0.04, 0.097), (0.02, 0.103), (0.012, 0.11), (0.016, 0.118), (0.0, 0.122)],
           24, matrix=T)
    _tube(bm, [(0.06, 0, 0.035), (0.09, 0, 0.05), (0.105, 0, 0.075), (0.112, 0, 0.088)], 0.011, 8, 4, matrix=T)
    _tube(bm, [(-0.06, 0, 0.07), (-0.095, 0, 0.075), (-0.105, 0, 0.05), (-0.09, 0, 0.025), (-0.065, 0, 0.022)],
          0.007, 6, 4, matrix=T)
    _mk(_nm("tea.pot"), bm, pc, ["props_zisha"], smooth=True)
    bm = bmesh.new()
    for k, (x, y) in enumerate(((0.06, -0.06), (0.12, -0.03), (0.12, 0.05), (0.06, 0.08))):
        _lathe(bm, [(0.0, 0.0), (0.016, 0.0), (0.017, 0.004), (0.026, 0.012), (0.033, 0.034), (0.03, 0.034),
                    (0.023, 0.014), (0.0, 0.008)], 20, matrix=Matrix.Translation((x, y, 0.012)))
    _mk(_nm("tea.cups"), bm, pc, ["ceramic_celadon"], smooth=True)


def tea_set(collection, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Tea set on a black lacquer tray (0.42 x 0.28 m): purple-clay (zisha) teapot with spout,
    loop handle and knobbed lid, four celadon cups. Origin at the tray's bottom centre (place it
    on a table top). Collection instance."""
    pc = _proto("tea_set", _build_tea)
    return _place(pc, collection, name, "tea_set", parent, location, rotation, scale)


def _build_cushion(pc, D, style, material):
    R = D / 2
    bm = bmesh.new()
    if style == "round":
        prof = [(0.0, 0.0), (R * 0.85, 0.0), (R * 0.97, 0.02)]
        for i in range(7):                                  # coiled side
            a = math.pi * i / 6
            prof.append((R * (0.97 + 0.03 * math.sin(a)) + 0.004 * math.sin(6 * a), 0.02 + 0.09 * i / 6))
        rr = R * 0.97
        while rr > 0.03:                                    # concentric coils on top
            prof.append((rr - 0.012, 0.118 + 0.004 * (rr / R)))
            prof.append((rr - 0.024, 0.112 + 0.004 * (rr / R)))
            rr -= 0.026
        prof.append((0.0, 0.12))
        _lathe(bm, prof, 64)
        _mk(_nm("cushion.round"), bm, pc, [material or "props_straw"], smooth=True)
    else:
        nu = 12

        def pt(u, v, top):
            x, y = u * R, v * R
            puff = (1 - u ** 4) * (1 - v ** 4)
            z = (0.12 + 0.05 * puff) if top else 0.0
            return Vector((x * (1 + 0.04 * puff), y * (1 + 0.04 * puff), z))
        tops = [[bm.verts.new(pt(-1 + 2 * i / nu, -1 + 2 * j / nu, True)) for i in range(nu + 1)] for j in range(nu + 1)]
        bots = [[bm.verts.new(pt(-1 + 2 * i / nu, -1 + 2 * j / nu, False)) for i in range(nu + 1)] for j in range(nu + 1)]
        for j in range(nu):
            for i in range(nu):
                bm.faces.new((tops[j][i], tops[j][i + 1], tops[j + 1][i + 1], tops[j + 1][i]))
                bm.faces.new((bots[j][i], bots[j + 1][i], bots[j + 1][i + 1], bots[j][i + 1]))
        ring_t = [tops[0][i] for i in range(nu)] + [tops[j][nu] for j in range(nu)] + \
                 [tops[nu][i] for i in range(nu, 0, -1)] + [tops[j][0] for j in range(nu, 0, -1)]
        ring_b = [bots[0][i] for i in range(nu)] + [bots[j][nu] for j in range(nu)] + \
                 [bots[nu][i] for i in range(nu, 0, -1)] + [bots[j][0] for j in range(nu, 0, -1)]
        m = len(ring_t)
        for i in range(m):
            bm.faces.new((ring_b[i], ring_b[(i + 1) % m], ring_t[(i + 1) % m], ring_t[i]))
        _outward(bm)
        _mk(_nm("cushion.square"), bm, pc, [material or "cloth_gold"], smooth=True)
        bm = bmesh.new()
        for sx in (-1, 1):
            for sy in (-1, 1):
                _tassel(bm, (sx * R * 1.02, sy * R * 1.02, 0.06), 0.09, 0.008, 0.018, 8)
        _mk(_nm("cushion.tassels"), bm, pc, ["cloth_red"], smooth=True)


def cushion(collection, diameter=0.6, style="round", material=None, name=None, parent=None,
            location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    """Meditation cushion. style 'round': woven straw pu tuan (``diameter`` m, 0.12 m high) with
    coiled sides and concentric coils on top. style 'square': puffed silk cushion (``diameter`` m
    square, default cloth_gold) with corner tassels. Origin at the ground centre. Instanced."""
    key = "cushion.%s.%s.%s" % (style, _k(diameter), material)
    pc = _proto(key, lambda pc: _build_cushion(pc, diameter, style, material))
    return _place(pc, collection, name, "cushion", parent, location, rotation, scale)


def _fish_outline(L):
    pts = []
    for i in range(13):
        t = i / 12
        x = -L / 2 + L * 0.8 * t
        h = L * 0.17 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.8
        pts.append((x, h))
    tail = [(L * 0.32, L * 0.03), (L * 0.5, L * 0.16), (L * 0.44, 0.0), (L * 0.5, -L * 0.16), (L * 0.32, -L * 0.03)]
    lower = [(x, -h) for x, h in pts[::-1]]
    return pts + tail + lower[1:-1]


def _build_chime(pc, s):
    S = Matrix.Diagonal((s, s, s, 1.0))
    bm = bmesh.new()
    _torus(bm, 0.02, 0.005, 12, 6, matrix=S @ Matrix.Translation((0, 0, -0.02)) @ ROT_XZ)
    _tube(bm, [(0, 0, -0.04), (0, 0, -0.10)], 0.004, 6, 1, matrix=S)
    _lathe(bm, [(0.0, -0.10), (0.03, -0.10), (0.05, -0.13), (0.06, -0.20), (0.075, -0.255), (0.066, -0.255),
                (0.05, -0.20), (0.04, -0.14), (0.0, -0.12)][::-1], 32,
           zmod=lambda a, i, r, z: z - (0.012 * abs(math.sin(2 * a)) if i in (3, 4) else 0.0), matrix=S)
    _tube(bm, [(0, 0, -0.12), (0, 0, -0.36)], 0.0025, 5, 1, matrix=S)
    vs = _prism(bm, _fish_outline(0.16), 0.004, y0=-0.002)
    _xf(bm, S @ Matrix.Translation((0, 0, -0.44)) @ Matrix.Rotation(-math.pi / 2, 4, 'Y'), vs)
    _mk(_nm("chime.bronze"), bm, pc, ["bronze_verdigris"], smooth=math.radians(40))
    bm = bmesh.new()
    _sphere(bm, 0.016, (0, 0, -0.30), 12, 6, matrix=S)
    _mk(_nm("chime.jade"), bm, pc, ["jade_glow"], smooth=True, glow=1.8)


def wind_chime(collection, size=1.0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Eave wind bell (feng duo): bronze bell with a lobed mouth, a clapper string with a jade bead
    and a fish-shaped wind plate, about 0.52*size m long. Origin at the hook (hangs below it).
    Collection instance."""
    b, res = _bucket(size, 1.0)
    pc = _proto("chime.%s" % _k(b), lambda pc: _build_chime(pc, b))
    return _place(pc, collection, name, "wind_chime", parent, location, rotation, res)


def _polearm(bm_shaft, bm_steel, bm_red, bm_gold, kind, x, lean, H=2.2):
    m = Matrix.Translation((x, 0.0, 0.10)) @ Matrix.Rotation(lean, 4, 'Y')
    _lathe(bm_shaft, [(0.0, 0.0), (0.016, 0.0), (0.014, H - 0.30), (0.0, H - 0.30)], 10, matrix=m)
    _lathe(bm_gold, [(0.0, -0.02), (0.02, -0.02), (0.018, 0.04), (0.0, 0.04)], 10, matrix=m)
    _lathe(bm_gold, [(0.0, H - 0.32), (0.02, H - 0.32), (0.022, H - 0.27), (0.0, H - 0.26)], 10, matrix=m)
    top = H - 0.27
    if kind == "spear":
        secs = [(top + 0.02 + 0.22 * t, _blade_section(0.07 * math.sin(math.pi * min(1, 0.12 + 0.88 * t)) ** 0.8 + 0.01, 0.01))
                for t in [i / 8 for i in range(9)]]
        vs = _loft(bm_steel, secs, tip=(0, 0, top + 0.28))
        _xf(bm_steel, m, vs)
        _tassel(bm_red, (0, 0, top - 0.01), 0.16, 0.02, 0.06, 14, head=False, matrix=m)
        return ("spear", m, top)
    if kind == "guandao":
        outline = [(-0.015, 0.0), (0.03, 0.0), (0.08, 0.12), (0.1, 0.30), (0.05, 0.48), (0.0, 0.52), (0.01, 0.40),
                   (0.0, 0.20), (-0.02, 0.10)]
        vs = _prism(bm_steel, [(x, z + top) for x, z in outline], 0.01, y0=-0.005)
        _xf(bm_steel, m, vs)
        return ("guandao", m, top)
    if kind == "ji":
        secs = [(top + 0.02 + 0.18 * t, _blade_section(0.05 * math.sin(math.pi * min(1, 0.12 + 0.88 * t)) ** 0.8 + 0.01, 0.01))
                for t in [i / 8 for i in range(9)]]
        vs = _loft(bm_steel, secs, tip=(0, 0, top + 0.24))
        _xf(bm_steel, m, vs)
        crescent = [(0.0, 0.0)]
        for i in range(13):
            a = -math.pi / 2 + math.pi * i / 12
            crescent.append((0.02 + 0.13 * math.cos(a), 0.06 + 0.11 * math.sin(a)))
        for i in range(12, -1, -1):
            a = -math.pi / 2 + math.pi * i / 12
            crescent.append((0.02 + 0.08 * math.cos(a), 0.06 + 0.07 * math.sin(a)))
        vs = _prism(bm_steel, [(x, z + top - 0.02) for x, z in crescent], 0.008, y0=-0.004)
        _xf(bm_steel, m, vs)
        return ("ji", m, top)
    if kind == "trident":
        for px, h in ((-0.06, 0.18), (0.0, 0.24), (0.06, 0.18)):
            secs = [(top + 0.05 + h * t, _blade_section(0.025 * (1 - 0.3 * t), 0.012)) for t in (0.0, 0.5, 1.0)]
            vs = _loft(bm_steel, secs, tip=(0, 0, top + 0.05 + h + 0.05))
            _xf(bm_steel, m @ Matrix.Translation((px, 0, 0)), vs)
        vs = _box(bm_steel, (0.15, 0.02, 0.03), (0, 0, top + 0.05))
        _xf(bm_steel, m, vs)
        return ("trident", m, top)
    return ("staff", m, top)


def _build_rack(pc, width, seed):
    r = U.rng(seed, "rack")
    bm = bmesh.new()
    for sx in (-1, 1):
        x = sx * width / 2
        _box(bm, (0.09, 0.09, 2.0), (x, 0, 1.0))
        _box(bm, (0.14, 0.55, 0.09), (x, 0, 0.045))
        for sy in (-1, 1):
            _tube(bm, [(x, sy * 0.25, 0.09), (x, sy * 0.05, 0.42)], 0.025, 4, 1)
        _sphere(bm, 0.06, (x, 0, 2.04), 10, 6, scale=(1, 1, 0.8))
    _box(bm, (width + 0.16, 0.08, 0.08), (0, 0, 1.86))
    _box(bm, (width + 0.06, 0.10, 0.07), (0, 0, 0.14))
    _box(bm, (width + 0.06, 0.05, 0.05), (0, 0, 1.0))
    _mk(_nm("rack.frame"), bm, pc, ["wood_dark"], smooth=False, bevel=0.008)
    bms = [bmesh.new() for _ in range(4)]
    kinds = ["spear", "guandao", "ji", "trident", "spear", "staff", "guandao", "ji"]
    n = max(2, int(width / 0.32))
    off = r.randrange(len(kinds))
    for i in range(n):
        x = -width / 2 + 0.2 + (width - 0.4) * i / max(1, n - 1)
        kind = kinds[(i + off) % len(kinds)]
        _polearm(bms[0], bms[1], bms[2], bms[3], kind, x, r.uniform(-0.04, 0.04))
    names = (("rack.shafts", "lacquer_red_worn"), ("rack.blades", "steel"), ("rack.tassels", "cloth_red"),
             ("rack.fittings", "gold"))
    for bmx, (nm_, mt) in zip(bms, names):
        if len(bmx.verts):
            _mk(_nm(nm_), bmx, pc, [mt], smooth=math.radians(35))
        else:
            bmx.free()


def weapon_rack(collection, width=2.0, seed=0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Rosewood weapon rack (bing qi jia), ``width`` m wide, 2.05 m tall, holding a row of polearms
    (spears with red horsehair tassels, guandao, ji halberds, tridents, staves) about 2.2 m tall.
    Origin at the ground centre, front -Y. Collection instance."""
    pc = _proto("rack.%s.%d" % (_k(width), seed % 4), lambda pc: _build_rack(pc, width, seed % 4))
    return _place(pc, collection, name, "weapon_rack", parent, location, rotation, 1.0)


def _build_anvil(pc, s):
    S = Matrix.Diagonal((s, s, s, 1.0))
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.36, 0.0), (0.33, 0.06), (0.30, 0.15), (0.30, 0.44), (0.0, 0.44)], 24,
           rmod=lambda a, i, r, z: r * (1 + 0.05 * math.sin(5 * a + i)), cap_end=False, matrix=S)
    _mk(_nm("anvil.stump"), bm, pc, ["bark_dark"], smooth=True)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.0), (0.298, 0.0), (0.0, 0.0)], 24, matrix=S @ Matrix.Translation((0, 0, 0.44)),
           rmod=lambda a, i, r, z: r * (1 + 0.05 * math.sin(5 * a + 4)))
    _mk(_nm("anvil.stump_top"), bm, pc, ["wood_light"], smooth=True)
    bm = bmesh.new()
    for z in (0.10, 0.36):
        _torus(bm, 0.305, 0.012, 32, 5, matrix=S @ Matrix.Translation((0, 0, z)))
    z0 = 0.44
    secs = []
    for i, (z, hx, hy) in enumerate(((0.0, 0.14, 0.11), (0.04, 0.12, 0.09), (0.09, 0.075, 0.07), (0.13, 0.08, 0.075),
                                     (0.17, 0.12, 0.095), (0.21, 0.13, 0.10))):
        secs.append((z0 + z, [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]))
    _loft(bm, secs)
    vs = _lathe(bm, [(0.075, 0.0), (0.0, 0.20)], 12)
    _xf(bm, Matrix.Translation((-0.13, 0, z0 + 0.17)) @ Matrix.Rotation(-math.pi / 2, 4, 'Y'),
        [v for ring in vs for v in ring])
    _box(bm, (0.06, 0.13, 0.04), (0.16, 0, z0 + 0.19))
    # hammer
    _box(bm, (0.05, 0.12, 0.05), (0.05, -0.03, z0 + 0.235), matrix=Matrix.Rotation(0.3, 4, 'Z'))
    _xf(bm, S, bm.verts[:])
    _outward(bm)
    _mk(_nm("anvil.iron"), bm, pc, ["iron"], smooth=math.radians(35), bevel=0.004 * s)
    bm = bmesh.new()
    _tube(bm, [(0.05, -0.03, 0.675), (0.12, 0.2, 0.68), (0.18, 0.38, 0.69)], 0.014, 8, 2,
          matrix=S @ Matrix.Rotation(0.3, 4, 'Z'))
    _mk(_nm("anvil.handle"), bm, pc, ["wood_light"], smooth=True)


def anvil(collection, size=1.0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Forge anvil: waisted iron block with a horn and a heel on an iron-banded tree stump, a
    hammer resting on the face; about 0.66*size m tall. Origin at the ground centre. Instanced."""
    b, res = _bucket(size, 1.0)
    pc = _proto("anvil.%s" % _k(b), lambda pc: _build_anvil(pc, b))
    return _place(pc, collection, name, "anvil", parent, location, rotation, res)


def _rock_chunk(bm, c, r, seed, m=None, sq=0.7):
    rr = U.rng(seed, "chunk")
    vs = _ico(bm, r, (0, 0, 0), 2)
    off = rr.uniform(0, 100)
    for v in vs:
        p = v.co.copy()
        n = U.fbm(p / max(r, 1e-6) + Vector((off, 0, 0)), 0.9, 3)
        k = 1.0 + 0.35 * n
        v.co = Vector((p.x * k, p.y * k * rr.uniform(0.85, 1.15), p.z * k * sq))
    rot = Euler((rr.uniform(-0.4, 0.4), rr.uniform(-0.4, 0.4), rr.uniform(0, TAU)), 'XYZ').to_matrix().to_4x4()
    mm = Matrix.Translation(c) @ rot
    if m is not None:
        mm = m @ mm
    _xf(bm, mm, vs)
    return vs


def _build_ore(pc, s, seed):
    r = U.rng(seed, "ore")
    bm = bmesh.new()
    bg = bmesh.new()
    R, H = 0.7 * s, 0.45 * s
    for i in range(34):
        a = r.uniform(0, TAU)
        rad = R * math.sqrt(r.random()) * 0.95
        h = H * max(0.0, 1 - (rad / R) ** 1.4)
        cr = s * r.uniform(0.07, 0.15)
        c = Vector((rad * math.cos(a), rad * math.sin(a), max(cr * 0.5, h - cr * 0.3)))
        _rock_chunk(bg if i % 9 == 4 else bm, c, cr, seed * 100 + i)
    _mk(_nm("ore.chunks"), bm, pc, ["props_ore"], smooth=False)
    _mk(_nm("ore.gold"), bg, pc, ["gold"], smooth=False)
    bm = bmesh.new()
    for i in range(7):
        a = r.uniform(0, TAU)
        rad = R * r.uniform(0.0, 0.6)
        h = H * max(0.0, 1 - (rad / R) ** 1.4)
        L = s * r.uniform(0.18, 0.34)
        w = s * r.uniform(0.035, 0.06)
        prof = [(w, 0.0), (w, L * 0.75), (0.0, L)]
        d = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1.0)).normalized()
        d = (d + Vector((r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0))).normalized()
        rings = _lathe(bm, [(0.0, 0.0)] + prof, 6)
        _xf(bm, Matrix.Translation((rad * math.cos(a), rad * math.sin(a), h * 0.7)) @ U.align_z(d).to_4x4(),
            [v for ring in rings for v in ring])
    _mk(_nm("ore.crystals"), bm, pc, ["jade_glow"], smooth=False, glow=2.4)


def ore_pile(collection, size=1.0, seed=0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Heap of dark iron ore chunks (about 1.4*size m across, 0.5*size m high) with a few gold-ore
    lumps and glowing jade spirit crystals poking out. Origin at the ground centre. Instanced."""
    b, res = _bucket(size, 1.0)
    pc = _proto("ore.%s.%d" % (_k(b), seed % 4), lambda pc: _build_ore(pc, b, seed % 4))
    return _place(pc, collection, name, "ore_pile", parent, location, rotation, res)


# ============================================================ crane and koi

def _feather(bm, base, direction, length, width, bend=0.0, up=(0, 0, 1), mat=0, n=5):
    """Tapered, slightly curved feather card from ``base`` along ``direction``."""
    d = Vector(direction).normalized()
    side = d.cross(Vector(up))
    if side.length < 1e-6:
        side = d.cross(Vector((1, 0, 0)))
    side.normalize()
    nrm = side.cross(d).normalized()
    L, R = [], []
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * min(1.0, 0.18 + 0.82 * t)) ** 0.6 * (1 - 0.55 * t)
        c = Vector(base) + d * (length * t) + nrm * (bend * length * t * t)
        L.append(bm.verts.new(c + side * w / 2))
        R.append(bm.verts.new(c - side * w / 2))
    made = L + R
    for i in range(n):
        f = bm.faces.new((L[i], R[i], R[i + 1], L[i + 1]))
        f.material_index = mat
    return made


def _crane_head(els, bm_parts, head, fwd, s=1.0):
    """Head (white), black face, red crown, bill; appended to element list / part bmeshes."""
    E = 'ELLIPSOID'
    hx, hy, hz = head
    fy, fz = fwd
    els.append(_mb(E, head, 0.048 * s, (0.85, 1.35, 0.85)))
    bw, bb, br, bh = bm_parts
    _sphere(br, 0.032 * s, (hx, hy + 0.005 * s, hz + 0.034 * s), 12, 6, scale=(0.9, 1.3, 0.45))
    _sphere(bb, 0.030 * s, (hx, hy - 0.035 * s, hz - 0.012 * s), 10, 6, scale=(0.95, 1.0, 1.0))
    for sx in (-1, 1):
        _sphere(bb, 0.008 * s, (hx + sx * 0.03 * s, hy - 0.03 * s, hz + 0.012 * s), 8, 4)
    _lathe(bh, [(0.0, 0.0), (0.016 * s, 0.0), (0.011 * s, 0.09 * s), (0.0, 0.17 * s)], 10,
           matrix=Matrix.Translation((hx, hy - 0.04 * s, hz - 0.01 * s)) @ U.align_z((0, fy, fz)).to_4x4())


def _build_crane(pc, s, pose):
    E = 'ELLIPSOID'
    bw, bb, br, bh, bl = (bmesh.new() for _ in range(5))
    S = Matrix.Diagonal((s, s, s, 1.0))
    if pose == "standing":
        els = [_mb(E, (0, 0.06, 0.98), 0.16, (1.0, 2.0, 1.0), Quaternion((1, 0, 0), -0.18)),
               _mb(E, (0, -0.10, 1.04), 0.11, (1.05, 1.2, 1.0)),
               _mb(E, (0, 0.20, 1.00), 0.12, (1.25, 1.4, 0.8))]
        # neck (black) as a tapered tube along an S curve, head
        neck = [(0, -0.17, 1.06, 1.0), (0, -0.25, 1.17, 0.85), (0, -0.245, 1.30, 0.72), (0, -0.205, 1.41, 0.65),
                (0, -0.225, 1.49, 0.62)]
        _tube(bb, neck, 0.046, 10, 5)
        _crane_head(els, (bw, bb, br, bh), (0, -0.25, 1.515), (-0.92, -0.38))
        me = _mb_mesh(els, 0.012)
        _smooth_mesh(me, 3, 0.5)
        bw.from_mesh(me)
        bpy.data.meshes.remove(me)
        # folded wings: layered white feathers along the flanks, black tertials drooping over the tail
        for sx in (-1, 1):
            for k in range(8):
                base = (sx * 0.145, -0.12 + 0.055 * k, 1.08 - 0.008 * k)
                _feather(bw, base, (sx * 0.10, 1.0, -0.25), 0.36, 0.13, bend=-0.05, up=(sx, 0, 0))
            for k in range(7):
                base = (sx * (0.02 + 0.03 * k), 0.26, 1.05 - 0.01 * k)
                _feather(bb, base, (sx * (0.15 + 0.35 * k / 6), 0.70, -0.70), 0.42 - 0.025 * k, 0.11, bend=0.25,
                         up=(0, 0, 1))
        for sx in (-1, 1):                                  # legs, backward-bending ankles, toes
            hip = Vector((sx * 0.055, 0.07, 0.90))
            ank = Vector((sx * 0.06, 0.11, 0.47))
            foot = Vector((sx * 0.06, 0.06, 0.02))
            _tube(bl, [tuple(hip), tuple(hip.lerp(ank, 0.5) + Vector((0, 0.01, 0))), tuple(ank)], 0.011, 6, 2)
            _sphere(bl, 0.016, tuple(ank), 8, 4)
            _tube(bl, [tuple(ank), tuple(foot)], 0.0095, 6, 2)
            for a in (-0.45, 0.0, 0.45):
                d = Vector((math.sin(a), -math.cos(a), -0.05)).normalized()
                _tube(bl, [tuple(foot), tuple(foot + d * 0.11)], 0.006, 5, 1)
            _tube(bl, [tuple(foot), tuple(foot + Vector((0, 0.05, 0.005)))], 0.005, 5, 1)
    else:
        els = [_mb(E, (0, 0.0, 0.0), 0.14, (0.9, 2.1, 0.9)), _mb(E, (0, -0.22, 0.02), 0.08, (0.9, 1.3, 0.95))]
        neck = [(0, -0.26, 0.03, 1.0), (0, -0.50, 0.06, 0.8), (0, -0.74, 0.08, 0.68), (0, -0.86, 0.085, 0.62)]
        _tube(bb, neck, 0.044, 10, 4)
        _crane_head(els, (bw, bb, br, bh), (0, -0.90, 0.09), (-1.0, -0.12))
        me = _mb_mesh(els, 0.012)
        _smooth_mesh(me, 3, 0.5)
        bw.from_mesh(me)
        bpy.data.meshes.remove(me)
        for sx in (-1, 1):                                  # spread wings with fingered primaries
            ns, nc = 9, 4
            grid = []
            for i in range(ns + 1):
                t = i / ns
                le = Vector((sx * (0.10 + 1.0 * t), -0.10 + 0.10 * t * t, 0.14 * t + 0.06 * math.sin(math.pi * t)))
                chord = 0.46 * (1 - 0.5 * t)
                row = []
                for j in range(nc + 1):
                    c = j / nc
                    p = le + Vector((0, chord * c, -0.02 * c + 0.035 * math.sin(math.pi * c) * (1 - t)))
                    row.append(p)
                grid.append(row)
            vg = [[bw.verts.new(p) for p in row] for row in grid]
            for i in range(ns):
                for j in range(nc):
                    bw.faces.new((vg[i][j], vg[i + 1][j], vg[i + 1][j + 1], vg[i][j + 1]))
            for i in range(12):                             # black secondaries along the inner trailing edge
                t = 0.02 + 0.05 * i
                fi = t * ns
                i0 = min(ns - 1, int(fi))
                le = grid[i0][nc].lerp(grid[i0 + 1][nc], fi - i0)
                _feather(bb, tuple(le + Vector((0, -0.05, 0.002))), (sx * 0.08, 1.0, -0.06), 0.24, 0.13, up=(0, 0, 1))
            for k in range(7):                              # primaries fanning from the hand
                a = math.radians(-8 + 9 * k)
                base = grid[ns][1] + Vector((0, 0.02 * k, 0))
                d = Vector((sx * math.cos(a), math.sin(a) + 0.25, 0.05))
                _feather(bw, tuple(base), tuple(d), 0.36 - 0.015 * k, 0.07, bend=-0.08, up=(0, 0, 1))
        for k in range(5):
            _feather(bw, (0.03 * (k - 2), 0.28, 0.02), (0.08 * (k - 2), 1.0, -0.12), 0.24, 0.07, up=(0, 0, 1))
        for sx in (-1, 1):
            hip = Vector((sx * 0.05, 0.20, -0.06))
            _tube(bl, [tuple(hip), (sx * 0.05, 0.55, -0.07), (sx * 0.045, 0.98, -0.06)], 0.01, 6, 2)
            foot = Vector((sx * 0.045, 0.98, -0.06))
            for a in (-0.3, 0.0, 0.3):
                _tube(bl, [tuple(foot), tuple(foot + Vector((math.sin(a) * 0.04, 0.10, -0.01)))], 0.006, 5, 1)
    for bmx, nm_, mt in ((bw, "crane.white", "props_feather_white"), (bb, "crane.black", "props_feather_black"),
                         (br, "crane.crown", "props_crane_crown"), (bh, "crane.bill", "props_horn"),
                         (bl, "crane.legs", "props_leg")):
        _xf(bmx, S, bmx.verts[:])
        _mk(_nm(nm_), bmx, pc, [mt], smooth=True)


def crane(collection, pose="standing", size=1.0, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Red-crowned crane (dan ding he), stylised: white body and wings, black neck and drooping black
    tertials, red crown, olive bill, long dark legs. pose 'standing': about 1.55*size m tall, facing
    -Y, origin between the feet. pose 'flying': neck stretched forward (-Y), legs trailing, wings
    spread about 2.6*size m with fingered primaries; origin at the body centre. Instanced."""
    if pose not in ("standing", "flying"):
        raise ValueError("crane pose must be 'standing' or 'flying'")
    b, res = _bucket(size, 1.0)
    pc = _proto("crane.%s.%s" % (pose, _k(b)), lambda pc: _build_crane(pc, b, pose))
    return _place(pc, collection, name, "crane_" + pose, parent, location, rotation, res)


def _build_koi(pc, L, seed):
    r = U.rng(seed, "koi")
    A = r.uniform(0.04, 0.10) * L * (1 if seed % 2 else -1)
    ph = r.uniform(-0.4, 0.4)
    n = 18
    secs = []
    spine = []
    for i in range(n + 1):
        t = i / n
        y = -L / 2 + L * t
        x = A * math.sin(math.pi * 1.1 * t + ph) * t
        if t < 0.22:
            prof = (t / 0.22) ** 0.45
        else:
            prof = max(0.22, 1.0 - ((t - 0.22) / 0.66) ** 1.5 * 0.78)
        h = 0.105 * L * prof
        w = h * 0.62
        spine.append((x, y))
        secs.append((x, y, w, h))
    bm = bmesh.new()
    rings = []
    for x, y, w, h in secs:
        ring = []
        for k in range(12):
            a = TAU * k / 12
            zz = math.sin(a) * h * (0.92 if math.sin(a) < 0 else 1.0)
            ring.append(bm.verts.new((x + math.cos(a) * w, y, zz)))
        rings.append(ring)
    for a_, b_ in zip(rings[:-1], rings[1:]):
        for k in range(12):
            k2 = (k + 1) % 12
            bm.faces.new((a_[k], a_[k2], b_[k2], b_[k]))
    tip = bm.verts.new((secs[0][0], secs[0][1] - 0.012 * L, 0.0))
    for k in range(12):
        bm.faces.new((rings[0][(k + 1) % 12], rings[0][k], tip))
    bm.faces.new(list(reversed(rings[-1])))
    _outward(bm)
    _mk(_nm("koi.body"), bm, pc, ["koi"], smooth=True)
    bm = bmesh.new()
    tx, ty = spine[-1]
    dx = spine[-1][0] - spine[-3][0]
    for sz in (-1, 1):                                       # forked tail fin (vertical)
        pts = [(tx, ty, 0.0), (tx + dx * 1.5 + 0.02 * L * sz, ty + 0.18 * L, sz * 0.11 * L),
               (tx + dx * 2.0, ty + 0.24 * L, sz * 0.16 * L), (tx + dx * 1.2, ty + 0.12 * L, sz * 0.03 * L)]
        v = [bm.verts.new(p) for p in pts]
        bm.faces.new(v)
    i0, i1 = int(n * 0.30), int(n * 0.70)                    # dorsal fin along the back
    top = [bm.verts.new((spine[i][0], spine[i][1], secs[i][3] * 0.95)) for i in range(i0, i1 + 1)]
    up = [bm.verts.new((spine[i][0], spine[i][1] + 0.02 * L, secs[i][3] + 0.05 * L * math.sin(math.pi * (i - i0) / (i1 - i0)) ** 0.6))
          for i in range(i0, i1 + 1)]
    for a_ in range(len(top) - 1):
        bm.faces.new((top[a_], top[a_ + 1], up[a_ + 1], up[a_]))
    ip = int(n * 0.24)
    for sx in (-1, 1):                                       # pectoral fins
        c = Vector((spine[ip][0] + sx * secs[ip][2] * 0.8, spine[ip][1], -secs[ip][3] * 0.4))
        pts = [c, c + Vector((sx * 0.10 * L, 0.06 * L, -0.05 * L)), c + Vector((sx * 0.07 * L, 0.12 * L, -0.03 * L)),
               c + Vector((0, 0.05 * L, 0))]
        bm.faces.new([bm.verts.new(p) for p in pts])
    _mk(_nm("koi.fins"), bm, pc, ["props_fin"], smooth=True)
    bm = bmesh.new()
    hx, hy = spine[2]
    for sx in (-1, 1):
        _sphere(bm, 0.012 * L, (hx + sx * secs[2][2] * 0.8, hy, secs[2][3] * 0.25), 8, 4)
        _tube(bm, [(hx + sx * 0.01 * L, -L / 2 + 0.005 * L, -0.02 * L), (hx + sx * 0.03 * L, -L / 2 - 0.02 * L, -0.04 * L)],
              0.003 * L, 4, 1)
    _mk(_nm("koi.eyes"), bm, pc, ["ink"], smooth=True)


def koi(collection, seed=0, length=0.5, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Koi carp, ``length`` m nose to tail, swimming toward -Y with a seeded S-bend: tapered body
    (koi pattern differs per instance), forked tail, dorsal and pectoral fins (translucent), eyes and
    barbels. Origin at the body centre (put it just below a water surface). Instanced (6 bends)."""
    pc = _proto("koi.%d" % (seed % 6), lambda pc: _build_koi(pc, 0.5, seed % 6))
    return _place(pc, collection, name, "koi", parent, location, rotation, length / 0.5)


# ============================================================ magic layer

def _sigil(bm, r, cx, cy, size, ang, width):
    """Procedural talisman sigil in a cell of ``size`` at (cx, cy) rotated by ``ang``."""
    m = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(ang, 4, 'Z')
    h = size / 2
    lw = width
    kind = r.randrange(5)
    strokes = []
    strokes.append(_arc_pts(h * 0.42, 0, TAU, 20))           # a ring in every sigil
    if kind == 0:
        strokes += [[(-h, 0), (h, 0)], [(0, -h), (0, h)]]
    elif kind == 1:
        strokes += [[(-h * 0.8, -h * 0.7), (0, h * 0.9), (h * 0.8, -h * 0.7), (-h * 0.8, -h * 0.7)]]
    elif kind == 2:
        strokes += [[(-h, -h * 0.5), (-h * 0.5, h * 0.5), (0, -h * 0.5), (h * 0.5, h * 0.5), (h, -h * 0.5)]]
    elif kind == 3:
        strokes += [[(0, -h), (0, h)], [(-h * 0.6, h * 0.6), (h * 0.6, h * 0.6)], [(-h * 0.6, -h * 0.6), (h * 0.6, -h * 0.6)]]
    else:
        strokes += [_arc_pts(h * 0.85, math.pi * 0.15, math.pi * 0.85, 10), _arc_pts(h * 0.85, math.pi * 1.15, math.pi * 1.85, 10)]
    for st in strokes:
        closed = len(st) > 3 and (Vector(st[0]) - Vector(st[-1])).length < 1e-6
        _ribbon(bm, st[:-1] if closed else st, lw, z=0.0, closed=closed, matrix=m)
    for k in range(r.randrange(1, 4)):                       # dots
        a = r.uniform(0, TAU)
        d = h * r.uniform(0.15, 0.3)
        _annulus(bm, 0.0, lw * 0.9, 8, 0.0, matrix=m @ Matrix.Translation((d * math.cos(a), d * math.sin(a), 0)))


def _build_rune_ring(radius, width, kind, seed):
    def build():
        bm = bmesh.new()
        r = U.rng(seed, "rune", kind)
        lw = max(0.012, 0.05 * width)
        r_in, r_out = radius - width / 2, radius + width / 2
        segs = max(64, int(TAU * radius / 0.08))
        _annulus(bm, r_out - lw, r_out, segs, 0.0)
        _annulus(bm, r_in, r_in + lw, segs, 0.0)
        circ = TAU * radius
        if kind == "trigram":
            n = 8 * max(1, int(round(circ / (8 * width * 2.4))))
            bar_t, gap = 0.13 * width, 0.07 * width
            bar_len = 0.55 * width
            for k in range(n):
                th = math.pi / 2 - TAU * k / n
                lines = TRIGRAMS[BAGUA_ORDER[k % 8]]
                for i, yang in enumerate(lines):
                    rr0 = radius - 1.5 * bar_t - gap + i * (bar_t + gap)
                    half = bar_len / 2 / radius
                    if yang:
                        _annulus(bm, rr0, rr0 + bar_t, 6, 0.0, th - half, th + half)
                    else:
                        g = 0.09 * width / radius
                        _annulus(bm, rr0, rr0 + bar_t, 3, 0.0, th - half, th - g)
                        _annulus(bm, rr0, rr0 + bar_t, 3, 0.0, th + g, th + half)
                tm = th - math.pi / n                         # diamond marker between trigrams
                c = Vector((radius * math.cos(tm), radius * math.sin(tm), 0))
                d = 0.07 * width
                v = [bm.verts.new(c + Vector(p)) for p in ((d, 0, 0), (0, d, 0), (-d, 0, 0), (0, -d, 0))]
                bm.faces.new(v)
                for rr in (r_in + 0.14 * width, r_out - 0.14 * width):
                    _annulus(bm, rr - lw * 0.4, rr + lw * 0.4, 4, 0.0, tm - 0.05 * width / radius, tm + 0.05 * width / radius)
        elif kind == "sigil":
            n = max(6, int(round(circ / (width * 1.6))))
            for k in range(n):
                th = TAU * k / n
                _sigil(bm, r, radius * math.cos(th), radius * math.sin(th), width * 0.62, th, lw)
                a0, a1 = th + width * 0.42 / radius, th + TAU / n - width * 0.42 / radius
                if a1 > a0:
                    _annulus(bm, radius - lw * 0.5, radius + lw * 0.5, max(2, int((a1 - a0) * radius / 0.1)), 0.0, a0, a1)
        else:
            text = CLASSICS[seed % len(CLASSICS)]
            n = max(8, int(round(circ / (width * 0.95))))
            k0 = r.randrange(len(text))
            res = 1 if width < 0.8 else 2
            for k in range(n):
                th = math.pi / 2 - TAU * k / n
                me = _text_mesh(text[(k0 + k) % len(text)], width * 0.62, res)
                m = Matrix.Translation((radius * math.cos(th), radius * math.sin(th), 0.0)) @ \
                    Matrix.Rotation(th - math.pi / 2, 4, 'Z')
                _add_mesh(bm, me, m)
        return bm
    return build


def rune_ring(collection, radius=5.0, width=0.6, kind="trigram", material="rune_cyan", seed=0, spin=0.0,
              groove=False, name=None, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Flat glowing rune circle on the ground (8 mm above the local origin plane), ``radius`` m to
    the centre of a band ``width`` m wide, framed by two thin rings. kind 'trigram': the eight bagua
    trigrams (yang solid, yin broken bars, bottom line innermost, Fu Xi order, qian at +Y) repeated
    around the ring with diamond markers; 'sigil': procedural talisman sigils linked by arcs;
    'script': classical characters standing outward around the circle. ``spin`` (rad/s) adds a
    frame driver that slowly rotates it; groove=True lays a dark engraved channel underneath.
    Mesh shared per parameter set. Returns the ring object."""
    if kind not in ("trigram", "sigil", "script"):
        raise ValueError("rune_ring kind must be 'trigram', 'sigil' or 'script'")
    key = "props.rune_ring.%s.%s.%s.%d.v%d" % (kind, _k(radius), _k(width), seed, _VERSION)
    me = U.shared_mesh(key, _build_rune_ring(radius, width, kind, seed))
    if not len(me.materials):
        U.set_materials(me, [material])
    ob = _obj(U.unique_name(name or PREFIX + ".rune_ring"), me, collection, parent=parent,
              location=Vector(location) + Vector((0, 0, 0.008)), rotation=rotation)
    U.set_object_material(ob, material, 0)
    U.set_visibility(ob, shadow=False)
    if groove:
        def gb():
            bm = bmesh.new()
            _annulus(bm, radius - width / 2 - 0.02, radius + width / 2 + 0.02, max(64, int(TAU * radius / 0.1)), 0.0)
            return bm
        gm = _mesh("props.rune_groove.%s.%s" % (_k(radius), _k(width)), gb, ["stone_dark"], smooth=False)
        _obj(U.unique_name(ob.name + ".groove"), gm, collection, parent=ob, location=(0, 0, -0.005))
    if spin:
        fc = ob.driver_add("rotation_euler", 2)
        fc.driver.type = 'SCRIPTED'
        z0 = float(ob.rotation_euler.z)
        fc.driver.expression = "%r + frame*%r" % (z0, spin / 24.0)
    return ob


def light_beam(collection, p0, p1, radius=0.1, material="props_beam_link", core=True, ends=True, name=None,
               parent=None):
    """Glowing beam of light from ``p0`` to ``p1`` (parent space): an additive cylinder whose
    silhouette and ends fade, with streaks flowing from p0 to p1, a brighter thin core and soft
    glowing nodes at both ends. Casts no shadow. Shared unit-length meshes scaled to the span.
    Returns the beam object (parent of core and end nodes)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = max(d.length, 1e-4)

    def cyl(rr):
        def b():
            bm = bmesh.new()
            _lathe(bm, [(rr, 0.0), (rr, 1.0)], 16, cap_start=False, cap_end=False)
            return bm
        return b
    me = _mesh("props.beam.%s.%s" % (_k(radius), material), cyl(radius), [material], smooth=True)
    rot = U.align_z(d).to_4x4()
    ob = U.object_from_mesh(U.unique_name(name or PREFIX + ".beam"), me, collection, parent=parent,
                            matrix=Matrix.Translation(p0) @ rot @ Matrix.Diagonal((1, 1, L, 1)))
    U.set_visibility(ob, shadow=False)
    if core:
        mc = _mesh("props.beam.%s.%s" % (_k(radius * 0.3), material), cyl(radius * 0.3), [material], smooth=True)
        c = U.object_from_mesh(U.unique_name(ob.name + ".core"), mc, collection, parent=ob)
        c["glow"] = 2.2
        U.set_visibility(c, shadow=False)
    if ends:
        def node():
            bm = bmesh.new()
            _ico(bm, radius * 1.6, subdiv=2)
            return bm
        mn = _mesh("props.beam_node.%s" % _k(radius), node, ["props_mote"], smooth=True)
        for z in (0.0, 1.0):
            n = U.object_from_mesh(U.unique_name(ob.name + ".node"), mn, collection, parent=ob,
                                   location=(0, 0, z), scale=(1, 1, 1.0 / L))
            U.set_visibility(n, shadow=False)
    return ob


def light_pillar(collection, height=40.0, radius=1.0, material="light_beam", name=None, parent=None,
                 location=(0, 0, 0)):
    """Vertical pillar of light rising ``height`` m from the origin: an additive outer column that
    fades upward, a brighter core, a radial glow pool on the ground and three floating halo rings.
    Casts no shadow. Returns the root Empty."""
    root = _root(collection, name, "light_pillar", parent, location, (0, 0, 0))
    pn = root.name

    def col(rr, segs):
        def b():
            bm = bmesh.new()
            _lathe(bm, [(rr, 0.0), (rr * 0.85, 1.0)], segs, cap_start=False, cap_end=False)
            return bm
        return b
    outer = _mesh("props.pillar.%s.%s" % (_k(radius), material), col(radius, 32), [material], smooth=True)
    o = _obj(U.unique_name(pn + ".column"), outer, collection, parent=root, scale=(1, 1, height))
    inner = _mesh("props.pillar.%s.%s" % (_k(radius * 0.3), material), col(radius * 0.3, 16), [material], smooth=True)
    c = _obj(U.unique_name(pn + ".core"), inner, collection, parent=root, scale=(1, 1, height), glow=1.3)

    def disc():
        bm = bmesh.new()
        _lathe(bm, [(0.0, 0.0), (radius * 3.5, 0.0)], 48, cap_start=False, cap_end=False)
        return bm
    fl = _mesh("props.pillar_pool.%s" % _k(radius), disc, ["props_flare"], smooth=False)
    f = _obj(U.unique_name(pn + ".pool"), fl, collection, parent=root, location=(0, 0, 0.02))
    rings = []
    for i, (zf, rf) in enumerate(((0.12, 2.2), (0.26, 1.8), (0.42, 1.45))):
        def ring(rf=rf):
            bm = bmesh.new()
            _torus(bm, radius * rf, radius * 0.04, 64, 6)
            return bm
        rm = _mesh("props.pillar_halo.%s.%d" % (_k(radius), i), ring, ["rune_cyan"], smooth=True)
        rings.append(_obj(U.unique_name(pn + ".halo"), rm, collection, parent=root, location=(0, 0, height * zf)))
    for ob in [o, c, f] + rings:
        U.set_visibility(ob, shadow=False)
    return root


def spirit_motes(collection, count=200, bounds=((-5, -5, 0.5), (5, 5, 5)), seed=0, size=0.04,
                 material="props_mote", drift=0.25, rise=0.0, name=None, parent=None):
    """``count`` tiny glowing spirit motes scattered (seeded) inside ``bounds`` (min, max corners
    in parent space), sizes 0.4-1.0 x ``size`` m, instanced by geometry nodes on one point cloud.
    They drift gently with scene time (``drift`` m wobble); ``rise`` m/s makes them float upward
    and wrap within the box height. Returns the instancer object."""
    r = U.rng(seed, "motes")
    lo, hi = Vector(bounds[0]), Vector(bounds[1])
    pts = [Vector((r.uniform(lo.x, hi.x), r.uniform(lo.y, hi.y), r.uniform(lo.z, hi.z))) for _ in range(count)]
    scl = [size * r.uniform(0.4, 1.0) for _ in range(count)]
    ph = [r.random() for _ in range(count)]

    def build(pc):
        bm = bmesh.new()
        _ico(bm, 1.0, subdiv=2)
        _mk(_nm("mote"), bm, pc, [material], smooth=True, glow=1.0)
    proto = _proto_object("pt.mote.%s" % material, build)
    drift_d = dict(rise=rise, height=max(0.1, hi.z - lo.z), wobble=drift, speed=0.15)
    ob = _point_instancer(U.unique_name(name or PREFIX + ".motes"), collection, proto, pts, None, scl, ph,
                          parent=parent, drift=drift_d)
    U.set_visibility(ob, shadow=False)
    return ob


def shield_dome(collection, radius=30.0, height=None, material="glass_shield", ring=True, name=None,
                parent=None, location=(0, 0, 0)):
    """Faint protective formation dome: a hemisphere ``radius`` m wide and ``height`` m tall
    (default = radius) in glass_shield (fresnel rim glow, energy cells, additive, no shadow), with a
    glowing ring where it meets the ground. Returns the dome object."""
    H = radius if height is None else height

    def b():
        bm = bmesh.new()
        prof = [(radius * math.cos(math.pi / 2 * i / 20), H * math.sin(math.pi / 2 * i / 20)) for i in range(21)]
        prof[-1] = (0.0, H)
        _lathe(bm, prof, 96, cap_start=False, cap_end=False)
        return bm
    me = _mesh("props.dome.%s.%s.%s" % (_k(radius), _k(H), material), b, [material], smooth=True)
    ob = _obj(U.unique_name(name or PREFIX + ".shield_dome"), me, collection, parent=parent, location=location)
    U.set_visibility(ob, shadow=False)
    if ring:
        def rb():
            bm = bmesh.new()
            _annulus(bm, radius - max(0.05, radius * 0.006), radius, 128, 0.0)
            return bm
        rm = _mesh("props.dome_ring.%s" % _k(radius), rb, ["rune_cyan"], smooth=False)
        rr = _obj(U.unique_name(ob.name + ".ring"), rm, collection, parent=ob, location=(0, 0, 0.01))
        U.set_visibility(rr, shadow=False)
    return ob


# ============================================================ showcase

def _frame_posts(collection, root, nm, x0, x1, y, h, material="lacquer_red"):
    """Two lacquered posts with a beam on top (display frame for plaques, lanterns, tablets)."""
    bm = bmesh.new()
    for x in (x0, x1):
        _sq_lathe(bm, [(0, 0), (0.30, 0), (0.30, 0.25), (0.24, 0.30), (0, 0.30)], matrix=Matrix.Translation((x, y, 0)))
        _lathe(bm, [(0, 0.30), (0.17, 0.30), (0.16, h), (0, h)], 16, matrix=Matrix.Translation((x, y, 0)))
    _box(bm, (abs(x1 - x0) + 0.9, 0.28, 0.32), ((x0 + x1) / 2, y, h + 0.16))
    _outward(bm)
    _mk(U.unique_name(nm), bm, collection, [material], parent=root, smooth=math.radians(40), bevel=0.02)
    bm = bmesh.new()
    for x in (x0 - 0.45, x1 + 0.45):
        _box(bm, (0.06, 0.32, 0.36), (x, y, h + 0.16))
    _mk(U.unique_name(nm + ".caps"), bm, collection, ["gold"], parent=root, smooth=False, bevel=0.01)


def showcase(collection):
    """Display court for review renders: every prop, laid out readably on a marble floor.
    Centre: lit ding with the 15 artifacts orbiting over three rune rings and spirit motes. Back:
    stele on its bixi turtle, a second stele, plaque frames (horizontal 月华宗, vertical 藏经阁)
    with palace and round lanterns, a light pillar linked by light beams. Left: five banners, the
    bamboo-slip scroll, floating scrolls, jade tablets and a wind chime on a frame, forge corner
    (square ding, anvil, ore, weapon rack). Right: cranes, a koi basin, chain and rope between
    posts, bell and drum. Front: guardian lions, stone lanterns, incense burner, a tea corner
    under a shield dome. Returns the root Empty."""
    c = collection
    root = U.empty("props.showcase", c, display_size=2.0)
    P = lambda *parts: "props.show." + ".".join(str(p) for p in parts)
    bm = bmesh.new()
    # concentric rings, no long thin centre fan (EEVEE bump shading streaks on sliver triangles)
    top = [(17.5 - 1.25 * i, 0.0) for i in range(14)] + [(0.0, 0.0)]
    _lathe(bm, [(0.0, -0.40), (17.5, -0.40)] + top, 128)
    _mk(P("floor"), bm, c, ["marble_paving"], parent=root, smooth=False)
    bm = bmesh.new()
    _lathe(bm, [(0.0, -0.40), (17.8, -0.40), (17.8, 0.06), (17.5, 0.08), (17.45, 0.0), (0.0, 0.0)], 128,
           cap_end=False)
    _mk(P("kerb"), bm, c, ["marble_white"], parent=root, smooth=False)
    # ---- centre: ding, rune rings, artifact ring, motes
    cauldron_ding(c, 2.6, lit=True, legs=3, name=P("ding"), parent=root)
    rune_ring(c, 3.0, 0.5, "trigram", name=P("ring_trigram"), parent=root)
    rune_ring(c, 4.0, 0.55, "sigil", seed=1, name=P("ring_sigil"), parent=root)
    rune_ring(c, 5.1, 0.6, "script", seed=2, spin=0.03, name=P("ring_script"), parent=root)
    for i, kind in enumerate(ARTIFACT_KINDS):
        a = -math.pi / 2 + TAU * i / len(ARTIFACT_KINDS)
        artifact(c, kind, 0.95, name=P("art", kind), parent=root,
                 location=(3.8 * math.cos(a), 3.8 * math.sin(a), 2.7 + 0.25 * math.sin(3 * a)),
                 rotation=(0, 0, a + math.pi / 2))
    spirit_motes(c, 140, ((-6, -6, 0.6), (6, 6, 5.5)), seed=4, name=P("motes"), parent=root)
    # ---- back: steles, plaques, lanterns, light pillar and beams
    stele(c, 4.0, "rune_cyan", True, seed=0, name=P("stele"), parent=root, location=(0, 10.0, 0))
    stele(c, 3.0, "rune_gold", False, seed=2, name=P("stele2"), parent=root, location=(4.2, 10.5, 0))
    _frame_posts(c, root, P("frame_l"), -9.0, -4.0, 8.5, 5.4)
    plaque(c, "月华宗", 3.2, name=P("plaque_h"), parent=root, location=(-6.5, 8.28, 4.55))
    _frame_posts(c, root, P("frame_r"), 6.4, 9.6, 8.5, 5.4)
    plaque(c, "藏经阁", 1.1, vertical=True, name=P("plaque_v"), parent=root, location=(8.0, 8.28, 3.55))
    for x, st in ((-9.0, "palace"), (-4.0, "palace"), (6.4, "round"), (9.6, "round")):
        lantern_hanging(c, st, 0.9, cord=0.35, name=P("lantern", st), parent=root, location=(x, 8.2, 5.4))
    light_pillar(c, 26.0, 0.7, name=P("pillar"), parent=root, location=(0, 14.5, 0))
    light_beam(c, (0, 14.5, 7.0), (-6.5, 8.5, 5.9), 0.06, name=P("beam_l"), parent=root)
    light_beam(c, (0, 14.5, 7.0), (8.0, 8.5, 5.9), 0.06, name=P("beam_r"), parent=root)
    # ---- left: banners, slips, scrolls, tablets, chime, forge corner
    for i in range(5):
        banner(c, 6.5, 1.0, material=i, seed=i, name=P("banner", i), parent=root,
               location=(-13.5, -6.0 + 3.0 * i, 0), rotation=(0, 0, -math.pi / 2 + 0.25))
    bamboo_slip_scroll(c, 4.2, 1.7, 0.18, seed=1, name=P("slips"), parent=root, location=(-7.5, 3.0, 2.4),
                       rotation=(0, 0, 0.35))
    floating_scroll(c, 1.3, True, seed=1, name=P("scroll_open"), parent=root, location=(-4.6, 5.6, 2.9),
                    rotation=(0, 0, 0.2))
    floating_scroll(c, 1.1, False, name=P("scroll_closed"), parent=root, location=(-4.1, 5.4, 2.1),
                    rotation=(0.2, 0, 0.6))
    _frame_posts(c, root, P("frame_tab"), -10.5, -7.0, -4.0, 3.2, material="wood_dark")
    for i, x in enumerate((-9.9, -9.0, -8.1)):
        jade_tablet(c, 0.6, seed=i, cord=0.45, name=P("tablet", i), parent=root, location=(x, -4.16, 3.2))
    wind_chime(c, 1.2, name=P("chime"), parent=root, location=(-7.4, -4.16, 3.2))
    cauldron_ding(c, 1.4, lit=False, legs=4, name=P("ding4"), parent=root, location=(-6.0, -6.6, 0),
                  rotation=(0, 0, 0.3))
    anvil(c, 1.0, name=P("anvil"), parent=root, location=(-9.4, -8.6, 0), rotation=(0, 0, 0.5))
    ore_pile(c, 1.0, seed=1, name=P("ore"), parent=root, location=(-11.4, -7.6, 0))
    weapon_rack(c, 2.2, name=P("rack"), parent=root, location=(-10.5, -10.8, 0), rotation=(0, 0, 0.35))
    # ---- right: cranes, koi basin, chain & rope, bell, drum
    crane(c, "standing", 1.0, name=P("crane"), parent=root, location=(8.6, -2.6, 0), rotation=(0, 0, 0.9))
    crane(c, "flying", 1.2, name=P("crane_flying"), parent=root, location=(5.5, 2.5, 8.0), rotation=(0.05, -0.15, -0.5))
    bm = bmesh.new()
    _lathe(bm, [(1.55, 0.0), (1.85, 0.0), (1.85, 0.45), (1.75, 0.5), (1.55, 0.5), (1.55, 0.0)], 64,
           cap_start=False, cap_end=False)
    _mk(P("basin"), bm, c, ["marble_white"], parent=root, smooth=False, location=(12.0, -5.0, 0), bevel=0.02)
    bm = bmesh.new()
    _lathe(bm, [(0.0, 0.36), (1.56, 0.36)], 64, cap_start=False, cap_end=False)
    _mk(P("water"), bm, c, ["water_pond"], parent=root, smooth=False, location=(12.0, -5.0, 0))
    for i in range(5):
        a = TAU * i / 5 + 0.3
        koi(c, seed=i, length=0.5, name=P("koi", i), parent=root,
            location=(12.0 + 0.85 * math.cos(a), -5.0 + 0.85 * math.sin(a), 0.27), rotation=(0, 0, a + 0.4))
    bm = bmesh.new()
    for x in (10.4, 14.6):
        _sq_lathe(bm, [(0, 0), (0.22, 0), (0.22, 2.6), (0.18, 2.7), (0.12, 2.75), (0, 2.75)],
                  matrix=Matrix.Translation((x, 2.5, 0)))
    _mk(P("chain_posts"), bm, c, ["stone_grey"], parent=root, smooth=False, bevel=0.015)
    chain(c, (10.6, 2.5, 2.45), (14.4, 2.5, 2.45), 0.26, 0.55, name=P("chain"), parent=root)
    rope(c, (10.6, 2.5, 1.7), (14.4, 2.5, 1.7), 0.35, 0.035, name=P("rope"), parent=root)
    bell(c, 1.5, frame=True, name=P("bell"), parent=root, location=(13.2, 7.5, 0), rotation=(0, 0, -0.35))
    drum(c, 1.2, name=P("drum"), parent=root, location=(10.6, 6.2, 0), rotation=(0, 0, -0.3))
    # ---- front: lions, stone lanterns, incense, tea corner under a dome
    guardian_lion(c, 1.0, False, name=P("lion_m"), parent=root, location=(-3.4, -9.2, 0))
    guardian_lion(c, 1.0, True, name=P("lion_f"), parent=root, location=(3.4, -9.2, 0))
    for x in (-5.8, 5.8):
        lantern_stone(c, 2.4, name=P("stone_lantern", x), parent=root, location=(x, -9.2, 0))
    incense_burner(c, 1.1, name=P("incense"), parent=root, location=(0, -7.6, 0))
    stone_table(c, 1.0, 4, name=P("table"), parent=root, location=(8.8, -9.2, 0))
    tea_set(c, name=P("tea"), parent=root, location=(8.75, -9.25, 0.78), rotation=(0, 0, 0.3))
    book_stack(c, 3, seed=2, name=P("books"), parent=root, location=(9.05, -8.85, 0.78), rotation=(0, 0, -0.2))
    cushion(c, 0.6, "round", name=P("cushion_r"), parent=root, location=(10.9, -10.4, 0))
    cushion(c, 0.55, "square", name=P("cushion_s"), parent=root, location=(6.9, -10.6, 0), rotation=(0, 0, 0.3))
    shield_dome(c, 2.9, 2.4, name=P("dome"), parent=root, location=(8.8, -9.2, 0))
    sword(c, 1.0, "jian", name=P("sword_jian"), parent=root, location=(5.4, -6.0, 1.3), rotation=(0, 0.25, 0.4))
    sword(c, 1.0, "dao", name=P("sword_dao"), parent=root, location=(6.0, -6.2, 1.3), rotation=(0, -0.2, 0.4))
    return root


showcase.preview_cameras = [
    ("overview", (-21.0, -27.0, 15.5), (0.0, -0.5, 1.5), 32),
    ("front", (0.0, -29.0, 4.5), (0.0, 0.0, 3.2), 35),
    ("center", (0.0, -10.8, 3.6), (0.0, 0.0, 2.4), 35),
    ("back", (-2.0, -0.5, 3.4), (0.5, 9.5, 3.6), 35),
    ("left", (-4.5, -7.5, 3.2), (-10.5, 1.5, 2.6), 35),
    ("right", (4.0, -9.0, 3.8), (11.5, 1.5, 2.2), 35),
    ("lions", (0.0, -18.0, 2.6), (0.0, -8.8, 1.5), 32),
    ("corner", (5.8, -14.2, 2.4), (8.8, -9.0, 0.9), 40),
    ("aerial", (0.0, -9.0, 17.0), (0.0, 0.5, 0.0), 35),
]


def closeups(collection):
    """Review target with close cameras: the 15 artifacts in two rows, plaques of 2, 3 and 4
    characters (one vertical, one right to left), a stele crown, a lion head, lanterns. Use with
    look.py --target sect.lib.props:closeups."""
    c = collection
    root = U.empty("props.closeups", c, display_size=1.0)
    bm = bmesh.new()
    top = [(14.0 - 1.0 * i, 0.0) for i in range(14)] + [(0.0, 0.0)]
    _lathe(bm, [(0.0, -0.40), (14.0, -0.40)] + top, 96)
    _mk("props.close.floor", bm, c, ["marble_paving"], parent=root, smooth=False)
    for i, kind in enumerate(ARTIFACT_KINDS):
        row, k = divmod(i, 8)
        artifact(c, kind, 0.9, name="props.close.art.%s" % kind, parent=root,
                 location=((k - 3.5) * 1.2 + 0.6 * row, -2.0 + 1.4 * row, 2.4 - 1.15 * row))
    _frame_posts(c, root, "props.close.frame", -4.5, 4.5, 3.0, 5.0)
    plaque(c, "洞府", 1.9, name="props.close.plaque2", parent=root, location=(-3.0, 2.78, 4.25))
    plaque(c, "护宗大阵", 3.0, rtl=True, name="props.close.plaque4", parent=root, location=(0.6, 2.78, 4.25))
    plaque(c, "心镜台", 0.95, vertical=True, name="props.close.plaque_v", parent=root, location=(3.6, 2.78, 3.35))
    lantern_hanging(c, "palace", 0.8, cord=0.3, name="props.close.lantern_p", parent=root, location=(-4.5, 2.8, 5.0))
    lantern_hanging(c, "round", 0.8, cord=0.3, name="props.close.lantern_r", parent=root, location=(4.5, 2.8, 5.0))
    stele(c, 4.0, "rune_cyan", True, seed=3, name="props.close.stele", parent=root, location=(8.5, 3.0, 0))
    guardian_lion(c, 1.0, False, name="props.close.lion", parent=root, location=(-8.0, 1.0, 0))
    return root


closeups.preview_cameras = [
    ("artifacts", (0.3, -8.6, 2.2), (0.3, -1.0, 1.9), 40),
    ("arts_left", (-2.4, -5.6, 2.1), (-2.4, -1.0, 1.9), 40),
    ("arts_right", (2.6, -5.6, 2.1), (2.6, -1.0, 1.9), 40),
    ("plaques", (0.0, -6.5, 4.2), (0.0, 3.0, 4.1), 35),
    ("stele_crown", (8.5, -1.8, 3.9), (8.5, 3.0, 3.7), 40),
    ("lion_head", (-7.6, -1.6, 2.1), (-8.0, 1.0, 1.9), 45),
]
