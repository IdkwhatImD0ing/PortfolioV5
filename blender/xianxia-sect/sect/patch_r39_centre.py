"""Round 39, lane 'centre': the Jin Yong references at the Stele Forest, the Jade Slip Pavilion and Ice-Fire Island get
the r31 plan's staging (as approved by the owner, 2026-10-23, without the cards' "why it is here" lines), in an existing
out/sect_chase.blend, so it matches what a fresh build of areas/steles.py, scroll.py and scenery.py (with
sect/lib/refs_centre.py and props.JIN_YONG_MANUALS) makes. Run on the cloud box, on a copy first, AFTER
patch_r28_lions.py, patch_r29_forge.py, patch_r34_west.py and patch_r34_east.py, and BEFORE patch_r36_icefire.py:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/<copy>.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r39_centre.py [-- DRY_RUN=1] [SCAN=0]

What it does:
- steles (hold 974): every stele carves the manual steles.STELE_MANUALS / MASTER_MANUAL give it now: each row's front
  stele (west, inner) a manual that fits the row's skill (voice-first 獅子吼 and 清心普善咒 on both inner steles, agents
  吸星大法, latency 天羅地網勢, a human in the loop 玉女心經, when the model is wrong 乾坤大挪移); 天罡北斗陣 (the Mission
  Hall's now), 劍塚 (the Jade Slip Pavilion's) and the master stele's 華山論劍 (the arena's) are gone; the master stele
  carves 獨孤九劍 with 只要有招 便有破綻 at its foot. Each stele's prototype ('props.stele.*', one per stele) gets the
  slab, key-fret border, crown and glyph meshes of a fresh props stele build for its new manual (cut the round-12 way:
  the glyphs fill holes in the slab and crown, so nothing tears or flickers); the turtle stays. Every stele instance
  gets obj['manual'] = its title (export_web LORE_WHEN waits for the master's). The Ming Sect's six Holy Flame Tokens
  come in at the head of the agents row, halved, on a waist-high stand: 'steles.tokens' (refs_centre.steles_tokens)
  under 'steles.stele.r1', the row's front stele, so hotspot skills:1 hosts them.
- scroll (1103): the tokens' old stand on the terrace ('scroll.slip_stack' and its four meshes) goes. Dugu Qiubai's
  Sword Tomb comes in on the lawn right of the pavilion: 'scroll.sword_tomb' (refs_centre.sword_tomb: a boulder with 劍塚
  cut into its dressed face, a bluestone slab with the keen sword, a stone strip, the heavy sword's empty place and the
  wooden sword).
- library (772): Ice-Fire Island 'scenery.island.009' and its companions (its waterfall) turn scenery.ICEFIRE_TURN deg
  about the island's own vertical and drop scenery.ICEFIRE_DROP m (scenery.turn_icefire), so its fire half faces the
  hold and it sits whole in the sky there. patch_r36_icefire.py, run after this one, rebuilds the island's look in its
  turned place (it was rehearsed on exactly this turn: PATCH DIGEST afdfacc4fcba30a1453f4363a49a48c6).

State: each part is 'old' (the round-34 file), 'r39' (exactly this build: meshes compared face by face, order-free,
with a scratch build of the same code) or 'stale' (round 39's objects there but not this build: rebuilt). Anything else
stops the patch. Idempotent: on this build's file it prints 'PATCH nothing changed: not saving' and the same DIGEST.

Checks (any failure stops the patch before saving; DRY_RUN=1 runs everything and never saves):
- glyphs: every character carved (manuals, 劍塚) has faces in KaiTi and is not the font's missing-glyph shape;
- carved: every re-carved prototype's slab, crown and glyphs carry the round-12 'cut' tag, and their meshes are the
  fresh build's; every stele carries its manual;
- grounded: the tokens' plinth foot on the stele field (sunk 0-8 cm); the tomb's slab and boulder feet under the lawn;
  the swords and the strip on their mortises' floors;
- clear: nothing but the floor they stand on comes within CLEAR_MIN of the tokens or the tomb;
- reading: each hold as the site frames it (1600 x 900): the tokens, the master stele and the tomb wholly in frame, at
  least READ_SEEN of them unhidden, none under the stop's panel or the page's buttons; the island in frame at 772; the
  characters' and glyph cells' sizes are logged;
- flight: chase.cam never comes nearer than CAM_MIN to the tokens or the tomb;
- hotspots and lore: of the steles, scroll and library click boxes only skills:1 grows (the tokens); export_web's
  LORE finds holy-fire-tokens (hosted by skills:1), dugu-nine-swords (by the steles label) and sword-tomb (its own
  card);
- coplanar scan (SCAN=1): parallel same-facing faces within 5 mm and 5-12 mm of the tokens (no more than the old
  stand's) and the tomb (at most NEW_MAX m2);
- names and counts: objects change by exactly what was removed and added; no scratch data or scene left.
Prints 'PATCH CACHES needs audit' and 'PATCH DIGEST <md5>' of everything the round touches (the steles' prototype
meshes and manuals, the tokens, the tomb, the island's and its waterfall's placement; not the island's own meshes,
which patch_r36_icefire.py rebuilds).
"""
import hashlib
import math
import os
import re
import sys
import time
import zlib

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect import scenery as SN  # noqa: E402
from sect.areas import forge as F  # noqa: E402
from sect.areas import scroll as SC  # noqa: E402
from sect.areas import steles as ST  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import refs_centre as RC  # noqa: E402
from sect.lib import util as U  # noqa: E402

SCRATCH = "~r39c"
RES = (1600, 900)
CLEAR_MIN = 0.02           # m
CAM_MIN = 4.0              # m: chase.cam from the tokens or the tomb
READ_SEEN = 0.9            # share of an item's points a ray from the hold camera reaches
TOKEN_SINK = (0.0, 0.08)   # m: the tokens' plinth foot this far under the field's top
TOMB_SINK = (0.05, 1.3)    # m: the tomb's slab and boulder feet under the lawn
MORTISE_TOL = 0.03         # m: a sword's or the strip's lowest point from its mortise floor
SCAN_TOL, SCAN_TOL12, SCAN_PAR = 0.0055, 0.0125, 0.985
SCAN_STEP = 0.05           # m between samples
NEW_MAX = 0.02             # m2 of same-facing parallel faces (both bands) the tomb may have against anything
SKIP = ("world.haze", "world.range", "world.roots", "world.stream", "world.cloud")
SEE_THROUGH = ("world.haze", "world.cloud", "world.mist", "world.fog")
MISSING_REF = "\u0e01"     # Thai ko kai: not in KaiTi, so Blender draws the font's missing-glyph shape
HOLDS = dict(library=772, steles=974, scroll=1103)
FRAMING = {1103: SC.SITE_FRAMING}               # hold frame -> (yaw deg, pitch deg, back frames): framing.ts
# the page's panels and buttons at 1600 x 900 (px: x0, y0, x1, y1), measured on the r31 audit's hold shots and r33's
# jade-slip framing: nothing new may sit under them
UI_RECTS = dict(library=(("panel", (1188, 82, 1487, 314)),), steles=(("panel", (1057, 82, 1487, 363)),),
                scroll=(("panel", (1137, 82, 1487, 278)),))
UI_COMMON = (("voice", (1500, 800, 1580, 880)), ("header", (20, 15, 378, 95)), ("map", (1485, 15, 1577, 110)),
             ("dots", (1560, 280, 1582, 620)))
# the round-34 file: the manuals the steles carried (STELE_MANUALS / MASTER_MANUAL of round 9) and the texts of those
# props.JIN_YONG_MANUALS no longer has (or has changed)
OLD_STELE_MANUALS = (
    (("打狗棒法", "降龍十八掌"), ("天罡北斗陣", "桃花島")),
    (("乾坤大挪移", "吸星大法"), ("空明拳", "黯然銷魂掌")),
    (("九陰真經", "九陽神功"), ("劍塚", "獨孤九劍")),
    (("太極拳", "太極劍"), ("七傷拳", "龍爪手")),
    (("古墓派", "玉女心經"), ("沖靈劍法", "華山劍法")),
)
OLD_MASTER = "華山論劍"
OLD_TEXTS = {
    "天罡北斗陣": dict(title="天罡北斗陣", cols=("天樞馬鈺天璇譚處端", "天璣劉處玄天權丘處機", "玉衡王處一開陽郝大通",
                                                  "搖光孫不二"), back=("射鵰英雄傳", "全真七子")),
    "劍塚": dict(title="劍塚", cols=("凌厲剛猛無堅不摧", "弱冠前以之與河朔群雄爭鋒", "紫薇軟劍三十歲前所用",
                                     "誤傷義士不祥悔恨無已乃棄之深谷", "重劍無鋒大巧不工", "四十歲前恃之橫行天下",
                                     "四十歲後不滯於物草木竹石均可為劍", "自此精修漸進於無劍勝有劍之境"),
                 back=("神鵰俠侶", "劍魔獨孤求敗")),
    "獨孤九劍": dict(title="獨孤九劍", cols=("總訣式破劍式破刀式", "破槍式破鞭式破索式", "破掌式破箭式破氣式"),
                     back=("笑傲江湖", "風清揚")),
    "華山論劍": dict(title="華山論劍", cols=("東邪黃藥師西毒歐陽鋒", "南帝段智興北丐洪七公", "中神通王重陽",
                                             "東邪黃藥師西狂楊過", "南僧一燈北俠郭靖", "中頑童周伯通"),
                     back=("射鵰英雄傳", "神鵰俠侶")),
}
STELE_PARTS = ("props.stele.slab", "props.stele.border", "props.stele.crown", "props.stele.glyphs")
CUT_PARTS = ("props.stele.slab", "props.stele.crown", "props.stele.glyphs")
# Ice-Fire Island in the round-34 file (read on 7f218a52 + lions, forge, west, east): the rock's world place and turn,
# its waterfall's place
ISLAND_OLD = dict(loc=(330.0776, 992.6684, 306.5266), rotz=-7.8187)
FALL = "scenery.island.fall.003"
R36_BUILD = "icefire_build"   # rock[R36_BUILD] once sect/lib/icefire_island.py (round 36) built it
OLD_TOKEN_NAMES = SC.TOKEN_NAMES
STAND_ITEM = SC.STAND_ITEM


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
            raise SystemExit("patch_r39_centre: unknown option %r (DRY_RUN=1, SCAN=0)" % a)
    return dry, scan


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


def obj(name):
    return bpy.data.objects.get(name)


def tree(ob):
    return [ob] + list(ob.children_recursive)


def base(n):
    return re.sub(r"\.\d{3}$", "", n)


# ------------------------------------------------------------------------------------------------------ mesh helpers

def local_tris(me):
    try:
        me.calc_loop_triangles()
    except Exception:  # noqa: BLE001
        pass
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tv)
    return co.reshape(nv, 3)[tv.reshape(nt, 3)]


def faces_sig(me):
    """Order-free fingerprint: every face as its rounded corners (cyclic from the smallest) and material name, the
    'edge' attribute's sum, and the counts."""
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
    a = me.attributes.get(U.EDGE_ATTR)
    if a is not None and a.domain == 'FACE':
        vals = np.zeros(len(me.polygons))
        a.data.foreach_get("value", vals)
        h.update(("%.3f" % float(vals.sum())).encode())
    return h.hexdigest()


def tri_normals(T):
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(cr, axis=1)
    ok = L > 1e-12
    n = np.zeros_like(cr)
    n[ok] = cr[ok] / L[ok, None]
    return n, 0.5 * L


def bvh(T):
    return BVHTree.FromPolygons([Vector(p) for p in T.reshape(-1, 3)], [(3 * i, 3 * i + 1, 3 * i + 2)
                                                                       for i in range(len(T))], all_triangles=True)


def world_tris(dg, owners=None, near=None, skip=(), skip_world=True):
    """{owner: (n, 3, 3) world triangles} of the evaluated scene's meshes (instances under their instancer's name):
    these owners, or those whose box meets the box ``near`` (lo, hi)."""
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        own = inst.parent.original.name if inst.is_instance and inst.parent else o.original.name
        if (owners is not None and own not in owners) or own in skip or (skip_world and own.startswith(SKIP)):
            continue
        W = np.array(inst.matrix_world)
        if near is not None:
            bb = np.array(o.bound_box) @ W[:3, :3].T + W[:3, 3]
            if (bb.min(0) > near[1]).any() or (bb.max(0) < near[0]).any():
                continue
        L = local_tris(o.data)
        if not len(L):
            continue
        T = L @ W[:3, :3].T + W[:3, 3]
        if near is not None:
            keep = ~((T.min(1) > near[1]).any(1) | (T.max(1) < near[0]).any(1))
            T = T[keep]
            if not len(T):
                continue
        out.setdefault(own, []).append(T)
    return {k: np.concatenate(v) for k, v in out.items()}


def obj_tris(dg, names):
    T = world_tris(dg, owners=set(names))
    return np.concatenate(list(T.values())) if T else np.zeros((0, 3, 3))


def all_T(ob):
    W = np.array(ob.matrix_world)
    return local_tris(ob.data) @ W[:3, :3].T + W[:3, 3]


def props_of(ob):
    out = {}
    for k in sorted(ob.keys()):
        if k.startswith("_"):
            continue
        v = ob[k]
        if isinstance(v, str):
            pass
        elif isinstance(v, (int, float)):
            v = round(float(v), 5)
        else:
            try:
                v = [round(float(x), 5) for x in v]
            except (TypeError, ValueError):
                v = repr(v)
        out[k] = v
    return out


def ob_sig(ob, strip=None):
    """Fingerprint of an object: (name with ``strip`` removed, local transform, parent, mesh faces, slots, props)."""
    nm = ob.name.replace(strip, "", 1) if strip else ob.name
    par = ob.parent.name.replace(strip, "", 1) if (strip and ob.parent) else (ob.parent.name if ob.parent else None)
    h = hashlib.md5()
    h.update(nm.encode())
    h.update(np.round(np.array(ob.matrix_basis), 5).tobytes())
    h.update(repr(par).encode())
    if ob.type == 'MESH':
        h.update(faces_sig(ob.data).encode())
        h.update(repr([s.material.name if s.material else None for s in ob.material_slots]).encode())
        h.update(repr(ob.data.get(RC.TAG)).encode())
        h.update(repr(ob.data.get(P.R12_TAG)).encode())
    h.update(repr(props_of(ob)).encode())
    return nm, h.hexdigest()


def sigs(obs, strip=None):
    return dict(ob_sig(o, strip) for o in obs)


def delete_tree(ob, removed):
    obs = tree(ob)
    removed += [o.name for o in obs]
    U.delete_hierarchy(ob)


class Scratch:
    """A scratch collection for builds compared with the file's objects (removed with everything in it, and every mesh
    made since it opened that nothing uses)."""

    def __init__(self):
        self.meshes0 = set(m.name for m in bpy.data.meshes)
        self.coll = bpy.data.collections.new(SCRATCH + ".coll")
        bpy.context.scene.collection.children.link(self.coll)

    def drop(self):
        for ob in list(self.coll.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(self.coll)
        for m in list(bpy.data.meshes):
            if m.users == 0 and m.name not in self.meshes0 and not m.name.startswith("props.txt."):
                bpy.data.meshes.remove(m)


def transplant(src_me, dst):
    """Give object ``dst`` the mesh ``src_me`` (the old mesh freed, its name kept)."""
    old = dst.data
    name = old.name
    dst.data = src_me
    for s in dst.material_slots:
        if s.link != 'DATA':
            s.link = 'DATA'
    if old.users == 0:
        bpy.data.meshes.remove(old)
    src_me.name = name


# --------------------------------------------------------------------------------------------------------- the steles

def stele_slots():
    """[(instance object, row, (height, glow material, seed), old title, new title)] for the 20 steles and the master,
    as steles.build hands them out (row from y, inner / outer from |x|, west / east from x's sign, in steles.root's
    frame)."""
    root = obj("steles.root")
    Rw = U.world_matrix(root).inverted()
    out = []
    for o in sorted((o for o in bpy.data.objects if o.name.startswith("steles.stele")), key=lambda o: o.name):
        if o.instance_type != 'COLLECTION' or o.instance_collection is None:
            continue
        p = Rw @ U.world_matrix(o).translation
        if o.name.startswith("steles.stele_master"):
            out.append((o, None, (ST.MASTER_H, ST.MASTER_GLYPH, 5), OLD_MASTER, ST.MASTER_MANUAL))
            continue
        r = min(range(len(ST.ROWS_Y)), key=lambda i: abs(ST.ROWS_Y[i] - p.y))
        c = min(range(len(ST.COLS_X)), key=lambda i: abs(ST.COLS_X[i] - abs(p.x)))
        s = 0 if p.x < 0 else 1
        seed = r * 2 + c + (0 if s == 0 else 3)
        out.append((o, r, (ST.ROW_H[r], ST.ROW_GLYPHS[r], seed), OLD_STELE_MANUALS[r][c][s], ST.STELE_MANUALS[r][c][s]))
    return out


def manual_new(title):
    return {m["title"]: m for m in P.JIN_YONG_MANUALS}[title]


def manual_old(title):
    return OLD_TEXTS[title] if title in OLD_TEXTS else manual_new(title)


def proto_parts(pc):
    return {base(o.name): o for o in pc.all_objects if o.type == 'MESH'}


_FRESH = {}
FRESH_MADE = set()         # the fresh builds' kept meshes (drop_fresh removes them)


def fresh_stele(spec, manual):
    """{part: (mesh sig, mesh)} of a scratch props stele build (height, glow material, seed) carving ``manual``; the
    meshes are kept (cached) until drop_fresh()."""
    key = (spec, P._manual_key(manual))
    if key in _FRESH:
        return _FRESH[key]
    h, gm, seed = spec
    b, _res = P._bucket(h, 4.0)
    sc_ = Scratch()
    P._build_stele(sc_.coll, b, gm, True, seed % 6, "stone_dark", manual)
    out = {}
    for o in list(sc_.coll.all_objects):
        if o.type != 'MESH' or base(o.name) not in STELE_PARTS:
            continue
        me = o.data
        o.data = bpy.data.meshes.new(SCRATCH + ".empty")
        me.use_fake_user = True                  # keep it past the scratch's drop
        out[base(o.name)] = (faces_sig(me), me)
        FRESH_MADE.add(me.name)
    sc_.drop()
    for m in list(bpy.data.meshes):
        if m.name.startswith(SCRATCH + ".empty") and m.users == 0:
            bpy.data.meshes.remove(m)
    _FRESH[key] = out
    return out


def drop_fresh():
    for parts in _FRESH.values():
        for _sig, me in parts.values():
            me.use_fake_user = False
            if me.users == 0:
                bpy.data.meshes.remove(me)
    _FRESH.clear()
    FRESH_MADE.intersection_update(m.name for m in bpy.data.meshes)


def steles_state(fail):
    """('old' | 'r39' | 'mixed', rows): each stele's prototype meshes against fresh builds of its old and new manual."""
    rows = []
    states = set()
    for o, r, spec, t_old, t_new in stele_slots():
        pc = o.instance_collection
        parts = proto_parts(pc)
        miss = [k for k in STELE_PARTS if k not in parts]
        if miss:
            fail.add("steles: %s's prototype %s lacks %s" % (o.name, pc.name, miss))
            continue
        have = {k: faces_sig(parts[k].data) for k in STELE_PARTS}
        new = fresh_stele(spec, manual_new(t_new))
        if all(have[k] == new[k][0] for k in STELE_PARTS):
            st = "r39"
        else:
            old = fresh_stele(spec, manual_old(t_old))
            st = "old" if all(have[k] == old[k][0] for k in STELE_PARTS) else "unknown"
        if st == "unknown":
            fail.add("steles: %s (%s) is neither %s nor %s" % (o.name, pc.name, t_old, t_new))
        states.add(st)
        rows.append((o, pc, st, t_old, t_new, spec))
    st = states.pop() if len(states) == 1 else ("mixed" if states <= {"old", "r39"} else "unknown")
    return st, rows


def steles_apply(rows, changed):
    """Each stele not yet this build gets its new manual's slab, border, crown and glyph meshes; every stele its
    manual property."""
    n = 0
    for o, pc, st, t_old, t_new, spec in rows:
        if st != "r39":
            parts = proto_parts(pc)
            new = fresh_stele(spec, manual_new(t_new))
            for k in STELE_PARTS:
                sig, me = new[k]
                cp = me.copy()
                cp.use_fake_user = False
                transplant(cp, parts[k])
            n += 1
            changed.append(o.name)
        if o.get(ST.MANUAL_PROP) != t_new:
            o[ST.MANUAL_PROP] = t_new
    log("steles: %d of %d prototypes re-carved" % (n, len(rows)))


def tokens_build(coll, prefix=""):
    host = obj(RC.TOKENS_HOST)
    names = tuple(prefix + n for n in RC.TOKENS_NAMES)
    return RC.steles_tokens(coll, obj("steles.root"), host, names)


def tokens_state(sc_, fail):
    """'old' (no tokens at the steles), 'r39' (this build's) or 'stale'."""
    have = obj(RC.TOKENS_NAME)
    if have is None:
        return "old"
    want = tokens_build(sc_.coll, SCRATCH + ".")
    a, b = sigs(tree(have)), sigs(tree(want), SCRATCH + ".")
    if a == b and have.parent is not None and have.parent.name == RC.TOKENS_HOST:
        return "r39"
    log("tokens: stale (%s)" % sorted(set(a) ^ set(b) or [k for k in a if a[k] != b.get(k)])[:6])
    return "stale"


# --------------------------------------------------------------------------------------------------------- the scroll

def old_stand_state(sc_, fail):
    """'old' (the terrace's tokens as round 5 built them), 'gone' or 'unknown'."""
    stack = obj(OLD_TOKEN_NAMES[0])
    if stack is None:
        return "gone"
    kids = sorted(c.name for c in stack.children)
    if kids != sorted(OLD_TOKEN_NAMES[1:]):
        fail.add("scroll: %s holds %s, not %s" % (stack.name, kids, sorted(OLD_TOKEN_NAMES[1:])))
        return "unknown"
    root = obj("scroll.root")
    loc = U.world_matrix(root).inverted() @ U.world_matrix(stack).translation
    want = SC.fire_tokens(sc_.coll, root, tuple(SCRATCH + "." + n for n in OLD_TOKEN_NAMES), None,
                          location=(SC.STAND_C[0], SC.STAND_C[1], 0.0))
    a = {base(o.name): faces_sig(o.data) for o in tree(stack) if o.type == 'MESH'}
    b = {base(o.name).replace(SCRATCH + ".", "", 1): faces_sig(o.data) for o in tree(want) if o.type == 'MESH'}
    near = (loc - Vector((SC.STAND_C[0], SC.STAND_C[1], 0.0))).length < 1e-3
    log("scroll: the old stand at (%.2f, %.2f, %.2f), %s; meshes %s the r5 build (TokenSpec())" % (
        loc.x, loc.y, loc.z, "at STAND_C" if near else "NOT at STAND_C", "equal to" if a == b else "DIFFERENT from"))
    if not near or a != b:
        fail.add("scroll: the terrace's token stand is not round 5's (place %s, meshes %s)" % (near, a == b))
        return "unknown"
    return "old"


def tomb_state(sc_, fail):
    """'old' (no tomb at the scroll), 'r39' or 'stale'."""
    have = obj(RC.TOMB_NAME)
    if have is None:
        return "old"
    want, _info = RC.sword_tomb(sc_.coll, obj("scroll.root"), SCRATCH + "." + RC.TOMB_NAME)
    a, b = sigs(tree(have)), sigs(tree(want), SCRATCH + ".")
    if a == b:
        return "r39"
    log("tomb: stale (%s)" % sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))[:6])
    return "stale"


# --------------------------------------------------------------------------------------------------------- the island

def island_state(fail):
    rock = obj(SN.ICEFIRE_ISLAND)
    if rock is None:
        fail.add("island: %s not found" % SN.ICEFIRE_ISLAND)
        return "unknown"
    p = rock.matrix_world.translation
    rz = math.degrees(rock.matrix_world.to_euler().z)
    o = Vector(ISLAND_OLD["loc"])
    turned = math.degrees(math.radians(ISLAND_OLD["rotz"] + SN.ICEFIRE_TURN))
    turned = (turned + 180.0) % 360.0 - 180.0
    fall = obj(FALL)
    log("island: %s at (%.4f, %.4f, %.4f), turned %.4f deg; its waterfall %s at %s; r36 build %s" % (
        rock.name, p.x, p.y, p.z, rz, FALL, None if fall is None else tuple(round(v, 4) for v in
                                                                              fall.matrix_world.translation),
        rock.get(R36_BUILD)))
    if (p - o).length < 2e-3 and abs(rz - ISLAND_OLD["rotz"]) < 2e-3:
        if rock.get(R36_BUILD):
            fail.add("island: round 36's island is already built on the unturned rock: run this patch before "
                     "patch_r36_icefire.py")
            return "unknown"
        return "old"
    if (p - (o + Vector((0.0, 0.0, -SN.ICEFIRE_DROP)))).length < 2e-3 and abs(rz - turned) < 2e-3:
        return "r39"
    fail.add("island: %s is neither where round 34 left it nor turned %.0f deg and dropped %.0f m" % (
        rock.name, SN.ICEFIRE_TURN, SN.ICEFIRE_DROP))
    return "unknown"


# ------------------------------------------------------------------------------------------------------------- checks

def site_view(sc, cam, frame):
    """chase.cam's world matrix as the page shows ``frame`` (FRAMING at a framed hold). Sets the scene frame."""
    yaw, pitch, back = FRAMING.get(frame, (0.0, 0.0, 0))
    sc.frame_set(frame - back)
    Mw = cam.matrix_world.copy()
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Mw.to_3x3().normalized() @ \
        Matrix.Rotation(math.radians(pitch), 3, 'X')
    out = R.to_4x4()
    out.translation = Mw.translation
    return out


def screen_pts(sc, cam, P_):
    xs, ys, zs = [], [], []
    for p in P_:
        v = world_to_camera_view(sc, cam, Vector(p))
        xs.append(v.x * RES[0])
        ys.append((1 - v.y) * RES[1])
        zs.append(v.z)
    return np.array(xs), np.array(ys), np.array(zs)


def seen_share(sc, dg, cam, P_, names, lift=0.02, n=80):
    cw = cam.matrix_world.translation.copy()
    k, seen = 0, 0
    for p in P_[::max(1, len(P_) // n)]:
        q = Vector(p)
        d = q - cw
        q = q - d.normalized() * lift
        o = cw.copy()
        for _ in range(6):                       # past the haze and clouds (sprites on the page)
            hit, loc, nrm, idx, hob, _ = sc.ray_cast(dg, o, d.normalized(), distance=(q - o).length + 0.05)
            if not hit or not getattr(hob, "original", hob).name.startswith(SEE_THROUGH):
                break
            o = loc + d.normalized() * 0.01
        k += 1
        if not hit:
            seen += 1
            continue
        top = getattr(hob, "original", hob)
        while top is not None and top.name not in names:
            top = top.parent
        seen += bool(top is not None or (loc - q).length < 0.05)
    return seen / max(k, 1)


def check_reading(sc, dg, cam, stop, label, P_, names, fail, need=True, seen_min=READ_SEEN):
    xs, ys, zs = screen_pts(sc, cam, P_)
    inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1]) & (zs > 0)))
    box = (xs.min(), xs.max(), ys.min(), ys.max())
    hit_ui = []
    for nm, (x0, y0, x1, y1) in UI_RECTS.get(stop, ()) + UI_COMMON:
        if not (box[1] < x0 or box[0] > x1 or box[3] < y0 or box[2] > y1):
            hit_ui.append(nm)
    seen = seen_share(sc, dg, cam, P_, names)
    log("read %s %s: x %.0f..%.0f y %.0f..%.0f px, %.0f%% in frame, %.0f%% unhidden%s" % (
        stop, label, box[0], box[1], box[2], box[3], 100 * inside, 100 * seen,
        ("; under " + ", ".join(hit_ui)) if hit_ui else ""))
    if need and (inside < 1.0 or seen < seen_min or hit_ui):
        fail.add("%s %s does not read at the hold (%.0f%% in frame, %.0f%% unhidden, under %s)" % (
            stop, label, 100 * inside, 100 * seen, hit_ui or "nothing"))
    return box


def px_size(sc, cam, a, b):
    """Screen distance (px) between world points a and b."""
    xs, ys, _zs = screen_pts(sc, cam, [a, b])
    return float(math.hypot(xs[1] - xs[0], ys[1] - ys[0]))


def floor_hit(floors_T, p, top=6.0):
    """z of the highest of the floor triangles under the point p, or None."""
    best = None
    for tr in floors_T:
        loc, _n, _i, _d = tr.ray_cast(Vector((p[0], p[1], p[2] + top)), Vector((0.0, 0.0, -1.0)), top + 10.0)
        if loc is not None and (best is None or loc.z > best):
            best = loc.z
    return best


def check_grounded(dg, label, names, floor_prefix, sink, fail):
    """The piece's lowest points (within 5 mm of its lowest) lie ``sink`` under the top of the floor (the meshes whose
    names start with ``floor_prefix``)."""
    floor_names = sorted(o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(floor_prefix))
    T = obj_tris(dg, names)
    V = T.reshape(-1, 3)
    zmin = V[:, 2].min()
    pts = V[V[:, 2] < zmin + 0.005]
    if len(pts) > 64:
        pts = pts[np.linspace(0, len(pts) - 1, 64).astype(int)]
    near = (V.min(0) - 3.0, V.max(0) + 3.0)
    fl = [bvh(t) for t in world_tris(dg, owners=set(floor_names), near=near, skip_world=False).values()]
    worst = (1e9, -1e9)
    for p in pts:
        z = floor_hit(fl, p)
        if z is None:
            fail.add("%s: no floor (%s) under its foot at %s" % (label, floor_names, tuple(round(float(v), 2) for v in p)))
            return
        s = z - p[2]
        worst = (min(worst[0], s), max(worst[1], s))
        if not (sink[0] - 1e-4 <= s <= sink[1]):
            fail.add("%s: foot sunk %.3f m under %s (want %.2f..%.2f)" % (label, s, floor_names, sink[0], sink[1]))
            return
    log("grounded %s: %d foot points sunk %.3f..%.3f m under %s" % (label, len(pts), worst[0], worst[1], floor_names))


def check_clear(dg, label, names, allow, fail):
    own = set(names)
    T = obj_tris(dg, own)
    lo, hi = T.reshape(-1, 3).min(0) - 0.5, T.reshape(-1, 3).max(0) + 0.5
    tw = bvh(T)
    V = T.reshape(-1, 3)[::5]
    rows = []
    for o, To in world_tris(dg, near=(lo, hi), skip=own).items():
        if o.startswith(SCRATCH):
            continue
        to = bvh(To)
        touch = len(tw.overlap(to))
        d = min(min(to.find_nearest(Vector(p))[3] for p in V), min(tw.find_nearest(Vector(p))[3]
                                                                     for p in To.reshape(-1, 3)[::5]))
        ok = any(o == a or o.startswith(a) for a in allow)
        rows.append((d, o, ok))
        if not ok and (touch or d < CLEAR_MIN):
            fail.add("%s: %s is %.3f m from it (%d crossing triangle pairs)" % (label, o, d, touch))
    rows.sort()
    log("clear %s: nearest %s" % (label, ", ".join("%s %.3f m%s" % (o, d, " (its floor)" if ok else "")
                                                    for d, o, ok in rows[:5]) or "nothing"))


def check_camera(sc, cam, label, names, fail):
    T = world_tris(bpy.context.evaluated_depsgraph_get(), owners=set(names))
    V = np.concatenate([t.reshape(-1, 3) for t in T.values()])
    lo, hi = V.min(0), V.max(0)
    frames = list(range(sc.frame_start, sc.frame_end + 1))
    best, bf = 1e9, 0
    for f, M in zip(frames, EW.sample_matrices(cam, frames)):
        p = np.array(M.translation)
        d = float(np.linalg.norm(np.maximum(0.0, np.maximum(lo - p, p - hi))))
        if d < best:
            best, bf = d, f
    log("flight %s: chase.cam comes within %.1f m (frame %d)" % (label, best, bf))
    if best < CAM_MIN:
        fail.add("%s: chase.cam comes within %.1f m (frame %d)" % (label, best, bf))


def scan(dg, names, label):
    """{piece: [same <=5 mm, same 5-12 mm, back-to-back <=5 mm]} m2 of parallel faces against itself and every mesh
    whose box meets its own (patch_r34_east's scan)."""
    t0 = time.time()
    rows = {}
    for nm in names:
        ob = obj(nm)
        rng = np.random.default_rng(zlib.crc32(base(nm).encode()))
        T = all_T(ob)
        if not len(T):
            continue
        lo, hi = T.reshape(-1, 3).min(0) - 0.03, T.reshape(-1, 3).max(0) + 0.03
        others, oid = [], []
        for own, To in world_tris(dg, near=(lo, hi), skip={nm}).items():
            if own.startswith(SCRATCH):
                continue
            others.append(To)
            oid += [own] * len(To)
        tn = bvh(np.concatenate(others)) if others else None
        ts = bvh(T)
        nrm, ar = tri_normals(T)
        tot = [0.0, 0.0, 0.0]
        who = {}
        for t in np.nonzero(ar > 1e-9)[0]:
            k = int(min(60, max(1, round(ar[t] / (SCAN_STEP * SCAN_STEP)))))
            u, v = rng.random(k), rng.random(k)
            f = u + v > 1.0
            u[f], v[f] = 1.0 - u[f], 1.0 - v[f]
            n = Vector(nrm[t])
            w = ar[t] / k
            for p in T[t, 0] + np.outer(u, T[t, 1] - T[t, 0]) + np.outer(v, T[t, 2] - T[t, 0]):
                p = Vector(p)
                for sgn in (-1.0, 1.0):
                    for tr, ids in ((ts, None), (tn, oid)):
                        if tr is None:
                            continue
                        loc, hn, fi, _d = tr.ray_cast(p + n * (sgn * 1e-4), n * sgn, SCAN_TOL12)
                        if loc is None:
                            continue
                        c = hn.dot(n)
                        g = abs((loc - p).dot(n))
                        if abs(c) < SCAN_PAR or g > SCAN_TOL12:
                            continue
                        o = "<self>" if ids is None else ids[fi]
                        if c < 0.0:
                            if g <= SCAN_TOL:
                                tot[2] += w
                                who.setdefault(o, [0.0, 0.0, 0.0])[2] += w
                            continue
                        b = 0 if g <= SCAN_TOL else 1
                        tot[b] += w
                        who.setdefault(o, [0.0, 0.0, 0.0])[b] += w
        rows[nm] = (tot, who)
        top = sorted(who.items(), key=lambda kv: -sum(kv[1]))[:3]
        log("scan %s %s: same-facing within 5 mm %.3f m2, 5-12 mm %.3f m2; back-to-back within 5 mm %.3f m2%s" % (
            label, base(nm), tot[0], tot[1], tot[2], "".join("; %s %.3f + %.3f / %.3f" % (o, a, b, c_)
                                                             for o, (a, b, c_) in top if a + b + c_ >= 0.001)))
    log("scan %s: %d pieces, %.1f s" % (label, len(rows), time.time() - t0))
    return rows


def check_glyphs(fail):
    """Every character carved this round has faces in KaiTi and is not the font's missing-glyph shape."""
    chars = set(RC.TOMB_TEXT)
    for m in P.JIN_YONG_MANUALS:
        for t in [m["title"]] + list(m["cols"]) + list(m.get("back", ())) + list(m.get("foot", ())):
            chars.update(t)
    font = RC._font()
    ref = P._text_mesh(MISSING_REF, 1.0, 2, font=font)
    ref_sig = (len(ref.vertices), len(ref.polygons), tuple(np.round(np.array(ref.vertices[0].co), 4))
               if len(ref.vertices) else None)
    bad = []
    for ch in sorted(chars):
        me = P._text_mesh(ch, 1.0, 2, font=font)
        sig = (len(me.vertices), len(me.polygons), tuple(np.round(np.array(me.vertices[0].co), 4))
               if len(me.vertices) else None)
        if not len(me.polygons) or sig == ref_sig:
            bad.append(ch)
    log("glyphs: %d characters, all in KaiTi" % len(chars) if not bad else "glyphs: missing %s" % bad)
    if bad:
        fail.add("characters missing from KaiTi: %s" % "".join(bad))


def stele_glyph_px(sc, cam, o, manual, spec):
    """(px of a front glyph cell, share of the front glyphs in frame) of stele instance ``o``."""
    h = spec[0]
    plan = P.stele_glyph_plan(h, True, manual)
    M = U.world_matrix(o)
    g = [d for d in plan["glyphs"] if d["face"] == "front"]
    pts = [M @ d["centre"] for d in g]
    xs, ys, zs = screen_pts(sc, cam, pts)
    inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1]) & (zs > 0)))
    d0 = g[0]
    cell = px_size(sc, cam, M @ d0["centre"], M @ (d0["centre"] + Vector((0.0, 0.0, d0["cell"]))))
    f = g[-1]                                     # the foot block comes after the columns (props._manual_blocks)
    fcell = px_size(sc, cam, M @ f["centre"], M @ (f["centre"] + Vector((0.0, 0.0, f["cell"])))) \
        if manual.get("foot") else None
    return cell, inside, fcell, (xs.min(), xs.max(), ys.min(), ys.max())


def lore_check(fail):
    """export_web's own hotspot and lore functions (read only): the three references find their boxes and hosts."""
    EW.PROFILE = "full"
    EW._MEMBERS = None
    EW.LORE_DEFS[:] = []
    EW.build_hotspot_defs()
    members = EW.hotspot_members()
    defs, _miss = EW.build_lore_defs()
    want = {"holy-fire-tokens": "skills:1", "dugu-nine-swords": "steles", "sword-tomb": None,
            "icefire-island": None}
    for d in defs:
        if d["id"] not in want:
            continue
        if not d["boxes"]:
            fail.add("lore %s: no box (%s)" % (d["id"], EW._lore_waits(d["id"]) or "objects missing"))
            continue
        for names in d["boxes"]:
            b, objs = EW._lore_box(names)
            host = next((members[o] for o in objs if o in members), None)
            log("lore %s: %s, %d objects, host %s, box %s .. %s" % (
                d["id"], names, len(objs), host, tuple(round(float(v), 1) for v in b[0]),
                tuple(round(float(v), 1) for v in b[1])))
            if host != want[d["id"]]:
                fail.add("lore %s: hosted by %s, want %s" % (d["id"], host, want[d["id"]]))
    EW._MEMBERS = None


def hotspot_boxes():
    defs = [(h, n) for h, _l, n in EW.AREA_HOTSPOTS if h.split("-")[0] in ("library", "steles", "scroll")]
    defs += [("skills:%d" % r, ["steles.stele.r%d" % r] + EW._resolve(["steles.stele.r%d.*" % r])) for r in range(5)]
    defs += [("resume", ["scroll.jade_scroll"])]
    defs += [("school:%d" % si, ["library.lit_core.%d" % s, "library.shelves.%d" % s]) for s, si in EW.LIBRARY_FLOORS]
    out = {}
    for h, names in defs:
        b = EW._subtree_box(names)
        out[h] = None if b is None else (tuple(round(v, 4) for v in b[0]), tuple(round(v, 4) for v in b[1]))
    return out


def run_checks(sc, fail, do_scan, scan0):
    cam = obj(EW.CAMERA)
    dg = bpy.context.evaluated_depsgraph_get()
    check_glyphs(fail)
    # carved: every stele its manual; the re-carved meshes cut the round-12 way
    for o, r, spec, t_old, t_new in stele_slots():
        if o.get(ST.MANUAL_PROP) != t_new:
            fail.add("steles: %s carries %r, want %r" % (o.name, o.get(ST.MANUAL_PROP), t_new))
        parts = proto_parts(o.instance_collection)
        untagged = [k for k in CUT_PARTS if parts[k].data.get(P.R12_TAG) != "cut"]
        if untagged:
            fail.add("steles: %s's %s are not tagged %s = 'cut'" % (o.name, untagged, P.R12_TAG))
    # the tokens
    tok = [o.name for o in tree(obj(RC.TOKENS_NAME)) if o.type == 'MESH']
    check_grounded(dg, "tokens", tok, "steles.field.w", TOKEN_SINK, fail)
    check_clear(dg, "tokens", tok, ("steles.field.w",), fail)
    check_camera(sc, cam, "tokens", tok, fail)
    # the tomb
    tomb = [o.name for o in tree(obj(RC.TOMB_NAME)) if o.type == 'MESH']
    for nm in (RC.TOMB_NAME + ".slab", RC.TOMB_NAME + ".boulder"):
        check_grounded(dg, base(nm), [nm], "world.range", TOMB_SINK, fail)
    lay = RC.tomb_layout()
    Mt = U.world_matrix(obj(RC.TOMB_NAME))
    slots = {k: (x, ml, mw) for k, x, ml, mw, _md in F.ST_SLOTS}
    for key, nm in (("sharp", "sharp_sword"), ("soft", "strip"), ("wood", "wood_sword")):
        o = obj(RC.TOMB_NAME + "." + nm)
        T = all_T(o).reshape(-1, 3)
        lowest = Mt.inverted() @ Vector(T[T[:, 2].argmin()])
        fl = Vector(lay["floors"][key])
        x, ml, mw = slots[key]
        dz = lowest.z - fl.z
        inside = abs(lowest.x - x) <= ml / 2 + 1e-3 and abs(lowest.y - fl.y) <= mw / 2 + 1e-3
        log("mortise %s: its lowest point %.3f m over the %s place's floor, %s its mortise" % (
            nm, dz, key, "inside" if inside else "OUTSIDE"))
        if abs(dz) > MORTISE_TOL or not inside:
            fail.add("tomb: %s's foot is %.3f m over its mortise floor%s" % (nm, dz, "" if inside else ", outside it"))
    if obj(RC.TOMB_NAME + ".boulder").data.get(P.R12_TAG) != "cut":
        fail.add("tomb: the boulder's mesh is not tagged %s = 'cut'" % P.R12_TAG)
    check_clear(dg, "tomb", tomb, ("world.range",), fail)
    check_camera(sc, cam, "tomb", tomb, fail)
    # reading at the holds
    old_mw = cam.matrix_world.copy()
    try:
        cam.matrix_world = site_view(sc, cam, HOLDS["steles"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        tn = set(o.name for o in tree(obj(RC.TOKENS_NAME)))
        P_ = np.concatenate([all_T(obj(n)).reshape(-1, 3) for n in tok])
        P_ = P_[np.linspace(0, len(P_) - 1, 400).astype(int)]
        check_reading(sc, dg, cam, "steles", "tokens", P_, tn, fail)
        lo = P_.min(0)
        hi = P_.max(0)
        log("read steles tokens: %.0f px tall (%.2f m)" % (px_size(sc, cam, Vector((lo[0], lo[1], lo[2])),
                                                                     Vector((lo[0], lo[1], hi[2]))), hi[2] - lo[2]))
        for o, r, spec, t_old, t_new in stele_slots():
            if r is not None and o.name.split(".")[-1] not in ("r%d" % r,) and not (r == 0 and o.name.endswith(".001")):
                continue
            cell, inside, fcell, box = stele_glyph_px(sc, cam, o, manual_new(t_new), spec)
            log("read steles %s %s: glyph cell %.1f px, %.0f%% of its front in frame (x %.0f..%.0f y %.0f..%.0f)%s" % (
                o.name, t_new, cell, 100 * inside, box[0], box[1], box[2], box[3],
                (", foot cell %.1f px" % fcell) if fcell else ""))
            if r is None and inside < 1.0:
                fail.add("steles: the master stele's front is not wholly in frame at the hold")
        cam.matrix_world = site_view(sc, cam, HOLDS["scroll"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        tt = set(o.name for o in tree(obj(RC.TOMB_NAME)))
        P_ = np.concatenate([all_T(obj(n)).reshape(-1, 3) for n in tomb])
        P_ = P_[np.linspace(0, len(P_) - 1, 600).astype(int)]
        check_reading(sc, dg, cam, "scroll", "tomb", P_, tt, fail)
        b = obj(RC.TOMB_NAME + ".boulder")
        me = b.data
        Wb = U.world_matrix(b)
        paint = [i for i, m in enumerate(me.materials) if m and m.name.endswith(RC.TOMB_PAINT)]
        pv = sorted({v for p in me.polygons if p.material_index in paint for v in p.vertices})
        PP = np.array([tuple(Wb @ me.vertices[i].co) for i in pv])
        check_reading(sc, dg, cam, "scroll", "劍塚", PP[np.linspace(0, len(PP) - 1, 200).astype(int)], tt, fail)
        _r, boxes = RC._glyph_regions()
        for ch, (x0, x1, z0, z1) in zip(RC.TOMB_TEXT, boxes):
            log("read scroll %s: %.0f x %.0f px" % (
                ch, px_size(sc, cam, Wb @ Vector((x0, 0.0, 0.5 * (z0 + z1))), Wb @ Vector((x1, 0.0, 0.5 * (z0 + z1)))),
                px_size(sc, cam, Wb @ Vector((0.5 * (x0 + x1), 0.0, z0)), Wb @ Vector((0.5 * (x0 + x1), 0.0, z1)))))
        for nm in ("sharp_sword", "strip", "wood_sword"):
            T = all_T(obj(RC.TOMB_NAME + "." + nm)).reshape(-1, 3)
            log("read scroll %s: %.0f px tall" % (nm, px_size(sc, cam, Vector(T[T[:, 2].argmin()]),
                                                              Vector(T[T[:, 2].argmax()]))))
        rock = obj(SN.ICEFIRE_ISLAND)
        isl = [o for o in tree(rock) if o.type == 'MESH' and not o.name.startswith(EW.LORE_SKIP)]
        PI = np.concatenate([all_T(o).reshape(-1, 3) for o in isl])
        PI = PI[np.linspace(0, len(PI) - 1, 400).astype(int)]
        names_i = set(o.name for o in tree(rock))
        for stop in ("library", "steles"):
            cam.matrix_world = site_view(sc, cam, HOLDS[stop])
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            check_reading(sc, dg, cam, stop, "island", PI, names_i, fail, need=False)
        cam.matrix_world = site_view(sc, cam, HOLDS["library"])
        bpy.context.view_layer.update()
        xs, ys, zs = screen_pts(sc, cam, PI)
        inside = float(np.mean((xs >= 0) & (xs <= RES[0]) & (ys >= 0) & (ys <= RES[1]) & (zs > 0)))
        if inside < 1.0:
            fail.add("library: the island is not wholly in frame at 772 (%.0f%%)" % (100 * inside))
    finally:
        cam.matrix_world = old_mw
        bpy.context.view_layer.update()
    lore_check(fail)
    if do_scan:
        dg = bpy.context.evaluated_depsgraph_get()
        rows = scan(dg, tok + tomb, "after")
        if scan0:
            before = sum(sum(v[0][:2]) for v in scan0.values())
            after = sum(sum(rows[n][0][:2]) for n in tok if n in rows)
            log("scan: the tokens' same-facing faces within 12 mm %.3f m2 (the terrace's stand: %.3f m2)" % (
                after, before))
            if after > before + 1e-6:
                fail.add("scan: the tokens have more same-facing faces within 12 mm than the old stand")
        for n in tomb:
            if n in rows:
                tot, who = rows[n]
                ext = sum(sum(v[:2]) for o, v in who.items() if o not in tt and o != "<self>")
                if ext > NEW_MAX:
                    fail.add("scan: %s has %.3f m2 of same-facing faces within 12 mm of other pieces" % (n, ext))


# ------------------------------------------------------------------------------------------------------------- main

def touched():
    obs, extra = [], []
    for o, r, spec, t_old, t_new in stele_slots():
        extra.append("%s|%s|%s" % (o.name, o.get(ST.MANUAL_PROP), o.instance_collection.name))
        parts = proto_parts(o.instance_collection)
        for k in STELE_PARTS:
            me = parts[k].data
            extra.append("%s|%s|%s|%s" % (o.name, k, faces_sig(me), me.get(P.R12_TAG)))
    for n in (RC.TOKENS_NAME, RC.TOMB_NAME):
        if obj(n) is not None:
            obs += tree(obj(n))
    for n in (SN.ICEFIRE_ISLAND, FALL):
        o = obj(n)
        if o is not None:
            extra.append("%s|%s" % (n, np.round(np.array(o.matrix_world), 4).tolist()))
    absent = list(OLD_TOKEN_NAMES)
    return obs, extra, absent


def digest():
    obs, extra, absent = touched()
    h = hashlib.md5()
    for nm, s in sorted(sigs(obs).items()):
        h.update(nm.encode())
        h.update(s.encode())
    for e in extra:
        h.update(e.encode())
    for n in absent:
        h.update(("%s:%s" % (n, obj(n) is not None)).encode())
    return h.hexdigest()


def drop_eval(had_eval):
    if not had_eval:
        s_ = bpy.data.scenes.get(P._EVAL_SCENE)
        if s_ is not None and s_ != bpy.context.scene and not len(s_.objects):
            bpy.data.scenes.remove(s_)


def main():
    dry, do_scan = options()
    t0 = time.time()
    fail = Fail()
    sc = bpy.context.scene
    for n in ("steles.root", "scroll.root", "steles.stele_master", RC.TOKENS_HOST, SN.ICEFIRE_ISLAND, EW.CAMERA):
        if obj(n) is None:
            log("NOT SAVED: %s not found: is this out/sect_chase.blend?" % n)
            raise SystemExit(1)
    if obj("arena.seats") is None or obj("mission.dipper.tianshu") is None or obj("mirror.siguoya") is None:
        log("NOT SAVED: run patch_r28_lions.py, patch_r29_forge.py, patch_r34_west.py and patch_r34_east.py first")
        raise SystemExit(1)
    ST._register_materials()
    rx, ry, rp = sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    n_obj0 = len(bpy.data.objects)
    scenes0 = sorted(s.name for s in bpy.data.scenes)
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    log("refs_centre: tokens at %s turned %.0f deg (k %.2f, plinth top %.2f m) under %s; tomb at %s turned %.1f deg, "
        "%s %.2f m cells; island turn %.0f deg, drop %.0f m" % (
            RC.TOKENS_AT, math.degrees(RC.TOKENS_YAW), RC.TOKENS_K, RC.TOKENS_PLINTH[-1][3], RC.TOKENS_HOST,
            RC.TOMB_AT, math.degrees(RC.TOMB_YAW), RC.TOMB_TEXT, RC.TOMB_CELL, SN.ICEFIRE_TURN, SN.ICEFIRE_DROP))
    hs0 = hotspot_boxes()
    removed, added, changed = [], [], []
    sc_ = Scratch()
    try:
        t1 = time.time()
        st_s, rows = steles_state(fail)
        st_t = tokens_state(sc_, fail)
        st_o = old_stand_state(sc_, fail)
        st_b = tomb_state(sc_, fail)
        st_i = island_state(fail)
        log("states: steles %s (%s), tokens %s, the terrace's stand %s, tomb %s, island %s (%.1f s)" % (
            st_s, ", ".join("%s %s" % (k, sum(1 for r in rows if r[2] == k)) for k in ("old", "r39")), st_t, st_o,
            st_b, st_i, time.time() - t1))
        if fail:
            log("NOT SAVED: the file is not in a state this patch knows (%d problems)" % len(fail))
            raise SystemExit(1)
        todo = st_s != "r39" or st_t != "r39" or st_o != "gone" or st_b != "r39" or \
            st_i != "r39" or any(o.get(ST.MANUAL_PROP) != t for o, _pc, _s, _to, t, _sp in rows)
        scan0 = None
        if todo and do_scan and st_o == "old":
            dg = bpy.context.evaluated_depsgraph_get()
            scan0 = scan(dg, [o.name for o in tree(obj(OLD_TOKEN_NAMES[0])) if o.type == 'MESH'], "before")
        sc_.drop()
        sc_ = None
        if todo:
            steles_apply(rows, changed)
            if st_t != "r39":
                if st_t == "stale":
                    delete_tree(obj(RC.TOKENS_NAME), removed)
                g = tokens_build(bpy.data.objects[RC.TOKENS_HOST].users_collection[0])
                added += [o.name for o in tree(g)]
            if st_o == "old":
                delete_tree(obj(OLD_TOKEN_NAMES[0]), removed)
            if st_b != "r39":
                if st_b == "stale":
                    delete_tree(obj(RC.TOMB_NAME), removed)
                emp, info = RC.sword_tomb(obj("scroll.root").users_collection[0], obj("scroll.root"))
                added += [o.name for o in tree(emp)]
                log("tomb: boulder %s" % ({k: v for k, v in info.items() if k != "boxes"},))
                if info["open_edges"]:
                    fail.add("tomb: the boulder has %d open edges" % info["open_edges"])
            if st_i == "old":
                comp = SN.turn_icefire()
                log("island: turned with %s" % comp)
                changed.append(SN.ICEFIRE_ISLAND)
    finally:
        if sc_ is not None:
            sc_.drop()
    drop_eval(had_eval)
    bpy.context.view_layer.update()
    # after: the build matches the scratch build (the same code)
    sc2 = Scratch()
    try:
        st = (steles_state(fail)[0], tokens_state(sc2, fail), old_stand_state(sc2, fail), tomb_state(sc2, fail),
              island_state(fail))
    finally:
        sc2.drop()
    drop_fresh()
    drop_eval(had_eval)
    log("after: states %s" % (st,))
    if st != ("r39", "r39", "gone", "r39", "r39"):
        fail.add("after the patch the file is not this build: %s" % (st,))
    run_checks(sc, fail, do_scan and todo, scan0)
    drop_eval(had_eval)
    hs1 = hotspot_boxes()
    grown = [h for h in hs0 if hs0[h] != hs1.get(h)]
    log("hotspots: %d boxes of the steles, scroll and library, changed %s" % (len(hs0), grown or "none"))
    if todo and set(grown) - {"skills:1"}:
        fail.add("hotspot boxes changed: %s (only skills:1 may grow)" % grown)
    n_obj1 = len(bpy.data.objects)
    log("objects %d -> %d (removed %d, added %d)" % (n_obj0, n_obj1, len(removed), len(added)))
    if n_obj1 != n_obj0 - len(removed) + len(added):
        fail.add("objects %d -> %d, want %d - %d + %d" % (n_obj0, n_obj1, n_obj0, len(removed), len(added)))
    left = [o.name for o in bpy.data.objects if o.name.startswith(SCRATCH)] + \
        [m.name for m in bpy.data.meshes if m.name.startswith(SCRATCH) or m.name in FRESH_MADE] + \
        [c.name for c in bpy.data.collections if c.name.startswith(SCRATCH)]
    if left:
        fail.add("scratch data left: %s" % left[:8])
    scenes1 = sorted(s.name for s in bpy.data.scenes)
    if scenes1 != scenes0:
        fail.add("scenes %s -> %s" % (scenes0, scenes1))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, rp
    log("removed: %s" % (", ".join(sorted(removed)) or "nothing"))
    log("added: %s" % (", ".join(sorted(added)) or "nothing"))
    log("changed: %s" % (", ".join(changed) or "nothing"))
    log("DIGEST", digest())
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if not todo:
        log("CACHES ok: nothing changed")
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    log("CACHES needs audit: objects added (steles.tokens, scroll.sword_tomb), removed (scroll.slip_stack) and moved "
        "(scenery.island.009 and its waterfall) and the steles' prototype meshes re-carved - run export_web.py -- audit "
        "--profile full, then -- chunks,meta --profile full (the lore boxes holy-fire-tokens, dugu-nine-swords and "
        "sword-tomb are new; icefire-island moves), then bake_web.py -- bakefull --profile full --chunks "
        "steles,scroll,formation,backdrop (island.009 is in the formation chunk and the backdrop's stand-ins; add "
        "library if export_web forces it there), then pack; no trees bake (no plant mask changed)")
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
