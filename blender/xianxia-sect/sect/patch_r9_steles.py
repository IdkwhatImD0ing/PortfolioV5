"""Re-letter the Stele Forest of Techniques with Jin Yong's martial-arts manuals (round 9, lane 'steles'): bring an
existing out/sect_chase.blend to the design in sect/areas/steles.py (STELE_MANUALS, MASTER_MANUAL over
props.JIN_YONG_MANUALS) and save it. Run on the cloud box (on a copy first):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r9_steles.py [-- DRY_RUN=1]

What it does (a fresh build makes the same through steles.build): the 20 steles and the master stele used to carry
Daoist classics (props.CLASSICS) in their glyph columns and 玄天宝录 in every crown. Now each is one manual from Jin
Yong's four novels: the art's name in the crown panel, its moves or mnemonic on the front (each listed string one
column, top to bottom, right to left), the novel and the art's master on the back; the gold master stele carries the
Five Greats of the first and third Mount Hua contests under 華山論劍. Only the mesh data of each prototype's glyph
object ('props.stele.glyphs*' inside the 'props.stele.*' prototype collections) changes: it is replaced by
props.stele_glyph_mesh(...) for that stele's height, seed and manual (same object, name, mesh name, material, glow,
shadow flag). No object is added, removed or moved; the prototype collections keep their names.

Which manual goes where follows from each instancer's place in the forest (row from its y, inner or outer column from
|x|, west or east from the sign of x, in steles.root's frame), exactly as steles.build hands them out. Every prototype
must serve exactly one stele (true for this layout), so every stele gets its own manual.

Checks before saving (it stops without saving when one fails): the manuals in props.JIN_YONG_MANUALS are the round-9
text (EXPECTED), every title is placed exactly once and the 20 + 1 are distinct; every character is in simkai.ttf's
own character map and its Blender glyph has faces and is not the font's missing-glyph shape; each stele's prototype
tag agrees with its place (height bucket, glow material, seed); the file's glyph mesh is either the fresh classics
build for that stele (proves the frame: same builder, height, seed) or already this round's manual (a re-run); the new
mesh holds exactly the planned glyphs (every vertex inside a planned glyph cell on its face plane, every planned cell
filled, vertex total = the sum of the glyphs); names, materials, glow and shadow flags are unchanged; the object count
is unchanged. It logs every stele's text, triangle counts before and after, and at the 974 hold which steles are in
frame and how tall a glyph cell lands.

Caches: export_web keys its caches on object names and boxes pieces by their bound box. Names stay; when every new
glyph mesh's box lies inside the box of the classics it replaces (2 mm tolerance) it prints 'PATCH CACHES ok', else
'PATCH CACHES needs audit' (run the export audit and chunks,meta). Either way re-bake the steles chunk (and the
backdrop chunks, which can hold far steles) for the new glyphs.

Idempotent: every run rebuilds each glyph mesh from scratch and frees the replaced one.
"""

import os
import struct
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import steles as ST  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import util as U  # noqa: E402

TMP = "_tmp_r9_steles"
HOLD = 974
BOX_TOL = 2e-3
MISSING_REF = "\u0e01"      # Thai ko kai: not in KaiTi's character map, so Blender draws the font's missing glyph
# The round-9 text: title -> (front columns joined, back lines joined). Guards props.JIN_YONG_MANUALS against edits.
EXPECTED = {
    "降龍十八掌": ("亢龍有悔飛龍在天見龍在田鴻漸於陸潛龍勿用利涉大川突如其來震驚百里或躍在淵雙龍取水魚躍於淵時乘六龍"
                  "密雲不雨損則有孚龍戰於野履霜冰至羝羊觸藩神龍擺尾", "射鵰英雄傳北丐洪七公"),
    "打狗棒法": ("絆劈纏戳挑引封轉天下無狗", "射鵰英雄傳丐幫幫主"),
    "九陰真經": ("移魂大法手揮五弦大伏魔拳摧堅神爪摧心掌白蟒鞭法九陰白骨爪", "射鵰英雄傳黃裳"),
    "空明拳": ("空朦洞鬆風通容夢沖窮中弄童庸弓蟲", "射鵰英雄傳老頑童周伯通"),
    "桃花島": ("落英神劍掌旋風掃葉腿蘭花拂穴手彈指神通玉簫劍法碧海潮生曲", "射鵰英雄傳東邪黃藥師"),
    "天罡北斗陣": ("天樞馬鈺天璇譚處端天璣劉處玄天權丘處機玉衡王處一開陽郝大通搖光孫不二", "射鵰英雄傳全真七子"),
    "黯然銷魂掌": ("心驚肉跳杞人憂天無中生有拖泥帶水徘徊空谷力不從心行屍走肉庸人自擾倒行逆施廢寢忘食孤形隻影飲恨吞聲"
                  "六神不安窮途末路面無人色想入非非呆若木雞", "神鵰俠侶西狂楊過"),
    "古墓派": ("少思少念少欲少事少語少笑少愁少樂少喜少怒少好少惡行此十二少乃養生之都契也", "神鵰俠侶小龍女"),
    "玉女心經": ("浪跡天涯花前月下清飲小酌撫琴按簫掃雪烹茶松下對弈池邊調鶴", "神鵰俠侶林朝英"),
    "劍塚": ("凌厲剛猛無堅不摧弱冠前以之與河朔群雄爭鋒紫薇軟劍三十歲前所用誤傷義士不祥悔恨無已乃棄之深谷重劍無鋒大巧不工"
            "四十歲前恃之橫行天下四十歲後不滯於物草木竹石均可為劍自此精修漸進於無劍勝有劍之境", "神鵰俠侶劍魔獨孤求敗"),
    "九陽神功": ("他自狠來他自惡我自一口真氣足", "倚天屠龍記張無忌"),
    "乾坤大挪移": ("第一層第二層第三層第四層第五層第六層第七層", "倚天屠龍記明教"),
    "太極拳": ("攬雀尾單鞭提手上勢白鶴亮翅摟膝勾步手揮琵琶進步搬攔錘如封似閉十字手抱虎歸山虛靈頂勁涵胸拔背鬆腰垂臀沉肩墜肘",
              "倚天屠龍記張三丰"),
    "太極劍": ("三環套月大魁星燕子抄水左攔掃右攔掃指南針持劍歸原", "倚天屠龍記張三丰"),
    "七傷拳": ("五行之氣調陰陽損心傷肺摧肝腸藏離精失意恍惚三焦齊逆兮魂魄飛揚", "倚天屠龍記崆峒派"),
    "龍爪手": ("捕風式捉影式撫琴式鼓瑟式批亢式搗虛式拿雲式搶珠式抱殘式守缺式", "倚天屠龍記少林空性"),
    "獨孤九劍": ("總訣式破劍式破刀式破槍式破鞭式破索式破掌式破箭式破氣式", "笑傲江湖風清揚"),
    "華山劍法": ("白虹貫日有鳳來儀金雁橫空截劍式金玉滿堂鐘鼓齊鳴行雲流水任意所至", "笑傲江湖令狐沖"),
    "沖靈劍法": ("青梅如豆柳葉似眉霧中初見雨後乍逢同生共死", "笑傲江湖令狐沖岳靈珊"),
    "吸星大法": ("當令丹田常如空箱恆似深谷空箱可貯物深谷可容水若有內息散之於任脈諸穴", "笑傲江湖任我行"),
    "華山論劍": ("東邪黃藥師西毒歐陽鋒南帝段智興北丐洪七公中神通王重陽東邪黃藥師西狂楊過南僧一燈北俠郭靖中頑童周伯通",
                "射鵰英雄傳神鵰俠侶"),
}


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
            raise SystemExit("patch_r9_steles: unknown option %r (DRY_RUN=1)" % a)
    return dry


def font_cmap(path):
    """Code points the font's own character map covers (TrueType 'cmap' formats 4 and 12; first face of a .ttc)."""
    with open(path, "rb") as f:
        data = f.read()
    base = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    n_tab = struct.unpack(">H", data[base + 4:base + 6])[0]
    cm = None
    for i in range(n_tab):
        rec = base + 12 + 16 * i
        if data[rec:rec + 4] == b"cmap":
            cm = struct.unpack(">I", data[rec + 8:rec + 12])[0]
    if cm is None:
        raise RuntimeError("%s has no cmap table" % path)
    cps = set()
    for i in range(struct.unpack(">H", data[cm + 2:cm + 4])[0]):
        _pid, _eid, off = struct.unpack(">HHI", data[cm + 4 + 8 * i:cm + 12 + 8 * i])
        so = cm + off
        fmt = struct.unpack(">H", data[so:so + 2])[0]
        if fmt == 4:
            n2 = struct.unpack(">H", data[so + 6:so + 8])[0]
            n = n2 // 2
            ends = struct.unpack(">%dH" % n, data[so + 14:so + 14 + n2])
            starts = struct.unpack(">%dH" % n, data[so + 16 + n2:so + 16 + 2 * n2])
            deltas = struct.unpack(">%dh" % n, data[so + 16 + 2 * n2:so + 16 + 3 * n2])
            ro = so + 16 + 3 * n2
            offs = struct.unpack(">%dH" % n, data[ro:ro + n2])
            for k in range(n):
                for c in range(starts[k], ends[k] + 1):
                    if c == 0xFFFF:
                        continue
                    if offs[k] == 0:
                        g = (c + deltas[k]) & 0xFFFF
                    else:
                        gi = ro + 2 * k + offs[k] + 2 * (c - starts[k])
                        g = struct.unpack(">H", data[gi:gi + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    if g:
                        cps.add(c)
        elif fmt == 12:
            for k in range(struct.unpack(">I", data[so + 12:so + 16])[0]):
                s, e, g0 = struct.unpack(">III", data[so + 16 + 12 * k:so + 28 + 12 * k])
                cps.update(c for c in range(s, e + 1) if g0 + (c - s))
    return cps


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def verts(me):
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def box(me):
    v = verts(me)
    return (v.min(0), v.max(0)) if len(v) else None


def fmt_box(b):
    return "(%s) .. (%s)" % (", ".join("%.3f" % x for x in b[0]), ", ".join("%.3f" % x for x in b[1]))


def same_mesh(a, b):
    """(equal vertex count, max vertex offset)."""
    if len(a.vertices) != len(b.vertices):
        return False, None
    if not len(a.vertices):
        return True, 0.0
    return True, float(np.abs(verts(a) - verts(b)).max())


def manuals_check(fails):
    by_title = {}
    for m in P.JIN_YONG_MANUALS:
        if m["title"] in by_title:
            fails.append("manual title %s twice in props.JIN_YONG_MANUALS" % m["title"])
        by_title[m["title"]] = m
    for t, m in by_title.items():
        texts = [m["title"]] + list(m["cols"]) + list(m.get("back", ()))
        if any(not s or not all(ch.isalpha() and ord(ch) > 0x2E80 for ch in s) for s in texts):
            fails.append("manual %s: empty string, punctuation, space or non-CJK character" % t)
        want = EXPECTED.get(t)
        got = ("".join(m["cols"]), "".join(m.get("back", ())))
        if want is None:
            fails.append("manual %s is not in the round-9 text" % t)
        elif got != want:
            fails.append("manual %s differs from the round-9 text" % t)
    for t in EXPECTED:
        if t not in by_title:
            fails.append("round-9 manual %s missing from props.JIN_YONG_MANUALS" % t)
    placed = [t for row in ST.STELE_MANUALS for pair in row for t in pair] + [ST.MASTER_MANUAL]
    dup = sorted({t for t in placed if placed.count(t) > 1})
    unknown = [t for t in placed if t not in by_title]
    log("manuals: %d in props, %d placed (%d steles + master), duplicates %s, unknown %s" % (
        len(by_title), len(placed), len(placed) - 1, dup or "none", unknown or "none"))
    if dup or unknown or len(placed) != 21 or len(ST.STELE_MANUALS) != len(ST.ROWS_Y):
        fails.append("STELE_MANUALS / MASTER_MANUAL do not place 21 distinct known manuals")
    return by_title


def glyph_check(chars, size, fails):
    """Every character: in simkai.ttf's cmap, a Blender glyph with faces, not the missing-glyph shape."""
    path = U.FONT_KAITI
    if os.path.basename(path).lower() != "simkai.ttf" or not os.path.exists(path):
        fails.append("KaiTi font not found at %s" % path)
        return
    cps = font_cmap(path)
    missing = [c for c in chars if ord(c) not in cps]
    log("font", path, "cmap covers %d code points;" % len(cps), "%d distinct characters in the manuals," % len(chars),
        "all in the cmap, ok" if not missing else "NOT IN THE FONT: %s" % "".join(missing))
    if missing:
        fails.append("characters missing from simkai.ttf: %s" % "".join(missing))
    ref = None
    if ord(MISSING_REF) in cps:
        log("WARN the missing-glyph reference U+%04X is in the font; tofu comparison skipped" % ord(MISSING_REF))
    else:
        me = P._text_mesh(MISSING_REF, size, 2)
        ref = (len(me.vertices), tuple(round(v, 4) for v in P._mesh_dims(me)[:2])) if len(me.vertices) else None
        log("missing-glyph reference U+%04X:" % ord(MISSING_REF), "verts %d dims %s" % ref if ref else "no geometry")
    empty, tofu, small = [], [], []
    for c in chars:
        me = P._text_mesh(c, size, 2)
        dims = P._mesh_dims(me)
        if not len(me.polygons):
            empty.append(c)
            continue
        if ref is not None and (len(me.vertices), tuple(round(v, 4) for v in dims[:2])) == ref:
            tofu.append(c)
        if max(dims.x, dims.y) < 0.55 * size:
            small.append((c, round(max(dims.x, dims.y) / size, 2)))
    log("glyphs: %d with faces; empty %s; missing-glyph shapes %s; under 55 %% of the em %s" % (
        len(chars) - len(empty), "".join(empty) or "none", "".join(tofu) or "none", small or "none"))
    if empty or tofu or small:
        fails.append("glyphs that do not render: empty %r tofu %r small %r" % (empty, tofu, small))


def place_of(inst, root_inv):
    """(row, column, side) of a stele instancer from its place in steles.root's frame; None for the master."""
    p = root_inv @ inst.matrix_world.translation
    if inst.name.startswith(ST.KEY + ".stele_master"):
        return None, p
    r = min(range(len(ST.ROWS_Y)), key=lambda k: abs(p.y - ST.ROWS_Y[k]))
    c = min(range(len(ST.COLS_X)), key=lambda k: abs(abs(p.x) - ST.COLS_X[k]))
    if abs(p.y - ST.ROWS_Y[r]) > 0.05 or abs(abs(p.x) - ST.COLS_X[c]) > 0.05:
        raise RuntimeError("%s at %s is not on a stele place" % (inst.name, tuple(round(x, 2) for x in p)))
    return (r, c, -1 if p.x < 0 else 1), p


def plan_check(me, plan, label, fails):
    """Every vertex inside a planned glyph cell on its face plane; every planned cell filled; vertex total = the sum
    of the planned glyphs' meshes."""
    v = verts(me)
    gl = plan["glyphs"]
    cen = np.array([tuple(g["centre"]) for g in gl])
    half = np.array([0.5 * g["cell"] * 1.02 for g in gl])
    hit = np.zeros(len(v), bool)
    filled = 0
    for k in range(len(gl)):
        d = np.abs(v - cen[k])
        inside = (d[:, 1] < 1e-4) & (d[:, 0] <= half[k]) & (d[:, 2] <= half[k])
        hit |= inside
        filled += bool(inside.any())
    want = sum(len(P._text_mesh(g["char"], g["cell"] * 0.86, 2).vertices) for g in gl)
    ok = hit.all() and filled == len(gl) and want == len(v)
    if not ok:
        log("  %s plan BAD: %d stray verts, %d of %d cells filled, %d verts (planned %d)" % (
            label, int((~hit).sum()), filled, len(gl), len(v), want))
        fails.append("%s: the glyph mesh does not hold exactly the planned glyphs" % label)
    return ok


def hold_report(rows):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("chase.cam")
    if cam is None:
        log("WARN no chase.cam: hold framing not checked")
        return
    f0 = sc.frame_current
    sc.frame_set(HOLD)
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    try:
        for inst, title, plan in rows:
            front = [g for g in plan["glyphs"] if g["face"] == "front"]
            M = inst.matrix_world
            ps = [world_to_camera_view(sc, cam, M @ g["centre"]) for g in front]
            inside = sum(1 for p in ps if p.z > 0 and 0 <= p.x <= 1 and 0 <= p.y <= 1)
            g = front[0]
            a = world_to_camera_view(sc, cam, M @ (g["centre"] + Vector((0, 0, g["cell"] / 2))))
            b = world_to_camera_view(sc, cam, M @ (g["centre"] - Vector((0, 0, g["cell"] / 2))))
            c = ps[0]
            log("hold %d: %-22s %-6s front glyphs in frame %3d of %3d, centre (%5.0f, %4.0f), a cell %.1f px, %.1f m" % (
                HOLD, inst.name, title, inside, len(front), c.x * 1600, (1 - c.y) * 900, abs(a.y - b.y) * 900, c.z))
    finally:
        sc.frame_set(f0)
        sc.render.resolution_x, sc.render.resolution_y = rx, ry


def main():
    dry = options()
    root = bpy.data.objects.get(ST.KEY + ".root")
    if root is None:
        raise RuntimeError("no %s.root: is this out/sect_chase.blend?" % ST.KEY)
    fails = []
    by_title = manuals_check(fails)
    insts = sorted([o for o in root.children if o.instance_type == 'COLLECTION' and o.instance_collection is not None
                    and o.name.startswith(ST.KEY + ".stele")], key=lambda o: o.name)
    if len(insts) != 21:
        raise RuntimeError("expected 21 stele instancers under %s, found %d" % (root.name, len(insts)))
    users = {}
    for o in bpy.data.objects:
        if o.instance_type == 'COLLECTION' and o.instance_collection is not None:
            users.setdefault(o.instance_collection.name, []).append(o.name)
    root_inv = root.matrix_world.inverted()

    # what goes where
    jobs = []
    for inst in insts:
        place, p = place_of(inst, root_inv)
        if place is None:
            h, glyph, seed, title = ST.MASTER_H, ST.MASTER_GLYPH, 5, ST.MASTER_MANUAL
        else:
            r, c, side = place
            h, glyph = ST.ROW_H[r], ST.ROW_GLYPHS[r]
            seed = r * 2 + c + (0 if side < 0 else 3)
            title = ST.STELE_MANUALS[r][c][0 if side < 0 else 1]
        pc = inst.instance_collection
        tag = str(pc.get(P._PROTO_TAG) or "")
        parts = tag.split(".")
        b = P._bucket(h, 4.0)[0]
        want = ["stele", P._k(b), glyph, "1", str(seed % 6), "stone_dark", "v%d" % P._VERSION]
        if parts != want:
            fails.append("%s: prototype tag %r, its place wants %r" % (inst.name, tag, ".".join(want)))
        if users.get(pc.name) != [inst.name]:
            fails.append("%s: prototype %s serves %s (needs exactly this stele)" % (inst.name, pc.name, users.get(pc.name)))
        gs = [o for o in pc.all_objects if o.type == 'MESH' and o.name.startswith("props.stele.glyphs")]
        if len(gs) != 1:
            raise RuntimeError("%s: %d glyph objects in %s" % (inst.name, len(gs), pc.name))
        side_s = "master" if place is None else "r%d c%d %s" % (place[0], place[1], "west" if place[2] < 0 else "east")
        jobs.append(dict(inst=inst, pc=pc, glyph_ob=gs[0], h=h, seed=seed, title=title, place=side_s,
                         manual=by_title.get(title)))
    if fails:
        raise RuntimeError("checks failed before any change, NOT saved: %s" % fails)

    n_obj = len(bpy.data.objects)
    pre_meshes = {m.name for m in bpy.data.meshes}
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    saved_font = U.FONT_KAITI           # absolute on the Linux box (gate._gate / patch_gate_plaque do the same)
    if os.name != "nt" and os.path.exists(os.path.abspath(saved_font)):
        U.FONT_KAITI = os.path.abspath(saved_font)
    tot_old = tot_new = 0
    grew = []
    hold_rows = []
    try:
        chars = sorted({ch for j in jobs for m in [j["manual"]] for s in [m["title"], *m["cols"], *m.get("back", ())]
                        for ch in s})
        glyph_check(chars, 0.1, fails)
        for j in jobs:
            g, m = j["glyph_ob"], j["manual"]
            old_me = g.data
            info = dict(name=old_me.name, mats=[mm.name if mm else None for mm in old_me.materials],
                        slots=[s.material.name if s.material else None for s in g.material_slots], glow=g.get("glow"),
                        shadow=g.visible_shadow, mw=[tuple(r) for r in j["inst"].matrix_world])
            classic = P.stele_glyph_mesh(TMP + ".classic", j["h"], True, j["seed"], None)
            new = P.stele_glyph_mesh(TMP + ".new", j["h"], True, j["seed"], m)
            eq_c, off_c = same_mesh(old_me, classic)
            eq_m, off_m = same_mesh(old_me, new)
            ref = box(classic)                          # the classics box (= the file's before this round)
            if eq_c and off_c < 1e-4:
                state = "classics (the fresh classics build matches, max offset %.1e m)" % off_c
            elif eq_m and off_m < 1e-4:
                state = "already this manual (a re-run)"
            else:
                bo = box(old_me)
                if bo is not None and np.abs(bo[0] - ref[0]).max() < 1e-3 and np.abs(bo[1] - ref[1]).max() < 1e-3:
                    state = "classics by box (tessellation differs: %d vs %d verts)" % (len(old_me.vertices),
                                                                                        len(classic.vertices))
                    log("WARN %s: %s" % (g.name, state))
                else:
                    state = "UNKNOWN"
                    fails.append("%s: the file's glyphs are neither the classics nor this manual" % g.name)
            plan = P.stele_glyph_plan(j["h"], True, m)
            label = "%s (%s)" % (j["inst"].name, m["title"])
            plan_check(new, plan, label, fails)
            nb = box(new)
            g_grew = bool(np.any(nb[0] < ref[0] - BOX_TOL) or np.any(nb[1] > ref[1] + BOX_TOL))
            if g_grew:
                grew.append(g.name)
            t_old, t_new = tris(old_me), tris(new)
            tot_old += t_old
            tot_new += t_new
            cells = {f: next((x["cell"] for x in plan["glyphs"] if x["face"] == f), 0.0) for f in ("front", "back", "crown")}
            log("stele %-22s %-14s %-6s seed %2d  %s" % (j["inst"].name, j["place"], m["title"], j["seed"], state))
            log("      crown %s | front %s | back %s" % ("/".join(P.title_lines(m["title"])), " ".join(m["cols"]),
                                                       " ".join(m.get("back", ()))))
            log("      cells: front %.3f m (%.2f of the grid's %.3f), back %.3f, crown %.3f (local); tris %d -> %d; box %s %s" % (
                cells["front"], cells["front"] / plan["grid"], plan["grid"], cells["back"], cells["crown"], t_old, t_new,
                fmt_box(nb), "GREW past the classics box" if g_grew else "inside the classics box"))
            # swap the new data in
            for mm in old_me.materials:
                new.materials.append(mm)
            g.data = new
            bpy.data.meshes.remove(classic)
            if old_me.users == 0:
                bpy.data.meshes.remove(old_me)
            else:
                log("WARN old mesh %s still has %d users; kept" % (old_me.name, old_me.users))
            new.name = info["name"]
            if new.name != info["name"]:
                fails.append("%s: mesh name %s taken" % (g.name, info["name"]))
            after = dict(name=new.name, mats=[mm.name if mm else None for mm in new.materials],
                         slots=[s.material.name if s.material else None for s in g.material_slots], glow=g.get("glow"),
                         shadow=g.visible_shadow, mw=[tuple(r) for r in j["inst"].matrix_world])
            for k in info:
                if info[k] != after[k]:
                    fails.append("%s: %s changed %r -> %r" % (g.name, k, info[k], after[k]))
            hold_rows.append((j["inst"], m["title"], plan))
    finally:
        U.FONT_KAITI = saved_font
        for me in list(bpy.data.meshes):              # temporary and glyph cache meshes made by this run (orphans)
            if me.users == 0 and me.name not in pre_meshes and (me.name.startswith(TMP) or
                                                               me.name.startswith("props.txt.")):
                bpy.data.meshes.remove(me)
        if not had_eval:
            esc = bpy.data.scenes.get(P._EVAL_SCENE)
            if esc is not None and esc != bpy.context.scene:
                bpy.data.scenes.remove(esc)
    bpy.context.view_layer.update()

    log("glyph triangles over the 21 steles %d -> %d (%+.0f %%)" % (tot_old, tot_new,
                                                                   100.0 * (tot_new - tot_old) / max(1, tot_old)))
    if len(bpy.data.objects) != n_obj:
        fails.append("object count changed %d -> %d" % (n_obj, len(bpy.data.objects)))
    hold_report(hold_rows)
    if grew:
        log("CACHES needs audit: glyph boxes grew past the classics they replace (%s) - run the export audit and "
            "chunks,meta, then re-bake the steles and backdrop chunks" % ", ".join(grew))
    else:
        log("CACHES ok: same names and every glyph mesh's box inside the classics box it replaces; re-bake the steles "
            "and backdrop chunks for the new glyphs")
    if fails:
        raise RuntimeError("checks failed, NOT saved: %s" % fails)
    if dry:
        log("DRY_RUN: checks passed, not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
