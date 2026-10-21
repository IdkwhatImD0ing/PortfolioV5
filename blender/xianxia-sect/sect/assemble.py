"""Assemble the Moonlit Sect: world + the 11 areas + the fly-through camera -> out/sect.blend.

    blender --background --factory-startup --python sect/assemble.py -- \\
        [--quality blocking|preview] [--out out/sect.blend] [--stills] [--strips] [--reuse]
        [--no-save] [--no-check] [--only gate,mirror]

- a fresh scene; look.setup_render with the chosen quality (default 'blocking', see
  QUALITY_BLOCKING) and look.setup_lookdev (golden-hour sky, sun, compositor);
- world.build(scene, anchors) (sky, moon, haze, the floating range, clouds, islets, links);
- every area module's build() into its own collection named after its key; the root Empty is
  moved to the anchor and turned by the area's yaw so its front (local -Y) faces the incoming
  camera (camera.area_yaws). A module that fails to import or build is logged and replaced by a
  labelled stand-in block, and assembly continues;
- camera.build(): the one fly-through camera, frame range, out/section_timeline.json;
- prints ASSEMBLE_AREA / ASSEMBLE_STATS lines (evaluated triangles, build times), saves the
  .blend (fonts packed so it opens anywhere);
- --stills renders out/stills/seg<NN>_start|end.png, hero_<area>.png and the one-frame-per-second
  contact frames (out/tmp/assembly/contact/, tiled into out/stills/contact_sheet.png when PIL or
  numpy tiling works);
- --reuse opens the saved .blend instead of rebuilding (camera / stills iteration).

Full blocking render, frames kept on the cloud box (no copy back):
    python tools/rblender.py --sh "/root/blender/blender --factory-startup -b out/sect.blend -y -o //frames/#### -a"
"""

import argparse
import importlib
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # on the cloud box this is the '/E:/...' mirror
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from sect.lib import look as L  # noqa: E402
from sect.lib import util as U  # noqa: E402
from sect import camera as C  # noqa: E402

# Blocking render quality: ~1 s per 1280x720 frame on the cloud RTX 5090 with the full scene.
# Low TAA, coarse ray tracing / GI / shadows, no motion blur, cheap bloom. Volumes stay fine
# (4 px tiles, 64 samples): 16 px / 24 samples printed a regular blotchy cell pattern over the
# opening cloud (review), and the finer setting measured the same ~1.05 s per still.
QUALITY_BLOCKING = dict(samples=6, rt_resolution="4", trace_quality=0.2, fast_gi_resolution="4",
                        fast_gi_steps=4, shadow_rays=1, shadow_steps=4, shadow_pool="512",
                        vol_tile="4", vol_samples=64, vol_shadow_samples=4, motion_blur=False,
                        glare_quality="Low", sun_jitter=False, overscan=False)
L.QUALITY["blocking"] = QUALITY_BLOCKING
RESOLUTION = (1280, 720)
CONTACT_RES = (480, 270)


def log(*a):
    print("ASSEMBLE", *a, flush=True)


def _abs(p):
    if p is None:
        return None
    p = p.replace("\\", "/")
    if os.path.isabs(p) and not (len(p) > 1 and p[1] == ":" and os.name != "nt"):
        return p
    if len(p) > 1 and p[1] == ":":            # 'E:/...' on the cloud box -> the mirror
        return os.path.abspath(p) if os.name != "nt" else p
    return os.path.join(ROOT, p).replace("\\", "/")


# ------------------------------------------------------------------------------------------
# fonts: util.load_font hands Blender 'C:/Windows/Fonts/...' which only resolves on Windows.
# On the box, load the absolute mirror path ('/C:/Windows/Fonts/...'). Patched here, not in lib.
# ------------------------------------------------------------------------------------------

def fix_fonts():
    if os.name == "nt" or getattr(U, "_assemble_font_fix", False):
        return
    orig = U.load_font

    def load_font(path=None):
        p = path or U.FONT_KAITI
        cands = [p, U.FONT_KAITI, U.FONT_YAHEI]
        for c in cands:
            if not c:
                continue
            a = os.path.abspath(c)
            if os.path.exists(a):
                try:
                    return bpy.data.fonts.load(a, check_existing=True)
                except RuntimeError:
                    continue
        try:
            return orig(p)
        except RuntimeError:
            return bpy.data.fonts.get("Bfont Regular")

    U.load_font = load_font
    for attr in ("FONT_KAITI", "FONT_YAHEI"):
        v = getattr(U, attr, None)
        if v and not os.path.isabs(v):
            setattr(U, attr, os.path.abspath(v))
    U._assemble_font_fix = True
    log("font fix: util.load_font loads absolute paths", U.FONT_KAITI)


# ------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------

def anchors_with_yaw():
    from sect import world as W
    anchors = {k: tuple(v[:4]) for k, v in W.ANCHORS.items()}
    yaws = C.area_yaws(anchors)
    return {k: anchors[k] + (yaws[k],) for k in C.ORDER if k in anchors}


def _standin(coll, key, anchor, reason):
    """Labelled red block with a teal roof where an area failed."""
    import bmesh
    U.clear_collection(coll)
    fp = anchor[3]
    root = U.empty(key + ".root", coll, display_size=4.0)
    bm = bmesh.new()
    U.bm_box(bm, (fp * 0.9, fp * 0.5, 14.0), center=(0.0, 0.0, 7.0))
    U.mesh_from_bmesh(key + ".standin", bm, coll, materials=["lacquer_red"], parent=root)
    bm = bmesh.new()
    U.bm_cylinder(bm, radius=fp * 0.6, depth=8.0, segments=4, center=(0.0, 0.0, 18.0), radius_top=1.0)
    U.mesh_from_bmesh(key + ".standin_roof", bm, coll, materials=["roof_tile_teal"], parent=root,
                      rotation=(0.0, 0.0, math.pi / 4))
    try:
        U.text(key + ".standin_label", "MISSING %s" % key, coll, size=5.0, extrude=0.2,
               material="gold", location=(0.0, -fp * 0.25 - 0.6, 7.0), parent=root)
    except Exception as exc:
        log("WARN stand-in label for", key, exc)
    root["standin_reason"] = str(reason)[:500]
    return root


def build_areas(scene, anchors, only=None):
    modules, report = {}, {}
    for key in C.ORDER:
        a = anchors[key]
        coll = U.get_collection(key, scene=scene)
        t0 = time.perf_counter()
        mod, root, err = None, None, None
        try:
            mod = importlib.import_module("sect.areas." + key)
        except Exception:
            err = traceback.format_exc()
        if mod is not None and (only is None or key in only):
            try:
                root = mod.build(coll)
            except Exception:
                err = traceback.format_exc()
        elif mod is not None:
            err = "skipped (--only)"
        if root is None:
            log("AREA FAILED", key, "\n" + (err or "build returned None"))
            root = _standin(coll, key, a, err)
        modules[key] = mod
        root.location = (a[0], a[1], a[2])
        root.rotation_mode = "XYZ"
        root.rotation_euler = (0.0, 0.0, a[4])
        report[key] = dict(ok=err is None, build_s=round(time.perf_counter() - t0, 2),
                           yaw_deg=round(math.degrees(a[4]), 1), objects=len(coll.all_objects))
    bpy.context.view_layer.update()
    for key in C.ORDER:
        try:
            report[key]["triangles"] = U.evaluated_triangle_count(bpy.data.collections[key])
        except Exception as exc:
            report[key]["triangles"] = "error: %s" % exc
        log("AREA", key, json.dumps(report[key]))
    return modules, report


# ------------------------------------------------------------------------------------------
# clouds: world.py's mid-level cloud banks are 320-460 m wide and some of their puffs reach up
# into the area plazas (forge, mission...) and across the flight line, which veils the hero
# frames in blotchy fog. Lower those puffs (never delete them) so they float under the terraces.
# ------------------------------------------------------------------------------------------

CLOUD_KEEP = ("opening", "stairfoot")      # the opening bank is meant to be flown through


def _cloud_objects(scene):
    return [ob for ob in scene.objects if ob.type == "MESH" and ob.name.startswith("world.cloud.")
            and not any(k in ob.name for k in CLOUD_KEEP)]


def _wbbox(ob):
    import numpy as np
    mw = np.array(ob.matrix_world)
    bb = np.array([tuple(c) for c in ob.bound_box]) @ mw[:3, :3].T + mw[:3, 3]
    return bb.min(0), bb.max(0)


def _lower(ob, dz):
    from mathutils import Matrix
    ob.matrix_world = Matrix.Translation((0.0, 0.0, -dz)) @ ob.matrix_world


def clear_clouds_areas(scene, anchors, pad=35.0, below=12.0, above=90.0):
    """Lower cloud puffs whose box reaches into an area's airspace (footprint + pad around the
    anchor, from anchor z - below to anchor z + above) until their top is under anchor z - below."""
    moved = {}
    for _ in range(4):
        bpy.context.view_layer.update()
        changed = False
        for ob in _cloud_objects(scene):
            lo, hi = _wbbox(ob)
            need = 0.0
            for k, a in anchors.items():
                x, y, z, fp = a[:4]
                dx = max(lo[0] - x, 0.0, x - hi[0])
                dy = max(lo[1] - y, 0.0, y - hi[1])
                if math.hypot(dx, dy) < fp + pad and hi[2] > z - below and lo[2] < z + above:
                    need = max(need, hi[2] - (z - below))
            if need > 0.01:
                _lower(ob, need + 0.5)
                moved[ob.name] = round(moved.get(ob.name, 0.0) + need + 0.5, 1)
                changed = True
        if not changed:
            break
    bpy.context.view_layer.update()
    log("CLOUDS lowered under area airspace:", len(moved), json.dumps(moved))
    return moved


def clear_clouds_path(scene, pos, shrink=0.15, gap=12.0):
    """Lower puffs the camera would fly through (box shrunk by `shrink` per side)."""
    import numpy as np
    moved = {}
    bpy.context.view_layer.update()
    for ob in _cloud_objects(scene):
        lo, hi = _wbbox(ob)
        d = (hi - lo) * shrink
        inside = np.all((pos >= lo + d) & (pos <= hi - d), axis=1)
        if inside.any():
            zmin = float(pos[inside, 2].min())
            need = hi[2] - (zmin - gap)
            if need > 0.01:
                _lower(ob, need)
                moved[ob.name] = [round(need, 1), int(np.flatnonzero(inside)[0]) + C.FRAME_START]
    bpy.context.view_layer.update()
    log("CLOUDS lowered under the flight path:", len(moved), json.dumps(moved))
    return moved


def import_modules():
    mods = {}
    for key in C.ORDER:
        try:
            mods[key] = importlib.import_module("sect.areas." + key)
        except Exception:
            log("WARN import", key, traceback.format_exc())
            mods[key] = None
    return mods


def setup_quality(scene, quality):
    L.setup_render(scene, quality, RESOLUTION)
    L.setup_compositor(scene, quality=quality)


def build_all(args):
    t_all = time.perf_counter()
    fix_fonts()
    L.reset_scene()
    scene = bpy.context.scene
    scene.name = "sect"
    L.setup_render(scene, args.quality, RESOLUTION)
    L.setup_lookdev(scene, haze=False, compositor=True, cloud_floor=True)
    anchors = anchors_with_yaw()
    stats = dict(quality=args.quality)
    t0 = time.perf_counter()
    try:
        from sect import world as W
        W.build(scene, anchors)
        stats["world_ok"] = True
    except Exception:
        log("WORLD FAILED\n" + traceback.format_exc())
        stats["world_ok"] = False
    stats["world_s"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    modules, areas = build_areas(scene, anchors, only=args.only)
    stats["areas_s"] = round(time.perf_counter() - t0, 2)
    stats["clouds_lowered_areas"] = len(clear_clouds_areas(scene, anchors))
    stats["areas"] = areas
    stats["build_s"] = round(time.perf_counter() - t_all, 2)
    return scene, anchors, modules, stats


def scene_triangles(scene):
    try:
        w = U.evaluated_triangle_count(bpy.data.collections["world"])
    except Exception:
        w = None
    return dict(total=U.evaluated_triangle_count(None), world=w)


# ------------------------------------------------------------------------------------------
# stills
# ------------------------------------------------------------------------------------------

def _render(scene, frame, path):
    scene.frame_set(frame)
    scene.render.filepath = path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return round(time.perf_counter() - t, 2)


def render_stills(scene, tl, contact=True):
    stills_dir = os.path.join(ROOT, "out", "stills")
    contact_dir = os.path.join(ROOT, "out", "tmp", "assembly", "contact")
    os.makedirs(stills_dir, exist_ok=True)
    os.makedirs(contact_dir, exist_ok=True)
    jobs = {}
    for g in tl["segments"]:
        jobs.setdefault(g["frame_start"], []).append("seg%02d_start.png" % g["index"])
        jobs.setdefault(g["frame_end"], []).append("seg%02d_end.png" % g["index"])
    for s in tl["sections"]:
        jobs.setdefault(s["hero_frame"], []).append("hero_%s.png" % s["area"])
    times = {}
    files = []
    import shutil
    for f in sorted(jobs):
        names = jobs[f]
        first = os.path.join(stills_dir, names[0])
        times[f] = _render(scene, f, first)
        files.append(first)
        for nm in names[1:]:
            shutil.copyfile(first, os.path.join(stills_dir, nm))
            files.append(os.path.join(stills_dir, nm))
        log("STILL", f, names, times[f], "s")
    contact_files = []
    if contact:
        r = scene.render
        old = (r.resolution_x, r.resolution_y)
        r.resolution_x, r.resolution_y = CONTACT_RES
        fr = list(range(tl["frame_start"], tl["frame_end"] + 1, C.FPS))
        for i, f in enumerate(fr):
            p = os.path.join(contact_dir, "c%03d.png" % i)
            _render(scene, f, p)
            contact_files.append(p)
        r.resolution_x, r.resolution_y = old
        log("CONTACT", len(contact_files), "frames at 1 fps in", contact_dir)
        try:
            tile_contact(contact_files, os.path.join(stills_dir, "contact_sheet.png"))
        except Exception:
            log("WARN contact sheet tiling failed\n" + traceback.format_exc())
    rt = sorted(times.values())
    log("RENDER_TIMES", json.dumps(dict(first=rt[-1] if rt else None,
                                        median=rt[len(rt) // 2] if rt else None, n=len(rt))))
    return files, contact_files


def render_strips(scene, tl, offsets=(-24, -12, 12, 24), res=(640, 360)):
    """Review aid: frames around every hero frame plus the opening second, small, into
    out/previews/assembly/ (strip_<area>_<frame>.png, open_<frame>.png)."""
    out_dir = os.path.join(ROOT, "out", "previews", "assembly")
    os.makedirs(out_dir, exist_ok=True)
    r = scene.render
    old = (r.resolution_x, r.resolution_y)
    r.resolution_x, r.resolution_y = res
    n = 0
    for f in (1, 8, 16, 24, 36):
        _render(scene, f, os.path.join(out_dir, "open_%04d.png" % f))
        n += 1
    for s in tl["sections"]:
        for d in (0,) + tuple(offsets):
            f = min(max(s["hero_frame"] + d, tl["frame_start"]), tl["frame_end"])
            _render(scene, f, os.path.join(out_dir, "strip_%s_%04d.png" % (s["area"], f)))
            n += 1
    r.resolution_x, r.resolution_y = old
    log("STRIPS", n, "frames in", out_dir)


def tile_contact(files, out_path, cols=8):
    """Tile the contact frames into one PNG with numpy (no PIL / ffmpeg needed on the box)."""
    import numpy as np
    w, h = CONTACT_RES
    rows = int(math.ceil(len(files) / cols))
    sheet = np.zeros((rows * (h + 4) + 4, cols * (w + 4) + 4, 4), np.float32)
    sheet[..., 3] = 1.0
    for i, p in enumerate(files):
        img = bpy.data.images.load(p, check_existing=False)
        px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(img.size[1], img.size[0], 4)       # bottom-up rows
        bpy.data.images.remove(img)
        r, c = divmod(i, cols)
        y0 = (rows - 1 - r) * (h + 4) + 4                  # image origin is bottom-left
        x0 = c * (w + 4) + 4
        sheet[y0:y0 + h, x0:x0 + w] = px[:h, :w]
    out = bpy.data.images.new("contact_sheet", sheet.shape[1], sheet.shape[0], alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    log("CONTACT_SHEET", out_path, "%dx%d" % (sheet.shape[1], sheet.shape[0]))


# ------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------

def parse(argv):
    p = argparse.ArgumentParser(prog="assemble.py")
    p.add_argument("--quality", default="blocking", choices=sorted(L.QUALITY))
    p.add_argument("--out", default="out/sect.blend")
    p.add_argument("--stills", action="store_true")
    p.add_argument("--no-contact", action="store_true")
    p.add_argument("--strips", action="store_true", help="also render frames around each hero")
    p.add_argument("--reuse", action="store_true", help="open --out instead of rebuilding")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--no-check", action="store_true", help="skip the BVH clearance pass")
    p.add_argument("--only", default=None, help="comma list of areas to build (others: stand-ins)")
    a = p.parse_args(argv)
    a.only = set(a.only.split(",")) if a.only else None
    a.out = _abs(a.out)
    return a


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse(argv)
    t_all = time.perf_counter()
    if args.reuse:
        fix_fonts()
        bpy.ops.wm.open_mainfile(filepath=args.out)
        scene = bpy.context.scene
        setup_quality(scene, args.quality)
        anchors = anchors_with_yaw()
        modules = import_modules()
        stats = dict(quality=args.quality, reused=args.out)
    else:
        scene, anchors, modules, stats = build_all(args)
    t0 = time.perf_counter()
    cam = C.build(scene, anchors, modules, timeline_path=os.path.join(ROOT, "out", "section_timeline.json"),
                  check=not args.no_check)
    stats["camera_s"] = round(time.perf_counter() - t0, 2)
    stats["clouds_lowered_path"] = len(clear_clouds_path(scene, cam["plan"]["pos"]))
    stats["camera"] = {k: v for k, v in cam["report"].items() if k not in ("waypoints", "pushes")}
    t0 = time.perf_counter()
    stats["triangles"] = scene_triangles(scene)
    stats["count_s"] = round(time.perf_counter() - t0, 2)
    stats["objects"] = len(bpy.data.objects)
    scene.frame_set(scene.frame_start)
    if not args.no_save:
        for f in bpy.data.fonts:
            if f.filepath and f.packed_file is None and f.users:
                try:
                    f.pack()
                except Exception as exc:
                    log("WARN could not pack font", f.filepath, exc)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=args.out, compress=True)
        stats["saved"] = args.out
        stats["blend_mb"] = round(os.path.getsize(args.out) / 1e6, 1)
    stats["total_s"] = round(time.perf_counter() - t_all, 2)
    log("STATS", json.dumps(stats))
    if args.stills:
        render_stills(scene, cam["timeline"], contact=not args.no_contact)
    if args.strips:
        render_strips(scene, cam["timeline"])
    log("DONE", round(time.perf_counter() - t_all, 1), "s")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print("ASSEMBLE_ERROR", flush=True)
        sys.exit(1)
