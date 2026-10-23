"""Vegetation for the web fly-through: `bake_web.py -- trees` (run on the cloud box, out/sect_chase.blend).

Trees, shrubs, grass and lotus are scatter instances of a few prototypes (nature.proto.*). Nothing here is
baked per instance:

- Near (nearest distance to the camera path below --tree-near, shrubs below 25 m): GPU instances
  (EXT_mesh_gpu_instancing) of light prototype meshes (the designed `far` LOD for Huangshan pines, other
  species reduced from their hero/mid LOD with the alpha needle/leaf cards removed). Each prototype gets a
  small baked texture in several lighting variants: the sun from N directions around the tree (8 for pines,
  4 otherwise) plus one "in shadow" variant (sky + fill only). Each instance uses the variant whose sun
  direction matches the real sun in the instance's own frame (its yaw), or the shadow variant when a ray
  cast from its crown toward the sun is blocked. One instanced draw per (prototype, variant).
- Far: crossed cards (front, side and a horizontal top quad) with sprites rendered from the best prototype
  LOD (with its alpha needles) in 4+1 lighting variants, merged into one static mesh per zone (one draw).
- Grass beyond 40 m and lotus beyond 150 m are dropped (sub-pixel).

Lighting rig for the prototypes = the sect's world sky rotated with the variant, the scene's sun lamp, the
bake's warm fill sun and a ground plane for bounce, graded like the atlases (AgX Punchy + look.py grade).
Output: out/web/raw/trees.glb, out/web/bake/trees/{trees_mesh.png, trees_cards.png} (+ previews), stats in
out/web/bake/trees_stats.json.

FULL PATH (all 11 areas, chase.cam frames 1-1729; run this file directly, commands joined by commas run in one
Blender session):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_trees.py -- plan|build|verify[,...] [options]

    plan    classification and counts only (no ray casts, no bakes): out/web/full/bake/trees/plan.json
    build   ray casts, mesh bakes, sprites; writes out/web/full/raw/<area>_trees.glb for every chunk of
            out/web/full/chunks.json and out/web/full/raw/backdrop_trees.glb; stats in
            out/web/full/bake/trees/trees_stats.json (per needle family: cards, card sizes, lite share), texture
            previews (and needle_alpha.png with --needle-cards fan) next to it. Needs assets/web/twig_card.png
            (tools/prep_textures.mjs; rblender.py uploads it) for the default twig cards
    verify  the original scene with its vegetation hidden and the tree GLBs imported, at every hold frame: the film
            render (EEVEE, AgX + grade) of the scene, with the trees rendered on top unlit (Standard view, the web's
            display-referred colours; every other material swapped for a Holdout shader, clouds/haze hidden) ->
            out/web/full/bake/trees/verify_<frame>.png. Chunks are drawn per their need ranges like the page;
            --max-chunks 3 draws only the 3 nearest areas (the page's resident cap) and the backdrop proxies for the
            rest -> verify_max3_<frame>.png. The original trees' instancers are hidden (they place only vegetation).
    bake_web.py -- trees --profile full runs plan + build through cmd_trees (options it does not parse pass through).

Same method as the prototype (near GPU-instanced meshes with yaw/shadow lighting variants from the ray-cast cache,
far crossed cards with baked sprites), applied per chunk. The page turns the view all the way round, so the distances
and sizes include export_web's look-around views: mesh vs card vs dropped uses d_eff / px_eff (the path's nearest
distance and largest size, or the weighted look views' when nearer or larger), and the hold distance (hold mesh and
sprite sizes) is the nearest distance at which any of the hold's views (path frame or look-around) sees the tree. Every vegetation instance belongs to the chunk export_web's
plan gives it (chunks.npz: the area where it is nearest the camera; never split). Choices for the full path:

- <area>_trees.glb (one of the chunk's files, drawn with the chunk): every vegetation instance of that chunk, near
  ones as instanced meshes ('trees.<area>.<family>.sun<k>|shade' groups, groups under 3 merged into
  'trees.near.<area>'), the rest as crossed cards merged into 'trees.cards.<area>'. The textures hold only what the
  chunk uses: mesh slots at full size where a hold camera sees the tree within --hold-mesh-near m or the path passes
  within --mesh-full-d m, half size elsewhere; card sprites at --hold-sprite-px (256) for trees a hold camera sees
  within --hold-card-near m, --sprite-px (128) elsewhere. Spend detail where the camera stops, go cheaper elsewhere.
- Vegetation of a click target (e.g. the abode's peach tree, the mirror's blossom, the library's lotus) is a separate
  node 'trees.hs.<hotspot>' with extras {"hotspot", "label"} (meshes within --hot-near m), so it highlights too.
- Trees seen only from far (never within the 400 m band: chunk -1 in chunks.npz) go to the GLOBAL set,
  backdrop_trees.glb (always loaded, add it to manifest "global"), as cards under 'trees.far'.
- backdrop_trees.glb also holds one card stand-in per area, 'trees.proxy.<area>' with extras {"proxyOf": area}: the
  area's trees that are seen from outside its core range (150 m band), so a hillside keeps its forest while that
  area's chunk is not drawn (the page hides the proxy while the chunk is drawn, as for the backdrop's area proxies).
  The backdrop sheet uses --backdrop-px (64) sprites.
- Bamboo near meshes keep their leaves (opaque blades, unlike the alpha needle/flower cards that are removed).
- Pine near meshes (huangshan, cliff, ancient) keep needle cards: built from the '.hero' LOD (else '.mid'; --needle-lod
  mid: the pilot's order), trunk + cushions collapse-decimated to NEEDLE_OPAQUE_TRIS, the needle fans never decimated,
  only thinned (whole fans, seeded per family) to --needle-max-tris. With --needle-cards twig (the default) every kept
  fan becomes a twig card: one square quad on the fan's root, axis and plane, textured with a cell of
  assets/web/twig_card.png (tools/prep_textures.mjs: photographed pine twigs; G coverage, R luminance detail). Before
  the bake the cushions and cards get crown normals (the smoothed foliage's outward normal, CROWN_*). The cards bake
  into the mesh slots like the rest (a bake material that is opaque to the bake but lets shadow and bounce rays through
  between the needles) and export as a second material 'trees.needle.<area>' (same atlas on texCoord 0;
  occlusionTexture on texCoord 1 = the card texture on the cards' own UVs, extras cardAlpha 'twig' (twig_card.png,
  RGB) or 'needle' (--needle-cards fan: needle_alpha.png, greyscale); alphaMode OPAQUE in the file: the page moves
  that map to the alpha map). Near pines no hold camera sees within --needle-full-near m (and the path passes no nearer
  than --needle-full-d m) use a 'lite' copy: --needle-lite-tris of the same cards, grown (same bake and slot); their
  instance groups are named 'trees.<area>.<family>.lite.<shade|sunK>'.
  --no-needles keeps the old needle-less near meshes (huangshan '.far', cliff/ancient '.hero' at 0.35).
- Bushes (shrub.green / shrub.azalea) are near meshes wherever a card would show as flat: the path passes within
  --shrub-near m, or their largest on-screen size reaches --shrub-mesh-px (screen_px: px at 1280x720 over the path and
  the hold look-around views at full size, the between look views x --between-px-w), or it reaches --shrub-steep-px in
  the views that look down on it from STEEP_DEG or more above (the card's flat top shows sooner), or a hold camera sees
  them within --shrub-hold-near m. A crossed card a few dozen pixels wide reads as two flat planes as the camera moves
  past or the visitor looks round (the peaks' 2-4 m ledge shrubs stand 40+ m off the path, so the path distance alone
  kept every one of them a card). The old rule (path distance only, clumps-only near mesh) is --shrub-mesh-px 0
  --shrub-steep-px 0 --shrub-mesh blob. With --shrub-mesh leafy (the default)
  the near bush is the '.hero' shrub (else '.low'): its leafy clumps collapse-decimated to --shrub-blob-tris, every leaf
  spray kept whole as a cut-out card (material 'trees.needle.leaf.<area>', extras cardAlpha 'needle', leaf_alpha.png:
  nature._mat_needle's 8-leaf fan alpha) and the azalea flowers kept as small opaque quads (pink in the bake); the
  whole bush gets crown normals (one soft rounded mass). --shrub-mesh blob: the old near shrub (green '.low' clumps,
  azalea '.hero' clumps x0.3, leaves and flowers removed).
- The "in shadow" lighting variant keeps the sun at SHADE_SUN (0.3) of its energy, raised to SHADE_SUN_ELEV_DEG,
  instead of switching it off (shade pines baked near-black). Card sprites of pines are rendered from the '.hero' LOD
  with every needle fan replaced by a twig card (cut out by the twig texture), so far trees get the same fine edge.
- Card textures: transparent texels get the colour of the nearest leaves (push-pull fill per sprite), so mipmaps and
  alpha-tested edges show no dark fringes. Material names start with 'trees.mesh' / 'trees.needle' / 'trees.cards'
  (sect_pack.py).
Quality (--quality dev|production, bake_web.BAKE_QUALITY; bake_web.py -- trees passes its own --quality on): dev (the
default) is unchanged. production bakes the mesh variants at 512 samples (dev 128), their albedo guide at 32 (dev 8)
and the card sprites at 192 (dev 48), with adaptive sampling off and the denoisers pinned to High. Slot sizes, sprite
sizes, files and brightness stay the same. Production mesh bakes and sprites carry QUALITY_TAG ('.qp') in their cache
names, so they never reuse dev renders; the sun-visibility cache is shared. The build's first line says which
("BAKE TREES quality production mesh 512 ..."), trees_stats.json stores it (bake_settings).
Expected time on one RTX 5090: the dev build took 39 min = 30 min sun ray casts (not sample-bound; 0 when sunvis.npz is
cached on the box) + 1.5 min mesh bakes + 5.3 min sprites + 1 min export. Production: mesh bakes about 6 min (up to 12
if adaptive sampling had stopped dev texels early), sprites up to about 21 min, the rest unchanged: about 1 h cold,
about 30 min with the ray-cast cache.

    ... sect_chase.blend --python bake_trees.py -- build --quality production

Caches on the box (bakecache/trees_full, not copied back): sun visibility per record key, mesh bakes, sprites;
--fresh ignores them. Test runs: --out out/<name> sends plan.json, the GLBs, the previews, verify renders and the caches
under that folder (raw/, bake/trees/, cache/ or --cache-dir) instead of out/web/full and bakecache/trees_full; with
--only <chunks> --only-recs a build casts, bakes and renders sprites for those chunks' records only. Mesh-bake names
carry NEEDLE_TAG / TWIG_TAG (needle pines), SHRUB_TAG (leafy bushes) and LIGHT_TAG (shade variant), sprite
names TWIG_TAG (twig-card pines) and LIGHT_TAG (shade variant), so a change there re-bakes only what it affects.
"""
import argparse
import collections
import json
import math
import os
import struct
import sys
import time
import zlib

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import bake_web as BW  # noqa: E402
from sect import export_web as EW  # noqa: E402

log = BW.log
TREES_OUT = os.path.join(BW.BAKE_OUT, "trees")
TCACHE = os.path.join(BW.CACHE_DIR, "trees")
CARD_NB = 4
SPRITE_PX = 128
SLOT_PX = {"pine": 384, "blossom": 320, "shrub": 160, "grass": 64, "lotus": 64, "bamboo": 192}
REMOVE_MATS = ("M.nature_pine_needle", "M.nature_shrub_leaf", "M.nature_flower_azalea", "M.nature_flower_peach",
               "M.nature_bamboo_leaf")
# Sample counts come from bake_web.BAKE_QUALITY by --quality (dev: mesh variants 128, their albedo guide 8, card
# sprites 48; production: 512, 32, 192). Production bakes and sprites carry QUALITY_TAG in their cache names.
QUALITY_TAG = dict(dev="", production=".qp")
GROUND = (0.11, 0.13, 0.06)


def tq(a):
    """This run's row of bake_web.BAKE_QUALITY (tree_mesh, tree_albedo, tree_sprite, adaptive, denoise_pin)."""
    return BW.BAKE_QUALITY[getattr(a, "quality", "dev")]


def tree_settings(a):
    """The effective tree bake settings: logged at the start of a build, stored in trees_stats.json."""
    Q = tq(a)
    q = getattr(a, "quality", "dev")
    return dict(quality=q, mesh_samples=Q["tree_mesh"], albedo_samples=Q["tree_albedo"],
                sprite_samples=Q["tree_sprite"],
                adaptive="scene default" if Q["adaptive"] is None else ("on" if Q["adaptive"] else "off"),
                denoise="pinned High" if Q["denoise_pin"] else "default", cache_tag=QUALITY_TAG[q])


def log_tree_quality(a):
    s = tree_settings(a)
    log("TREES quality", s["quality"], "mesh", s["mesh_samples"], "albedo", s["albedo_samples"], "sprites",
        s["sprite_samples"], "adaptive", s["adaptive"], "denoise", s["denoise"], "cache tag", repr(s["cache_tag"]))


def mesh_nb(fam):
    return 8 if fam.startswith("pine") else 4


# ---- prototype names ------------------------------------------------------------------------------

def parse(tk):
    """'nature.proto.pine.huangshan.v3.hero' -> ('pine', 'pine.huangshan.v3', 'hero')."""
    parts = tk.split(".")[2:]
    kind = parts[0]
    if kind == "lotus":
        return kind, ".".join(parts), ""
    if kind == "grass":
        return kind, ".".join(parts[:2]), ""
    vi = next((k for k, p in enumerate(parts) if p.startswith("v") and p[1:].isdigit()), len(parts) - 1)
    fam = ".".join(parts[:vi + 1])
    lod = ".".join(parts[vi + 1:])
    return kind, fam, lod


def proto_obj(name):
    ob = bpy.data.objects.get("nature.proto." + name)
    return ob if ob is not None and ob.type == "MESH" else None


def mesh_source(fam):
    """(object, decimation ratio) for the near mesh of a family."""
    kind = fam.split(".")[0]
    if fam.startswith("pine.huangshan"):
        return proto_obj(fam + ".far") or proto_obj(fam + ".mid") or proto_obj(fam + ".hero"), 1.0
    if kind == "pine":
        return proto_obj(fam + ".hero") or proto_obj(fam + ".mid"), 0.35
    if kind == "blossom":
        return proto_obj(fam + ".far") or proto_obj(fam + ".mid") or proto_obj(fam + ".hero"), 0.25
    if fam.startswith("shrub.green"):
        return proto_obj(fam + ".low") or proto_obj(fam), 1.0 if proto_obj(fam + ".low") else 0.3
    if kind == "shrub":
        return proto_obj(fam), 0.3
    if kind == "bamboo":
        return proto_obj(fam), 0.3
    return proto_obj(fam), 1.0


def card_source(fam):
    kind = fam.split(".")[0]
    if kind == "pine":
        return proto_obj(fam + ".hero") or proto_obj(fam + ".mid") or proto_obj(fam + ".far")
    if kind == "blossom":
        return proto_obj(fam + ".mid") or proto_obj(fam + ".hero") or proto_obj(fam + ".far")
    if kind in ("shrub", "bamboo"):
        return proto_obj(fam) or proto_obj(fam + ".low")
    return None


def strip_faces(me, names):
    """Copy of `me` without the faces whose material is in `names`."""
    mats = [m.name if m else "" for m in me.materials]
    bad = [i for i, m in enumerate(mats) if m in names]
    if not bad:
        return me
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    keep = ~np.isin(mi, bad)
    if not keep.any():
        return me
    return EW.submesh(me, keep, me.name + ".solid")


# ---- sun visibility ---------------------------------------------------------------------------------

def sun_visibility(sc, pts, radius, sdir):
    """Fraction of two rays per instance (crown centre and upper crown, started one crown radius toward
    the sun) that reach the sky. Volumes, FX, the flyer and waterfalls are hidden from the ray casts."""
    hidden = []
    icache = {}

    def info(m):
        if m.name not in icache:
            icache[m.name] = EW.material_info(m)
        return icache[m.name]
    for ob in sc.objects:
        infos = [info(s.material) for s in ob.material_slots if s.material]
        vol = bool(infos) and all(i["volume_only"] or EW._is_fx(i) for i in infos)
        flyer = any(c.name == EW.FLYER_COLL for c in ob.users_collection)
        if vol or flyer or ob.name.startswith(("world.haze", "world.cloud", "world.moon", "world.cirrus")) or any(
                "waterfall" in (s.material.name if s.material else "") for s in ob.material_slots):
            if not ob.hide_viewport:
                ob.hide_viewport = True
                hidden.append(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    s = Vector(sdir)
    vis = np.zeros(len(pts))
    t0 = time.time()
    for i, (p, r) in enumerate(zip(pts, radius)):
        hits = 0
        for dz in (0.0, 0.35):
            o = Vector(p) + s * (r * 1.05 + 0.3) + Vector((0, 0, dz * r * 2))
            hit = sc.ray_cast(dg, o, s, distance=3000.0)[0]
            hits += 0 if hit else 1
        vis[i] = hits / 2.0
        if i == 199:
            log("ray cast rate", round((time.time() - t0) / 400 * 1000, 2), "ms per ray")
        elif i % 2500 == 2499:
            log("ray casts:", i + 1, "of", len(pts), "instances,", round(time.time() - t0, 1), "s")
    for ob in hidden:
        ob.hide_viewport = False
    log("sun visibility for", len(pts), "instances in", round(time.time() - t0, 1), "s; lit share",
        round(float((vis >= 0.5).mean()), 3))
    return vis


# ---- prototype lighting scene -------------------------------------------------------------------------

class Rig:
    """New scene with the sect sky (rotatable), sun lamp, fill sun, ground plane, Cycles GPU, AgX + grade."""

    def __init__(self, src, exposure, sat, quality="dev"):
        from sect.lib import look as LK
        self.sc = sc = bpy.data.scenes.new("trees.proto")
        BW.setup_cycles(sc, BW.BAKE_QUALITY[quality]["tree_mesh"], quality)
        sc.view_settings.view_transform = LK.LOOK["view_transform"]
        sc.view_settings.look = LK.LOOK["look"]
        sc.view_settings.exposure = exposure
        sc.display_settings.display_device = "sRGB"
        w = src.world.copy()
        w.name = "trees.world"
        sc.world = w
        nt = w.node_tree
        tc = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeTexCoord")
        rot = nt.nodes.new("ShaderNodeVectorRotate")
        rot.rotation_type = "Z_AXIS"
        for l in list(tc.outputs["Generated"].links):
            nt.links.new(rot.outputs["Vector"], l.to_socket)
        nt.links.new(tc.outputs["Generated"], rot.inputs["Vector"])
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeTexSky" and n.inputs.get("Vector") is not None and not n.inputs["Vector"].is_linked:
                nt.links.new(rot.outputs["Vector"], n.inputs["Vector"])
        self.rot = rot
        bg = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBackground")
        bg.inputs["Strength"].default_value = BW.BAKE_LIGHT["world_strength"]
        if bg.inputs["Color"].is_linked:
            srcs = bg.inputs["Color"].links[0].from_socket
            mul = nt.nodes.new("ShaderNodeVectorMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = BW.BAKE_LIGHT["world_tint"]
            nt.links.new(srcs, mul.inputs[0])
            nt.links.new(mul.outputs[0], bg.inputs["Color"])
        sun_src = bpy.data.objects["look.sun"]
        self.sdir = sun_src.matrix_world.to_3x3().col[2].normalized()
        self.sun_az = math.atan2(self.sdir.y, self.sdir.x)
        self.sun_el = math.asin(max(-1.0, min(1.0, self.sdir.z)))
        self.sun = bpy.data.objects.new("trees.sun", sun_src.data.copy())
        self.sun_energy = self.sun.data.energy
        self.shade_sun = SHADE_SUN          # share of the sun in the shade variant (0: off, the old bake)
        sc.collection.objects.link(self.sun)
        L = BW.BAKE_LIGHT
        fd = bpy.data.lights.new("trees.fill", "SUN")
        fd.energy, fd.angle, fd.color = L["fill_energy"], math.radians(L["fill_angle_deg"]), L["fill_color"]
        self.fill = bpy.data.objects.new("trees.fill", fd)
        sc.collection.objects.link(self.fill)
        gm = bpy.data.meshes.new("trees.ground")
        s = 40.0
        gm.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        mat = bpy.data.materials.new("trees.ground")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = GROUND + (1.0,)
        mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
        gm.materials.append(mat)
        self.ground = bpy.data.objects.new("trees.ground", gm)
        sc.collection.objects.link(self.ground)
        self.ground.visible_camera = False
        self.objs = []
        self._grade(LK.LOOK, sat)

    def _grade(self, LOOK, sat):
        from sect.lib import look as LK
        ng = bpy.data.node_groups.new("trees.grade", "CompositorNodeTree")
        ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        N, Lk = ng.nodes, ng.links
        rl = N.new("CompositorNodeRLayers")
        rl.scene = self.sc
        grade = N.new("CompositorNodeColorBalance")
        LK._inp(grade, "Type").default_value = "Offset/Power/Slope (ASC-CDL)"
        grade.inputs["Factor"].default_value = 1.0
        sl, of, pw = LOOK["grade_slope"], LOOK["grade_offset"], LOOK["grade_power"]
        for sock in grade.inputs:
            if sock.identifier == "Color Slope":
                sock.default_value = (sl[0], sl[1], sl[2], 1.0)
            elif sock.identifier == "Color Offset":
                sock.default_value = (of[0], of[1], of[2], 1.0)
            elif sock.identifier == "Color Power":
                sock.default_value = (pw[0], pw[1], pw[2], 1.0)
        Lk.new(rl.outputs["Image"], grade.inputs["Image"])
        cc = N.new("CompositorNodeColorCorrection")
        for sock in cc.inputs:
            if sock.identifier == "Highlights Saturation":
                sock.default_value = LOOK["grade_highlight_saturation"]
            elif sock.identifier == "Shadows Saturation":
                sock.default_value = LOOK["grade_shadow_saturation"]
        Lk.new(grade.outputs["Image"], cc.inputs["Image"])
        hs = N.new("CompositorNodeHueSat")
        hs.inputs["Saturation"].default_value = sat
        Lk.new(cc.outputs["Image"], hs.inputs["Image"])
        go = N.new("NodeGroupOutput")
        Lk.new(hs.outputs["Image"], go.inputs["Image"])
        self.sc.compositing_node_group = ng
        self.sc.render.use_compositing = True

    def light(self, local_az, shadow):
        """Sun at azimuth `local_az` (radians, in the prototype's frame) at the real elevation; the sky turns
        with it. shadow=True (the shade variant): the sun at self.shade_sun (SHADE_SUN) of its energy, raised to at
        least SHADE_SUN_ELEV_DEG (a soft top light standing in for the open sky; switched off, the old bake, baked
        near-black trees); shade_sun 0: no sun (sky + fill only)."""
        delta = local_az - self.sun_az
        self.rot.inputs["Angle"].default_value = -delta
        e = max(self.sun_el, math.radians(SHADE_SUN_ELEV_DEG)) if shadow else self.sun_el
        v = Vector((math.cos(local_az) * math.cos(e), math.sin(local_az) * math.cos(e), math.sin(e)))
        self.sun.rotation_mode = "QUATERNION"
        self.sun.rotation_quaternion = v.to_track_quat("Z", "Y")
        self.sun.hide_render = bool(shadow) and self.shade_sun <= 0
        self.sun.data.energy = self.sun_energy * (self.shade_sun if shadow else 1.0)
        fe = math.radians(BW.BAKE_LIGHT["fill_elev_deg"])
        f = Vector((math.cos(local_az) * math.cos(fe), math.sin(local_az) * math.cos(fe), math.sin(fe)))
        self.fill.rotation_mode = "QUATERNION"
        self.fill.rotation_quaternion = f.to_track_quat("Z", "Y")

    def add(self, name, me):
        ob = bpy.data.objects.new(name, me)
        self.sc.collection.objects.link(ob)
        ob.hide_render = True
        self.objs.append(ob)
        return ob

    def only(self, ob):
        for o in self.objs:
            o.hide_render = o is not ob
        vl = self.sc.view_layers[0]
        for o in self.sc.objects:
            o.select_set(o is ob, view_layer=vl)
        vl.objects.active = ob

    def ctx(self, ob=None):
        kw = dict(scene=self.sc, view_layer=self.sc.view_layers[0])
        if ob is not None:
            kw.update(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob])
        return bpy.context.temp_override(**kw)


def variant_az(v, nb):
    return 2 * math.pi * v / nb


# ---- the command --------------------------------------------------------------------------------------

def cmd_trees(a):
    if EW.PROFILE == "full":           # bake_web.py -- trees --profile full: the full-path build (see main())
        fa = full_args(["build"] + list(getattr(a, "extra", None) or []))
        for k in ("exposure", "sat", "tree_near", "quality"):
            if hasattr(a, k):
                setattr(fa, k, getattr(a, k))
        apply_out(fa)
        sc = bpy.context.scene
        full_build(fa, sc, full_plan(fa, sc))
        return
    sc = bpy.context.scene
    t0 = time.time()
    T = {}
    R = EW.gather(sc)
    S, cache_frames = EW.load_cache(R)
    px = S["px_eff"].astype(float)
    dmin = S["d_eff"]
    idx = np.array([i for i in range(len(R)) if BW.is_veg_rec(R, i) and S["any"][i] and px[i] >= EW.MIN_PX])
    cam = bpy.data.objects[EW.CAMERA]
    views = EW.load_views(cam)
    frames = [int(f) for f in views.frames]
    cam_pos = views.pos
    zones = BW.zone_of_records(R, idx, cam_pos, frames)
    recs = []
    drops = collections.Counter()
    for i, z in zip(idx, zones):
        kind, fam, lod = parse(R.tkey[i])
        d = float(dmin[i])
        if kind == "grass":
            cls = "mesh" if d < 40 else None
        elif kind == "lotus":
            cls = "mesh" if d < 150 else None
        elif kind == "shrub":
            cls = "mesh" if d < 25 else ("card" if px[i] >= 3 else None)
        else:
            cls = "mesh" if d < a.tree_near else ("card" if px[i] >= 2 else None)
        if cls is None:
            drops[kind] += 1
            continue
        recs.append(dict(i=int(i), kind=kind, fam=fam, cls=cls, zone=str(z), d=d))
    log("vegetation", len(idx), "visible instances ->", collections.Counter((r["cls"], r["kind"]) for r in recs),
        "dropped", dict(drops))

    # prototype meshes (local space)
    dec = BW.Decimator(sc)
    mesh_fams = sorted({r["fam"] for r in recs if r["cls"] == "mesh"})
    card_fams = sorted({r["fam"] for r in recs if r["cls"] == "card"})
    fam_mesh = {}
    for fam in mesh_fams:
        ob, ratio = mesh_source(fam)
        if ob is None:
            log("WARN no mesh source for", fam)
            continue
        me = ob.data.copy()
        me.name = "tree.src." + fam
        EW._slot_materials(me, ob)
        me = strip_faces(me, REMOVE_MATS)
        if ratio < 0.999:
            me = dec.get("tree." + fam, me, ratio)
        fam_mesh[fam] = me
        log("mesh proto", fam, ob.name, len(me.polygons), "faces")
    fam_card = {}
    for fam in card_fams:
        ob = card_source(fam)
        if ob is None:
            log("WARN no card source for", fam)
            continue
        fam_card[fam] = ob
    recs = [r for r in recs if (r["fam"] in fam_mesh if r["cls"] == "mesh" else r["fam"] in fam_card)]

    # crown points + sun visibility + variant per instance
    sun = bpy.data.objects["look.sun"]
    sdir = np.array(sun.matrix_world.to_3x3().col[2].normalized())
    pts, rad = [], []
    bbox = {}

    def fam_box(key, me):
        if key not in bbox:
            n = len(me.vertices)
            co = np.empty(n * 3, np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3) if n else np.zeros((1, 3), np.float32)
            bbox[key] = (co.min(0).astype(float), co.max(0).astype(float))
        return bbox[key]
    for r in recs:
        if r["cls"] == "mesh":
            lo, hi = fam_box(("m", r["fam"]), fam_mesh[r["fam"]])
        else:
            lo, hi = fam_box(("c", r["fam"]), fam_card[r["fam"]].data)
        r["lo"], r["hi"] = lo, hi
        M = np.asarray(R.mw[r["i"]], float)
        c = 0.5 * (lo + hi)
        c[2] = lo[2] + 0.6 * (hi[2] - lo[2])
        pts.append(M[:3, :3] @ c + M[:3, 3])
        sc3 = np.linalg.norm(M[:3, :3], axis=0)
        rad.append(0.5 * max((hi[0] - lo[0]) * sc3[0], (hi[1] - lo[1]) * sc3[1]))
    t1 = time.time()
    keys = np.array([R.key[r["i"]] for r in recs])
    vp = os.path.join(TCACHE, "sunvis.npz")
    vis = None
    if os.path.isfile(vp):
        z = np.load(vp, allow_pickle=False)
        old = dict(zip(z["keys"].tolist(), z["vis"].tolist()))
        if all(k in old for k in keys.tolist()):
            vis = np.array([old[k] for k in keys.tolist()])
            log("sun visibility from cache", vp)
    if vis is None:
        vis = sun_visibility(sc, pts, rad, sdir)
        os.makedirs(TCACHE, exist_ok=True)
        np.savez_compressed(vp, keys=keys, vis=vis)
    T["raycast"] = round(time.time() - t1, 1)
    for r, v in zip(recs, vis):
        M = np.asarray(R.mw[r["i"]], float)
        Rm = M[:3, :3] / np.maximum(np.linalg.norm(M[:3, :3], axis=0), 1e-9)
        sl = Rm.T @ sdir
        az = math.atan2(sl[1], sl[0])
        nb = mesh_nb(r["fam"]) if r["cls"] == "mesh" else CARD_NB
        r["vis"] = float(v)
        r["var"] = nb if v < 0.5 else int(round(az / (2 * math.pi / nb))) % nb

    # ---- prototype scene: bake mesh variants, render card sprites
    log_tree_quality(a)
    rig = Rig(sc, a.exposure, a.sat, a.quality)
    os.makedirs(TCACHE, exist_ok=True)
    os.makedirs(TREES_OUT, exist_ok=True)
    used_mesh = sorted({(r["fam"], r["var"]) for r in recs if r["cls"] == "mesh"})
    used_card = sorted({(r["fam"], r["var"]) for r in recs if r["cls"] == "card"})
    log("mesh variants", len(used_mesh), "card variants", len(used_card))
    # UVs per prototype (own projection + packer, 0-1)
    fam_uv = {}
    for fam, me in fam_mesh.items():
        A = BW.ma(me)
        kind = fam.split(".")[0]
        spx = SLOT_PX.get(kind, 128)
        rho = spx * math.sqrt(0.5 / max(A.area, 1e-6))          # texels per metre, roughly
        u0 = BW.project_box26(A.co * rho, A.vi, A.ls)
        u, info = BW.pack_shelf(u0, A.co * rho, A.vi, A.ls, spx, margin=1.5)
        lay = me.uv_layers.new(name="bake")
        lay.data.foreach_set("uv", u.ravel())
        me.uv_layers.active = lay
        fam_uv[fam] = u
    # bake objects + material copies with a bake target node
    fam_obj, fam_nodes = {}, {}
    for fam, me in fam_mesh.items():
        bme = me.copy()
        bme.name = "tree.bake." + fam
        for k, m in enumerate(bme.materials):
            if m is None:
                continue
            mc = m.copy()
            mc.name = m.name + "@tree"
            nt = mc.node_tree
            tn = nt.nodes.new("ShaderNodeTexImage")
            nt.nodes.active = tn
            fam_nodes.setdefault(fam, []).append(tn)
            bme.materials[k] = mc
        fam_obj[fam] = rig.add("tree.bake." + fam, bme)
    t1 = time.time()
    images = {}
    with rig.ctx():
        for fam in fam_mesh:
            kind = fam.split(".")[0]
            spx = SLOT_PX.get(kind, 128)
            ob = fam_obj[fam]
            rig.only(ob)
            alb = bpy.data.images.new("tree_alb.%s" % fam, spx, spx, alpha=False, float_buffer=True)
            for tn in fam_nodes.get(fam, []):
                tn.image = alb
            rig.sc.cycles.samples = tq(a)["tree_albedo"]
            with rig.ctx(ob):
                bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, uv_layer="bake", margin=4,
                                    margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
            images[(fam, "albedo")] = alb
            rig.sc.cycles.samples = tq(a)["tree_mesh"]
            nb = mesh_nb(fam)
            for (f2, v) in used_mesh:
                if f2 != fam:
                    continue
                rig.light(variant_az(min(v, nb - 1), nb), shadow=(v == nb))
                im = bpy.data.images.new("tree.%s.v%d" % (fam, v), spx, spx, alpha=False, float_buffer=True)
                for tn in fam_nodes.get(fam, []):
                    tn.image = im
                with rig.ctx(ob):
                    bpy.ops.object.bake(type="COMBINED",
                                        pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT", "TRANSMISSION"},
                                        uv_layer="bake", margin=4, margin_type="EXTEND", use_clear=True,
                                        target="IMAGE_TEXTURES")
                images[(fam, v)] = im
    T["mesh_bakes"] = round(time.time() - t1, 1)
    log("baked", len(used_mesh), "mesh variants in", T["mesh_bakes"], "s")

    # assemble the mesh atlas (float) + albedo atlas, then denoise + grade like the main atlases
    slots = [(fam, v) for (fam, v) in used_mesh]
    sizes = [SLOT_PX.get(fam.split(".")[0], 128) for fam, v in slots]
    W, place = shelf_squares(sizes, 4096)
    H = place["height"]
    big = np.zeros((H, W, 4), np.float32)
    big[..., 3] = 1
    alb = np.zeros((H, W, 4), np.float32)
    alb[..., 3] = 1
    for (fam, v), sz, (x, y) in zip(slots, sizes, place["pos"]):
        big[y:y + sz, x:x + sz] = pixels(images[(fam, v)])
        alb[y:y + sz, x:x + sz] = pixels(images[(fam, "albedo")])
    p_lin = save_float(big, "trees_mesh_lin", os.path.join(TCACHE, "trees_mesh_lin.exr"))
    p_alb = save_float(alb, "trees_mesh_alb", os.path.join(TCACHE, "trees_mesh_alb.exr"))
    post, n_im, n_al = BW.post_scene((W, H), a.exposure, a.sat, denoise=True, quality=a.quality)
    n_im.image = bpy.data.images.load(p_lin, check_existing=False)
    n_al.image = bpy.data.images.load(p_alb, check_existing=False)
    p_mesh_png = BW.run_post(post, os.path.join(TREES_OUT, "trees_mesh.png"))
    slot_uv = {}
    for (fam, v), sz, (x, y) in zip(slots, sizes, place["pos"]):
        # image rows: numpy row 0 = Blender's bottom row = UV v=0
        slot_uv[(fam, v)] = (x / W, y / H, sz / W, sz / H)

    # ---- card sprites
    t1 = time.time()
    cam_ob = bpy.data.objects.new("trees.cam", bpy.data.cameras.new("trees.cam"))
    rig.sc.collection.objects.link(cam_ob)
    rig.sc.camera = cam_ob
    cam_ob.data.type = "ORTHO"
    rig.sc.render.film_transparent = True
    rig.sc.render.resolution_x = rig.sc.render.resolution_y = SPRITE_PX
    rig.sc.render.resolution_percentage = 100
    rig.sc.cycles.samples = tq(a)["tree_sprite"]
    rig.sc.cycles.use_denoising = True
    ims = rig.sc.render.image_settings
    ims.file_format = "PNG"
    ims.color_mode = "RGBA"
    ims.color_depth = "8"
    card_obj, card_geo = {}, {}
    for fam, ob in fam_card.items():
        me = ob.data.copy()
        EW._slot_materials(me, ob)
        co = np.array([v.co for v in me.vertices])
        lo, hi = co.min(0), co.max(0)
        card_obj[fam] = rig.add("tree.card." + fam, me)
        card_geo[fam] = (lo, hi)
    sprites = {}
    spr_dir = os.path.join(TCACHE, "sprites")
    os.makedirs(spr_dir, exist_ok=True)
    for fam, v in used_card:
        ob = card_obj[fam]
        rig.only(ob)
        rig.light(variant_az(min(v, CARD_NB - 1), CARD_NB), shadow=(v == CARD_NB))
        lo, hi = card_geo[fam]
        c = 0.5 * (lo + hi)
        ext = hi - lo
        views = dict(front=(Vector((c[0], lo[1] - 30.0, c[2])), (math.pi / 2, 0.0, 0.0), max(ext[0], ext[2])),
                     side=(Vector((hi[0] + 30.0, c[1], c[2])), (math.pi / 2, 0.0, math.pi / 2), max(ext[1], ext[2])),
                     top=(Vector((c[0], c[1], hi[2] + 30.0)), (0.0, 0.0, 0.0), max(ext[0], ext[1])))
        for vw, (loc, rot, scale) in views.items():
            cam_ob.location = loc
            cam_ob.rotation_mode = "XYZ"
            cam_ob.rotation_euler = rot
            cam_ob.data.ortho_scale = scale * 1.04
            cam_ob.data.clip_start, cam_ob.data.clip_end = 0.1, 200.0
            p = os.path.join(spr_dir, "%s.v%d.%s.png" % (fam, v, vw))
            rig.sc.render.filepath = p
            bpy.ops.render.render(write_still=True, scene=rig.sc.name)
            sprites[(fam, v, vw)] = (p, scale * 1.04)
    T["sprites"] = round(time.time() - t1, 1)
    log("rendered", len(sprites), "sprites in", T["sprites"], "s")
    keys = sorted(sprites)
    per_row = 4096 // SPRITE_PX
    rows = int(math.ceil(len(keys) / per_row))
    SH = rows * SPRITE_PX
    SW = 4096 if len(keys) >= per_row else 1 << int(math.ceil(math.log2(len(keys) * SPRITE_PX)))
    sheet = np.zeros((SH, SW, 4), np.float32)
    spr_uv = {}
    for k, key in enumerate(keys):
        x = (k % per_row) * SPRITE_PX
        y = (k // per_row) * SPRITE_PX
        sheet[y:y + SPRITE_PX, x:x + SPRITE_PX] = load_rgba(sprites[key][0])
        spr_uv[key] = (x / SW, y / SH, SPRITE_PX / SW, SPRITE_PX / SH)
    sheet = bleed_alpha(sheet)
    p_card_png = save_png(sheet, "trees_cards", os.path.join(TREES_OUT, "trees_cards.png"))

    # ---- export objects
    coll = bpy.data.collections.new("web.trees")
    sc.collection.children.link(coll)
    mat_mesh = tex_material("trees.mesh", p_mesh_png, alpha=False)
    mat_card = tex_material("trees.cards", p_card_png, alpha=True)
    made = []
    stats = collections.Counter()
    tri_total = 0
    # instanced near meshes: one Empty per (zone, family, variant), children share the variant mesh
    var_mesh = {}
    groups = collections.defaultdict(list)
    for r in recs:
        if r["cls"] == "mesh":
            groups[(r["fam"], r["var"])].append(r)
    small = collections.defaultdict(list)          # zone -> [(variant mesh, matrix)] for groups under 3
    for (fam, v), lst in sorted(groups.items()):
        me = var_mesh.get((fam, v))
        if me is None:
            me = fam_mesh[fam].copy()
            me.name = "tree.%s.v%d" % (fam, v)
            for lay in [l for l in me.uv_layers if l.name != "bake"]:
                me.uv_layers.remove(lay)
            x0, y0, sw, sh = slot_uv[(fam, v)]
            u = fam_uv[fam]
            me.uv_layers["bake"].data.foreach_set("uv", np.stack([x0 + u[:, 0] * sw, y0 + u[:, 1] * sh], 1).ravel())
            me.materials.clear()
            me.materials.append(mat_mesh)
            me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32))
            var_mesh[(fam, v)] = me
        if len(lst) < 3:
            for r in lst:
                small[r["zone"]].append((me, R.mw[r["i"]]))
            tri_total += len(me.polygons) * len(lst)
            stats["merged_near_trees"] += len(lst)
            continue
        g = bpy.data.objects.new("trees.%s.%s" % (fam, "shade" if v == mesh_nb(fam) else "sun%d" % v), None)
        coll.objects.link(g)
        made.append(g)
        g["instances"] = len(lst)
        for k, r in enumerate(lst):
            o = bpy.data.objects.new("%s#%d" % (g.name[:50], k), me)
            coll.objects.link(o)
            o.parent = g
            o.matrix_basis = Matrix(np.asarray(R.mw[r["i"]], float).tolist())
            made.append(o)
        tri_total += len(me.polygons) * len(lst)
        stats["mesh_instances"] += len(lst)
        stats["mesh_groups"] += 1
    for zone, items in small.items():
        me = merge_uv_meshes(items, "trees.near." + zone)
        me.materials.append(mat_mesh)
        ob = bpy.data.objects.new("trees.near." + zone, me)
        coll.objects.link(ob)
        made.append(ob)
    # cards: one merged static mesh per zone
    for zone in ("gate", "mirror"):
        lst = [r for r in recs if r["cls"] == "card" and r["zone"] == zone]
        if not lst:
            continue
        co, uv, faces = [], [], []
        for r in lst:
            fam, v = r["fam"], r["var"]
            lo, hi = card_geo[fam]
            c = 0.5 * (lo + hi)
            M = np.asarray(R.mw[r["i"]], float)
            quads = card_quads(c, lo, hi, {vw: sprites[(fam, v, vw)][1] for vw in ("front", "side", "top")},
                               {vw: spr_uv[(fam, v, vw)] for vw in ("front", "side", "top")})
            for q_co, q_uv in quads:
                base = len(co)
                for p, t in zip(q_co, q_uv):
                    co.append(M[:3, :3] @ np.asarray(p) + M[:3, 3])
                    uv.append(t)
                faces.append((base, base + 1, base + 2, base + 3))
        co = np.array(co, np.float32)
        vi = np.array(faces, np.int32).ravel()
        ls = np.arange(0, len(vi), 4, dtype=np.int32)
        me = BW.make_mesh("trees.cards." + zone, co, vi, ls)
        lay = me.uv_layers.new(name="bake")
        lay.data.foreach_set("uv", np.array(uv, np.float32)[vi].ravel())
        me.materials.append(mat_card)
        ob = bpy.data.objects.new("trees.cards." + zone, me)
        coll.objects.link(ob)
        made.append(ob)
        tri_total += 2 * len(faces)
        stats["cards_" + zone] = len(lst)
    path = os.path.join(BW.RAW, "trees.glb")
    export_trees(path, made)
    st = EW.glb_stats(path)
    T["total"] = round(time.time() - t0, 1)
    out = dict(glb=st, blender_tris=tri_total, stats=dict(stats), times=T, bake_settings=tree_settings(a),
               mesh_variants=[list(k) for k in used_mesh], card_variants=[list(k) for k in used_card],
               atlas=dict(mesh=[W, H], cards=[SW, SH]),
               lit_share=round(float(np.mean([r["vis"] >= 0.5 for r in recs])), 3),
               by_family=dict(collections.Counter("%s/%s" % (r["cls"], r["fam"]) for r in recs)))
    BW.dump(os.path.join(BW.BAKE_OUT, "trees_stats.json"), out)
    log("TREES", json.dumps(dict(glb=st, stats=dict(stats), times=T)))
    for p in (p_mesh_png, p_card_png):
        preview_png(p, os.path.join(TREES_OUT, "preview_" + os.path.basename(p)))


def merge_uv_meshes(items, name, materials=False):
    """One static mesh from [(mesh with a 'bake' UV, 4x4 matrix)] in world space. Meshes with needle cards (a 'needle'
    UV, material 1) keep their material indices and fan UVs (zeros on the other faces). materials=True: the merged
    mesh takes the union of the items' material slots (first seen first), each item's indices remapped onto it, so
    pine needle cards and bush leaf cards keep their own materials; else the caller adds the slots (_near_materials)."""
    co, vi, ls, uv, nuv, mi = [], [], [], [], [], []
    slots = []
    vo = lo_ = 0
    for me, M in items:
        A = BW.ma(me)
        M = np.asarray(M, float)
        co.append((A.co @ M[:3, :3].T + M[:3, 3]).astype(np.float32))
        perm = A.flip_perm() if np.linalg.det(M[:3, :3]) < 0 else np.arange(A.nl)
        vi.append(A.vi[perm] + vo)
        ls.append(A.ls + lo_)
        u = np.empty(A.nl * 2, np.float32)
        me.uv_layers["bake"].data.foreach_get("uv", u)
        uv.append(u.reshape(-1, 2)[perm])
        n = np.zeros(A.nl * 2, np.float32)
        if "needle" in me.uv_layers:
            me.uv_layers["needle"].data.foreach_get("uv", n)
        nuv.append(n.reshape(-1, 2)[perm])
        if materials:
            remap = []
            for m in me.materials:
                if m not in slots:
                    slots.append(m)
                remap.append(slots.index(m))
            remap = np.array(remap or [0], np.int32)
            mi.append(remap[np.clip(A.mi, 0, len(remap) - 1)])
        else:
            mi.append(A.mi)
        vo += A.nv
        lo_ += A.nl
    mi = np.concatenate(mi)
    out = BW.make_mesh(name, np.concatenate(co), np.concatenate(vi), np.concatenate(ls), mi if mi.any() else None)
    lay = out.uv_layers.new(name="bake")
    lay.data.foreach_set("uv", np.concatenate(uv).ravel())
    if mi.any():
        lay = out.uv_layers.new(name="needle")
        lay.data.foreach_set("uv", np.concatenate(nuv).ravel())
        out.uv_layers["bake"].active_render = True
    for m in slots:
        out.materials.append(m)
    return out


def _near_materials(me, mat_mesh, mat_needle):
    """Material slots of a merged near mesh: trees.mesh, plus trees.needle when it holds needle cards."""
    me.materials.append(mat_mesh)
    if mat_needle is not None and "needle" in me.uv_layers:
        me.materials.append(mat_needle)


def _needle_tris(C, fam, lod="full"):
    """Triangles of the needle cards on a family's near mesh (0 without); lod 'lite': its lite subset."""
    nd = C["fam_nd"].get(fam)
    if nd is None:
        return 0
    lt = np.empty(len(nd), np.int32)
    C["fam_mesh"][fam].polygons.foreach_get("loop_total", lt)
    lite = C.get("fam_lite", {}).get(fam)
    if lod == "lite" and lite is not None:
        nd = nd & lite["keep"]
    return int((lt[nd] - 2).sum())


def card_quads(c, lo, hi, scales, uvs):
    """Front (XZ plane), side (YZ plane) and top (horizontal, at 62 % height) quads matching the ortho sprite
    renders; each quad is the sprite's square footprint, UVs into the sprite sheet."""
    out = []
    s = scales["front"] / 2
    x0, y0, w, h = uvs["front"]
    out.append(([(c[0] - s, c[1], c[2] - s), (c[0] + s, c[1], c[2] - s), (c[0] + s, c[1], c[2] + s),
                 (c[0] - s, c[1], c[2] + s)], [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]))
    s = scales["side"] / 2
    x0, y0, w, h = uvs["side"]
    out.append(([(c[0], c[1] - s, c[2] - s), (c[0], c[1] + s, c[2] - s), (c[0], c[1] + s, c[2] + s),
                 (c[0], c[1] - s, c[2] + s)], [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]))
    s = scales["top"] / 2
    z = lo[2] + 0.62 * (hi[2] - lo[2])
    x0, y0, w, h = uvs["top"]
    out.append(([(c[0] - s, c[1] - s, z), (c[0] + s, c[1] - s, z), (c[0] + s, c[1] + s, z),
                 (c[0] - s, c[1] + s, z)], [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]))
    return out


def shelf_squares(sizes, width):
    """Place squares (largest first) in rows of `width`; returns width and positions (x, y) in pixels."""
    order = sorted(range(len(sizes)), key=lambda k: -sizes[k])
    pos = [None] * len(sizes)
    x = y = row_h = 0
    for k in order:
        s = sizes[k]
        if x + s > width:
            y += row_h
            x = row_h = 0
        pos[k] = (x, y)
        x += s
        row_h = max(row_h, s)
    h = y + row_h
    H = int(math.ceil(max(h, 4) / 4.0)) * 4          # WebGL2 handles non-power-of-two textures
    return width, dict(pos=pos, height=H)


def pixels(im):
    w, h = im.size
    p = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(p)
    return p.reshape(h, w, 4)


def load_rgba(path):
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    p = pixels(im)
    bpy.data.images.remove(im)
    return p


def save_float(arr, name, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=True, float_buffer=True)
    im.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    im.filepath_raw = path
    im.file_format = "OPEN_EXR"
    im.save()
    return path


def save_png(arr, name, path):
    """arr: display values 0-1 RGBA (straight alpha), numpy row 0 = bottom."""
    h, w = arr.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(np.ascontiguousarray(np.clip(arr, 0, 1), np.float32).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return path


def bleed_alpha(a, iters=6):
    """Spread colour into transparent texels (so mip levels and alpha-test edges do not pick up black)."""
    rgb = a[..., :3].copy()
    known = a[..., 3] > 0.05
    for _ in range(iters):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]
            cnt += k
        new = (~known) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known = known | new
    out = a.copy()
    out[..., :3] = rgb
    return out


def preview_png(path, out, size=1024):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    f = max(1.0, max(w, h) / size)
    im.scale(int(w / f), int(h / f))
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def tex_material(name, path, alpha):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(path, check_existing=True)
    tn.image.colorspace_settings.name = "sRGB"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "bake"
    nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
    nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0
    if alpha:
        rnd = nt.nodes.new("ShaderNodeMath")
        rnd.operation = "ROUND"              # the glTF exporter reads Round(alpha) as alphaMode MASK, cutoff 0.5
        nt.links.new(tn.outputs["Alpha"], rnd.inputs[0])
        nt.links.new(rnd.outputs[0], b.inputs["Alpha"])
        m.use_backface_culling = False
        m["alphaTest"] = 0.5
    m["baked"] = True
    return m


def export_trees(path, objects):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    BW.deselect_all()
    for ob in objects:
        ob.select_set(True)
    kw = dict(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True, export_extras=True,
              export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
              export_animations=False, export_materials="EXPORT", export_texcoords=True, export_normals=False,
              export_tangents=False, export_vertex_color="NONE", export_image_format="AUTO",
              export_draco_mesh_compression_enable=False, export_gpu_instances=True)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    for k in list(kw):
        if k not in props:
            kw.pop(k)
    bpy.ops.export_scene.gltf(**kw)
    log("wrote", path, os.path.getsize(path))


# ======================================================================================================
# FULL PATH: all 11 areas (see the module docstring). Run this file directly: bake_trees.py -- plan|build|verify
# ======================================================================================================

FULL_RAW = os.path.join(EW.FULL, "raw")
FULL_OUT = os.path.join(EW.FULL, "bake", "trees")
FULL_CACHE = os.path.join(BW.CACHE_DIR, "trees_full")     # box only (bakecache/ is outside out/)
VIEWS = ("front", "side", "top")
KEEP_MATS = {"bamboo": ("M.nature_bamboo_leaf",)}         # opaque leaf blades: kept on the near meshes
FULL_RATIO = {"bamboo": 1.0}                              # kind -> near-mesh decimation (collapse shreds leaf blades)
FULL_SLOT_PX = dict(SLOT_PX, bamboo=256)                   # bamboo keeps its leaves: more surface per slot
SMALL_KINDS = ("grass", "lotus")                           # never cards, never in the proxies
NEEDLE_MAT = "M.nature_pine_needle"                        # needle-fan cards (nature._needle_fan, _mat_needle)
NEEDLE_OPAQUE_TRIS = {"huangshan": 2000, "cliff": 2000, "ancient": 2400}   # pine style -> trunk + cushion tris of a
#                                                            near mesh with needle cards (was 1000/1200/1600)
NEEDLE_TEXEL = 0.7          # needle fans' texel density in a mesh slot relative to the trunk and cushions (linear)
NEEDLE_ALPHA_PX = 256       # needle_alpha.png: the fans' alpha in fan-UV space, shared by every trees.needle material
NEEDLE_TAG = "nd2"          # in the mesh-bake cache names of needle meshes; bump when needle_bake_nodes, the twig cards
#                             or the crown normals change (nd1: .mid fans, no crown normals)
# Twig cards (--needle-cards twig, the default): every kept needle fan becomes one square quad (2 triangles) on the fan's
# root, axis and plane, textured with a cell of TWIG_TEX (tools/prep_textures.mjs: a brush of photographed pine twigs,
# Poly Haven pine_tree_01, CC0; G = coverage, R = luminance detail, 0.5 neutral). Exported as cardAlpha 'twig'.
TWIG_TEX = os.path.join(ROOT, "assets", "web", "twig_card.png")
TWIG_GRID = 2               # TWIG_TEX holds TWIG_GRID x TWIG_GRID card variants (prep_textures.mjs TWIG_GRID)
TWIG_LEN_K = 1.0            # card side / source fan length
TWIG_FILL_EXP = 0.25        # cards grow by (kept share of the fans) ^ -this when the triangle cap thins them
TWIG_SCALE_EXP = 0.5        # cards shrink by (the family's median instance scale) ^ -this: needles stay nearer one size
#                             on big and small trees (a shared prototype cannot cancel the instance scale fully)
TWIG_TEXEL = 0.5            # twig cards' texel density in a mesh slot (they only need the crown's light: ~3 texels)
TWIG_SPRITE_DETAIL = 1.0    # sprite renders: the colour times (1 + (2 R - 1) * this), the page's detail baked in
TWIG_TAG = "tw1"            # in mesh-bake and sprite cache names of twig-card pines; bump when TWIG_TEX changes
# Crown normals: before the bake, foliage (cushions and needle cards) gets the normal of a smoothed copy of the tree's
# foliage (the gradient of its blurred vertex density on a CROWN_CELL grid): CROWN_MIX of the plate-scale blur
# (sigma CROWN_SIGMA[0]) and the rest of the whole-crown blur (CROWN_SIGMA[1]), so a decimated cushion no longer bakes
# per-facet light and dark patches and the cards shade as one soft volume. Cards add CROWN_UP of +Z (sky-lit tops,
# like nature._needle_fan's up_w); cushions keep CROWN_OWN of their own vertex normal.
CROWN_CELL = 0.25
CROWN_SIGMA = (0.45, 1.4)
CROWN_MIX = 0.6
CROWN_UP = 0.3
CROWN_OWN = 0.15
# The shade variant (instances whose crown sees no sun) keeps the sun at SHADE_SUN of its energy, raised to at least
# SHADE_SUN_ELEV_DEG (one variant serves every yaw, so its sun must not light one side), instead of switching it off:
# shade pines baked near-black (median 0.02 on a 0-1 display scale).
SHADE_SUN = 0.3
SHADE_SUN_ELEV_DEG = 45.0
LIGHT_TAG = "l2"            # in the cache names of shade-variant bakes and sprites; bump when SHADE_SUN* change
TREE_TRANSPARENT_BOUNCES = 24   # the tree rig's Cycles transparent bounces (many twig cards overlap along a ray)
# Bushes (see the module docstring). SHRUB_MESH_PX: px at 1280x720 (x1.25 at 1600x900) from which a shrub is a mesh.
# From the r17 crops: crossed cards up to about 20 px wide (25 px at 1600x900) seen from the side pass for bushes;
# bigger, the two planes and the flat top show as the view moves.
SHRUB_MESH_PX = 20.0
SHRUB_STEEP_PX = 12.0       # seen from above (camera STEEP_DEG+ over it) a card shows its flat top sprite crossed by
#                             the vertical planes ("lily pads" on the arena lawn): from above it is a mesh from this
STEEP_DEG = 25.0
SHRUB_HERO_PX = 40.0        # leafy near bushes this big (screen_px) use the '.hero' shrub; smaller ones the '.low' one
SHRUB_HOLD_NEAR = 0.0       # m: also a mesh when a hold camera sees it this near (0: off; screen_px covers the holds)
BETWEEN_PX_W = 0.6          # screen_px: weight of the between look views (the visitor can turn anywhere, rarely does)
SHRUB_LEAF_MAT = "M.nature_shrub_leaf"        # leaf sprays (nature._needle_fan, _mat_needle with 8 wide leaves)
SHRUB_FLOWER_MAT = "M.nature_flower_azalea"   # azalea flower quads (nature._bm_flower)
SHRUB_LEAF_ALPHA = dict(needles=8.0, spread=2.3, width=0.12)   # nature 'nature_shrub_leaf' (_mat_needle arguments)
SHRUB_BLOB_TRIS = 800       # leafy near bush: its clumps (M.nature_shrub) collapse-decimated to about this many tris
SHRUB_SLOT_PX = 224         # leafy near bush ('.hero'): mesh slot (the blob shrub's was SLOT_PX shrub, 160)
SHRUB_SLOT_PX_LOW = 160     # leafy near bush ('.low')
SHRUB_LEAF_GROW = 1.7       # leafy near bush: every leaf spray grown about its root (the r17 verify renders: at the
#                             prototype's 0.11-0.18 m the sprays hid inside the clumps' outline and the bush read as a
#                             smooth moss ball; grown, they break the outline into leaves)
SHRUB_FLOWER_SRGB = (0.91, 0.43, 0.56)   # leafy near bush: the opaque flower quads bake this flat pink (the petal
#                             #e0587a a little lighter); with the material's own ramp the square's corners (rim #c8385c)
#                             and dark centre baked them red-orange, where the far cards' cut-out flowers read pink
SHRUB_TAG = "lf3"           # in the mesh-bake cache names of leafy bushes; bump when shrub_near_mesh changes


def needle_style(fam, a):
    """Pine style whose near mesh keeps its needle cards ('huangshan', 'cliff', 'ancient'), else None."""
    p = fam.split(".")
    if a is None or getattr(a, "no_needles", False) or len(p) < 2 or p[0] != "pine":
        return None
    return p[1] if p[1] in NEEDLE_OPAQUE_TRIS else None


def full_mesh_source(fam, a=None):
    """(object, decimation ratio); needle pines use '.hero' (else '.mid'; --needle-lod mid: the other way round, the
    pilot's choice) and decimate per part (needle_near_mesh)."""
    if needle_style(fam, a):
        lods = (".mid", ".hero") if getattr(a, "needle_lod", "hero") == "mid" else (".hero", ".mid")
        return proto_obj(fam + lods[0]) or proto_obj(fam + lods[1]), 1.0
    if leafy_shrub(fam, a):
        return proto_obj(fam) or proto_obj(fam + ".low"), 1.0
    ob, ratio = mesh_source(fam)
    return ob, FULL_RATIO.get(fam.split(".")[0], ratio)


def leafy_shrub(fam, a):
    """True when a shrub family's near mesh is the leafy bush (--shrub-mesh leafy): clumps + leaf cards (+ flowers)."""
    return fam.split(".")[0] == "shrub" and a is not None and getattr(a, "shrub_mesh", "blob") == "leafy"


def slot_px(fam, a):
    """Mesh-slot size (px) of a family's near mesh: FULL_SLOT_PX by kind, SHRUB_SLOT_PX for a leafy bush."""
    if leafy_shrub(fam, a):
        return SHRUB_SLOT_PX_LOW if fam.endswith(".low") else SHRUB_SLOT_PX
    return FULL_SLOT_PX.get(fam.split(".")[0], 128)


def opaque_tris(style, a=None):
    """Trunk + cushion triangles of a needle pine's near mesh: NEEDLE_OPAQUE_TRIS, or --needle-opaque-tris
    'huangshan,cliff,ancient' (e.g. 1000,1200,1600: the pilot's)."""
    s = getattr(a, "needle_opaque_tris", "") if a is not None else ""
    if s:
        v = dict(zip(("huangshan", "cliff", "ancient"), (int(x) for x in s.split(","))))
        if style in v:
            return v[style]
    return NEEDLE_OPAQUE_TRIS[style]


def light_tag(a):
    """Cache-name tag of the shade variant's lighting ('' with --shade-sun 0: the old sun-off bake and its caches)."""
    s = getattr(a, "shade_sun", SHADE_SUN)
    return "" if s <= 0 else "%s.s%d" % (LIGHT_TAG, int(round(s * 100)))


def twig_on(a):
    """True when needle pines get twig cards (--needle-cards twig and TWIG_TEX on disk)."""
    return a is not None and getattr(a, "needle_cards", "twig") == "twig" and os.path.isfile(TWIG_TEX)


def needle_lod(r, a):
    """'full' or 'lite' needle cards for a near-pine record: full where a hold camera sees it within
    --needle-full-near m, the path passes within --needle-full-d m, or it is a click target; 'lite' elsewhere (a
    --needle-lite-tris subset of the same baked cards, grown to keep the cover)."""
    if r.get("hot") or r["hold"] <= a.needle_full_near or r["d"] <= a.needle_full_d:
        return "full"
    return "lite"


def full_remove(fam, a=None):
    keep = KEEP_MATS.get(fam.split(".")[0], ())
    if needle_style(fam, a):
        keep = keep + (NEEDLE_MAT,)
    if leafy_shrub(fam, a):
        keep = keep + (SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT)
    return tuple(m for m in REMOVE_MATS if m not in keep)


def flat_colour_nodes(m, srgb):
    """Every BSDF of material m but the transparent ones takes one flat colour (sRGB 0-1) instead of its linked one."""
    lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb) + (1.0,)
    nt = m.node_tree
    for n in nt.nodes:
        if not n.bl_idname.startswith("ShaderNodeBsdf") or n.bl_idname == "ShaderNodeBsdfTransparent":
            continue
        for nm in ("Base Color", "Color"):
            sk = n.inputs.get(nm)
            if sk is not None:
                for l in list(sk.links):
                    nt.links.remove(l)
                sk.default_value = lin


def grow_fans(me, mask, k):
    """Scale every fan (connected piece of the polygons in `mask`) about its root vertex (UV v ~ 0, nature._needle_fan)
    by k, in place. Returns the number of fans grown."""
    mi, ls, lt, vi = _poly_arrays(me)
    sub = np.nonzero(mask)[0]
    if not len(sub):
        return 0
    lay = me.uv_layers.get("UVMap") or (me.uv_layers[0] if len(me.uv_layers) else None)
    if lay is None:
        return 0
    uv = np.empty(len(vi) * 2, np.float32)
    lay.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    # pieces: union of the fans' vertices (faces sharing a vertex), by repeated min-label propagation
    pl = np.repeat(np.arange(len(ls)), lt)
    lm = mask[pl]
    v_l, p_l = vi[lm], pl[lm]
    lab = np.arange(len(me.vertices))
    for _ in range(64):
        fmin = np.full(len(ls), len(lab), np.int64)
        np.minimum.at(fmin, p_l, lab[v_l])
        new = lab.copy()
        np.minimum.at(new, v_l, fmin[p_l])
        if (new == lab).all():
            break
        lab = new
    root_l = lm & (uv[:, 1] < 0.02)
    root = {}
    for v in vi[root_l]:
        root.setdefault(int(lab[v]), co[v])
    verts = np.unique(v_l)
    for v in verts:
        r = root.get(int(lab[v]))
        if r is not None:
            co[v] = r + (co[v] - r) * k
    me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.update()
    return len(root)


def shrub_near_mesh(fam, me, dec, blob_tris, crown=True):
    """Leafy near bush from a shrub prototype (its '.hero' LOD, else '.low'): the clumps (every face that is not a leaf
    spray or a flower) collapse-decimated to about `blob_tris`, the leaf sprays (SHRUB_LEAF_MAT, cut-out cards on the
    page) and the azalea flowers (SHRUB_FLOWER_MAT, small opaque quads) kept whole. Crown normals over the whole bush
    (crown=False: not), so it bakes as one soft rounded mass instead of per-clump facets. Returns (mesh, info)."""
    mats = [m.name if m else "" for m in me.materials]
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    keep = np.zeros(len(mi), bool)
    for m in (SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT):
        if m in mats:
            keep |= mi == mats.index(m)
    field = crown_field(me) if crown else None
    info = {}
    lt = np.empty(len(mi), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    for m, k in ((SHRUB_LEAF_MAT, "leaf"), (SHRUB_FLOWER_MAT, "flower")):
        if m in mats:
            info[k + "_tris"] = int((lt[mi == mats.index(m)] - 2).sum())
    if SHRUB_LEAF_MAT in mats and SHRUB_LEAF_GROW != 1.0:
        info["leaf_grow"] = grow_fans(me, mi == mats.index(SHRUB_LEAF_MAT), SHRUB_LEAF_GROW)
    if (~keep).any():
        blob = EW.submesh(me, ~keep, me.name + ".blob")
        n0 = ntris(blob)
        r = min(1.0, blob_tris / max(n0, 1))
        blob = dec.get("tree.%s.blob" % fam, blob, r)
        info.update(blob_tris_source=n0, blob_tris=ntris(blob), ratio=round(r, 3))
        if keep.any():
            cards = EW.submesh(me, keep, me.name + ".cards")
            parts = [blob, cards] if "UVMap" in blob.uv_layers else [cards, blob]
            out = join_meshes(parts, "tree.near." + fam)
        else:
            out = blob.copy()
            out.name = "tree.near." + fam
    else:
        out = me
    if field is not None:
        info.update(crown_normals=crown_normals(out, field))
    info["tris"] = ntris(out)
    return out, info


def _poly_arrays(me):
    """(material index, loop start, loop total) per polygon and vertex index per loop."""
    npl, nl = len(me.polygons), len(me.loops)
    mi, ls, lt, vi = (np.empty(n, np.int32) for n in (npl, npl, npl, nl))
    me.polygons.foreach_get("material_index", mi)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    me.loops.foreach_get("vertex_index", vi)
    return mi, ls, lt, vi


def fan_pieces(me):
    """Connected piece per polygon (faces sharing a vertex: one needle fan each), numbered in creation order."""
    mi, ls, lt, vi = _poly_arrays(me)
    npl = len(ls)
    f_of_l = np.repeat(np.arange(npl), lt)
    lab = np.arange(npl)
    for _ in range(1000):
        vm = np.full(len(me.vertices), npl, np.int64)
        np.minimum.at(vm, vi, lab[f_of_l])
        new = np.minimum.reduceat(vm[vi], ls)
        new = new[new]
        if (new == lab).all():
            break
        lab = new
    return np.unique(lab, return_inverse=True)[1].ravel()


def join_meshes(meshes, name):
    """One mesh from meshes with the same material slots (bmesh appends them; the first mesh sets the data layers,
    the others' layers are matched by name). UV maps missing from some of the meshes are added to them (zeros)
    first, so none is dropped."""
    import bmesh
    names = []
    for me in meshes:
        names += [l.name for l in me.uv_layers if l.name not in names]
    for me in meshes:
        for nm in names:
            if nm not in me.uv_layers:
                me.uv_layers.new(name=nm, do_init=False)
    bm = bmesh.new()
    for me in meshes:
        bm.from_mesh(me)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in meshes[0].materials:
        out.materials.append(m)
    return out


def needle_near_mesh(fam, me, dec, opaque_tris, max_needle_tris, twig=None, crown=True):
    """Near mesh of a pine that keeps its needle-fan cards: trunk and cushions collapse-decimated to about
    `opaque_tris` (collapse would shred the cards, so they are split off first), the fans kept whole but thinned when
    they hold more than `max_needle_tris` triangles: an evenly spaced share of the fans in creation order (ring by ring
    around each pad), offset seeded by the family name, so a family always gets the same mesh (mesh-bake cache).
    twig = {"scale": the family's median instance scale}: every kept fan becomes a twig card (twig_cards, 2 triangles
    each, so the cap keeps max_needle_tris / 2 of them), else the fans stay. Foliage then gets crown normals
    (crown_normals, from the whole source foliage; crown=False: not). Returns (mesh, info)."""
    mats = [m.name if m else "" for m in me.materials]
    mi, ls, lt, vi = _poly_arrays(me)
    nd = mi == mats.index(NEEDLE_MAT) if NEEDLE_MAT in mats else np.zeros(len(mi), bool)
    field = crown_field(me) if crown else None
    if not nd.any():
        n0 = ntris(me)
        r = min(1.0, opaque_tris / max(n0, 1))
        out = dec.get("tree." + fam, me, r)
        if field is not None:
            out = out.copy()
            out.name = "tree.near." + fam
            crown_normals(out, field)
        return out, dict(fans=0, needle_tris=0, opaque_tris_source=n0, opaque_tris=ntris(out), ratio=round(r, 3))
    fans = EW.submesh(me, nd, me.name + ".needle")
    pid = fan_pieces(fans)
    lt2 = _poly_arrays(fans)[2]
    ptri = np.full(int(pid.max()) + 1, 2.0) if twig is not None else np.bincount(pid, lt2 - 2)
    total = int(ptri.sum())
    kept = np.ones(len(ptri), bool)
    if 0 < max_needle_tris < total:
        u0 = np.random.default_rng(zlib.crc32(fam.encode())).random()
        k = max_needle_tris / float(total)
        j = np.arange(len(ptri))
        while True:
            kept = np.floor((j + 1) * k + u0) > np.floor(j * k + u0)
            if ptri[kept].sum() <= max_needle_tris:
                break
            k *= 0.98
        if twig is None:
            fans = EW.submesh(fans, kept[pid], me.name + ".needle.thin")
    info = dict(fans=int(kept.sum()), fans_source=len(ptri), needle_tris=int(ptri[kept].sum()),
                needle_tris_source=total)
    if twig is not None:
        size = twig_size(float(kept.mean()), twig["scale"])
        fans, tinfo = twig_cards(fans, pid, kept, fam, size, me.name + ".twig")
        info.update(cards=int(kept.sum()), card_size=round(size, 3), **tinfo)
    if (~nd).any():
        solid = EW.submesh(me, ~nd, me.name + ".opaque")
        n0 = ntris(solid)
        r = min(1.0, opaque_tris / max(n0, 1))
        solid = dec.get("tree.%s.opaque" % fam, solid, r)
        # the first mesh sets the layers: the decimated part, unless it lost the UV map that holds the fan UVs
        parts = [solid, fans] if "UVMap" in solid.uv_layers else [fans, solid]
        out = join_meshes(parts, "tree.near." + fam)
        info.update(opaque_tris_source=n0, opaque_tris=ntris(solid), ratio=round(r, 3))
    else:
        out = fans
    if field is not None:
        info.update(crown_normals=crown_normals(out, field))
    return out, info


def twig_size(keep, scale):
    """Twig card side / source fan length: TWIG_LEN_K, grown when the cap kept only `keep` of the fans, shrunk on a
    family whose instances are scaled up (median `scale`)."""
    k = TWIG_LEN_K * max(keep, 0.05) ** -TWIG_FILL_EXP * min(max(scale, 0.5), 3.0) ** -TWIG_SCALE_EXP
    return float(min(max(k, 0.6), 2.0))


def twig_cards(fans, pid, kept, fam, size, name):
    """One twig card per kept needle fan (`pid`: fan per polygon of `fans`, `kept`: per fan): a flat square quad, its
    root edge centred on the fan's root, along the fan's axis (root -> middle of the rim) in the fan's plane, side
    `size` x the fan's length. UV maps: 'UVMap' in the fans' convention (root (0.5, 0); x = (u - 0.5) * 2 and y = v
    in card lengths: the card spans u 0.25-0.75, v 0-1), which _mat_needle's colour and the bake islands read;
    'twig' = one TWIG_TEX cell (seeded per fan; half of them mirrored), the page's card texture (TEXCOORD_1).
    Material slots as on `fans`. Returns (mesh, info)."""
    mats = [m.name if m else "" for m in fans.materials]
    nmi = mats.index(NEEDLE_MAT) if NEEDLE_MAT in mats else 0
    mi, ls, lt, vi = _poly_arrays(fans)
    nv = len(fans.vertices)
    co = np.empty(nv * 3, np.float64)
    fans.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lay = fans.uv_layers.get("UVMap") or next((l for l in fans.uv_layers if l.active_render), None)
    uv = np.zeros(len(vi) * 2, np.float32)
    if lay is not None:
        lay.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2).astype(np.float64)
    nf = len(kept)
    lp = pid[np.repeat(np.arange(len(ls)), lt)]       # fan per loop
    p = co[vi]
    root_l = uv[:, 1] < 0.02                            # the fan's root corner (v 0); the rim is at v ~1.06
    rim_l = ~root_l

    def per_fan(w, x):
        return np.stack([np.bincount(lp, w * x[:, k], nf) for k in range(3)], 1)
    wr, wm = root_l.astype(np.float64), rim_l.astype(np.float64)
    nr = np.maximum(np.bincount(lp, wr, nf), 1e-9)[:, None]
    nm = np.maximum(np.bincount(lp, wm, nf), 1e-9)[:, None]
    root = per_fan(wr, p) / nr
    rim = per_fan(wm, p) / nm
    d = rim - root
    ln = np.linalg.norm(d, axis=1)
    d = d / np.maximum(ln, 1e-9)[:, None]
    # side: rim corners weighted by how far right of the fan's axis their UV is
    side = per_fan(wm * (uv[:, 0] - 0.5), p - root[lp])
    side -= d * (side * d).sum(1, keepdims=True)
    sl = np.linalg.norm(side, axis=1)
    alt = np.cross(d, np.array([0.0, 0.0, 1.0]))
    bad = sl < 1e-6
    side[bad] = alt[bad]
    side /= np.maximum(np.linalg.norm(side, axis=1), 1e-9)[:, None]
    flen = np.sqrt(np.bincount(lp, wm * ((p - root[lp]) ** 2).sum(1), nf) / nm[:, 0]) / 1.06
    keep = np.nonzero(kept & (np.bincount(lp, wr, nf) > 0) & (np.bincount(lp, wm, nf) > 0))[0]
    L = flen[keep] * size
    r0, dd, ss = root[keep], d[keep], side[keep]
    h = 0.5 * L[:, None] * ss
    quad = np.stack([r0 - h, r0 + h, r0 + h + dd * L[:, None], r0 - h + dd * L[:, None]], 1)   # (n, 4, 3)
    n = len(keep)
    vco = quad.reshape(-1, 3).astype(np.float32)
    vidx = np.arange(4 * n, dtype=np.int32)
    out = BW.make_mesh(name, vco, vidx, np.arange(0, 4 * n, 4, dtype=np.int32), np.full(n, nmi, np.int32))
    for m in fans.materials:
        out.materials.append(m)
    fu = np.tile(np.array([[0.25, 0.0], [0.75, 0.0], [0.75, 1.0], [0.25, 1.0]], np.float32), (n, 1))
    rng = np.random.default_rng(zlib.crc32(("twig." + fam).encode()))
    cell = rng.integers(0, TWIG_GRID * TWIG_GRID, len(kept))[keep]
    mirror = (rng.random(len(kept)) < 0.5)[keep]
    loc = np.tile(np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), (n, 1))
    loc[:, 0] = np.where(np.repeat(mirror, 4), 1.0 - loc[:, 0], loc[:, 0])
    cx = np.repeat(cell % TWIG_GRID, 4).astype(np.float32)
    cy = np.repeat(cell // TWIG_GRID, 4).astype(np.float32)
    tu = np.stack([(cx + loc[:, 0]) / TWIG_GRID, (cy + loc[:, 1]) / TWIG_GRID], 1)
    for lname, data in (("UVMap", fu), ("twig", tu)):
        lay = out.uv_layers.new(name=lname)
        lay.data.foreach_set("uv", np.ascontiguousarray(data, np.float32).ravel())
    out.uv_layers["UVMap"].active_render = True
    _set_smooth(out, np.ones(n, bool))
    # card sides in prototype metres (the canonical 10 m tree; x the instance scale on the page): 5/50/95 %
    return out, dict(card_m=[round(float(np.percentile(L, q)), 3) for q in (5, 50, 95)] if n else [],
                     fan_m=round(float(np.median(flen[keep])), 3) if n else 0.0)


def twig_sprite_mesh(fam, me, size, mat_twig, crown=True):
    """Card-sprite source of a pine (its '.hero' LOD): every needle fan replaced by a twig card (all of them: sprites
    have no triangle budget) on `mat_twig` (cut out by TWIG_TEX's G, with its detail), crown normals on the foliage
    (crown=False: not). None when the mesh has no needle fans."""
    mats = [m.name if m else "" for m in me.materials]
    if NEEDLE_MAT not in mats:
        return None
    k = mats.index(NEEDLE_MAT)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    nd = mi == k
    if not nd.any():
        return None
    field = crown_field(me) if crown else None
    fans = EW.submesh(me, nd, me.name + ".needle")
    pid = fan_pieces(fans)
    cards, _ = twig_cards(fans, pid, np.ones(int(pid.max()) + 1, bool), fam, size, me.name + ".twig")
    out = join_meshes([EW.submesh(me, ~nd, me.name + ".opaque"), cards], "tree.card.twig." + fam) \
        if (~nd).any() else cards
    if field is not None:
        crown_normals(out, field)                       # (reads the slot names: before the material swap)
    out.materials[k] = mat_twig
    if "UVMap" in out.uv_layers:
        out.uv_layers["UVMap"].active_render = True     # _mat_needle's colour ramp reads the fan-convention UVs
    return out


def lite_cards(me, nd, lite_tris, fam):
    """The 'lite' near mesh of a twig-card pine (needle_lod 'lite'): an evenly spaced lite_tris / 2 of its cards (offset
    seeded by the family), each grown about its root edge by (kept share) ^ -TWIG_FILL_EXP to keep the cover. The
    same vertices and UVs as the full mesh, so one bake serves both. {"keep": per-polygon mask, "co": vertex
    positions (float32, n x 3), "cards", "grow", "tris"}."""
    mi, ls, lt, vi = _poly_arrays(me)
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    idx = np.nonzero(nd)[0]
    n = len(idx)
    keep = np.ones(len(ls), bool)
    want = max(0, int(lite_tris) // 2)
    if n == 0 or want >= n:
        return dict(keep=keep, co=co, cards=n, grow=1.0, tris=ntris(me))
    u0 = np.random.default_rng(zlib.crc32(("lite." + fam).encode())).random()
    j = np.arange(n)
    sel = np.floor((j + 1) * (want / n) + u0) > np.floor(j * (want / n) + u0)
    keep[idx[~sel]] = False
    grow = float(min(2.0, max(sel.mean(), 0.05) ** -TWIG_FILL_EXP))
    uv = np.zeros(len(vi) * 2, np.float32)
    lay = me.uv_layers.get("UVMap")
    if lay is not None:
        lay.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    card = np.zeros(len(ls), bool)
    card[idx[sel]] = True
    pl = np.repeat(np.arange(len(ls)), lt)          # polygon per loop
    lk = card[pl]
    rl = (lk & (uv[:, 1] < 0.5)).astype(np.float64)  # root-edge corners ('UVMap' v 0)
    cnt = np.maximum(np.bincount(pl, rl, len(ls)), 1e-9)
    root = np.stack([np.bincount(pl, rl * co[vi, k], len(ls)) for k in range(3)], 1) / cnt[:, None]
    v = vi[lk]
    r = root[pl[lk]]
    co = co.copy()
    co[v] = (r + (co[v] - r) * grow).astype(np.float32)
    lt_k = lt[keep]
    return dict(keep=keep, co=co, cards=int(sel.sum()), grow=round(grow, 3), tris=int((lt_k - 2).sum()))


def _set_smooth(me, mask):
    """Smooth shading on the polygons in `mask` (custom normals need it on any Blender)."""
    sm = np.empty(len(me.polygons), bool)
    me.polygons.foreach_get("use_smooth", sm)
    sm |= np.asarray(mask, bool)
    me.polygons.foreach_set("use_smooth", sm)


FOLIAGE_MATS = (NEEDLE_MAT, "M.nature_shrub", SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT)


def _foliage_mask(me):
    """Per polygon: cushions, needle cards, a bush's clumps, leaves and flowers (materials '*pine_pad*' and
    FOLIAGE_MATS), not bark."""
    mats = [m.name if m else "" for m in me.materials]
    fol = np.array([("pine_pad" in m) or m in FOLIAGE_MATS for m in mats] or [False], bool)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    return fol[np.clip(mi, 0, len(fol) - 1)], mats


def _blur3(a, sigma):
    """Separable Gaussian blur of a 3D array (sigma in cells), zero outside."""
    r = int(math.ceil(3.0 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    for ax in range(3):
        pad = [(r, r) if i == ax else (0, 0) for i in range(3)]
        p = np.pad(a, pad)
        n = a.shape[ax]
        a = sum(w * np.take(p, np.arange(j, j + n), axis=ax) for j, w in enumerate(k))
    return a


def crown_field(me):
    """Smoothed foliage of a source tree mesh for crown_normals: the vertex density of its cushions and needle cards
    (prototype space) splatted on a CROWN_CELL grid and blurred at each CROWN_SIGMA, with the gradients. None without
    foliage."""
    fol, _ = _foliage_mask(me)
    if not fol.any():
        return None
    mi, ls, lt, vi = _poly_arrays(me)
    used = np.zeros(len(me.vertices), bool)
    used[vi[np.repeat(fol, lt)]] = True
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    pts = co.reshape(-1, 3)[used]
    pad = 3.0 * max(CROWN_SIGMA) + 2 * CROWN_CELL
    lo = pts.min(0) - pad
    shape = tuple(int(x) for x in np.ceil((pts.max(0) + pad - lo) / CROWN_CELL) + 2)
    g = np.zeros(shape)
    f = (pts - lo) / CROWN_CELL
    i0 = np.floor(f).astype(np.int64)
    t = f - i0
    for c in range(8):                       # trilinear splat
        o = np.array([(c >> 0) & 1, (c >> 1) & 1, (c >> 2) & 1])
        w = np.prod(np.where(o, t, 1.0 - t), axis=1)
        np.add.at(g, tuple((i0 + o).T), w)
    dens = [_blur3(g, s / CROWN_CELL) for s in CROWN_SIGMA]
    grads = [np.stack(np.gradient(dd, CROWN_CELL), -1) for dd in dens]
    return dict(lo=lo, grads=grads, shape=shape, points=len(pts))


def _sample3(field, arr, q):
    """Trilinear sample of a (X, Y, Z, C) grid array at points q (prototype space)."""
    f = np.clip((q - field["lo"]) / CROWN_CELL, 0.0, np.array(field["shape"]) - 1.001)
    i0 = np.floor(f).astype(np.int64)
    t = f - i0
    out = 0.0
    for c in range(8):
        o = np.array([(c >> 0) & 1, (c >> 1) & 1, (c >> 2) & 1])
        w = np.prod(np.where(o, t, 1.0 - t), axis=1)
        out = out + arr[tuple((i0 + o).T)] * w[:, None]
    return out


def crown_normals(me, field):
    """Custom normals for the foliage of a tree mesh (see CROWN_*): the outward normal of the smoothed foliage (minus
    the blurred density's gradient, plate and crown blurs mixed), + CROWN_UP of +Z on needle cards, CROWN_OWN of the
    vertex's own normal on cushions; bark keeps its automatic normals. Read by the bake (shading normal); the GLBs
    carry no normals. Returns the foliage vertex count."""
    fol, mats = _foliage_mask(me)
    if not fol.any():
        return 0
    mi, ls, lt, vi = _poly_arrays(me)
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    card = np.zeros(nv, bool)
    pad = np.zeros(nv, bool)
    cut = [k for k, m in enumerate(mats) if m in (NEEDLE_MAT, SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT)]   # card-like faces
    lf = np.repeat(fol, lt)
    lnd = np.repeat(np.isin(mi, cut), lt)
    card[vi[lf & lnd]] = True
    pad[vi[lf & ~lnd]] = True
    pad &= ~card
    sel = card | pad
    q = co[sel]
    n = np.zeros((len(q), 3))
    for w, gr in zip((CROWN_MIX, 1.0 - CROWN_MIX), field["grads"]):
        gv = -_sample3(field, gr, q)
        gl = np.linalg.norm(gv, axis=1, keepdims=True)
        n += w * np.where(gl > 1e-9, gv / np.maximum(gl, 1e-9), [[0.0, 0.0, 1.0]])
    up = np.array([[0.0, 0.0, 1.0]])
    own = np.empty(nv * 3, np.float64)
    me.vertex_normals.foreach_get("vector", own)
    own = own.reshape(-1, 3)[sel]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    is_card = card[sel][:, None]
    n = np.where(is_card, n * (1.0 - CROWN_UP) + up * CROWN_UP, n * (1.0 - CROWN_OWN) + own * CROWN_OWN)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    out = np.zeros((nv, 3))
    out[sel] = n
    _set_smooth(me, fol)
    if hasattr(me, "use_auto_smooth"):          # Blender < 4.1 uses custom normals only with auto smooth
        me.use_auto_smooth = True
    me.normals_split_custom_set_from_vertices([tuple(x) for x in out.tolist()])
    return int(sel.sum())


def needle_loops(me, layer="UVMap", mat=NEEDLE_MAT):
    """(per-polygon needle mask, per-loop UVs of `layer` on the needle cards with zeros elsewhere) of a near mesh
    with needle cards: 'UVMap' = the fan UVs (the bake islands; fans: also the page's needle UVs), 'twig' = twig
    cards' TWIG_TEX cell UVs (the page's card UVs). mat: the cards' material (SHRUB_LEAF_MAT: a bush's leaves)."""
    mats = [m.name if m else "" for m in me.materials]
    mi, ls, lt, vi = _poly_arrays(me)
    nd = mi == mats.index(mat) if mat in mats else np.zeros(len(mi), bool)
    fan = np.zeros((len(vi), 2), np.float32)
    lay = me.uv_layers.get(layer) or (next((l for l in me.uv_layers if l.active_render), None)
                                      if layer == "UVMap" else None)
    if lay is None:
        log("WARN no %s UVs on" % layer, me.name)
        return nd, fan
    u = np.empty(len(vi) * 2, np.float32)
    lay.data.foreach_get("uv", u)
    nl = np.repeat(nd, lt)
    fan[nl] = u.reshape(-1, 2)[nl]
    return nd, fan


def _hash01(k):
    """Cycles' hash_float_to_float (White Noise texture, 1D; its Color R is the same number): lookup3 final() of the
    float's bits, / 0xFFFFFFFF."""
    def rot(x, s):
        return (x << np.uint32(s)) | (x >> np.uint32(32 - s))
    kx = np.ascontiguousarray(k, np.float32).view(np.uint32)
    a = np.full(kx.shape, 0xdeadbeef + (1 << 2) + 13, np.uint32)
    b, c = a.copy(), a.copy()
    a = a + kx
    c = (c ^ b) - rot(b, 14)
    a = (a ^ c) - rot(c, 11)
    b = (b ^ a) - rot(a, 25)
    c = (c ^ b) - rot(b, 16)
    a = (a ^ c) - rot(c, 4)
    b = (b ^ a) - rot(a, 14)
    c = (c ^ b) - rot(b, 24)
    return c.astype(np.float64) / float(0xFFFFFFFF)


def _sstep(x, e0, e1):
    """Map Range SMOOTHSTEP from e0 to e1 (0-1, reversed edges allowed), like materials.smooth."""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def needle_alpha(px=NEEDLE_ALPHA_PX, ss=4, needles=34.0, spread=1.5, width=0.014, blur=0.6):
    """Alpha of nature._mat_needle (its defaults) in fan-UV space: root at (0.5, 0), x = (u - 0.5) * 2 and y = v in
    card lengths, rho = |(x, y)|, phi = atan2(x, y); `needles` tapered needles over `spread` radians, each with a
    jittered angle and its own length (0.62-1). Supersampled ss x ss, box-filtered, blurred `blur` px (Gaussian, edges
    clamped like the sampler) so mip levels keep the needles. (px, px) float32, numpy row 0 = v 0."""
    n = px * ss
    t = (np.arange(n) + 0.5) / n
    u, y = np.meshgrid(t, t)
    x = (u - 0.5) * 2.0
    rho = np.sqrt(x * x + y * y)
    phi = np.arctan2(x, y)
    f = (phi / spread + 0.5) * needles
    cell = np.floor(f)
    fr = f - cell
    h = _hash01(cell)
    jit = (h - 0.5) * 0.5
    ln = 0.62 + 0.38 * h
    arc = np.abs(fr - 0.5 - jit) * (spread / needles) * rho
    taper = width * np.clip(1.0 - rho / ln, 0.0, 1.0) * _sstep(rho, 0.02, 0.3)
    al = _sstep(arc - taper, 0.004, -0.004) * _sstep(rho, ln, ln * 0.94) * _sstep(rho, 0.0, 0.04)
    al = al.reshape(px, ss, px, ss).mean((1, 3))
    if blur > 0:
        r = int(math.ceil(blur * 3))
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / blur) ** 2)
        k /= k.sum()
        for ax in (0, 1):
            p = np.pad(al, [(r, r) if i == ax else (0, 0) for i in (0, 1)], mode="edge")
            al = sum(w * np.take(p, np.arange(j, j + px), axis=ax) for j, w in enumerate(k))
    return al.astype(np.float32)


def save_grey_png(arr, path):
    """8-bit greyscale PNG (colour type 0) of a 0-1 array, numpy row 0 = bottom (Blender's image rows), so the file's
    top row is v = 1. Written directly: the glTF exporter embeds the file's own bytes."""
    a = np.flipud(np.clip(np.round(np.asarray(arr) * 255.0), 0, 255).astype(np.uint8))
    h, w = a.shape

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + a[r].tobytes() for r in range(h))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) +
                 chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return path


def twig_image():
    """TWIG_TEX as a Blender image (Non-Color: G is coverage, R the luminance detail)."""
    im = bpy.data.images.load(TWIG_TEX, check_existing=True)
    im.colorspace_settings.name = "Non-Color"
    return im


def twig_alpha_nodes(m, img, detail=0.0):
    """Copy of M.nature_pine_needle on twig cards: every user of the procedural 34-needle alpha (the Principled
    alpha, the transparent / translucent mix) reads TWIG_TEX's G on the 'twig' UV map instead; the colour keeps
    _mat_needle's root -> tip ramp (on the cards' fan-convention 'UVMap'). detail > 0 (sprite renders): the base
    colour is also multiplied by 1 + (2 R - 1) * detail, the photographed needles' light and dark. False when the
    node tree is not the expected one (the fans' alpha then stays)."""
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None or not bsdf.inputs["Alpha"].is_linked:
        log("WARN twig material: unexpected node tree", m.name)
        return False
    old = bsdf.inputs["Alpha"].links[0].from_socket
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "twig"
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img
    tn.extension = "EXTEND"
    tn.interpolation = "Linear"
    nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tn.outputs["Color"], sep.inputs["Color"])
    for l in list(old.links):
        to = l.to_socket
        nt.links.remove(l)
        nt.links.new(sep.outputs["Green"], to)
    base = bsdf.inputs["Base Color"]
    if detail > 0 and base.is_linked:
        src = base.links[0].from_socket
        k = nt.nodes.new("ShaderNodeMath")
        k.operation = "MULTIPLY_ADD"                  # R * 2 detail + (1 - detail)
        nt.links.new(sep.outputs["Red"], k.inputs[0])
        k.inputs[1].default_value = 2.0 * detail
        k.inputs[2].default_value = 1.0 - detail
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        nt.links.new(src, mul.inputs[0])
        nt.links.new(k.outputs[0], mul.inputs[1])
        nt.links.new(mul.outputs["Vector"], base)
    return True


def needle_bake_nodes(m):
    """Mesh-slot bake copy of M.nature_pine_needle (or its twig copy, twig_alpha_nodes): opaque to the bake itself
    (the texel holds the needle colour; the page cuts the needles with its card texture), but transparent where the
    needle alpha is 0 to the rays the bake traces from other surfaces: shadow rays (Light Path 'Is Shadow Ray'), so the
    sun still reaches the cushions between the needles, and diffuse / glossy / transmission bounces (the twig cards
    cover about 4x the fans' area: kept opaque to bounces they would shut the sky out of the crown)."""
    nt = m.node_tree
    outn = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output), None) or \
        next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if outn is None or bsdf is None or not outn.inputs["Surface"].is_linked:
        log("WARN needle bake material: unexpected node tree", m.name)
        return
    alpha = bsdf.inputs["Alpha"].links[0].from_socket if bsdf.inputs["Alpha"].is_linked else None
    for l in list(bsdf.inputs["Alpha"].links):
        nt.links.remove(l)
    bsdf.inputs["Alpha"].default_value = 1.0
    for n in [n for n in nt.nodes if n.bl_idname == "ShaderNodeMixShader"]:     # mix(alpha, transparent, translucent)
        for k in (1, 2):
            if n.inputs[k].is_linked and n.inputs[k].links[0].from_node.bl_idname == "ShaderNodeBsdfTransparent":
                for l in list(n.inputs[0].links):
                    nt.links.remove(l)
                n.inputs[0].default_value = 1.0 if k == 1 else 0.0              # the other (translucent) shader
    if alpha is None:
        return
    surf = outn.inputs["Surface"].links[0].from_socket
    lp = nt.nodes.new("ShaderNodeLightPath")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation, inv.use_clamp = "SUBTRACT", True
    inv.inputs[0].default_value = 1.0
    nt.links.new(alpha, inv.inputs[1])
    ray = lp.outputs["Is Shadow Ray"]
    for nm in ("Is Diffuse Ray", "Is Glossy Ray", "Is Transmission Ray"):
        if lp.outputs.get(nm) is None:
            continue
        add = nt.nodes.new("ShaderNodeMath")
        add.operation, add.use_clamp = "ADD", True
        nt.links.new(ray, add.inputs[0])
        nt.links.new(lp.outputs[nm], add.inputs[1])
        ray = add.outputs[0]
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    nt.links.new(ray, fac.inputs[0])
    nt.links.new(inv.outputs[0], fac.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(fac.outputs[0], mix.inputs[0])
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], outn.inputs["Surface"])


def gltf_output_group():
    """The glTF exporter's 'glTF Material Output' node group (its Occlusion input becomes occlusionTexture), as the
    glTF add-on itself creates it; an existing one is reused (an Occlusion input added if missing)."""
    ng = next((g for g in bpy.data.node_groups if g.bl_idname == "ShaderNodeTree" and
               g.name.lower().startswith("gltf material output")), None)
    if ng is None:
        ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        ng.nodes.new("NodeGroupOutput")
        ng.nodes.new("NodeGroupInput")
    if not any(s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == "Occlusion" for s in ng.interface.items_tree):
        ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


def needle_material(name, path, alpha_path, mode="needle"):
    """trees.needle.<area>: the area's tree-mesh atlas on the 'bake' UV (texCoord 0) like trees.mesh, plus the card
    texture (clamped) on the 'needle' UV (texCoord 1) into the glTF Material Output group's Occlusion input, which the
    exporter writes as occlusionTexture with the file's own PNG bytes. Opaque and double-sided in the file; extras
    cardAlpha = mode (the page moves that map to the alpha map):
      'needle': needle_alpha.png (greyscale alpha) on the fans' own UVs;
      'twig':   TWIG_TEX (RGB: G coverage, R luminance detail with 0.5 neutral, B 0) on the twig cards' cell UVs."""
    m = tex_material(name, path, alpha=False)
    m.use_backface_culling = False
    nt = m.node_tree
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(alpha_path, check_existing=True)
    tn.image.colorspace_settings.name = "Non-Color"
    tn.extension = "EXTEND"                  # sampler CLAMP_TO_EDGE: the fans' rim UVs reach v 1.06
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "needle"
    nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = gltf_output_group()
    nt.links.new(tn.outputs["Color"], grp.inputs["Occlusion"])
    m["cardAlpha"] = mode
    return m


def classify(kind, d, px, a, spx=0.0, hold=float("inf"), steep=0.0):
    """'mesh', 'card' or None (dropped) from the nearest visible distance and the largest on-screen size (px: the
    audit's px_eff; spx: screen_px, shrubs only; hold: the nearest distance a hold camera sees it at; steep: screen_px
    over the views that look down on it)."""
    if kind == "grass":
        return "mesh" if d < a.grass_near else None
    if kind == "lotus":
        return "mesh" if d < a.lotus_near else None
    if kind == "shrub":
        if (d < a.shrub_near or (a.shrub_mesh_px > 0 and spx >= a.shrub_mesh_px) or hold <= a.shrub_hold_near or
                (a.shrub_steep_px > 0 and steep >= a.shrub_steep_px)):
            return "mesh"
        return "card" if px >= 3 else None
    if kind == "bamboo":
        return "mesh" if d < a.bamboo_near else ("card" if px >= 2 else None)
    return "mesh" if d < a.tree_near else ("card" if px >= 2 else None)


def ntris(me):
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum())


def screen_px(R, vis, views, idx, tv, between_w=BETWEEN_PX_W):
    """Per record of idx: (largest on-screen size in px at 1280x720, like the audit's pxmax; the view index giving it;
    the largest over the hold views only: each hold's path frame and its look-around views; the largest over the views
    that look down on it from STEEP_DEG or more above, weighted like the first). Over every audit view
    whose visibility bit (vis, the cache's columns) is set: full size on the path and the hold look views, x between_w
    on the between look views. Size = the record's largest bounds extent over its distance (camera to the bounds'
    centre, at least that extent). A view counts only when that centre lies in front of the camera and inside the 16:9
    frame widened by the record's bounding radius. The audit's px_eff is no use here: export_web.project takes a piece
    that straddles the camera plane as filling the frame, so bushes 400+ m off read 216-360 px (pxmax_look) in look
    views that only graze them."""
    lo, hi = R.lo[idx], R.hi[idx]
    c = 0.5 * (lo + hi)
    ext = hi - lo
    size = ext.max(1)
    rad = 0.5 * np.linalg.norm(ext, axis=1)
    kpx = 720.0 / (2.0 * tv)
    th = tv * EW.ASPECT
    kx, ky = math.sqrt(1.0 + th * th), math.sqrt(1.0 + tv * tv)
    best = np.zeros(len(idx))
    arg = np.full(len(idx), -1, np.int64)
    hold = np.zeros(len(idx))
    steep = np.zeros(len(idx))
    s_steep = math.sin(math.radians(STEEP_DEG))
    hold_frames = {int(x["holdFrame"]) for x in EW.AREAS}
    pv = np.nonzero(views.path)[0]
    hold_cols = set(int(pv[np.argmin(np.abs(views.frames[pv] - f))]) for f in hold_frames)
    hold_cols |= set(np.nonzero((views.kind == EW.VIEW_HOLD))[0].tolist())
    vsub = vis[idx]
    for j, M in enumerate(views.mats):
        on = vsub[:, j]
        if not on.any():
            continue
        Mi = np.linalg.inv(np.asarray(M, float))
        v = c @ Mi[:3, :3].T + Mi[:3, 3]
        z = -v[:, 2]
        ok = on & (z > -rad) & (np.abs(v[:, 0]) - th * z <= rad * kx) & (np.abs(v[:, 1]) - tv * z <= rad * ky)
        if not ok.any():
            continue
        dist = np.maximum(np.linalg.norm(c - views.pos[j], axis=1), size)
        px = np.where(ok, size / dist * kpx, 0.0)
        w = between_w if views.kind[j] == EW.VIEW_BETWEEN else 1.0
        up = px * w > best
        best = np.where(up, px * w, best)
        arg = np.where(up, j, arg)
        if j in hold_cols:
            hold = np.maximum(hold, px)
        above = (views.pos[j][2] - c[:, 2]) >= s_steep * dist
        steep = np.where(above, np.maximum(steep, px * w), steep)
    return best, arg, hold, steep


def full_plan(a, sc):
    """Vegetation records of the whole path with chunk, class, hold distance, click target and proxy flag."""
    t0 = time.time()
    R = EW.gather(sc)
    S, cache_frames = EW.load_cache(R)
    frames = np.asarray([int(f) for f in cache_frames])
    ch, ids = EW.load_chunks(R)
    with open(os.path.join(EW.WORK, "chunks.json"), encoding="utf-8") as fh:
        cplan = {c["id"]: c for c in json.load(fh)["chunks"]}
    px = S["px_eff"].astype(float)               # path pxmax, or the weighted look views' when larger
    dmin = S["d_eff"].astype(float)              # path dmin, or the weighted look views' when nearer
    vis = S["vis"]
    members = EW.hotspot_members()
    labels = {h["id"]: h["label"] for h in EW.HOTSPOT_DEFS}
    veg = np.array([BW.is_veg_rec(R, i) for i in range(len(R))], bool)
    idx = np.nonzero(veg & S["any"] & (px >= EW.MIN_PX) & (ch >= -1))[0]
    cam = bpy.data.objects[EW.CAMERA]
    th, tv = EW.camera_tan(cam)
    views = EW.load_views(cam)                   # path frames, then the look-around views (cache column order)
    frames = views.frames
    cam_pos = views.pos
    # nearest distance at which a hold camera sees the record: its forward 16:9 frame (depth-tested bit of the
    # nearest sampled path frame), or any of the hold's look-around views (they stand at the hold camera; their
    # distance counts x VIEW_D_SCALE, the half weight the look views get for detail)
    hold_frames = [int(x["holdFrame"]) for x in EW.AREAS]
    near_hold = np.full(len(R), np.inf)
    pv = np.nonzero(views.path)[0]
    for f, M in zip(hold_frames, EW.sample_matrices(cam, hold_frames)):
        inside, film, d, _, _ = EW.project(R, M, tv, EW.ASPECT)
        j = int(pv[np.argmin(np.abs(frames[pv] - f))])
        near_hold = np.where(film & vis[:, j], np.minimum(near_hold, d), near_hold)
        lk = np.nonzero((views.kind == EW.VIEW_HOLD) & (frames == f))[0]
        if len(lk):
            dl = d * EW.VIEW_D_SCALE[EW.VIEW_HOLD]
            near_hold = np.where(vis[:, lk].any(1), np.minimum(near_hold, dl), near_hold)
    # bushes: their largest on-screen size over every view (screen_px), for the mesh-or-card choice
    sh = np.array([i for i in idx if parse(R.tkey[i])[0] == "shrub"], np.int64)
    spx, sview, shold, sstp = (np.zeros(len(R)), np.full(len(R), -1, np.int64), np.zeros(len(R)), np.zeros(len(R)))
    if len(sh):
        t1 = time.time()
        b, j, hp, st_ = screen_px(R, vis, views, sh, tv, a.between_px_w)
        spx[sh], sview[sh], shold[sh], sstp[sh] = b, j, hp, st_
        log("screen px of", len(sh), "shrubs over", len(views), "views in", round(time.time() - t1, 1), "s; tan_v",
            round(tv, 4), "px per m at 100 m", round(720.0 / (2.0 * tv) / 100.0, 2))
    recs = []
    drops = collections.Counter()
    for i in idx:
        kind, fam, lod = parse(R.tkey[i])
        d, p = float(dmin[i]), float(px[i])
        hid = members.get(R.owner[i], "")
        cls = classify(kind, d, p, a, float(spx[i]), float(near_hold[i]), float(sstp[i]))
        if cls == "mesh" and ch[i] == -1 and kind == "shrub":    # the global set holds cards only (backdrop_trees)
            cls = "card"
        if hid and kind not in SMALL_KINDS and d < a.hot_near:
            cls = "mesh"
        if cls is None:
            drops[kind] += 1
            continue
        recs.append(dict(i=int(i), kind=kind, fam=fam, cls=cls, chunk=int(ch[i]), d=d, px=p, hot=hid,
                         hold=float(near_hold[i]), proxy=False, fpx=0.0, spx=float(spx[i]),
                         sview=int(sview[i]), shold=float(shold[i]), sstp=float(sstp[i])))
        r = recs[-1]
        # leafy bushes: the '.low' shrub (3-4 clumps, 50 leaf sprays) unless seen big (--shrub-hero-px) or clickable
        if (kind == "shrub" and cls == "mesh" and leafy_shrub(fam, a) and not hid and
                max(r["spx"], r["sstp"]) < a.shrub_hero_px and proto_obj(fam) is not None and
                proto_obj(fam + ".low") is not None):
            r["fam"] = fam + ".low"
    # proxies: largest on-screen size while the camera is outside the chunk's core range and the record is visible
    cand = [r for r in recs if r["chunk"] >= 0 and r["kind"] not in SMALL_KINDS]
    if cand:
        ci = np.array([r["i"] for r in cand])
        lo, hi = R.lo[ci], R.hi[ci]
        ext = hi - lo
        size = np.maximum(ext[:, 2], np.maximum(ext[:, 0], ext[:, 1]))
        kpx = 720.0 / (2.0 * tv)
        core = np.array([cplan[ids[r["chunk"]]]["core"] for r in cand], float)
        fpx = np.zeros(len(ci))
        vsub = vis[ci]
        for j, (f, pos) in enumerate(zip(frames, cam_pos)):
            m = ((f < core[:, 0]) | (f > core[:, 1])) & vsub[:, j]
            if not m.any():
                continue
            dd = np.linalg.norm(np.maximum(np.maximum(lo - pos, pos - hi), 0.0), axis=1)
            # look views count at their size weight (VIEW_PX_WEIGHT), like pxmax_look
            fpx = np.where(m, np.maximum(fpx, size / np.maximum(dd, 1.0) * kpx * views.pxw[j]), fpx)
        for r, v in zip(cand, fpx):
            r["fpx"] = float(v)
            r["proxy"] = bool(v >= (3.0 if r["kind"] == "shrub" else 2.0))
    log("full plan:", len(idx), "visible vegetation instances ->", len(recs), "kept; dropped", dict(drops),
        round(time.time() - t0, 1), "s")
    return dict(R=R, S=S, ch=ch, ids=ids, cplan=cplan, recs=recs, drops=drops, labels=labels, frames=frames,
                tv=tv, members=members, views=views)


SPX_BANDS = (0, 5, 10, 15, 20, 25, 30, 40, 60, 100, 1e9)


def bush_report(P, a):
    """plan.json 'bushes': every shrub by class, family, chunk and largest on-screen size (screen_px at 1280x720),
    the cards' nearest distances, the views that make the biggest cards big, and the meshes' estimated triangles."""
    R, recs, ids = P["R"], P["recs"], P["ids"]
    views = P["views"]
    sh = [r for r in recs if r["kind"] == "shrub"]
    out = dict(rule=dict(shrub_near=a.shrub_near, shrub_mesh_px=a.shrub_mesh_px, shrub_hold_near=a.shrub_hold_near,
                         between_px_w=a.between_px_w, shrub_mesh=a.shrub_mesh,
                         px_unit="px at 1280x720 (x1.25 at 1600x900)", dropped_shrubs=int(P["drops"].get("shrub", 0))))
    out["by_class"] = dict(collections.Counter(r["cls"] for r in sh))
    out["by_family"] = dict(sorted(collections.Counter("%s/%s" % (r["cls"], r["fam"]) for r in sh).items()))
    owners = collections.Counter()
    for r in sh:
        o = R.owner[r["i"]]
        owners["%s/%s" % (r["cls"], o.rsplit(".", 1)[0] if o.rsplit(".", 1)[-1].isdigit() else o)] += 1
    out["by_owner"] = dict(owners.most_common(40))
    bands = {}
    for cls in ("card", "mesh"):
        rows = []
        for b0, b1 in zip(SPX_BANDS[:-1], SPX_BANDS[1:]):
            rr = [r for r in sh if r["cls"] == cls and b0 <= r["spx"] < b1]
            if rr:
                dd = np.array([r["d"] for r in rr])
                rows.append(dict(px="%g-%g" % (b0, b1), n=len(rr), d_min=round(float(dd.min()), 1),
                                 d_median=round(float(np.median(dd)), 1),
                                 hold_views=sum(1 for r in rr if r["sview"] >= 0 and
                                                views.kind[r["sview"]] == EW.VIEW_HOLD),
                                 between_views=sum(1 for r in rr if r["sview"] >= 0 and
                                                   views.kind[r["sview"]] == EW.VIEW_BETWEEN)))
        bands[cls] = rows
    out["by_screen_px"] = bands
    per = {}
    for k, cid in enumerate(ids + ["backdrop"]):
        kk = k if cid != "backdrop" else -1
        rk = [r for r in sh if r["chunk"] == kk]
        cards = [r for r in rk if r["cls"] == "card"]
        per[cid] = dict(meshes=sum(1 for r in rk if r["cls"] == "mesh"), cards=len(cards),
                        cards_px_ge=dict((str(t), sum(1 for r in cards if r["spx"] >= t))
                                         for t in (10, 15, 20, 25, 30, 50)),
                        cards_steep_px_ge=dict((str(t), sum(1 for r in cards if r["sstp"] >= t))
                                               for t in (8, 10, 12, 15, 20)),
                        meshes_hero=sum(1 for r in rk if r["cls"] == "mesh" and not r["fam"].endswith(".low")),
                        cards_max_px=round(max([r["spx"] for r in cards] or [0.0]), 1),
                        cards_hold_px_max=round(max([r["shold"] for r in cards] or [0.0]), 1),
                        meshes_hold_near=sum(1 for r in rk if r["cls"] == "mesh" and r["hold"] <= a.hold_mesh_near))
    out["per_file"] = per
    top = sorted([r for r in sh if r["cls"] == "card"], key=lambda r: -max(r["spx"], r["sstp"]))[:25]
    out["cards_steep"] = [dict(px="%g-%g" % (b0, b1),
                               n=sum(1 for r in sh if r["cls"] == "card" and b0 <= r["sstp"] < b1))
                          for b0, b1 in zip(SPX_BANDS[:-1], SPX_BANDS[1:])]
    out["meshes_by_lod"] = dict(collections.Counter(("low" if r["fam"].endswith(".low") else "hero")
                                                    for r in sh if r["cls"] == "mesh"))
    out["largest_cards"] = [dict(owner=R.owner[r["i"]], fam=r["fam"], chunk=ids[r["chunk"]] if r["chunk"] >= 0 else
                                 "backdrop", px=round(r["spx"], 1), hold_px=round(r["shold"], 1), d=round(r["d"], 1),
                                 view_frame=int(views.frames[r["sview"]]) if r["sview"] >= 0 else -1,
                                 view_kind=int(views.kind[r["sview"]]) if r["sview"] >= 0 else -1,
                                 steep_px=round(r["sstp"], 1),
                                 at=[round(float(x), 1) for x in 0.5 * (R.lo[r["i"]] + R.hi[r["i"]])],
                                 size=round(float((R.hi[r["i"]] - R.lo[r["i"]]).max()), 2)) for r in top]
    return out


def write_plan(P, a):
    R, recs, ids = P["R"], P["recs"], P["ids"]
    per = {}
    for k, cid in enumerate(ids + ["backdrop"]):
        kk = k if cid != "backdrop" else -1
        rk = [r for r in recs if r["chunk"] == kk]
        pines = [r for r in rk if r["cls"] == "mesh" and needle_style(r["fam"], a)]
        per[cid] = dict(
            by_class=dict(sorted(collections.Counter("%s/%s" % (r["cls"], r["kind"]) for r in rk).items())),
            hold_cards=sum(1 for r in rk if r["cls"] == "card" and r["hold"] <= a.hold_card_near),
            hold_meshes=sum(1 for r in rk if r["cls"] == "mesh" and r["hold"] <= a.hold_mesh_near),
            needle_pines=dict(collections.Counter(needle_lod(r, a) if twig_on(a) else "full" for r in pines)),
            proxy=sum(1 for r in rk if r["proxy"]),
            click_targets=dict(collections.Counter(r["hot"] for r in rk if r["hot"])))
    protos = {}
    for fam in sorted({r["fam"] for r in recs}):
        row = {}
        if any(r["fam"] == fam and r["cls"] == "mesh" for r in recs):
            ob, ratio = full_mesh_source(fam, a)
            if ob is not None:
                row["mesh"] = dict(object=ob.name, tris=ntris(ob.data), ratio=ratio,
                                   materials=[m.name if m else "" for m in ob.data.materials],
                                   removed=list(full_remove(fam, a)))
                st = needle_style(fam, a)
                if st:
                    row["mesh"].update(needles="twig" if twig_on(a) else "fan", opaque_tris=opaque_tris(st, a),
                                       needle_max_tris=a.needle_max_tris,
                                       needle_lite_tris=a.needle_lite_tris if twig_on(a) else None)
        if any(r["fam"] == fam and (r["cls"] == "card" or r["proxy"]) for r in recs):
            ob = card_source(fam)
            row["card"] = ob.name if ob is not None else None
        protos[fam] = row
    hot_owners = collections.defaultdict(set)
    for r in recs:
        if r["hot"]:
            hot_owners[r["hot"]].add(R.owner[r["i"]])
    # bushes: the near mesh's triangles per family (planned, before the build), per file
    est = {}
    for fam, row in protos.items():
        if fam.startswith("shrub") and "mesh" in row:
            ob = bpy.data.objects.get(row["mesh"]["object"])
            if ob is None:
                continue
            mats = [m.name if m else "" for m in ob.data.materials]
            mi, ls, lt, vi = _poly_arrays(ob.data)
            t = {m: int((lt[mi == k] - 2).sum()) for k, m in enumerate(mats)}
            if leafy_shrub(fam, a):
                blob = sum(v for m, v in t.items() if m not in (SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT))
                est[fam] = min(blob, a.shrub_blob_tris) + t.get(SHRUB_LEAF_MAT, 0) + t.get(SHRUB_FLOWER_MAT, 0)
            else:
                blob = sum(v for m, v in t.items() if m not in full_remove(fam, a))
                est[fam] = int(round(blob * row["mesh"]["ratio"]))
            row["mesh"]["near_tris_est"] = est[fam]
    for k, cid in enumerate(ids + ["backdrop"]):
        kk = k if cid != "backdrop" else -1
        per[cid]["shrub_mesh_tris_est"] = sum(est.get(r["fam"], 0) for r in recs
                                              if r["chunk"] == kk and r["kind"] == "shrub" and r["cls"] == "mesh")
    out = dict(kept=len(recs), dropped=dict(P["drops"]), per_file=per, protos=protos,
               click_target_owners={k: sorted(v) for k, v in hot_owners.items()},
               bushes=bush_report(P, a),
               options={k: v for k, v in vars(a).items() if k not in ("commands",)})
    os.makedirs(FULL_OUT, exist_ok=True)
    BW.dump(os.path.join(FULL_OUT, "plan.json"), out)
    log("PLAN", json.dumps({k: (v["by_class"], v["proxy"], v["hold_cards"]) for k, v in per.items()}))


def push_pull(rgba):
    """RGB of the transparent texels (alpha <= 0.02) from the nearest opaque ones: average down a pyramid with
    alpha weights, fill the holes from the coarser levels (the same fill as tools/sect_pack.py). Alpha unchanged."""
    w = (rgba[..., 3:4] > 0.02).astype(np.float64)
    c = rgba[..., :3].astype(np.float64) * w
    levels = [(c, w)]
    while min(levels[-1][1].shape[:2]) > 1:
        c0, w0 = levels[-1]
        h, wd = c0.shape[:2]
        h2, w2 = (h + 1) // 2, (wd + 1) // 2
        cp = np.zeros((h2 * 2, w2 * 2, 3))
        wp = np.zeros((h2 * 2, w2 * 2, 1))
        cp[:h, :wd] = c0
        wp[:h, :wd] = w0
        levels.append((cp.reshape(h2, 2, w2, 2, 3).sum((1, 3)), wp.reshape(h2, 2, w2, 2, 1).sum((1, 3))))
    col = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)
    for c0, w0 in reversed(levels[:-1]):
        h, wd = c0.shape[:2]
        up = np.repeat(np.repeat(col, 2, 0), 2, 1)[:h, :wd]
        col = np.where(w0 > 0, c0 / np.maximum(w0, 1e-9), up)
    out = rgba.copy()
    hole = rgba[..., 3] <= 0.02
    out[..., :3] = np.where(hole[..., None], col, rgba[..., :3]).astype(np.float32)
    return out


def box_down(a, f):
    if f <= 1:
        return a
    h, w = a.shape[:2]
    return a.reshape(h // f, f, w // f, f, a.shape[2]).mean((1, 3))


def pack_squares(sizes):
    """Shelf-packed squares in a roughly square power-of-two-wide texture (at most 4096 wide)."""
    total = float(sum(s * s for s in sizes))
    W = max(max(sizes), 1 << int(math.ceil(math.log2(max(math.sqrt(total), 1.0)))))
    while True:
        W, place = shelf_squares(sizes, W)
        if place["height"] <= W or W >= 4096:
            if place["height"] > 4096:
                log("WARN packed texture taller than 4096:", W, place["height"])
            return W, place
        W *= 2


def atlas_from(slots, div, G, gpos):
    """Mesh atlas of `slots` cut from the graded global atlas G (slot size divided by div[slot])."""
    sizes = [gpos[s][2] // div[s] for s in slots]
    W, place = pack_squares(sizes)
    H = place["height"]
    img = np.zeros((H, W, 4), np.float32)
    img[..., 3] = 1.0
    uv = {}
    for s, sz, (x, y) in zip(slots, sizes, place["pos"]):
        gx, gy, gs = gpos[s]
        img[y:y + sz, x:x + sz] = box_down(G[gy:gy + gs, gx:gx + gs], gs // sz)
        uv[s] = (x / W, y / H, sz / W, sz / H)
    return img, uv


def sheet_from(cpx, spr):
    """Card sheet: three views per (family, variant) at cpx[key] px (downsampled from the rendered sprites)."""
    cells = [(fam, v, vw) for (fam, v) in sorted(cpx) for vw in VIEWS]
    sizes = [cpx[(fam, v)] for fam, v, vw in cells]
    W, place = pack_squares(sizes)
    H = place["height"]
    sheet = np.zeros((H, W, 4), np.float32)
    uv = {}
    for cell, s, (x, y) in zip(cells, sizes, place["pos"]):
        src = spr[cell]
        sheet[y:y + s, x:x + s] = box_down(src, src.shape[0] // s)
        uv[cell] = (x / W, y / H, s / W, s / H)
    return push_pull(sheet), uv


def preview_arr(arr, path, size=1024, bg=None):
    """Downscaled copy of a display-referred RGBA array; bg = (r, g, b) composites it over a flat colour,
    bg = 'rgb' shows the colour channels with the alpha ignored (the fill under the transparent texels)."""
    h, w = arr.shape[:2]
    f = max(1, int(math.ceil(max(w, h) / size)))
    small = np.ascontiguousarray(arr[::f, ::f]).copy()
    if isinstance(bg, str):
        small[..., 3] = 1.0
    elif bg is not None:
        al = small[..., 3:4]
        small[..., :3] = small[..., :3] * al + np.array(bg, np.float32) * (1 - al)
        small[..., 3] = 1.0
    save_png(small, "preview", path)


def card_object(name, lst, R, C, uvs, mat):
    co, uv, faces = [], [], []
    for r in lst:
        fam, v = r["fam"], r["cvar"]
        lo, hi = C["card_geo"][fam]
        c = 0.5 * (lo + hi)
        M = np.asarray(R.mw[r["i"]], float)
        quads = card_quads(c, lo, hi, {vw: C["spr_scale"][(fam, vw)] for vw in VIEWS},
                           {vw: uvs[(fam, v, vw)] for vw in VIEWS})
        for q_co, q_uv in quads:
            base = len(co)
            for p, t in zip(q_co, q_uv):
                co.append(M[:3, :3] @ np.asarray(p) + M[:3, 3])
                uv.append(t)
            faces.append((base, base + 1, base + 2, base + 3))
    co = np.array(co, np.float32)
    vi = np.array(faces, np.int32).ravel()
    ls = np.arange(0, len(vi), 4, dtype=np.int32)
    me = BW.make_mesh(name, co, vi, ls)
    lay = me.uv_layers.new(name="bake")
    lay.data.foreach_set("uv", np.array(uv, np.float32)[vi].ravel())
    me.materials.append(mat)
    return bpy.data.objects.new(name, me), 2 * len(faces)


def full_build(a, sc, P):
    log_tree_quality(a)
    T = {}
    t0 = time.time()
    R, recs, ids = P["R"], P["recs"], P["ids"]
    if getattr(a, "only_recs", False) and a.only:          # test builds: only the --only chunks' records
        keep = {ids.index(c) for c in a.only.split(",") if c in ids}
        recs = [r for r in recs if r["chunk"] in keep]
        P["recs"] = recs
        log("--only-recs:", len(recs), "records of", sorted(ids[k] for k in keep))
    for d in (FULL_CACHE, FULL_OUT, FULL_RAW, os.path.join(FULL_CACHE, "mesh"), os.path.join(FULL_CACHE, "sprites"),
              os.path.join(FULL_CACHE, "tex")):
        os.makedirs(d, exist_ok=True)
    # ---- prototype meshes (local space) and card sources
    dec = BW.Decimator(sc)
    twig = twig_on(a)
    if a.needle_cards == "twig" and not twig and not a.no_needles:
        log("WARN", TWIG_TEX, "missing (tools/prep_textures.mjs --twig-only): needle pines keep the procedural fans")
    t_img = twig_image() if twig else None
    # the families' median instance scale (twig card size: needles nearer one size on big and small trees)
    fam_scale = {}
    for r in recs:
        fam_scale.setdefault(r["fam"], []).append(float(np.linalg.norm(np.asarray(R.mw[r["i"]], float)[:3, :3],
                                                                       axis=0).mean()))
    fam_scale = {f: round(float(np.median(v)), 1) for f, v in fam_scale.items()}
    fam_mesh, fam_card = {}, {}
    fam_needle, fam_nd, fam_fan = {}, {}, {}      # needle pines: build info, needle polygon mask, fan UVs per loop
    fam_nuv, fam_lite = {}, {}                    # twig cards: card UVs per loop (TEXCOORD_1), the lite subset
    fam_cut, fam_shrub = {}, {}                   # cut-out cards per family ('pine' needles/twigs, 'leaf'), bush info
    for fam in sorted({r["fam"] for r in recs if r["cls"] == "mesh"}):
        ob, ratio = full_mesh_source(fam, a)
        if ob is None:
            log("WARN no mesh source for", fam)
            continue
        me = ob.data.copy()
        me.name = "tree.src." + fam
        EW._slot_materials(me, ob)
        me = strip_faces(me, full_remove(fam, a))
        st = needle_style(fam, a)
        if leafy_shrub(fam, a):
            me, info = shrub_near_mesh(fam, me, dec, a.shrub_blob_tris, crown=not a.no_crown_normals)
            nd, fan = needle_loops(me, mat=SHRUB_LEAF_MAT)
            if nd.any():
                fam_nd[fam], fam_fan[fam], fam_cut[fam] = nd, fan, "leaf"
            fam_shrub[fam] = dict(info, source=ob.name)
            log("bush proto", fam, json.dumps(fam_shrub[fam]))
        elif st:
            me, info = needle_near_mesh(fam, me, dec, opaque_tris(st, a), a.needle_max_tris,
                                        twig=dict(scale=fam_scale.get(fam, 1.0)) if twig else None,
                                        crown=not a.no_crown_normals)
            nd, fan = needle_loops(me)
            if nd.any():
                fam_nd[fam], fam_fan[fam], fam_cut[fam] = nd, fan, "pine"
                if twig:
                    fam_nuv[fam] = needle_loops(me, "twig")[1]
                    fam_lite[fam] = lite_cards(me, nd, a.needle_lite_tris, fam)
                    info.update(lite_cards=int(fam_lite[fam]["cards"]), lite_grow=fam_lite[fam]["grow"])
            fam_needle[fam] = dict(info, source=ob.name, scale=fam_scale.get(fam, 1.0))
            log("needle proto", fam, json.dumps(fam_needle[fam]))
        elif ratio < 0.999:
            me = dec.get("tree." + fam, me, ratio)
        fam_mesh[fam] = me
        log("mesh proto", fam, ob.name, ntris(ob.data), "->", ntris(me), "tris")
    if not any(v == "pine" for v in fam_cut.values()):
        p_alpha = None
    elif twig:
        p_alpha = TWIG_TEX
    else:
        p_alpha = save_grey_png(needle_alpha(), os.path.join(FULL_OUT, "needle_alpha.png"))
    p_leaf = save_grey_png(needle_alpha(**SHRUB_LEAF_ALPHA), os.path.join(FULL_OUT, "leaf_alpha.png")) \
        if any(v == "leaf" for v in fam_cut.values()) else None
    for fam in sorted({r["fam"] for r in recs if r["cls"] == "card" or r["proxy"] or r["chunk"] == -1}):
        ob = card_source(fam)
        if ob is None:
            log("WARN no card source for", fam)
            continue
        fam_card[fam] = ob
    for r in recs:
        if r["cls"] == "mesh" and r["fam"] not in fam_mesh:
            r["cls"] = "card" if r["fam"] in fam_card else None
        if r["cls"] == "card" and r["fam"] not in fam_card:
            r["cls"] = None
        if r["fam"] not in fam_card:
            r["proxy"] = False
    recs = [r for r in recs if r["cls"]]
    P["recs"] = recs

    # ---- crown points + sun visibility (cached by record key) + lighting variants
    sun = bpy.data.objects["look.sun"]
    sdir = np.array(sun.matrix_world.to_3x3().col[2].normalized())
    bbox = {}

    def fam_box(key, me):
        if key not in bbox:
            n = len(me.vertices)
            co = np.empty(n * 3, np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(n, 3) if n else np.zeros((1, 3), np.float32)
            bbox[key] = (co.min(0).astype(float), co.max(0).astype(float))
        return bbox[key]
    pts, rad = [], []
    for r in recs:
        lo, hi = fam_box(("m", r["fam"]), fam_mesh[r["fam"]]) if r["cls"] == "mesh" else \
            fam_box(("c", r["fam"]), fam_card[r["fam"]].data)
        M = np.asarray(R.mw[r["i"]], float)
        c = 0.5 * (lo + hi)
        c[2] = lo[2] + 0.6 * (hi[2] - lo[2])
        pts.append(M[:3, :3] @ c + M[:3, 3])
        sc3 = np.linalg.norm(M[:3, :3], axis=0)
        rad.append(0.5 * max((hi[0] - lo[0]) * sc3[0], (hi[1] - lo[1]) * sc3[1]))
    t1 = time.time()
    keys = [R.key[r["i"]] for r in recs]
    vp = os.path.join(FULL_CACHE, "sunvis.npz")
    old = {}
    if os.path.isfile(vp) and not a.fresh:
        z = np.load(vp, allow_pickle=False)
        old = dict(zip(z["keys"].tolist(), z["vis"].tolist()))
    miss = [k for k, key in enumerate(keys) if key not in old]
    if miss:
        log("sun visibility: casting for", len(miss), "of", len(keys), "instances,", len(keys) - len(miss), "cached")
        v = sun_visibility(sc, [pts[k] for k in miss], [rad[k] for k in miss], sdir)
        for k, x in zip(miss, v):
            old[keys[k]] = float(x)
        np.savez_compressed(vp, keys=np.array(list(old.keys())), vis=np.array(list(old.values())))
    vis = np.array([old[k] for k in keys])
    T["raycast"] = round(time.time() - t1, 1)
    for r, v in zip(recs, vis):
        M = np.asarray(R.mw[r["i"]], float)
        Rm = M[:3, :3] / np.maximum(np.linalg.norm(M[:3, :3], axis=0), 1e-9)
        sl = Rm.T @ sdir
        az = math.atan2(sl[1], sl[0])
        nbm = mesh_nb(r["fam"])
        r["vis"] = float(v)
        r["mvar"] = nbm if v < 0.5 else int(round(az / (2 * math.pi / nbm))) % nbm
        r["cvar"] = CARD_NB if v < 0.5 else int(round(az / (2 * math.pi / CARD_NB))) % CARD_NB

    # ---- mesh variants: bake every (family, variant) any chunk uses (cached EXRs)
    rig = Rig(sc, a.exposure, a.sat, a.quality)
    rig.shade_sun = a.shade_sun
    rig.sc.cycles.transparent_max_bounces = TREE_TRANSPARENT_BOUNCES
    ltag = light_tag(a)
    qtag = QUALITY_TAG[a.quality]      # production renders never reuse dev caches (and dev never reuses production's)
    used_mesh = sorted({(r["fam"], r["mvar"]) for r in recs if r["cls"] == "mesh"})
    fam_uv, fam_tag = {}, {}
    for fam, me in fam_mesh.items():
        A = BW.ma(me)
        spx = slot_px(fam, a)
        co, area = A.co, A.area
        nd = fam_nd.get(fam)
        texel = TWIG_TEXEL if fam in fam_nuv else NEEDLE_TEXEL
        if nd is not None:          # needle cards get `texel` x the texel density (their own vertices: scale them)
            nv = np.zeros(A.nv, bool)
            nv[A.vi[np.repeat(nd, A.lt)]] = True
            co = np.where(nv[:, None], A.co * texel, A.co).astype(np.float32)
            ar = np.empty(A.np, np.float32)
            me.polygons.foreach_get("area", ar)
            area = float(ar[~nd].sum() + ar[nd].sum() * texel ** 2)
        rho = spx * math.sqrt(0.5 / max(area, 1e-6))
        u0 = BW.project_box26(co * rho, A.vi, A.ls)
        if nd is not None:          # one island per fan (not a sliver per projection direction): its own fan UVs,
            nl = np.repeat(nd, A.lt)        # isotropic in card lengths; pack_shelf rescales islands to their area
            f = fam_fan[fam][nl]
            u0[nl] = np.stack([(f[:, 0] - 0.5) * 2.0, f[:, 1]], 1)
        u, info = BW.pack_shelf(u0, co * rho, A.vi, A.ls, spx, margin=1.5)
        lay = me.uv_layers.new(name="bake")
        lay.data.foreach_set("uv", u.ravel())
        me.uv_layers.active = lay
        fam_uv[fam] = u
        fam_tag[fam] = "%s.p%d.s%d" % (fam, len(me.polygons), spx)
        if nd is not None:          # never an old needle-less bake: own tag, needle count and texel share in the name
            fam_tag[fam] += ".%s.n%d.t%d%s" % (NEEDLE_TAG, int(nd.sum()), int(round(texel * 100)),
                                               ".cn0" if a.no_crown_normals else "")
            if fam in fam_nuv:      # twig cards: their own tag and card size
                fam_tag[fam] += ".%s.k%d" % (TWIG_TAG, int(round(fam_needle[fam].get("card_size", 0) * 100)))
            if fam in fam_shrub:    # leafy bushes: their own tag
                fam_tag[fam] += "." + SHRUB_TAG
            if "UVMap" in me.uv_layers:
                me.uv_layers["UVMap"].active_render = True      # _mat_needle's colour (and fan alpha) read the fan UVs
    bake_px = {}

    def cache_path(fam, v):
        # the shade variant's lighting: its own tag (light_tag; none with --shade-sun 0, the old bake)
        lt_ = "." + ltag if v == mesh_nb(fam) and ltag else ""
        return os.path.join(FULL_CACHE, "mesh", "%s.%s%s%s.exr" % (fam_tag[fam], v, lt_, qtag))

    for fam in fam_mesh:
        for v in ["albedo"] + [v for f2, v in used_mesh if f2 == fam]:
            p = cache_path(fam, v)
            if os.path.isfile(p) and not a.fresh:
                im = bpy.data.images.load(p, check_existing=False)
                bake_px[(fam, v)] = pixels(im)
                bpy.data.images.remove(im)
    todo = [fam for fam in fam_mesh if any(k not in bake_px for k in
                                           [(fam, "albedo")] + [(fam, v) for f2, v in used_mesh if f2 == fam])]
    t1 = time.time()
    if todo:
        fam_obj, fam_nodes = {}, {}
        for fam in todo:
            bme = fam_mesh[fam].copy()
            bme.name = "tree.bake." + fam
            for k, m in enumerate(bme.materials):
                if m is None:
                    continue
                mc = m.copy()
                mc.name = m.name + "@tree"
                if m.name == NEEDLE_MAT and fam in fam_nd:
                    if fam in fam_nuv:
                        twig_alpha_nodes(mc, t_img)
                    needle_bake_nodes(mc)
                elif m.name in (SHRUB_LEAF_MAT, SHRUB_FLOWER_MAT) and fam in fam_shrub:
                    needle_bake_nodes(mc)       # leaves and flowers: opaque to their own texels, see-through to shadows
                    if m.name == SHRUB_FLOWER_MAT:
                        flat_colour_nodes(mc, SHRUB_FLOWER_SRGB)
                tn = mc.node_tree.nodes.new("ShaderNodeTexImage")
                mc.node_tree.nodes.active = tn
                fam_nodes.setdefault(fam, []).append(tn)
                bme.materials[k] = mc
            fam_obj[fam] = rig.add("tree.bake." + fam, bme)
        with rig.ctx():
            for fam in todo:
                spx = slot_px(fam, a)
                ob = fam_obj[fam]
                rig.only(ob)
                if (fam, "albedo") not in bake_px:
                    alb = bpy.data.images.new("tree_alb.%s" % fam, spx, spx, alpha=False, float_buffer=True)
                    for tn in fam_nodes.get(fam, []):
                        tn.image = alb
                    rig.sc.cycles.samples = tq(a)["tree_albedo"]
                    with rig.ctx(ob):
                        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, uv_layer="bake", margin=4,
                                            margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
                    bake_px[(fam, "albedo")] = pixels(alb)
                    save_float(bake_px[(fam, "albedo")], "c", cache_path(fam, "albedo"))
                rig.sc.cycles.samples = tq(a)["tree_mesh"]
                nb = mesh_nb(fam)
                for (f2, v) in used_mesh:
                    if f2 != fam or (fam, v) in bake_px:
                        continue
                    rig.light(variant_az(min(v, nb - 1), nb), shadow=(v == nb))
                    im = bpy.data.images.new("tree.%s.v%d" % (fam, v), spx, spx, alpha=False, float_buffer=True)
                    for tn in fam_nodes.get(fam, []):
                        tn.image = im
                    with rig.ctx(ob):
                        bpy.ops.object.bake(type="COMBINED",
                                            pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT", "TRANSMISSION"},
                                            uv_layer="bake", margin=4, margin_type="EXTEND", use_clear=True,
                                            target="IMAGE_TEXTURES")
                    bake_px[(fam, v)] = pixels(im)
                    save_float(bake_px[(fam, v)], "c", cache_path(fam, v))
                log("baked", fam, round(time.time() - t1, 1), "s")
    T["mesh_bakes"] = round(time.time() - t1, 1)
    log("mesh variants", len(used_mesh), "families", len(fam_mesh), "baked in", T["mesh_bakes"], "s")

    # ---- one global atlas of every mesh variant: denoise + grade like the main atlases; chunks cut their slots
    G, gpos = None, {}
    if used_mesh:
        sizes = [slot_px(fam, a) for fam, v in used_mesh]
        W, place = shelf_squares(sizes, 4096)
        H = place["height"]
        big = np.zeros((H, W, 4), np.float32)
        big[..., 3] = 1
        alb = np.zeros((H, W, 4), np.float32)
        alb[..., 3] = 1
        for (fam, v), sz, (x, y) in zip(used_mesh, sizes, place["pos"]):
            big[y:y + sz, x:x + sz] = bake_px[(fam, v)]
            alb[y:y + sz, x:x + sz] = bake_px[(fam, "albedo")]
            gpos[(fam, v)] = (x, y, sz)
        p_lin = save_float(big, "trees_full_lin", os.path.join(FULL_CACHE, "trees_mesh_lin.exr"))
        p_alb = save_float(alb, "trees_full_alb", os.path.join(FULL_CACHE, "trees_mesh_alb.exr"))
        post, n_im, n_al = BW.post_scene((W, H), a.exposure, a.sat, denoise=True, quality=a.quality)
        n_im.image = bpy.data.images.load(p_lin, check_existing=False)
        n_al.image = bpy.data.images.load(p_alb, check_existing=False)
        p_all = BW.run_post(post, os.path.join(FULL_CACHE, "trees_mesh_all.png"))
        G = BW.load_png_linear_bytes(p_all)
        preview_arr(G, os.path.join(FULL_OUT, "preview_all_mesh.png"))
        T["mesh_atlas_all"] = [W, H]

    # ---- card sprites: every (family, variant) any file uses, rendered once at the largest size a file needs
    need_px = {}
    for r in recs:
        k = (r["fam"], r["cvar"])
        if r["cls"] == "card" and r["chunk"] >= 0:
            need_px[k] = max(need_px.get(k, 0), a.hold_sprite_px if r["hold"] <= a.hold_card_near else a.sprite_px)
        if r["chunk"] == -1 or r["proxy"]:
            need_px[k] = max(need_px.get(k, 0), a.backdrop_px)
    t1 = time.time()
    cam_ob = bpy.data.objects.new("trees.cam", bpy.data.cameras.new("trees.cam"))
    rig.sc.collection.objects.link(cam_ob)
    rig.sc.camera = cam_ob
    cam_ob.data.type = "ORTHO"
    rig.sc.render.film_transparent = True
    rig.sc.render.resolution_percentage = 100
    rig.sc.cycles.samples = tq(a)["tree_sprite"]
    rig.sc.cycles.use_denoising = True
    ims = rig.sc.render.image_settings
    ims.file_format = "PNG"
    ims.color_mode = "RGBA"
    ims.color_depth = "8"
    card_geo, card_obj = {}, {}
    spr_twig, mat_twig = set(), None
    for fam, ob in fam_card.items():
        me = ob.data.copy()
        EW._slot_materials(me, ob)
        if twig and fam.split(".")[0] == "pine":       # far trees get the near trees' twig cards (finer silhouette)
            if mat_twig is None:
                src = next((m for m in me.materials if m is not None and m.name == NEEDLE_MAT), None)
                if src is not None:
                    mat_twig = src.copy()
                    mat_twig.name = NEEDLE_MAT + "@twig_sprite"
                    if not twig_alpha_nodes(mat_twig, t_img, detail=TWIG_SPRITE_DETAIL):
                        mat_twig = None
            tw = twig_sprite_mesh(fam, me, twig_size(1.0, fam_scale.get(fam, 1.0)), mat_twig,
                                  crown=not a.no_crown_normals) if mat_twig else None
            if tw is not None:
                me = tw
                spr_twig.add(fam)
        co = np.array([v.co for v in me.vertices])
        card_geo[fam] = (co.min(0), co.max(0))
        card_obj[fam] = rig.add("tree.card." + fam, me)
    if spr_twig:
        log("sprites: twig cards on", len(spr_twig), "pine card sources")

    def sprite_path(fam, v, vw, px):
        # tags: twig-card pines (TWIG_TAG + card size), the shade variant's light (light_tag); others keep their
        # cached renders
        tag = ""
        if fam in spr_twig:
            tag += ".%s.k%d%s" % (TWIG_TAG, int(round(twig_size(1.0, fam_scale.get(fam, 1.0)) * 100)),
                                  ".cn0" if a.no_crown_normals else "")
        if v == CARD_NB and ltag:
            tag += "." + ltag
        tag += qtag
        return os.path.join(FULL_CACHE, "sprites", "%s.v%d.%s.%d%s.png" % (fam, v, vw, px, tag))
    spr, spr_scale = {}, {}
    rendered = 0
    for (fam, v), spx in sorted(need_px.items()):
        lo, hi = card_geo[fam]
        c = 0.5 * (lo + hi)
        ext = hi - lo
        views = dict(front=(Vector((c[0], lo[1] - 30.0, c[2])), (math.pi / 2, 0.0, 0.0), max(ext[0], ext[2])),
                     side=(Vector((hi[0] + 30.0, c[1], c[2])), (math.pi / 2, 0.0, math.pi / 2), max(ext[1], ext[2])),
                     top=(Vector((c[0], c[1], hi[2] + 30.0)), (0.0, 0.0, 0.0), max(ext[0], ext[1])))
        lit = False
        for vw, (loc, rot, scale) in views.items():
            spr_scale[(fam, vw)] = scale * 1.04
            p = sprite_path(fam, v, vw, spx)
            big = [sprite_path(fam, v, vw, q) for q in (512, 256) if q > spx]
            big = [q for q in big if os.path.isfile(q)]
            if not a.fresh and not os.path.isfile(p) and big:     # a larger render from an earlier run
                src = push_pull(load_rgba(big[-1]))
                spr[(fam, v, vw)] = box_down(src, src.shape[0] // spx)
                continue
            if a.fresh or not os.path.isfile(p):
                if not lit:
                    rig.only(card_obj[fam])
                    rig.light(variant_az(min(v, CARD_NB - 1), CARD_NB), shadow=(v == CARD_NB))
                    lit = True
                rig.sc.render.resolution_x = rig.sc.render.resolution_y = spx
                cam_ob.location = loc
                cam_ob.rotation_mode = "XYZ"
                cam_ob.rotation_euler = rot
                cam_ob.data.ortho_scale = scale * 1.04
                cam_ob.data.clip_start, cam_ob.data.clip_end = 0.1, 200.0
                rig.sc.render.filepath = p
                bpy.ops.render.render(write_still=True, scene=rig.sc.name)
                rendered += 1
            spr[(fam, v, vw)] = push_pull(load_rgba(p))
    T["sprites"] = round(time.time() - t1, 1)
    log("sprites:", len(spr), "(", rendered, "rendered,", sum(1 for x in need_px.values() if x >= a.hold_sprite_px),
        "keys at", a.hold_sprite_px, "px) in", T["sprites"], "s")
    C = dict(G=G, gpos=gpos, fam_mesh=fam_mesh, fam_uv=fam_uv, card_geo=card_geo, spr=spr, spr_scale=spr_scale,
             labels=P["labels"], fam_nd=fam_nd, fam_fan=fam_fan, needle_alpha=p_alpha,
             needle_mode="twig" if fam_nuv else "needle", fam_nuv=fam_nuv, fam_lite=fam_lite, fam_cut=fam_cut,
             leaf_alpha=p_leaf)
    for r in recs:                  # near pines: full or lite twig cards (one bake, two meshes)
        lite = fam_lite.get(r["fam"])
        r["nlod"] = needle_lod(r, a) if r["cls"] == "mesh" and lite is not None and not lite["keep"].all() else "full"

    # ---- files
    only = set(x for x in a.only.split(",") if x)
    files = {}
    t1 = time.time()
    for k, cid in enumerate(ids):
        if only and cid not in only:
            continue
        rk = [r for r in recs if r["chunk"] == k]
        files[cid] = export_chunk(sc, a, cid, rk, R, C)
    if not only or "backdrop" in only:
        files["backdrop"] = export_backdrop(sc, a, ids, recs, R, C)
    T["export"] = round(time.time() - t1, 1)
    T["total"] = round(time.time() - t0, 1)
    tot = dict(triangles=sum(f["glb"]["triangles"] for f in files.values() if "glb" in f),
               bytes=sum(f["glb"]["bytes"] for f in files.values() if "glb" in f),
               draw_calls=sum(f["glb"]["draw_calls"] for f in files.values() if "glb" in f))
    out = dict(files=files, totals=tot, times=T, records=len(recs), bake_settings=tree_settings(a),
               lit_share=round(float(np.mean([r["vis"] >= 0.5 for r in recs])), 3),
               mesh_variants=len(used_mesh), card_keys=len(need_px),
               card_keys_hold=sum(1 for x in need_px.values() if x >= a.hold_sprite_px),
               needles=fam_needle, bushes=fam_shrub, options={k: v for k, v in vars(a).items() if k != "commands"})
    BW.dump(os.path.join(FULL_OUT, "trees_stats.json"), out)
    log("TREES FULL", json.dumps(dict(totals=tot, times=T)))
    for cid, f in files.items():
        log("FILE", cid, json.dumps({k: v for k, v in f.items() if k != "glb"}), "glb", json.dumps(f.get("glb")))


def _variant_mesh(cache, cid, fam, v, C, suv, mat, mat_needle=None, lod="full"):
    """Prototype mesh of (family, variant) on the chunk's atlas slot ('bake' UV); needle cards (pines) on mat_needle
    (material 1) with their card UVs as a second UV map 'needle' (glTF TEXCOORD_1): the fans' own UVs, or the twig
    cards' TWIG_TEX cells. lod 'lite' (twig cards): the family's lite subset (lite_cards), same UVs and slot."""
    lite = C.get("fam_lite", {}).get(fam) if lod == "lite" else None
    if lite is not None and lite["keep"].all():          # the cap already kept no more cards than the lite budget
        lite = None
    if lite is not None:
        me = cache.get((fam, v, "lite"))
        if me is None:
            full = _variant_mesh(cache, cid, fam, v, C, suv, mat, mat_needle)
            if len(full.vertices) != len(lite["co"]) or len(full.polygons) != len(lite["keep"]):
                log("WARN lite needle mesh of", fam, "does not match its full mesh: full cards used")
                cache[(fam, v, "lite")] = full
                return full
            tmp = full.copy()
            tmp.vertices.foreach_set("co", np.ascontiguousarray(lite["co"], np.float32).ravel())
            me = EW.submesh(tmp, lite["keep"], "tree.%s.%s.v%d.lite" % (cid, fam, v))
            bpy.data.meshes.remove(tmp)
            if "bake" in me.uv_layers:
                me.uv_layers["bake"].active_render = True
            cache[(fam, v, "lite")] = me
        return me
    me = cache.get((fam, v))
    if me is None:
        me = C["fam_mesh"][fam].copy()
        me.name = "tree.%s.%s.v%d" % (cid, fam, v)
        # by name: a removal shifts the layers left, so a reference held across it names the next layer (twig
        # pines carry 'UVMap' and 'twig': the stale 'twig' reference would remove 'bake')
        for nm in [l.name for l in me.uv_layers if l.name != "bake"]:
            me.uv_layers.remove(me.uv_layers[nm])
        x0, y0, sw, sh = suv[(fam, v)]
        u = C["fam_uv"][fam]
        me.uv_layers["bake"].data.foreach_set("uv", np.stack([x0 + u[:, 0] * sw, y0 + u[:, 1] * sh], 1).ravel())
        me.materials.clear()
        me.materials.append(mat)
        nd = C["fam_nd"].get(fam) if mat_needle is not None else None
        me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32) if nd is None else
                                nd.astype(np.int32))
        if nd is not None:
            me.materials.append(mat_needle)
            lay = me.uv_layers.new(name="needle")
            nuv = C.get("fam_nuv", {}).get(fam)
            lay.data.foreach_set("uv", np.ascontiguousarray(C["fam_fan"][fam] if nuv is None else nuv,
                                                            np.float32).ravel())
            me.uv_layers["bake"].active_render = True
        if me.validate(verbose=False, clean_customdata=False):
            log("validate: fixed", me.name)
        cache[(fam, v)] = me
    return me


def _finish_file(sc, coll, made, path, info, temp_meshes):
    fixed = [o.data.name for o in made if o.type == "MESH" and o.data.users == 1 and
             o.data.validate(verbose=False, clean_customdata=False)]
    if fixed:
        log("validate: fixed", fixed)
    export_trees(path, made)
    info["glb"] = EW.glb_stats(path)
    for o in made:
        bpy.data.objects.remove(o, do_unlink=True)
    for me in temp_meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)
    return info


def export_chunk(sc, a, cid, rk, R, C):
    """out/web/full/raw/<cid>_trees.glb: the chunk's near instanced meshes, its cards and its click-target trees."""
    coll = bpy.data.collections.new("web.trees." + cid)
    sc.collection.children.link(coll)
    made, temp = [], []
    st = collections.Counter()
    info = dict(file=cid + "_trees.glb")
    mesh_r = [r for r in rk if r["cls"] == "mesh"]
    card_r = [r for r in rk if r["cls"] == "card"]
    mat_mesh = mat_card = mat_needle = mat_leaf = None
    suv = spr_uv = None
    cut = C.get("fam_cut", {})
    if mesh_r:
        slots = sorted({(r["fam"], r["mvar"]) for r in mesh_r})
        full = {(r["fam"], r["mvar"]) for r in mesh_r
                if r["hold"] <= a.hold_mesh_near or r["d"] <= a.mesh_full_d or r["hot"]}
        img, suv = atlas_from(slots, {s: 1 if s in full else 2 for s in slots}, C["G"], C["gpos"])
        p = save_png(img, "trees_mesh_" + cid, os.path.join(FULL_CACHE, "tex", "%s_mesh.png" % cid))
        mat_mesh = tex_material("trees.mesh." + cid, p, alpha=False)
        if any(fam in C["fam_nd"] and cut.get(fam, "pine") == "pine" for fam, v in slots):
            mat_needle = needle_material("trees.needle." + cid, p, C["needle_alpha"], C.get("needle_mode", "needle"))
        if any(cut.get(fam) == "leaf" for fam, v in slots):      # leafy bushes: their leaf sprays' own cut-out
            mat_leaf = needle_material("trees.needle.leaf." + cid, p, C["leaf_alpha"], "needle")
        info.update(mesh_atlas=[img.shape[1], img.shape[0]], mesh_slots=len(slots), mesh_slots_full=len(full))
        preview_arr(img, os.path.join(FULL_OUT, "preview_%s_mesh.png" % cid))
    if card_r:
        cpx = {}
        for r in card_r:
            k = (r["fam"], r["cvar"])
            cpx[k] = max(cpx.get(k, 0), a.hold_sprite_px if r["hold"] <= a.hold_card_near else a.sprite_px)
        sheet, spr_uv = sheet_from(cpx, C["spr"])
        p = save_png(sheet, "trees_cards_" + cid, os.path.join(FULL_CACHE, "tex", "%s_cards.png" % cid))
        mat_card = tex_material("trees.cards." + cid, p, alpha=True)
        info.update(card_sheet=[sheet.shape[1], sheet.shape[0]], card_keys=len(cpx),
                    card_keys_hold=sum(1 for x in cpx.values() if x >= a.hold_sprite_px))
        preview_arr(sheet, os.path.join(FULL_OUT, "preview_%s_cards.png" % cid), bg=(0.45, 0.47, 0.5))
        preview_arr(sheet, os.path.join(FULL_OUT, "preview_%s_cards_rgb.png" % cid), bg="rgb")

    def card_mat(fam):
        """The cut-out material of a family's near mesh: the bush leaves' or the pines' needles / twigs."""
        return mat_leaf if cut.get(fam) == "leaf" else mat_needle
    vm = {}
    groups = collections.defaultdict(list)
    for r in mesh_r:
        if not r["hot"]:
            groups[(r["fam"], r["mvar"], r.get("nlod", "full"))].append(r)
    small = []
    for (fam, v, lod), lst in sorted(groups.items()):
        me = _variant_mesh(vm, cid, fam, v, C, suv, mat_mesh, card_mat(fam), lod)
        st["tris_mesh"] += ntris(me) * len(lst)
        if card_mat(fam) is not None:
            st["tris_leaf" if cut.get(fam) == "leaf" else "tris_needle"] += _needle_tris(C, fam, lod) * len(lst)
        if fam in C["fam_nd"] and cut.get(fam, "pine") == "pine":
            st["needle_trees_" + lod] += len(lst)
        if fam.startswith("shrub"):
            st["bush_meshes"] += len(lst)
            st["tris_bush"] += ntris(me) * len(lst)
        if len(lst) < 3:
            small += [(me, R.mw[r["i"]]) for r in lst]
            st["merged_near"] += len(lst)
            continue
        # 'trees.<area>.<family>[.lite].<shade|sunK>': the lighting variant stays the last part of the name
        g = bpy.data.objects.new("trees.%s.%s%s.%s" % (cid, fam, ".lite" if lod == "lite" else "",
                                                        "shade" if v == mesh_nb(fam) else "sun%d" % v), None)
        coll.objects.link(g)
        made.append(g)
        g["instances"] = len(lst)
        for k, r in enumerate(lst):
            o = bpy.data.objects.new("%s#%d" % (g.name[:50], k), me)
            coll.objects.link(o)
            o.parent = g
            o.matrix_basis = Matrix(np.asarray(R.mw[r["i"]], float).tolist())
            made.append(o)
        st["instances"] += len(lst)
        st["instance_groups"] += 1
    if small:
        me = merge_uv_meshes(small, "trees.near." + cid, materials=True)
        ob = bpy.data.objects.new("trees.near." + cid, me)
        coll.objects.link(ob)
        made.append(ob)
        temp.append(me)
    plain = [r for r in card_r if not r["hot"]]
    if plain:
        ob, nt = card_object("trees.cards." + cid, plain, R, C, spr_uv, mat_card)
        coll.objects.link(ob)
        made.append(ob)
        temp.append(ob.data)
        st["cards"] += len(plain)
        st["tris_cards"] += nt
    for hid in sorted({r["hot"] for r in rk if r["hot"]}):
        lst = [r for r in rk if r["hot"] == hid]
        e = bpy.data.objects.new("trees.hs." + hid, None)
        e["hotspot"] = hid
        e["label"] = C["labels"].get(hid, hid)
        coll.objects.link(e)
        made.append(e)
        ms = [r for r in lst if r["cls"] == "mesh"]
        if ms:
            me = merge_uv_meshes([(_variant_mesh(vm, cid, r["fam"], r["mvar"], C, suv, mat_mesh, card_mat(r["fam"])),
                                   R.mw[r["i"]]) for r in ms], "trees.hs.%s.mesh" % hid, materials=True)
            o = bpy.data.objects.new("trees.hs.%s.mesh" % hid, me)
            coll.objects.link(o)
            o.parent = e
            made.append(o)
            temp.append(me)
            st["tris_mesh"] += ntris(me)
            st["tris_needle"] += sum(_needle_tris(C, r["fam"]) for r in ms if card_mat(r["fam"]) is not None)
        cs = [r for r in lst if r["cls"] == "card"]
        if cs:
            o, nt = card_object("trees.hs.%s.cards" % hid, cs, R, C, spr_uv, mat_card)
            coll.objects.link(o)
            o.parent = e
            made.append(o)
            temp.append(o.data)
            st["tris_cards"] += nt
        st["click_target_trees"] += len(lst)
        info.setdefault("click_targets", {})[hid] = dict(meshes=len(ms), cards=len(cs))
    temp += list(vm.values())
    info.update(st)
    info["proxy_cards"] = sum(1 for r in rk if r["proxy"])
    return _finish_file(sc, coll, made, os.path.join(FULL_RAW, cid + "_trees.glb"), info, temp)


def export_backdrop(sc, a, ids, recs, R, C):
    """out/web/full/raw/backdrop_trees.glb (global): 'trees.far' (trees seen only beyond the 400 m band) and one
    'trees.proxy.<area>' (extras proxyOf) per area, all cards on one sheet."""
    coll = bpy.data.collections.new("web.trees.backdrop")
    sc.collection.children.link(coll)
    made, temp = [], []
    info = dict(file="backdrop_trees.glb")
    far_r = [r for r in recs if r["chunk"] == -1 and r["cls"] == "card"]
    prox = {cid: [r for r in recs if r["chunk"] == k and r["proxy"]] for k, cid in enumerate(ids)}
    cpx = {(r["fam"], r["cvar"]): a.backdrop_px for r in far_r + [r for v in prox.values() for r in v]}
    if not cpx:
        bpy.data.collections.remove(coll)
        return info
    sheet, uvs = sheet_from(cpx, C["spr"])
    p = save_png(sheet, "trees_cards_backdrop", os.path.join(FULL_CACHE, "tex", "backdrop_cards.png"))
    mat = tex_material("trees.cards.backdrop", p, alpha=True)
    info.update(card_sheet=[sheet.shape[1], sheet.shape[0]], card_keys=len(cpx))
    preview_arr(sheet, os.path.join(FULL_OUT, "preview_backdrop_cards.png"), bg=(0.45, 0.47, 0.5))
    preview_arr(sheet, os.path.join(FULL_OUT, "preview_backdrop_cards_rgb.png"), bg="rgb")
    tris = 0
    if far_r:
        e = bpy.data.objects.new("trees.far", None)
        coll.objects.link(e)
        made.append(e)
        o, nt = card_object("trees.cards.far", far_r, R, C, uvs, mat)
        coll.objects.link(o)
        o.parent = e
        made.append(o)
        temp.append(o.data)
        tris += nt
    info["far_cards"] = len(far_r)
    info["proxies"] = {}
    for cid, lst in prox.items():
        if not lst:
            continue
        e = bpy.data.objects.new("trees.proxy." + cid, None)
        e["proxyOf"] = cid
        coll.objects.link(e)
        made.append(e)
        o, nt = card_object("trees.cards.proxy." + cid, lst, R, C, uvs, mat)
        coll.objects.link(o)
        o.parent = e
        made.append(o)
        temp.append(o.data)
        tris += nt
        info["proxies"][cid] = len(lst)
    info["tris_cards"] = tris
    return _finish_file(sc, coll, made, os.path.join(FULL_RAW, "backdrop_trees.glb"), info, temp)


# ---- verify -------------------------------------------------------------------------------------------

def _emission_materials(objs, cards_alpha=0.5):
    """Imported tree materials -> unlit emission of the base-colour texture (display-referred), cards cut at
    alpha 0.5 (the web's alpha test); needle cards (trees.needle*) cut at 0.5 of their occlusion texture (the
    needle alpha the page uses as the alpha map)."""
    done = set()
    for o in objs:
        for s in o.material_slots:
            m = s.material
            if m is None or m.name in done or m.node_tree is None:
                continue
            done.add(m.name)
            nt = m.node_tree
            tex = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage"), None)
            outn = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
            if tex is None or outn is None:
                continue
            cut = tex.outputs["Alpha"] if "cards" in m.name else None
            if m.get("cardAlpha") in ("needle", "twig") or m.name.startswith("trees.needle"):
                texs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage"]
                base = [l.from_node for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"
                        for l in n.inputs["Base Color"].links]
                tex = next((n for n in texs if n in base), tex)
                al = next((n for n in texs if n is not tex), None)
                cut = al.outputs["Color"] if al is not None else None
                if al is not None and (m.get("cardAlpha") == "twig" or "twig" in (al.image.name if al.image else "")):
                    # twig cards: coverage is the G channel
                    sep = nt.nodes.new("ShaderNodeSeparateColor")
                    nt.links.new(al.outputs["Color"], sep.inputs["Color"])
                    cut = sep.outputs["Green"]
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(tex.outputs["Color"], em.inputs["Color"])
            if cut is not None:
                gt = nt.nodes.new("ShaderNodeMath")
                gt.operation = "GREATER_THAN"
                gt.inputs[1].default_value = cards_alpha
                nt.links.new(cut, gt.inputs[0])
                mix = nt.nodes.new("ShaderNodeMixShader")
                tr = nt.nodes.new("ShaderNodeBsdfTransparent")
                nt.links.new(gt.outputs[0], mix.inputs["Fac"])
                nt.links.new(tr.outputs[0], mix.inputs[1])
                nt.links.new(em.outputs[0], mix.inputs[2])
                nt.links.new(mix.outputs[0], outn.inputs["Surface"])
                m.use_backface_culling = False
                if hasattr(m, "surface_render_method"):
                    m.surface_render_method = "DITHERED"
            else:
                nt.links.new(em.outputs[0], outn.inputs["Surface"])


def full_verify(a, sc):
    """At every hold frame: film render of the scene with its vegetation hidden (pass A) and the imported tree
    GLBs rendered unlit over it (pass B: Standard view, rest of the scene as holdout, transparent film), drawn per
    the chunks' need ranges like the page (proxies of drawn chunks hidden). verify_<frame>.png = B over A."""
    t0 = time.time()
    ids = [x["id"] for x in EW.AREAS]
    with open(os.path.join(EW.WORK, "chunks.json"), encoding="utf-8") as fh:
        need = {c["id"]: c["need"] for c in json.load(fh)["chunks"]}
    frames = ([int(x) for x in a.frames.split(",")] if a.frames else
              ([] if a.looks else [int(x["holdFrame"]) for x in EW.AREAS]))
    # --looks frame:yaw:pitch (degrees; yaw about world up, positive left; pitch about the camera's right axis,
    # positive up): the page's free look at that frame, rendered from a copy of the camera turned like the page turns it
    shots = [(f, 0.0, 0.0) for f in frames] + [(int(f_), float(y_), float(p_)) for f_, y_, p_ in
                                              (x.split(":") for x in a.looks.split(",") if x)]
    # hide the original vegetation: every instancer of a vegetation prototype
    dg = bpy.context.evaluated_depsgraph_get()
    owners, other = collections.Counter(), collections.Counter()
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        tk = inst.object.original.name
        ow = inst.parent.original.name
        if tk.startswith("nature.proto.") and any(w in tk for w in BW.VEG_KINDS):
            owners[ow] += 1
        elif inst.object.type in EW.GEOM_TYPES:
            other[ow] += 1
    mixed = {o: other[o] for o in owners if other[o]}
    for nm in owners:
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            ob.hide_render = True
    log("verify: hid", len(owners), "vegetation instancers; they also place", sum(mixed.values()),
        "other instances in", len(mixed), "of them")
    EW.hide_flyer(sc)
    sc.camera = bpy.data.objects[EW.CAMERA]
    vl = bpy.context.view_layer
    # build,verify in one session: the build's own 'glTF Material Output' group (gltf_output_group: only an Occlusion
    # input) would be reused by the glTF importer, which then fails on its missing inputs ('Iridescence Factor')
    for g in list(bpy.data.node_groups):
        if g.name.lower().startswith("gltf material output") and not any(
                getattr(it, "name", "") == "Iridescence Factor" for it in g.interface.items_tree):
            g.name = "bake_trees.export_output_group"
    proxies = {}
    for name in ids + ["backdrop"]:
        path = os.path.join(FULL_RAW, name + "_trees.glb")
        if not os.path.isfile(path):
            log("WARN missing", path)
            continue
        coll = bpy.data.collections.new("verify." + name)
        sc.collection.children.link(coll)
        vl.active_layer_collection = vl.layer_collection.children[coll.name]
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if coll not in o.users_collection:
                coll.objects.link(o)
            for c in list(o.users_collection):
                if c is not coll:
                    c.objects.unlink(o)
        _emission_materials(new)
        if name == "backdrop":
            for o in new:
                p = o.get("proxyOf")
                if p:
                    proxies[p] = [o] + list(o.children_recursive)
        log("verify: imported", name, len(new), "objects")
    vl.active_layer_collection = vl.layer_collection
    tree_mats = {m.name for o in bpy.data.objects if o.users_collection and
                 o.users_collection[0].name.startswith("verify.") for m in
                 (s_.material for s_ in o.material_slots) if m is not None}
    # pass B: volumes and FX would hold the trees out; hide them there
    icache = {}

    def info(m):
        if m.name not in icache:
            icache[m.name] = EW.material_info(m)
        return icache[m.name]
    fx = []
    for ob in sc.objects:
        infos = [info(s.material) for s in ob.material_slots if s.material]
        if (infos and all(i["volume_only"] or EW._is_fx(i) for i in infos)) or ob.name.startswith(
                ("world.haze", "world.cloud", "world.moon_halo", "world.cirrus")):
            if not ob.hide_render:
                fx.append(ob)
    r = sc.render
    w, h = (int(x) for x in a.res.split("x"))
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    vs = sc.view_settings
    tmp = os.path.join(FULL_CACHE, "verify")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(FULL_OUT, exist_ok=True)
    log("verify: engine", r.engine, "fx hidden in pass B", len(fx), "tree materials", len(tree_mats))

    span = {x["id"]: (x["frameStart"], x["frameEnd"]) for x in EW.AREAS}
    cam0 = bpy.data.objects[EW.CAMERA]
    vcam = bpy.data.objects.new("verify.look_cam", cam0.data)
    sc.collection.objects.link(vcam)

    def set_shot(f, yaw, pitch):
        """Frame f; the chase camera, or (yaw / pitch) its copy turned like the page's free look. File tag."""
        sc.frame_set(f)
        if not yaw and not pitch:
            sc.camera = cam0
            return "%d" % f
        M = cam0.matrix_world.copy()
        R1 = (Matrix.Rotation(math.radians(yaw), 3, "Z") @ M.to_3x3().normalized() @
              Matrix.Rotation(math.radians(pitch), 3, "X"))
        vcam.matrix_world = Matrix.LocRotScale(M.to_translation(), R1.to_quaternion(), Vector((1.0, 1.0, 1.0)))
        sc.camera = vcam
        return "%d_y%g_p%g" % (f, yaw, pitch)

    def show_trees(f, on):
        drawn = [cid for cid in ids if need[cid][0] <= f <= need[cid][1]]
        if a.max_chunks > 0:          # like the page's resident cap: the areas nearest in frames, proxies for the rest
            gap = lambda c: max(span[c][0] - f, f - span[c][1], 0)   # noqa: E731
            drawn = sorted(drawn, key=lambda c: (gap(c), ids.index(c)))[:a.max_chunks]
        for name in ids + ["backdrop"]:
            lc = vl.layer_collection.children.get("verify." + name)
            if lc is not None:
                lc.exclude = not on or (name != "backdrop" and name not in drawn)
        for cid in ids:
            for o in proxies.get(cid, []):
                o.hide_render = cid in drawn
        return drawn
    # pass A (every frame): the film look without the vegetation
    for f, yaw, pitch in shots:
        tg = set_shot(f, yaw, pitch)
        show_trees(f, False)
        r.filepath = os.path.join(tmp, "a_%s.png" % tg)
        bpy.ops.render.render(write_still=True)
        log("verify: pass A", tg, round(time.time() - t0, 1), "s")
    # pass B (every frame): the tree GLBs unlit (Standard view, the web's display-referred colours), every other
    # material swapped for a Holdout shader (collection holdout misses instanced geometry), transparent film
    vs.view_transform, vs.look, vs.exposure = "Standard", "None", 0.0
    r.use_compositing, r.film_transparent = False, True
    for o in fx:
        o.hide_render = True
    swapped = 0
    for m in bpy.data.materials:
        if m.name in tree_mats or m.node_tree is None:
            continue
        nt = m.node_tree
        for outn in [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]:
            for l in list(outn.inputs["Volume"].links):
                nt.links.remove(l)
            ho = nt.nodes.new("ShaderNodeHoldout")
            nt.links.new(ho.outputs[0], outn.inputs["Surface"])
            swapped += 1
    log("verify: holdout on", swapped, "material outputs")
    rows = []
    for f, yaw, pitch in shots:
        tg = set_shot(f, yaw, pitch)
        drawn = show_trees(f, True)
        pb = os.path.join(tmp, "b_%s.png" % tg)
        r.filepath = pb
        bpy.ops.render.render(write_still=True)
        ia, ib = load_rgba(os.path.join(tmp, "a_%s.png" % tg)), load_rgba(pb)
        al = ib[..., 3:4]
        comp = ia.copy()
        comp[..., :3] = ia[..., :3] * (1 - al) + ib[..., :3] * al
        comp[..., 3] = 1.0
        tag = "_max%d" % a.max_chunks if a.max_chunks > 0 else ""
        save_png(comp, "verify", os.path.join(FULL_OUT, "verify%s_%s.png" % (tag, tg)))
        cover = float((al > 0.5).mean())
        rows.append(dict(frame=f, yaw=yaw, pitch=pitch, chunks=drawn, tree_pixels=round(cover, 4)))
        log("verify", tg, "chunks", drawn, "tree pixels", round(cover * 100, 2), "%", round(time.time() - t0, 1), "s")
    BW.dump(os.path.join(FULL_OUT, "verify%s.json" % ("_max%d" % a.max_chunks if a.max_chunks > 0 else "")), dict(frames=rows, hidden_instancers=len(owners),
                                                        mixed_instancers=mixed))


def full_args(argv):
    ap = argparse.ArgumentParser(prog="bake_trees.py")
    ap.add_argument("commands", help="plan, build, verify (comma-separated, run in order in one session)")
    ap.add_argument("--tree-near", type=float, default=70.0, help="pines/blossom: mesh below this nearest distance")
    ap.add_argument("--bamboo-near", type=float, default=70.0)
    ap.add_argument("--shrub-near", type=float, default=25.0)
    ap.add_argument("--grass-near", type=float, default=40.0, help="grass farther than this is dropped")
    ap.add_argument("--lotus-near", type=float, default=150.0, help="lotus farther than this is dropped")
    ap.add_argument("--hot-near", type=float, default=150.0, help="click-target trees: meshes below this distance")
    ap.add_argument("--sprite-px", type=int, default=128)
    ap.add_argument("--hold-sprite-px", type=int, default=256)
    ap.add_argument("--hold-card-near", type=float, default=110.0,
                    help="m: cards a hold camera sees nearer than this get --hold-sprite-px sprites")
    ap.add_argument("--backdrop-px", type=int, default=64)
    ap.add_argument("--hold-mesh-near", type=float, default=90.0)
    ap.add_argument("--mesh-full-d", type=float, default=35.0)
    ap.add_argument("--no-needles", action="store_true",
                    help="old pine near meshes: no needle cards (huangshan '.far', cliff/ancient '.hero' at 0.35)")
    ap.add_argument("--needle-max-tris", type=int, default=5000,
                    help="pine near meshes: at most this many needle-card triangles per family (whole fans thinned; "
                         "twig cards are 2 triangles each)")
    ap.add_argument("--needle-cards", choices=("twig", "fan"), default="twig",
                    help="twig: photographed twig cards (assets/web/twig_card.png, cardAlpha 'twig'); fan: the "
                         "procedural needle fans (cardAlpha 'needle', the pilot's)")
    ap.add_argument("--needle-lod", choices=("hero", "mid"), default="hero",
                    help="pine near meshes start from this LOD of the prototype (mid: the pilot's)")
    ap.add_argument("--needle-lite-tris", type=int, default=1600,
                    help="twig cards: near pines no hold camera sees within --needle-full-near m (and the path passes "
                         "no nearer than --needle-full-d m) keep this many needle triangles (same bake, grown cards)")
    ap.add_argument("--needle-full-near", type=float, default=45.0)
    ap.add_argument("--needle-full-d", type=float, default=20.0)
    ap.add_argument("--needle-opaque-tris", default="",
                    help="trunk + cushion tris of needle pines, 'huangshan,cliff,ancient' (default NEEDLE_OPAQUE_TRIS "
                         "2000,2000,2400; the pilot's: 1000,1200,1600)")
    ap.add_argument("--no-crown-normals", action="store_true",
                    help="bake needle pines with their own (decimated) normals, not the smoothed crown's")
    ap.add_argument("--shade-sun", type=float, default=SHADE_SUN,
                    help="the shade variant's sun, a share of its energy (0: off, the old bake)")
    ap.add_argument("--exposure", type=float, default=1.2)
    ap.add_argument("--sat", type=float, default=1.15)
    ap.add_argument("--only", default="", help="build: chunk ids (and/or 'backdrop') to write; default all")
    ap.add_argument("--fresh", action="store_true", help="ignore the caches in bakecache/trees_full")
    ap.add_argument("--quality", default="dev", choices=sorted(BW.BAKE_QUALITY),
                    help="dev: the fast bake (default); production: 4x samples for mesh bakes and sprites, adaptive "
                         "sampling off, own cache names (bake_web.BAKE_QUALITY)")
    ap.add_argument("--shrub-mesh-px", type=float, default=SHRUB_MESH_PX,
                    help="shrubs: a near mesh when their largest on-screen size (screen_px, px at 1280x720) reaches "
                         "this; 0: off (the old rule, path distance only, also needs --shrub-steep-px 0 and "
                         "--shrub-mesh blob)")
    ap.add_argument("--shrub-steep-px", type=float, default=SHRUB_STEEP_PX,
                    help="shrubs: also a near mesh when seen from %g deg or more above at this size (px at 1280x720; "
                         "0: off)" % STEEP_DEG)
    ap.add_argument("--shrub-hero-px", type=float, default=SHRUB_HERO_PX,
                    help="leafy near bushes at least this big (px at 1280x720) use the '.hero' shrub, the rest '.low'")
    ap.add_argument("--shrub-hold-near", type=float, default=SHRUB_HOLD_NEAR,
                    help="shrubs: also a near mesh when a hold camera sees them this near (m; 0: off)")
    ap.add_argument("--between-px-w", type=float, default=BETWEEN_PX_W,
                    help="screen_px: weight of the between look-around views (path and hold views count in full)")
    ap.add_argument("--shrub-mesh", choices=("leafy", "blob"), default="leafy",
                    help="leafy: near bushes keep their leaf sprays (cut-out cards) and flowers, clumps decimated to "
                         "--shrub-blob-tris; blob: the old near shrub (clumps only)")
    ap.add_argument("--shrub-blob-tris", type=int, default=SHRUB_BLOB_TRIS)
    ap.add_argument("--out", default="",
                    help="test runs: write under this folder (relative to the project, e.g. out/r17/new): raw/, "
                         "bake/trees/ and cache/ instead of out/web/full/raw, out/web/full/bake/trees and "
                         "bakecache/trees_full (inputs still come from out/web/full)")
    ap.add_argument("--cache-dir", default="", help="with --out: the bake cache (default <out>/cache)")
    ap.add_argument("--only-recs", action="store_true",
                    help="build with --only: cast, bake and render sprites for those chunks' records only (test runs: "
                         "needs --out)")
    ap.add_argument("--frames", default="", help="verify: Blender frames (default: the 11 hold frames)")
    ap.add_argument("--looks", default="",
                    help="verify: also frame:yaw:pitch views (degrees, the page's free look: yaw positive left, pitch "
                         "positive up), e.g. 516:45:-35; with --looks and no --frames only these")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--max-chunks", type=int, default=0,
                    help="verify: draw at most this many chunks (nearest areas), proxies for the rest (page default 3)")
    return ap.parse_args(argv)


def apply_out(a):
    """--out: plan, build and verify read and write their own files under that folder (raw/, bake/trees/, cache/ or
    --cache-dir) instead of out/web/full/raw, out/web/full/bake/trees and bakecache/trees_full. Refuses a folder
    inside out/web or bakecache (test runs must never touch the real build)."""
    global FULL_RAW, FULL_OUT, FULL_CACHE
    if getattr(a, "only_recs", False) and not getattr(a, "out", ""):
        raise SystemExit("--only-recs builds a partial set (a backdrop with some areas' proxies only): use it with --out")
    if not getattr(a, "out", ""):
        return
    base = os.path.normpath(a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out))
    cache = a.cache_dir and os.path.normpath(a.cache_dir if os.path.isabs(a.cache_dir) else
                                             os.path.join(ROOT, a.cache_dir))
    for p in (base, cache):
        if p and any(os.path.commonpath([p, os.path.normpath(q)]) == os.path.normpath(q)
                     for q in (EW.OUT_WEB, BW.CACHE_DIR)):
            raise SystemExit("--out / --cache-dir must not be inside out/web or bakecache: %s" % p)
    FULL_RAW = os.path.join(base, "raw")
    FULL_OUT = os.path.join(base, "bake", "trees")
    FULL_CACHE = cache or os.path.join(base, "cache")
    log("test run: outputs under", base, "cache", FULL_CACHE)


def main():
    a = full_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    apply_out(a)
    EW.use_profile("full")
    sc = bpy.context.scene
    t0 = time.time()
    P = None
    for cmd in a.commands.split(","):
        if cmd in ("plan", "build"):
            if P is None:
                P = full_plan(a, sc)
            if cmd == "plan":
                write_plan(P, a)
            else:
                full_build(a, sc, P)
        elif cmd == "verify":
            full_verify(a, sc)
        else:
            raise SystemExit("unknown command %r" % cmd)
        log("done", cmd, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
