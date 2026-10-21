"""Re-letter the Jade Slip Pavilion's great jade scroll with Jin Yong (round 8, lane 'scrolltext'): bring an existing
out/sect_chase.blend to the design in sect/areas/scroll.py (SCROLL_TEXT = props.JIN_YONG_VERSES) and save it. Run on
the cloud box (on a copy first; after patch_r5_scroll.py, though it only needs scroll.jade_scroll):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --fetch-blend --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r8_scrolltext.py [-- DRY_RUN=1]

What it does (a fresh build makes the same through scroll.build): the slips of scroll.jade_scroll used to carry the
Qing Jing Jing (props.CLASSICS[3]) over and over. Now they carry nine Jin Yong passages, one after another, read top to
bottom and right to left from the scroll's right end, each passage from the top of a new slip, no punctuation; after
the ninth a blank slip and the nine again; the two slips by the roll stay blank (props.passage_columns). Only the mesh
of scroll.jade_scroll.script changes: a fresh scroll is built with props.bamboo_slip_scroll in a temporary collection
and its script mesh replaces the old one (same object, name, parent, transform, material, glow, shadow flag); the
temporary objects and meshes are deleted again. No object is added, removed or moved.

Checks before saving (it stops without saving when one fails): the nine passages in props.JIN_YONG_VERSES are exactly
the ones asked for, in order; every character is in simkai.ttf's own character map and its Blender glyph has faces and
is not the font's missing-glyph shape; the freshly built slips match the file's (so the new script sits on them); each
slip carries exactly its planned column (glyphs from the top of the slip down to its last character, blank slips
empty); the object count is unchanged. It logs the layout, the triangle counts, and at the hold camera (1103) which
slips are in frame and how tall a glyph lands.

Caches: export_web keys its caches on object names and boxes pieces by their bound box. The name stays; when the new
script's world box lies inside the old one (2 mm tolerance) it prints 'PATCH CACHES ok', else 'PATCH CACHES needs
audit' (run the export audit and chunks,meta). Either way re-bake the scroll chunk for the new glyphs.

Idempotent: every run rebuilds the script mesh from scratch and frees the replaced one.
"""
import math
import os
import struct
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402
from sect.lib import props as P  # noqa: E402
from sect.lib import util as U  # noqa: E402

SCROLL = SC.K + ".jade_scroll"
PARTS = ("slips", "script", "cords")
TMP = "_tmp_r8_scrolltext"
HOLD = 1103
BOX_TOL = 2e-3
MISSING_REF = "\u0e01"      # Thai ko kai: not in KaiTi's character map, so Blender draws the font's missing glyph
# The passages as given for round 8 (punctuation only for reference; stripped before comparing).
EXPECTED = [
    "武林至尊，寶刀屠龍，號令天下，莫敢不從！倚天不出，誰與爭鋒？",
    "焚我殘軀，熊熊聖火，生亦何歡，死亦何苦？為善除惡，惟光明故，喜樂悲愁，皆歸塵土。憐我世人，憂患實多！",
    "他強由他強，清風拂山岡；他橫由他橫，明月照大江。",
    "重劍無鋒，大巧不工。",
    "劍魔獨孤求敗既無敵於天下，乃埋劍於斯。嗚呼！群雄束手，長劍空利，不亦悲夫！",
    "問世間，情是何物，直教生死相許？",
    "天之道，損有餘而補不足，是故虛勝實，不足勝有餘。",
    "歸妹趨無妄，無妄趨同人，同人趨大有。",
    "俠之大者，為國為民。",
]


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
            raise SystemExit("patch_r8_scrolltext: unknown option %r (DRY_RUN=1)" % a)
    return dry


def strip(s):
    return "".join(ch for ch in s if ch.isalpha())


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


def scroll_dims():
    """props.bamboo_slip_scroll's slip count, column height (characters), cell and arc for scroll.py's scroll."""
    W, H = SC.SCROLL_W, SC.SCROLL_H
    N = max(8, int(round(W / (H * 0.075))))
    pitch = W / N
    sw, st = pitch * 0.88, pitch * 0.16
    cell = sw * 0.80
    rows = int(H * 0.84 / cell)
    d = max(1e-4, SC.SCROLL_CURVE * W)
    R = (W * W / 4 + d * d) / (2 * d)
    half = math.asin(min(1.0, W / 2 / R))
    return dict(N=N, rows=rows, cell=cell, st=st, R=R, half=half)


def children_parts(root):
    out = {}
    for k in PARTS:
        ob = next((c for c in root.children if c.name == root.name + "." + k), None)
        if ob is None or ob.type != 'MESH':
            raise RuntimeError("%s.%s missing or not a mesh; children %s" % (
                root.name, k, [c.name for c in root.children]))
        out[k] = ob
    return out


def world_box(ob):
    M = ob.matrix_world
    pts = [M @ v.co for v in ob.data.vertices]
    if not pts:
        return None
    return (tuple(min(p[k] for p in pts) for k in range(3)), tuple(max(p[k] for p in pts) for k in range(3)))


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def fmt_box(b):
    return "(%s) .. (%s)" % (", ".join("%.3f" % v for v in b[0]), ", ".join("%.3f" % v for v in b[1]))


def verse_check(fails):
    want = [strip(s) for s in EXPECTED]
    got = [strip(s) for s in P.JIN_YONG_VERSES]
    if got != list(P.JIN_YONG_VERSES):
        fails.append("props.JIN_YONG_VERSES carries punctuation or spaces")
    if got != want:
        bad = [i + 1 for i in range(max(len(got), len(want)))
               if i >= len(got) or i >= len(want) or got[i] != want[i]]
        fails.append("props.JIN_YONG_VERSES differ from the passages asked for (passages %s)" % bad)
    if list(SC.SCROLL_TEXT) != list(P.JIN_YONG_VERSES):
        fails.append("scroll.SCROLL_TEXT is not props.JIN_YONG_VERSES")
    log("verses: %d passages, %s characters" % (len(got), "+".join(str(len(t)) for t in got)),
        "match the round-8 list, ok" if got == want else "DO NOT MATCH")


def layout_check(cols, dims, fails):
    """Log the planned columns and check the passages read in order, each from the top of a column."""
    rows, N = dims["rows"], dims["N"]
    log("layout: %d slips x %d characters (cell %.3f m unscaled, %.3f m at %.1fx); reading column 0 = the rightmost "
        "slip (slip index %d)" % (N, rows, dims["cell"], dims["cell"] * SC.SCROLL_SCALE, SC.SCROLL_SCALE, N - 1))
    for j, t in enumerate(cols):
        log("  column %2d  slip %2d  %2d  %s" % (j, N - 1 - j, len(t), t if t else "(blank)"))
    verses = [strip(s) for s in SC.SCROLL_TEXT]
    j, cycles, ok = 0, 0, True
    while j < N:
        if not cols[j]:
            j += 1
            continue
        for v in verses:                                    # a cycle: every passage, in order, each from a column top
            need = -(-len(v) // rows)
            if j + need > N or "".join(cols[j:j + need]) != v or any(len(c) != rows for c in cols[j:j + need - 1]):
                ok = False
                break
            j += need
        if not ok:
            break
        cycles += 1
    filled = sum(len(c) for c in cols)
    log("layout: %d whole cycle(s) of the nine passages, %d of %d cells written, blank slips at reading columns %s" % (
        cycles, filled, N * rows, [k for k, c in enumerate(cols) if not c]), "ok" if ok and cycles >= 1 else "BAD")
    if not ok or cycles < 1:
        fails.append("the planned columns do not read as the passages in order")


def glyph_check(chars, size, fails):
    """Every character: in simkai.ttf's cmap, a Blender glyph with faces, not the missing-glyph shape."""
    path = U.FONT_KAITI
    if os.path.basename(path).lower() != "simkai.ttf" or not os.path.exists(path):
        fails.append("KaiTi font not found at %s" % path)
        return
    cps = font_cmap(path)
    missing = [c for c in chars if ord(c) not in cps]
    log("font", path, "cmap covers %d code points;" % len(cps), "%d distinct characters in the verses," % len(chars),
        "all in the cmap, ok" if not missing else "NOT IN THE FONT: %s" % "".join(missing))
    if missing:
        fails.append("characters missing from simkai.ttf: %s" % "".join(missing))
    if ord(MISSING_REF) in cps:
        log("WARN the missing-glyph reference U+%04X is in the font; tofu comparison skipped" % ord(MISSING_REF))
        ref = None
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


def slips_match(old, new, fails):
    """The freshly built slips must be the file's slips (same builder, size and frame): then the script sits on them."""
    a, b = old.data.vertices, new.data.vertices
    if len(a) != len(b):
        log("slips: file %d verts, fresh build %d" % (len(a), len(b)), "DIFFER")
        fails.append("the fresh slips differ from the file's (vertex count)")
        return
    d = max(((v.co - w.co).length for v, w in zip(a, b)), default=0.0)
    log("slips: fresh build vs file, %d verts, max offset %.6f m" % (len(a), d), "ok" if d < 1e-4 else "DIFFER")
    if d >= 1e-4:
        fails.append("the fresh slips differ from the file's (max offset %.4f m)" % d)


def columns_check(script, cols, dims, fails):
    """Glyph vertices per slip (scroll frame, by plan angle): a blank slip has none; a written one has glyphs from its
    top cell down to the cell of its last character and none below."""
    N, rows, cell, R, half = dims["N"], dims["rows"], dims["cell"], dims["R"], dims["half"]
    top = rows * cell / 2.0
    per = [[] for _ in range(N)]
    stray = 0
    for v in script.data.vertices:
        a = math.atan2(v.co.x, v.co.y + R)
        i = int(math.floor((a + half) / (2.0 * half) * N))
        if 0 <= i < N:
            per[i].append(v.co.z)
        else:
            stray += 1
    bad = []
    for i in range(N):
        t = cols[N - 1 - i]
        zs = per[i]
        if not t:
            if zs:
                bad.append((i, "blank slip has %d verts" % len(zs)))
            continue
        if not zs:
            bad.append((i, "no glyphs"))
            continue
        lo, hi = min(zs), max(zs)
        last_c = top - (len(t) - 0.5) * cell
        if hi > top + 1e-3 or hi < top - cell or lo < top - len(t) * cell - 1e-3 or lo > last_c:
            bad.append((i, "z %.3f .. %.3f, wanted %d cells: top %.3f, last centre %.3f" % (
                lo, hi, len(t), top, last_c)))
    log("columns: %d slips checked against the plan, %d stray verts;" % (N, stray),
        "every slip carries its column, ok" if not bad and not stray else "BAD %s" % bad[:6])
    if bad or stray:
        fails.append("the script mesh does not follow the planned columns")


def hold_report(script, dims):
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
        N, rows, cell, R, half = dims["N"], dims["rows"], dims["cell"], dims["R"], dims["half"]
        M = script.matrix_world                              # the mesh is in the scroll's own (builder) frame
        top = rows * cell / 2.0
        seen, px = [], []
        for i in range(N):
            a = -half + 2 * half * (i + 0.5) / N
            x, y = R * math.sin(a), -R + R * math.cos(a)
            p0 = world_to_camera_view(sc, cam, M @ Vector((x, y, top - 0.5 * cell)))
            p1 = world_to_camera_view(sc, cam, M @ Vector((x, y, top - 1.5 * cell)))
            pl = world_to_camera_view(sc, cam, M @ Vector((x, y, -top + 0.5 * cell)))
            if p0.z > 0 and all(0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 for p in (p0, pl)):
                seen.append(i)
                px.append(abs(p0.y - p1.y) * 900)
        if seen:
            log("hold %d 1600x900: slips %d .. %d of 0 .. %d in frame (reading columns %d .. %d); a character cell is "
                "%.1f .. %.1f px tall there" % (HOLD, seen[0], seen[-1], N - 1, N - 1 - seen[-1], N - 1 - seen[0],
                                                min(px), max(px)))
        else:
            log("hold %d: no slip fully in frame" % HOLD)
        vs = script.data.vertices
        pts = [world_to_camera_view(sc, cam, script.matrix_world @ vs[k].co) for k in range(0, len(vs), 7)]
        log("hold %d 1600x900: script x %.0f .. %.0f, y %.0f .. %.0f" % (
            HOLD, min(p.x for p in pts) * 1600, max(p.x for p in pts) * 1600, min(1 - p.y for p in pts) * 900,
            max(1 - p.y for p in pts) * 900))
    finally:
        sc.frame_set(f0)
        sc.render.resolution_x, sc.render.resolution_y = rx, ry


def main():
    dry = options()
    js = bpy.data.objects.get(SCROLL)
    if js is None:
        raise RuntimeError("no %s: is this out/sect_chase.blend?" % SCROLL)
    parts = children_parts(js)
    script = parts["script"]
    log("scroll", SCROLL, "at", tuple(round(c, 3) for c in js.location), "turn %.1f deg" %
        math.degrees(js.rotation_euler.z), "scale %.3f" % js.scale[0], "(not moved)")
    fails = []
    dims = scroll_dims()
    verse_check(fails)
    cols = P.passage_columns(SC.SCROLL_TEXT, dims["N"], dims["rows"])
    layout_check(cols, dims, fails)
    chars = sorted(set("".join(cols)))
    size = dims["cell"] * 0.86                               # props._text_columns' glyph size

    n_obj = len(bpy.data.objects)
    pre_meshes = {m.name for m in bpy.data.meshes}
    had_eval = bpy.data.scenes.get(P._EVAL_SCENE) is not None
    before = world_box(script)
    if before is None:
        raise RuntimeError("%s has no vertices: nothing to compare the new script with" % script.name)
    old_me = script.data
    old_info = dict(name=old_me.name, verts=len(old_me.vertices), tris=tris(old_me),
                    slots=[s.material.name if s.material else None for s in script.material_slots],
                    glow=script.get("glow"), shadow=script.visible_shadow,
                    attrs=sorted(a.name for a in old_me.attributes if not a.name.startswith(".")))
    log("script before:", old_info)

    saved_font = U.FONT_KAITI           # absolute on the Linux box (gate._gate / patch_gate_plaque do the same)
    if os.name != "nt" and os.path.exists(os.path.abspath(saved_font)):
        U.FONT_KAITI = os.path.abspath(saved_font)
    tmp = bpy.data.collections.new(TMP)
    bpy.context.scene.collection.children.link(tmp)
    try:
        glyph_check(chars, size, fails)
        new_root = P.bamboo_slip_scroll(tmp, SC.SCROLL_W, SC.SCROLL_H, curve=SC.SCROLL_CURVE, glow=True, seed=3,
                                        rolled=True, name=TMP + ".scroll", passages=SC.SCROLL_TEXT)
        new = children_parts(new_root)
        slips_match(parts["slips"], new["slips"], fails)
        src = new["script"]
        me = src.data
        src.data = bpy.data.meshes.new(TMP + ".empty")
        me.name = old_me.name + ".new"
        script.data = me
        for s in script.material_slots:
            if s.link != 'DATA':
                s.link = 'DATA'
        if old_me.users == 0:
            bpy.data.meshes.remove(old_me)
        else:
            log("WARN old mesh still has %d users; kept" % old_me.users)
        me.name = script.name
        if me.name != script.name:
            log("WARN mesh name taken: the new mesh is", me.name)
        if src.get("glow") != old_info["glow"]:
            log("WARN fresh glow %s, the file's %s (kept the file's)" % (src.get("glow"), old_info["glow"]))
    finally:
        U.FONT_KAITI = saved_font
        for ob in list(tmp.all_objects):
            m = ob.data if ob.type == 'MESH' else None
            bpy.data.objects.remove(ob, do_unlink=True)
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)
        bpy.data.collections.remove(tmp)
        for m in list(bpy.data.meshes):              # glyph cache meshes made by this run (orphans)
            if m.users == 0 and m.name not in pre_meshes and m.name.startswith("props.txt."):
                bpy.data.meshes.remove(m)
        if not had_eval:
            esc = bpy.data.scenes.get(P._EVAL_SCENE)
            if esc is not None and esc != bpy.context.scene:
                bpy.data.scenes.remove(esc)
    bpy.context.view_layer.update()

    # checks
    me = script.data
    new_info = dict(name=me.name, verts=len(me.vertices), tris=tris(me),
                    slots=[s.material.name if s.material else None for s in script.material_slots],
                    glow=script.get("glow"), shadow=script.visible_shadow,
                    attrs=sorted(a.name for a in me.attributes if not a.name.startswith(".")))
    log("script after: ", new_info)
    log("triangles %d -> %d (%+.0f %%)" % (old_info["tris"], new_info["tris"],
                                          100.0 * (new_info["tris"] - old_info["tris"]) / max(1, old_info["tris"])))
    for k in ("name", "slots", "glow", "shadow", "attrs"):
        if new_info[k] != old_info[k]:
            fails.append("script %s changed: %r -> %r" % (k, old_info[k], new_info[k]))
    if not len(me.polygons):
        fails.append("the new script mesh is empty")
    if len(bpy.data.objects) != n_obj:
        fails.append("object count changed %d -> %d" % (n_obj, len(bpy.data.objects)))
    columns_check(script, cols, dims, fails)
    hold_report(script, dims)

    after = world_box(script)
    grew = after is None or any(b < a - BOX_TOL for a, b in zip(before[0], after[0])) or \
        any(b > a + BOX_TOL for a, b in zip(before[1], after[1]))
    log("box", script.name, "before", fmt_box(before), "after", fmt_box(after) if after else None)
    if grew:
        log("CACHES needs audit: %s's world box grew past the old one - run the export audit and chunks,meta, then "
            "re-bake the scroll chunk" % script.name)
    else:
        log("CACHES ok: same names and %s's world box inside the old one; re-bake the scroll chunk for the new glyphs"
            % script.name)
    if fails:
        raise RuntimeError("checks failed, NOT saved: %s" % fails)
    if dry:
        log("DRY_RUN: checks passed, not saved")
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects))


main()
