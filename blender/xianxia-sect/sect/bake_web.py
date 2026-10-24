"""Baked web export (first test: Mountain Gate -> Heart-Mirror Terrace, chase.cam frames 1-288).

Extends sect/export_web.py (selection, visibility cache, LOD picking) with Cycles light baking. Run on the
cloud box through the wrapper, never on the user's PC:

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py --background \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_web.py -- bake [options]
    python .../rblender.py --background --factory-startup --python .../sect/bake_web.py -- post [options]
    python .../rblender.py --background .../out/sect_chase.blend --python .../sect/bake_web.py -- trees [options]
    python .../rblender.py --background --factory-startup --python .../sect/bake_web.py -- verify [options]

Commands
    bake    Selects the near/mid set (export_web's visibility cache), picks LODs to the triangle budget,
            builds ONE joined world-space bake mesh for all atlas pieces ('bake.atlas') and one for the
            vertex-colour pieces ('bake.vc'), unwraps a 'bake' UV per atlas (texel density from each piece's
            nearest distance to the camera path), bakes COMBINED (diffuse direct + indirect + emission) with
            Cycles on the GPU into float atlases plus an albedo guide, and COMBINED into vertex colours for
            the distant pieces. Raw EXRs and bakecache/export.blend stay on the box (bakecache/ is outside
            out/); stats go to out/web/bake/bake_stats.json.
    post    Factory startup. Denoises the atlases (OIDN with the albedo guide), applies the scene grade
            (look.py CDL + saturation) and AgX / AgX - Punchy + exposure, writes 8-bit sRGB PNGs, grades
            the vertex colours the same way, and exports out/web/raw/{gate,mirror,backdrop}.glb.
    trees   Vegetation as GPU instances: per prototype a small baked texture in 9 lighting variants
            (8 sun directions relative to the tree + one in shadow); each instance picks the variant that
            matches its yaw and its sun visibility (ray cast). Near trees use the scene's designed LOD
            meshes, far ones crossed cards with baked sprites. Writes out/web/raw/trees.glb.
    verify  Factory startup. Imports GLBs (--glb-dir), rebuilds chase.cam from camera.json and renders the
            frames in --ref-frames with emission-only materials -> out/web/bake/verify/.
    water   Waterfall sheets and streams seen along the path as real geometry (decimated, UV u across / v along
            the flow, COLOR_0 = per-sheet seed and flow) -> out/web/raw/water.glb, plus lip/foot corners and the
            additive light beams -> out/web/water_meta.json (sect_pack.py merges it into meta.json).

LOD near the holds: pieces within HOLD_NEAR m of the hold cameras (frames 93 and 217) keep full detail (or
>= 50 % when heavier than HOLD_FULL_TRIS): collapse decimation crumpled the lanterns, lions and finials the
reader studies while the camera stands still. Tall thin pieces keep >= 25 %. `bake --plan-only` stops after
the LOD pick, atlas grouping and unwrap and writes out/web/bake/lod_plan.json and plan_atlases.json.

Post output: plain atlas and backdrop faces are split into spatially compact chunks of at most CHUNK_FACES faces
(extras {"chunk": 1}) so the browser can cull what is off screen; glowing faces get one material per source-material
class (GLOW_CLASSES) whose extras carry {"glow": strength, "glowTint": "#rrggbb"}. Full path: atlas faces of rock,
ground and paving source materials (DETAIL_CLASSES; a glow class wins) get their own materials
baked.<atlas>.detail.<class> (same atlas, extras {"baked": true, "detail": "rock" | "ground" | "paving"}: the web lays
a tiling detail texture over them), in their own chunk pieces <area>.baked.<A>.detail.<class>.c<n> and inside the
hotspot nodes; paving faces also carry PAVE_UV (TEXCOORD_1: the material's slab coordinates). Metal and glaze faces
(SURFACE_CLASSES; glow and detail classes win) get baked.<atlas>.surface.<class> (extras {"sectSurface": "metal" |
"glaze"}: the web adds a sky reflection) in pieces <area>.baked.<A>.surface.<class>.c<n>. The small pieces (VC_SMALL)
are vertex colours: <area>.baked.vc[.surface.<class>].c<n>, materials 'baked.vc[.surface.<class>]' (COLOR_0).

Unwrap (full path): project_box26, then roof tile sheets one slope at a time (SHEET_UNWRAP) and thin islands merged
across convex folds into charts (CHART_MERGE), packed with MARGIN_BIG texels around islands of MARGIN_BIG_TEXELS or
more; an atlas that packs looser than the chunk's densest halves (ATLAS_EVEN). Before the unwrap, duplicate and
tiny faces go (DEDUPE). facing_flip tests sightings for occlusion (FLIP_DEPTH) and decides per patch (FLIP_BY_PATCH).
The denoiser gets a baked normal guide (DENOISE_NORMAL). --out-dir <dir>: a test run writes under out/<dir> and
bakecache/<dir> instead of the live folders.

Why one joined mesh: Blender's bake operator re-syncs the whole scene for every selected object, so the
pieces are joined. The sect's procedural materials read object-space inputs (TexCoord Object/Generated,
Object Info Random, OBJECT attributes scale/glow/density/flow); the joined mesh stores them per vertex
('o_co', 'o_gen', 'o_scale', 'o_rand', 'o_<prop>') and the bake uses rewritten copies of the materials
that read those attributes, so the patterns bake as they render in the film.

FULL PATH (--profile full): all 11 areas of out/web/full/chunks.json (export_web.py --profile full chunks), frames
1-1729. Outputs under out/web/full/raw/ and out/web/full/bake/; raw EXRs + export.blend per chunk in
bakecache/full/<chunk>/ (box only).

    ... sect_chase.blend --python bake_web.py -- bakefull,water --profile full [--chunks backdrop,gate,...]
    ... --factory-startup --python bake_web.py -- verify --profile full [--chunks forge | --ref-frames 352,400]
    ... --factory-startup --python bake_web.py -- post --profile full --chunks forge      (redo the post step)

    bakefull  One session (the sect loads once, ~40 s setup): per chunk in the order given (default flight order,
              then the backdrop) the prototype's bake with the chunk's pieces (vegetation is bake_trees.py's, water
              is 'water'), --atlas-tris (700k) per chunk, texel budget FULL_ATLASES (1.25 x 4096^2: one 4096 + one
              2048; gate, forge, steles and summit 2.0), density x HOLD_RHO near the hold cameras, atlases packed
              material by material, then the post step in the same session -> raw/<area>.glb (hotspot nodes,
              glow classes, detail classes, extras chunk). While a chunk bakes the rest of the sect stays in the
              scene for shadows and bounce (hidden owners' other pieces come back as occluder copies). The range and
              the hanging roots are split face by face (export_web.face_assign). 'backdrop' = raw/backdrop.glb:
              vertex colours, 'backdrop.far' (pieces seen only beyond 400 m) + one 'proxy.<area>' Empty per area with
              extras {"proxyOf": area} (reduced copies of the area's pieces, sharing its terrain faces: no cracks).
              The forge ring's artifacts bake staged at the ring's front, stacked straight up (ring_stage), and
              go back in place before the export: the page turns the ring, so each must look front-lit anywhere.
              Look-around (the page turns the view all the way round): the camera views are the audit's
              (export_web.load_views: path frames, then look-around views at and between the holds). Pieces get
              their LOD and texel density from d_eff / px_eff (the look views count with distance x1.5 at the
              holds, x2 between, so the flight view keeps priority within the fixed budgets). Near the holds:
              besides the forward full-detail rule, every piece within HOLD_AROUND_NEAR m of a hold camera in any
              direction keeps >= HOLD_AROUND_FLOOR of its triangles and texel density x HOLD_RHO_AROUND.
              facing_flip decides by the path views first, the look views only for faces the path never saw.
              The split terrain (world.range, world.roots) skips facing_flip: its source winding points out, and
              the frustum-only test would flip every peak's far side (seen "from behind" through the rock).
              Turning objects (export_web.TURNING_GROUPS: the forge ring's artifacts, the flying cranes) skip
              facing_flip and get uniform texel density (no split by face distance) and one LOD floor per group.
              The range: decimated once to BIG_RATIO_FULL with full detail within RANGE_NEAR m of a view and on the
              grass/rock border, then shaded with the whole range's smooth normals in every piece cut out of it
              (smooth_range / carry_normals: no tone step along the chunk and distance-bin cuts; only folds over
              RANGE_SHARP_DEG, the knife-edge lips over the undersides, stay hard). Floating islands
              (and far-set rock) get LOD floors from their own on-screen size (_island_floors, sect/bake_rules.py).
              The joined bake objects carry shadow_terminator_geometry_offset = TERMINATOR_OFFSET.
              --plan-only stops every chunk after the LOD pick and unwrap: bake/plan_<id>.json, bake/plan_stats.json.
              Stats: bake/chunks/<id>.json, bake/post/<id>.json, bake/bake_stats.json; graded atlases bake/tex/.
    water     raw/<area>_water.glb per chunk + raw/backdrop_water.glb (seen only beyond 400 m, and the long streams
              that span areas: draw it with the backdrop); corners in out/web/full/water_meta.json. Besides UV0 and
              COLOR_0 (seed, flow) every vertex has TEXCOORD_1 (three.js uv1: metres across, seconds since the lip)
              and COLOR_0.b = the sheet's layer (0 core, 0.5 side curtain, 1 front veil): cmd_water_full. Needs the
              audit's vis_cache.npz and chunks.npz to know the sheets (by name), not a bake.
    verify    Imports raw/backdrop.glb and the baked chunks (+ <area>_trees.glb when present), shows per frame the
              chunks whose need range holds it (their proxies hidden), renders bake/verify/hold_<frame>.png.

Quality (--quality dev|production, table BAKE_QUALITY, shared with bake_trees.py): dev (the default) is the fast bake
for development, unchanged. production is for one final bake once the content is final and changes only noise
settings: atlas samples 768 (dev 160), vertex colours 1024 (dev 256), the denoiser's guide passes albedo 64 / normal 16
(dev 16 / 4), adaptive sampling off (dev keeps the scene's: Cycles' default, threshold 0.01), denoisers pinned to High.
Same chunk plan, LODs, texel density, atlas sizes, files and brightness (clamp and bounces unchanged). --samples /
--vc-samples still override. A run's first line says which ("BAKE quality production samples 768 vc 1024 ..."), and
each chunk's bake_meta.json and bake/chunks/<id>.json store it (quality, bake_settings).

    ... sect_chase.blend --python bake_web.py -- bakefull,water --profile full --quality production

Expected minutes per chunk on one RTX 5090 (CUDA), post step included. Dev = the last full bake (47 min with setup).
Production scales the sampling part of each pass (a pass costs about 12 s before it samples) and assumes the dev
texels took all their samples. If adaptive sampling stopped many dev texels at its 64-sample minimum, the atlas passes
take up to 2.5x longer than this (whole bake up to ~3.5 h): the first chunk's "baked atlases in N s" line tells.

    chunk      dev  production        chunk      dev  production
    gate       3.4   9.3              scroll     3.3   6.6
    mirror     2.3   5.6              formation  2.5   5.3
    forge      3.7   9.0              abode      3.0   7.5
    arena      2.9   6.1              steles     4.4   9.5
    mission    3.5   7.3              summit     5.5  14.3
    library    4.2   9.1              backdrop   2.9   3.9
    all chunks + ~5 min setup: dev 47 min, production about 1 h 40 min (worst case about 3.5 h)

Colour: atlases and vertex colours are display-referred sRGB (AgX Punchy + grade baked in); the web draws
them unlit with no tone mapping. Lighting for the bake = the scene's sun + sky, with the sky fill raised
x1.4 and warmed, plus a soft warm fill sun from the sun's side (stands in for the film's golden haze
in-scatter; calibrated on Cycles stills against the style frames).
"""
import argparse
import collections
import json
import math
import os
import re
import sys
import time
import zlib

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect import export_web as EW  # noqa: E402
from sect import bake_rules as BR  # noqa: E402

OUT_WEB = EW.OUT_WEB
BAKE_OUT = os.path.join(OUT_WEB, "bake")
RAW = os.path.join(OUT_WEB, "raw")
CACHE_DIR = os.path.join(ROOT, "bakecache")       # box only: raw EXRs + export.blend (not copied back)

GATE_END = 165                 # section timeline: gate frames 1-165, mirror 166-287
RHO_K = 678.0                  # texels per metre at 1 m: 1/(2.5 px * 5.9e-4 rad/px), 1920 px wide, 58.7 deg
RHO_MAX = 40.0
RHO_MIN = 1.0
ATLAS_MAX_D = 400.0            # pieces nearer than this get atlases, farther ones vertex colours
ATLAS_PX = 4096
ATLAS_FILL = 0.55              # texel demand per atlas (islands + margins + packing loss)
MARGIN_PX = 6                  # gap between islands (each side ~3 px)
BAKE_MARGIN = 16
BIG_BINS = (0.0, 25.0, 50.0, 100.0, 200.0, ATLAS_MAX_D)
SPLIT_BINS = (0.0, 15.0, 30.0, 60.0, 120.0, 250.0, 1e8)   # heavy pieces are split by face distance
SPLIT_DEMAND = 250_000         # texels at nominal density above which a piece is split
VC_MIN_PX = 6.0                # distant pieces smaller than this on screen are dropped
BIG_RATIO = 0.3                # terrain: overall decimation ratio, near the path protected by weights
VEG_KINDS = ("pine", "blossom", "shrub", "grass", "bamboo", "willow", "lotus")
COPY_ATTRS = ("arch_gen", "arch_dims", "arch_rand", "edge")
OBJ_PROPS_VEC = ("scale", "dimensions", "location")
GLOW_DEFAULT = 3.0
SUN_AZ_DEG = 252.0
HOLD_FRAMES = (93, 217)        # camera holds (gate, mirror): props near these views keep their shape
HOLD_AREAS = ("gate", "mirror")  # the area each hold looks at
HOLD_NEAR = 40.0               # m from a hold camera (box distance, in front of it)
HOLD_AREA_NEAR = (40.0, 95.0)  # m per hold, for pieces of the area it looks at (the mirror stands ~70 m off;
                               # the gate fills the frame within 40 m)
HOLD_FULL_TRIS = 30000         # near-hold pieces up to this size keep full detail, larger ones >= HOLD_MIN_RATIO
HOLD_PROP_WORDS = ("lantern", "lion", "censer", "finial", "baluster", "lattice", "mirror_stand", "rail")
HOLD_PROP_NEAR = 65.0          # m: small props the reader studies (the gate's front lanterns stand ~41 m off)
HOLD_MIN_RATIO = 0.5
SLENDER = 2.5                  # height / footprint above which a piece (rock spires) keeps >= SLENDER_FLOOR
SLENDER_FLOOR = 0.25
CHUNK_FACES = 24000            # post: plain atlas / backdrop faces are split into spatially compact chunks of at
                               # most this many faces (median cuts), so the browser can cull what is off screen
# glow per source material (substring of the Blender material name -> strength, tint): the web multiplies the
# baked colour by strength (x tint), so only these exceed 1.0 and bloom. Baked glow colours are already near
# 1.0, so a strength of 3 washes every hue to white; these keep gold gold and jade teal.
GLOW_CLASSES = (
    ("mirror_face", 1.3, "#ffd28a"),     # the Heart-Mirror's face: gold, not peach-white
    ("rune_cyan", 2.0, "#7fe8dc"),       # the mirror's rune ring, the gate's floor circle
    ("rune_gold", 1.6, "#ffd08a"),
    ("rune_silver", 1.6, None),
    ("rune_blossom", 1.6, "#ffb3cc"),    # the peach-blossom fan's flowers
    ("jade_glow", 1.6, "#8ff0d8"),       # sword monolith inlays
    ("formation_rune", 1.6, None),
    ("steles_rune", 1.6, None),
    ("paper_screen_lit", 1.8, "#ffc887"),
    ("lantern", 1.8, "#ffc887"),
    ("lamplight", 1.8, "#ffc887"),
    ("flame", 2.0, "#ffb060"),
    ("ember", 2.0, "#ff9a50"),
    ("molten", 2.0, "#ff9a50"),
    ("mote", 1.6, None),
)
GLOW_FALLBACK = (1.8, None)
# detail class per source material (full post): the web lays a tiling detail texture over these faces (rock: world
# triplanar, ground: top-down). Exact registered names (the sect_material tag, else the name without the 'M.' prefix):
# the moss and soil builders' other variants are props (rope, straw, ash...). A new rock_cliff variant has to be listed
# here: a factory-startup post does not load the material registry, so the base builder is not known there.
DETAIL_CLASSES = (
    ("rock", ("rock_cliff", "world_rock_under", "nature_rock_small", "world_pier_stone")),
    # (round 48: the far canopy mass, world.canopy_shell / world.canopy_hull, is ground too: the client grades
    # far range ground as canopy, and no grass tuft grows that far from the camera)
    ("ground", ("grass", "soil", "nature_soil_moss", "moss", "nature_canopy_mass")),
    # the plazas, paths and terrace tops (1.2 x 0.8 m slabs, 1.2 cm joints: materials._paving). The joints do not
    # survive 14-20 texels a metre, so the forge and mission plazas baked as flat white sheets (28 % of the lower
    # frame at their holds). Their faces carry the slab coordinates as a second UV set (PAVE_UV): the web draws the
    # joints, worn slabs and moss exactly where the material's slabs are (lib/sect/detail.ts, class "paving").
    ("paving", ("marble_paving",)),
    # the roof tile sheets' tile material (arch.tile_material: 'arch_tiles_<tile>', matched by TILE_PREFIX): the tube
    # courses (a pitch of 0.25-0.4 m) need 3+ texels a course and the hold atlases give 1.4-2, so roofs baked as smooth
    # dark sheets once each slope was one island (SHEET_UNWRAP). Their faces carry the sheet's own tile UVs (u: courses,
    # integers on the tube crests; v: laps, integers on the lips) as the second UV set, and the web draws the courses,
    # creases and lap shadows at any distance (lib/sect/detail.ts, class "tiles"). Glazed ones keep sectSurface "glaze".
    ("tiles", ()),
)
TILE_PREFIX = "arch_tiles_"    # registered names of the tiles class (arch.tile_material)
PAVE_UV = "pave"               # post: the second UV set (TEXCOORD_1) of paving and tiles faces. Paving: the source object's
                               # local x, y in metres (the 'o_co' attribute, the Object coordinates the brick texture reads);
                               # tiles: the sheet's own UVs (the bake mesh's 'UVMap'); 0 on other faces of the same piece
# surface class per source material (full post): faces of these get their own materials and chunk pieces with
# extras {"sectSurface": class}, so the web can add the sky reflection a diffuse bake cannot hold (rewrite_material
# bakes metal and glaze as their base colour). Matched on the sect_material tag (else the name without 'M.'): an
# exact name, or a name starting with one of the prefixes. roof_tile_black is unglazed (materials.py glazed=False).
SURFACE_CLASSES = (
    ("metal", ("gold", "silver", "bronze", "bronze_verdigris", "iron", "steel"),
     ("props_gold", "props_bronze", "props_iron", "props_steel", "props_silver")),
    ("glaze", ("roof_tile_teal", "roof_tile_moon", "ceramic_celadon"),
     ("arch_tiles_roof_tile_teal", "arch_tiles_roof_tile_moon", "arch_ridge_roof_tile_teal",
      "arch_ridge_roof_tile_moon", "arch_cap_roof_tile_teal", "arch_cap_roof_tile_moon",
      "arch_band_roof_tile_teal", "arch_band_roof_tile_moon")),
)
MAT_PREFIX = "M."              # materials.PREFIX
MAT_TAG = "sect_material"      # materials.TAG: the registered name, kept by the bake's material copies
VC_BAKE_ATTR = "w_vc"          # materials.GROUND_POINT_BAKE: POINT attribute (1) on the vertex-colour bake mesh. A vertex
                               # colour is one point sample per corner, so sub-metre patterns (the 0.25 m flower dots)
                               # would light a vertex's whole fan; the ground material leaves them out where it is set
VC_WELD = True                 # post: a vertex-colour bake (the backdrop) gets one colour per smooth point
                               # (bake_rules.weld_corner_colours, thresholds there): Cycles samples every triangle corner
                               # on its own, corners at one point disagreed by 24-31 % and every triangle showed its own
                               # three colours (the faceted far peaks, e.g. proxy.scroll at hold 619). False: as baked
PATH_LIFT ={"mirror.path_east": 0.012, "mirror.path_forge": 0.024}   # m: overlapping coplanar path strips
SHEET_UNWRAP = True            # roof tile sheets (arch.py's corrugated slopes, '<roof>.tiles') unwrap one slope at a time
                               # (bake_rules.sheet_project). The 26-direction projection cut every tile course into strips
                               # 1.7 texels wide (forge.baked.A0.c1: 8,874 islands), whose filtering pulled white, red and
                               # gold texels of neighbouring islands into the dark tiles: the roof speckle at 352 / 400 / 660
VC_SMALL = True                # full path: pieces whose surface lies mostly (VC_SMALL_SHARE of its area) in UV islands
VC_ISLAND_TEXELS = 4.0         # under VC_ISLAND_TEXELS long (at the piece's density) bake as welded vertex colours (their
VC_SMALL_SHARE = 0.6           # own bake object, 'baked.vc' materials) instead of atlas texels: eave caps and drips, rafter
                               # ends, brackets, balusters, lattices, finials, statues. Those islands held 56-70 % of the
                               # atlas triangles and with their margins 12-32 % of the atlas; a 2-texel island mixes with
                               # its neighbours from the first mip on. Their vertices sit closer than the atlas texels did.
                               # Never: hotspot items, glowing or detail-class pieces, turning objects, the split terrain
MARGIN_BIG = 2.0               # texels around islands of at least MARGIN_BIG_TEXELS (smaller ones keep PACK_MARGIN): the
MARGIN_BIG_TEXELS = 8.0        # half-size mip of a big island no longer reaches its neighbour
DENOISE_NORMAL = True          # full: bake a world-space NORMAL pass per atlas (<atlas>_normal.exr) and give it to the
                               # denoiser beside the albedo (it had the albedo only, over a mosaic of unrelated patches)
ATLAS_EVEN = 0.9               # full: after packing, an atlas whose density (texels_per_unit) stays at least this x the
                               # chunk's lowest after halving its size is halved (library_A1, 7 terrain pieces, came out a
                               # 4096 at 1.45x density beside the pagoda's 0.78x)

# bake lighting (variant C of out/web/bake/calib): sky x1.3 warmed + soft warm fill sun
BAKE_LIGHT = dict(world_strength=1.4, world_tint=(1.25, 1.0, 0.78), fill_energy=1.6, fill_elev_deg=32.0,
                  fill_angle_deg=110.0, fill_color=(1.0, 0.72, 0.5))
PROFILE = "proto"              # use_profile("full") switches paths and holds to the whole path (see the FULL section)


def log(*a):
    print("BAKE", *a, flush=True)


def dump(path, data, indent=1):
    EW.dump(path, data, indent=indent)


# ---- small mesh helpers -----------------------------------------------------------------------

class MA:
    """numpy arrays of a mesh in its local space (cached per mesh name)."""

    def __init__(self, me):
        self.name = me.name
        nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
        self.nv, self.nl, self.np = nv, nl, npl
        self.co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", self.co)
        self.co = self.co.reshape(nv, 3)
        self.vi = np.empty(nl, np.int32)
        me.loops.foreach_get("vertex_index", self.vi)
        self.ls = np.empty(npl, np.int32)
        me.polygons.foreach_get("loop_start", self.ls)
        self.lt = np.empty(npl, np.int32)
        me.polygons.foreach_get("loop_total", self.lt)
        self.mi = np.empty(npl, np.int32)
        me.polygons.foreach_get("material_index", self.mi)
        ar = np.empty(npl, np.float32)
        me.polygons.foreach_get("area", ar)
        self.area = float(ar.sum())
        self.cn = np.empty(nl * 3, np.float32)
        wn = me.attributes.get(W_NRM)
        if wn is not None and wn.domain == "CORNER" and wn.data_type == "FLOAT_VECTOR" and nl:
            wn.data.foreach_get("vector", self.cn)       # a range piece: the whole range's normals (carry_normals)
        else:
            try:
                me.corner_normals.foreach_get("vector", self.cn)
            except Exception:
                self.cn[:] = 0.0
        self.cn = self.cn.reshape(nl, 3)
        self.uv0 = None
        if len(me.uv_layers):
            u = np.empty(nl * 2, np.float32)
            lay = next((l for l in me.uv_layers if l.active_render), None) or me.uv_layers[0]
            lay.data.foreach_get("uv", u)
            self.uv0 = u.reshape(nl, 2)
        self.mats = [m.name if m is not None else "" for m in me.materials]
        self.attrs = {}
        for nm in COPY_ATTRS:
            a = me.attributes.get(nm)
            if a is None or a.domain not in ("POINT", "FACE", "CORNER"):
                continue
            n = {"POINT": nv, "FACE": npl, "CORNER": nl}[a.domain]
            if a.data_type == "FLOAT_VECTOR":
                d = np.empty(n * 3, np.float32)
                a.data.foreach_get("vector", d)
                d = d.reshape(n, 3)
            elif a.data_type in ("FLOAT", "INT", "BOOLEAN"):
                d = np.empty(n, np.float32 if a.data_type == "FLOAT" else np.int32)
                a.data.foreach_get("value", d)
                d = d.astype(np.float32)
            else:
                continue
            self.attrs[nm] = (a.domain, d)
        tl = np.array(me.texspace_location, np.float32)
        ts = np.maximum(np.abs(np.array(me.texspace_size, np.float32)), 1e-4)
        self.gen = (self.co - (tl - ts)) / (2.0 * ts)
        self._flip = None

    def flip_perm(self):
        """Loop permutation that reverses every polygon's winding (for mirrored instances)."""
        if self._flip is None:
            p = np.arange(self.nl, dtype=np.int64)
            for s, t in zip(self.ls, self.lt):
                p[s:s + t] = p[s:s + t][::-1]
            self._flip = p
        return self._flip


_MA = {}


def ma(me):
    m = _MA.get(me.name)
    if m is None:
        m = _MA[me.name] = MA(me)
    return m


def make_mesh(name, co, vi, ls, mi=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", np.ascontiguousarray(co, np.float32).ravel())
    me.loops.add(len(vi))
    me.loops.foreach_set("vertex_index", np.ascontiguousarray(vi, np.int32))
    me.polygons.add(len(ls))
    me.polygons.foreach_set("loop_start", np.ascontiguousarray(ls, np.int32))
    if mi is not None:
        me.polygons.foreach_set("material_index", np.ascontiguousarray(mi, np.int32))
    me.update(calc_edges=True)
    return me


def set_attr(me, name, typ, domain, data):
    a = me.attributes.get(name) or me.attributes.new(name, typ, domain)
    key = "vector" if typ in ("FLOAT_VECTOR", "FLOAT2") else ("color" if typ == "FLOAT_COLOR" else "value")
    dt = np.int32 if typ in ("INT", "BOOLEAN") else np.float32
    a.data.foreach_set(key, np.ascontiguousarray(data, dt).ravel())
    return a


def get_attr(me, name, n, width):
    a = me.attributes[name]
    key = "vector" if a.data_type in ("FLOAT_VECTOR", "FLOAT2") else (
        "color" if a.data_type in ("FLOAT_COLOR", "BYTE_COLOR") else "value")
    dt = np.int32 if a.data_type in ("INT", "BOOLEAN") else np.float32
    d = np.empty(n * width, dt)
    a.data.foreach_get(key, d)
    return d.reshape(n, width) if width > 1 else d


def _use_nodes(idb):
    """use_nodes = True on a material or world where it still means something: since Blender 5.0 they always have a
    node tree, and the setter (deprecated) goes in 6.0."""
    if bpy.app.version < (5, 0, 0) or getattr(idb, "node_tree", None) is None:
        idb.use_nodes = True


def mat_slots_and_props(ob):
    """(object scale, {prop: value}) the original renders with (OBJECT attribute lookups)."""
    if ob is None:
        return (1.0, 1.0, 1.0), {}
    props = {}
    for k in ob.keys():
        if k.startswith("_") or k in ("cycles", "web_export"):
            continue
        v = ob[k]
        if isinstance(v, (int, float)):
            props[k] = float(v)
    return tuple(ob.scale), props


# ---- material rewrite -------------------------------------------------------------------------

def object_attr_names(mats):
    out = set()
    for m in mats:
        if m is None or m.node_tree is None:
            continue
        for n in m.node_tree.nodes:
            if n.bl_idname == "ShaderNodeAttribute" and n.attribute_type == "OBJECT":
                out.add(n.attribute_name)
    return out


def rewrite_material(src, name):
    """Copy of `src` whose object-dependent inputs read per-vertex attributes of the joined bake mesh."""
    m = src.copy()
    m.name = name
    nt = m.node_tree
    if nt is None:
        return m
    made = {}

    def an(attr):
        if attr not in made:
            n = nt.nodes.new("ShaderNodeAttribute")
            n.attribute_type = "GEOMETRY"
            n.attribute_name = attr
            made[attr] = n
        return made[attr]

    for n in list(nt.nodes):
        t = n.bl_idname
        if t == "ShaderNodeTexCoord":
            for out, attr in (("Object", "o_co"), ("Generated", "o_gen")):
                for l in list(n.outputs[out].links):
                    nt.links.new(an(attr).outputs["Vector"], l.to_socket)
        elif t == "ShaderNodeAttribute" and n.attribute_type == "OBJECT":
            n.attribute_name = "o_" + n.attribute_name
            n.attribute_type = "GEOMETRY"
        elif t == "ShaderNodeObjectInfo":
            for out, attr, sock in (("Random", "o_rand", "Fac"), ("Location", "o_loc", "Vector")):
                for l in list(n.outputs[out].links):
                    nt.links.new(an(attr).outputs[sock], l.to_socket)
        elif t == "ShaderNodeBsdfPrincipled":
            lift = next((v for k, v in DARK_GLOSS_LIFT.items() if k in src.name), None)
            if lift is not None:
                sock = n.inputs["Base Color"]
                mx = nt.nodes.new("ShaderNodeVectorMath")
                mx.operation = "MAXIMUM"
                mx.inputs[1].default_value = lift
                if sock.is_linked:
                    nt.links.new(sock.links[0].from_socket, mx.inputs[0])
                else:
                    mx.inputs[0].default_value = tuple(sock.default_value)[:3]
                nt.links.new(mx.outputs["Vector"], sock)
            # a bake keeps only diffuse light: metals would bake black, glass would bake what is behind it.
            # Bake them as their base colour (painted gold / bronze), the usual lightmap convention.
            for nm in ("Metallic", "Transmission Weight"):
                sock = n.inputs.get(nm)
                if sock is None:
                    continue
                for l in list(sock.links):
                    nt.links.remove(l)
                sock.default_value = 0.0
    return m


# ---- selection --------------------------------------------------------------------------------

def is_veg_rec(R, i):
    tk = R.tkey[i]
    return bool(R.inst[i]) and tk.startswith("nature.proto.") and any(w in tk for w in VEG_KINDS)


def is_fall(R, i):
    return any("waterfall" in m or "water_fall" in m for m in R.tinfo[R.tkey[i]][2])


DETAIL = (("plaque", 2.5), ("inscription", 2.0), ("glyph", 1.5), ("lion", 1.6))
DETAIL_FULL = (("plaque", 2.5), ("inscription", 2.0), ("glyph", 3.0), ("lion", 1.6),   # full profile   # name part -> texel density factor
               ("formation.flag.", 3.0))
# (round 42) The formation's Five Element Banners 五行旗 (formation.flag.<element>): a 4.6 m cloth with one big
# character in a ring, which the visitor reads from 82 m at the nearest pass and 160 m at the hold. The distance rule
# (RHO_K / 82 m) gave them 8 texels a metre (37 across a flag, about 2 screen pixels a texel at that pass; the gate's
# and arena's banners have 16-30) and the abode's budget halved that for the two the export put in its chunk
# (export_web LORE_CHUNKS now keeps all five in the formation). x3: 21-25 texels a metre, about 80k more texels in a
# chunk using 5.7M of its 11.5M.


def detail_boost(name):
    """Extra density for small pieces whose detail is read up close (the gate's name plaque)."""
    return max([f for k, f in (DETAIL_FULL if PROFILE == "full" else DETAIL) if k in name] + [1.0])


NO_DECIMATE = ("plaque", ".text", "inscription", "glyph", "couplet", "banner")
# (round 42) Names never decimated within a farther distance than NO_DECIMATE's 80 m: {name part: metres}. The Five
# Element Banners are never nearer the camera than 82 m, so the 80 m rule never held them; their character and ring are
# faces of the cloth (slot 2) that collapse decimation merges into the cloth. A few thousand triangles.
NO_DECIMATE_FAR = {"formation.flag.": 250.0}


def no_decimate(name, owner, d):
    """NO_DECIMATE within 80 m, NO_DECIMATE_FAR within its own distance."""
    if d <= 80.0 and any(k in name or k in owner for k in NO_DECIMATE):
        return True
    return any(d <= far and (k in name or k in owner) for k, far in NO_DECIMATE_FAR.items())
# near-black glossy materials read in the film through their coat reflections of the sky; a diffuse-only bake
# leaves them black (the mission board). Their base colour is raised to at least this (linear) for the bake.
DARK_GLOSS_LIFT = {"lacquer_black": (0.030, 0.040, 0.045)}
ROOT_WORDS = (".roots", "world.roots")   # hanging root strands: collapse decimation turns them into shards
ROOT_FLOOR = 0.6


def uv_materials():
    """Materials whose pattern reads the mesh UV map (TexCoord UV, UV Map node or an image texture)."""
    out = set()
    for m in bpy.data.materials:
        nt = m.node_tree
        if nt is None:
            continue
        for n in nt.nodes:
            if (n.bl_idname == "ShaderNodeTexCoord" and n.outputs["UV"].is_linked) or n.bl_idname in (
                    "ShaderNodeUVMap", "ShaderNodeTexImage"):
                out.add(m.name)
                break
    return out


def rho_of(d):
    return float(np.clip(RHO_K / max(float(d), 1.0), RHO_MIN, RHO_MAX))


def capture(tkeys):
    """tkey -> evaluated mesh copy with all data layers (arch_* / edge attributes kept)."""
    dg = bpy.context.evaluated_depsgraph_get()
    need = set(tkeys)
    out = {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in EW.GEOM_TYPES:
            continue
        tk = ob.original.name if inst.is_instance else "#" + ob.original.name
        if tk in need and tk not in out:
            try:
                me = bpy.data.meshes.new_from_object(ob, preserve_all_data_layers=True, depsgraph=dg)
            except Exception as e:
                log("WARN capture failed", tk, e)
                continue
            EW._slot_materials(me, ob)
            out[tk] = me
            if len(out) == len(need):
                break
    log("captured", len(out), "of", len(need), "meshes")
    return out


DEGEN_AREA = 1e-10             # (r37) faces under this (m2, mesh space) count as degenerate: before a collapse, they and
DEGEN_DIST = 1e-6              # the zero-length edges are dissolved (degen_clean). tidy_rock (world.py, round 12) closes
_DEGEN = {}                    # each floating rock's cone in one point and leaves the moved bands' faces with no area;
                               # collapsed with them, a rock turned into one flat triangle (the summit rock at 0.06) or a
                               # crushed wedge (the arena->mission stones in the proxies), and could not get under ~340
                               # triangles at 0.008-0.015; cleaned, it keeps its cone at every level
DEGEN_WORDS = ("island", "islet", "arena_mission.stone")   # tidy_rock's rocks (nature.floating_rock); the joined
                               # lattices have zero-area faces too, but cleaned they collapse into crude stand-ins


def degen_clean(me):
    """`me`, or (memoized) a copy of it with its zero-area faces and zero-length edges dissolved."""
    import bmesh
    if me.name in _DEGEN:
        return _DEGEN[me.name]
    n = len(me.polygons)
    a = np.empty(n)
    me.polygons.foreach_get("area", a)
    out = me
    if n and (a < DEGEN_AREA).any():
        out = me.copy()
        bm = bmesh.new()
        bm.from_mesh(out)
        bmesh.ops.dissolve_degenerate(bm, dist=DEGEN_DIST, edges=bm.edges[:])
        bm.to_mesh(out)
        bm.free()
        out.update()
    _DEGEN[me.name] = out
    return out


class Decimator(EW.Decimator):
    """export_web.Decimator, keeping all data layers (the arch_* attributes drive the beam paintings)."""

    def get(self, key, base, ratio):
        if ratio >= 0.999:
            return base
        ck = (key, round(ratio, 4))
        if ck in self.cache:
            return self.cache[ck]
        t0 = time.time()
        if not self.mod.vertex_group and any(w in key for w in DEGEN_WORDS):  # (r37) the floating rocks only
            base = degen_clean(base)
        self.ob.data = base
        self.mod.ratio = ratio
        with bpy.context.temp_override(scene=self.sc, view_layer=self.sc.view_layers[0]):
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            ev = self.ob.evaluated_get(dg)
            me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        for i, m in enumerate(base.materials):
            if i < len(me.materials):
                me.materials[i] = m
        self.cache[ck] = me
        self.n += 1
        self.t += time.time() - t0
        return me


def face_dmin(me, M, cam_mats, tan_v, aspect_w, dscale=None):
    """Per face: nearest camera distance over the views where its centre is in the widened frustum (inf when
    never). dscale (export_web.Views.dscale): per view distance factor (look-around views count farther)."""
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    M = np.asarray(M, float)
    c = c.reshape(n, 3) @ M[:3, :3].T + M[:3, 3]
    dmin = np.full(n, np.inf)
    ds = np.ones(len(cam_mats)) if dscale is None else np.asarray(dscale, float)
    for Mc, s_ in zip(cam_mats, ds):
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = c @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            nx = v[:, 0] / z / (tan_v * aspect_w)
            ny = v[:, 1] / z / tan_v
        inside = (z > 0.1) & (np.abs(nx) <= 1.15) & (np.abs(ny) <= 1.15)
        d = np.linalg.norm(c - Mc[:3, 3], axis=1) * s_
        dmin = np.where(inside, np.minimum(dmin, d), dmin)
    return dmin


class Item:
    __slots__ = ("mesh", "M", "kind", "zone", "hot", "top", "owner", "name", "key", "dmin", "rho", "scale",
                 "props", "rand", "atlas", "demand", "uv", "tris", "boost")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))


PACK_SHAPE = "CONVEX"


def a_shape():
    return PACK_SHAPE


def vert_dmin(me, M, cam_mats, tan_v, aspect_w, dscale=None):
    """Per vertex: nearest camera distance over the views where it is in the widened frustum (inf never); dscale as
    in face_dmin."""
    n = len(me.vertices)
    c = np.empty(n * 3)
    me.vertices.foreach_get("co", c)
    M = np.asarray(M, float)
    c = c.reshape(n, 3) @ M[:3, :3].T + M[:3, 3]
    dmin = np.full(n, np.inf)
    ds = np.ones(len(cam_mats)) if dscale is None else np.asarray(dscale, float)
    for Mc, s_ in zip(cam_mats, ds):
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = c @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            nx = v[:, 0] / z / (tan_v * aspect_w)
            ny = v[:, 1] / z / tan_v
        inside = (z > 0.1) & (np.abs(nx) <= 1.3) & (np.abs(ny) <= 1.3)
        d = np.linalg.norm(c - Mc[:3, 3], axis=1) * s_
        dmin = np.where(inside, np.minimum(dmin, d), dmin)
    return dmin


def decimate_weighted(dec, key, base, M, cam_mats, tan_v, aspect_w, ratio, near=40.0, far=500.0, dscale=None,
                      keep=None):
    """One collapse decimation of a big mesh where vertices near the camera path are protected (Decimate
    vertex-group weights: 0 = keep, 1 = decimate freely), so near terrain stays dense and the far part pays
    for it, with no cracks between distance pieces. cam_mats / dscale: every audit view with its distance factor,
    so terrain a look-around view sees near a hold is protected too. keep (per vertex, optional): weight 0 wherever
    it is (the range's grass/rock border, bake_rules.border_vertices)."""
    d = vert_dmin(base, M, cam_mats, tan_v, aspect_w, dscale)
    q = BR.range_weights(d, keep, near, far)
    ob = dec.ob
    ob.data = base
    ob.vertex_groups.clear()
    vg = ob.vertex_groups.new(name="w")
    for val in np.unique(q):
        vg.add(np.nonzero(q == val)[0].tolist(), float(val), "REPLACE")
    dec.mod.vertex_group = "w"
    dec.mod.vertex_group_factor = 50.0
    me = dec.get(key, base, ratio)
    dec.mod.vertex_group = ""
    ob.vertex_groups.clear()
    log("weighted decimation", key, len(base.polygons), "->", len(me.polygons),
        "faces (%d triangles); near %d far %d m;" % (_tris(me), near, far), "protected verts", int((q < 0.05).sum()),
        "of", len(q),
        "(kept as border: %d)" % (int(np.asarray(keep, bool).sum()) if keep is not None else 0))
    return me


def smooth_range(me, label):
    """Full path, the decimated range: drop its hard normal splits (world.py marks folds over 55 deg sharp; only folds
    over RANGE_SHARP_DEG stay split, the knife-edge lips) and store the whole mesh's smooth corner normals as W_NRM,
    which carry_normals gives back to every piece cut out of it.
    A piece rebuilt through bmesh (export_web.submesh) recomputes its normals from its own faces only, so the shading
    normal jumped along every chunk and distance-bin cut line. Logs the check-first numbers: the sharp share before
    and after, and the mean angle between corner and face normals before / after (0 = flat shading)."""
    nl, npl, ne = len(me.loops), len(me.polygons), len(me.edges)
    if not nl:
        return me
    A = ma(me)
    fn = np.empty(npl * 3, np.float32)
    me.polygons.foreach_get("normal", fn)
    fn = fn.reshape(npl, 3)
    lf = np.repeat(np.arange(npl), A.lt)
    ar = np.empty(npl, np.float32)
    me.polygons.foreach_get("area", ar)
    share = {}
    for nm, n in (("sharp_edge", ne), ("sharp_face", npl)):
        a = me.attributes.get(nm)
        v = np.zeros(n, bool)
        if a is not None and n:
            a.data.foreach_get("value", v)
        share[nm] = float(v.mean()) if n else 0.0
    ang0 = BR.corner_face_angle(A.cn, fn, lf, ar[lf])
    for nm in ("sharp_edge", "sharp_face", "custom_normal"):
        a = me.attributes.get(nm)
        if a is not None:
            me.attributes.remove(a)
    # the knife-edge lips stay hard: averaged across a 150+ deg fold, the normal turns sideways on both sides
    try:
        me.set_sharp_from_angle(angle=math.radians(RANGE_SHARP_DEG))
    except Exception as e:
        log("WARN range normals: set_sharp_from_angle failed, every fold smoothed:", e)
    me.update()
    _MA.pop(me.name, None)
    a = me.attributes.get("sharp_edge")
    kept = np.zeros(ne, bool)
    if a is not None and ne:
        a.data.foreach_get("value", kept)
    share_after = float(kept.mean()) if ne else 0.0
    cn = np.empty(nl * 3, np.float32)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(nl, 3)
    set_attr(me, W_NRM, "FLOAT_VECTOR", "CORNER", cn)
    ang1 = BR.corner_face_angle(cn, fn, lf, ar[lf])
    log("range normals", label, "sharp_edge %.1f%% sharp_face %.1f%% -> %.1f%% / 0%% (folds over %d deg kept); "
        "corner-face angle %.2f -> %.2f deg" % (100 * share["sharp_edge"], 100 * share["sharp_face"], 100 * share_after,
                                                RANGE_SHARP_DEG, ang0, ang1), "(0 = flat);", W_NRM, "on", nl, "corners")
    _FC.setdefault("check", {})["range_normals"] = dict(
        sharp_edge=round(share["sharp_edge"], 4), sharp_face=round(share["sharp_face"], 4),
        sharp_edge_after=round(share_after, 4), sharp_deg=RANGE_SHARP_DEG, angle_before=round(ang0, 2),
        angle_after=round(ang1, 2), corners=nl, faces=npl, tris=_tris(me))
    return me


def carry_normals(me):
    """A piece cut out of the smoothed range (W_NRM present): shade it with the whole range's normals instead of the
    ones bmesh recomputed from the piece's own faces. False when the mesh has none (any other mesh)."""
    a = me.attributes.get(W_NRM)
    if a is None or a.domain != "CORNER" or not len(me.loops):
        return False
    try:
        me.normals_split_custom_set(get_attr(me, W_NRM, len(me.loops), 3))
    except Exception as e:
        log("WARN carry normals", me.name, e)
        return False
    _MA.pop(me.name, None)
    return True


def submesh(me, mask, name):
    """export_web.submesh, keeping the range's smooth normals on the piece (carry_normals)."""
    out = EW.submesh(me, mask, name)
    carry_normals(out)
    return out


def fix_normals(me):
    """Closed meshes whose faces point inward bake black (a bake looks out along the normal; a camera render
    shades back faces and hides it). Recalculate outside on closed (boundary-free) meshes only."""
    import bmesh
    if len(me.polygons) == 0:
        return False
    bm = bmesh.new()
    bm.from_mesh(me)
    if any(e.is_boundary for e in bm.edges):
        bm.free()
        return False
    before = np.array([f.normal.copy() for f in bm.faces])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    after = np.array([f.normal.copy() for f in bm.faces])
    flipped = int(((before * after).sum(1) < 0).sum())
    if flipped:
        bm.to_mesh(me)
        for nm in ("custom_normal", W_NRM):       # stored normals would point the old way: recomputed instead
            a = me.attributes.get(nm)
            if a is not None:
                me.attributes.remove(a)
        _MA.pop(me.name, None)
        _FLIPPED.append((me.name, flipped, len(me.polygons)))
    bm.free()
    return bool(flipped)


_FLIPPED = []


_CLEAN = {}


def clean_mesh(me):
    """Drop sliver / zero-area faces (collapse decimation leaves them): they are invisible, the glTF exporter
    drops them anyway, and their long zero-width UV islands wreck island packing."""
    if me.name in _CLEAN:
        return _CLEAN[me.name]
    if me.validate(verbose=False, clean_customdata=False):
        _MA.pop(me.name, None)
    fix_normals(me)
    A = ma(me)
    if A.np == 0:
        _CLEAN[me.name] = me
        return me
    p = A.co[A.vi]
    nxt = np.arange(A.nl) + 1
    ends = A.ls + A.lt
    nxt[ends - 1] = A.ls
    el = np.linalg.norm(p[nxt] - p, axis=1)
    per = np.add.reduceat(el, A.ls)
    ar = np.empty(A.np, np.float32)
    me.polygons.foreach_get("area", ar)
    bad = (ar < 1e-4 * per ** 2) | (ar < 1e-8)
    if not bad.any():
        _CLEAN[me.name] = me
        return me
    if bad.all():
        _CLEAN[me.name] = None
        return None
    out = submesh(me, ~bad, me.name[:50] + ".cl")
    _CLEAN[me.name] = out
    _CLEAN[out.name] = out
    return out


def split_heavy(items, cam_mats, tan_v, aspect_w, dscale=None):
    """Pieces whose texel demand is large are split by per-face camera distance, so only their near faces
    get the high density (a bounding-box distance gives a whole stairway or rock underside the density of
    its nearest corner). Faces no view sees get the minimum density. Turning objects (export_web.TURNING_GROUPS)
    are never split: every side of them shows on the page, so they keep one density."""
    out = []
    n_split = 0
    turning = EW.turning_owners()
    for it in items:
        if it.demand <= SPLIT_DEMAND or len(it.mesh.polygons) < 2 or it.owner in turning:
            out.append(it)
            continue
        fd = face_dmin(it.mesh, it.M, cam_mats, tan_v, aspect_w, dscale)
        fd = np.where(np.isfinite(fd), fd, 1e7)
        bins = list(SPLIT_BINS)
        pieces = 0
        for b0, b1 in zip(bins[:-1], bins[1:]):
            m = (fd >= b0) & (fd < b1)
            if not m.any():
                continue
            sub = submesh(it.mesh, m, "%s.s%d" % (it.name[:50], int(b0)))
            nit = Item(**{k: getattr(it, k) for k in Item.__slots__})
            nit.mesh = sub
            nit.name = "%s.s%d" % (it.name, int(b0))
            nit.dmin = max(b0, it.dmin, 6.0) if b1 < 1e7 else 1e4
            nit.rho = rho_of(nit.dmin) * detail_boost(it.name) * (it.boost or 1.0)
            A = ma(sub)
            L = np.asarray(it.M, float)[:3, :3]
            nit.demand = A.area * abs(np.linalg.det(L)) ** (2.0 / 3.0) * nit.rho ** 2
            out.append(nit)
            pieces += 1
        n_split += 1
    log("split", n_split, "heavy pieces by face distance;", len(items), "->", len(out), "items")
    return out


def near_holds(R, idx, hold_mats, near=HOLD_NEAR, area_near=None):
    """Records whose box comes within `near` m of a hold camera (or `area_near` m for pieces of the area that
    hold looks at), in front of it: the props the reader looks at while the camera stands still."""
    if area_near is None:
        area_near = HOLD_AREA_NEAR       # read at call time (use_profile / full_ctx replace it)
    out = np.zeros(len(idx), bool)
    if len(idx) == 0:
        return out
    lo, hi = R.lo[idx], R.hi[idx]
    c = 0.5 * (lo + hi)
    r = 0.5 * np.linalg.norm(hi - lo, axis=1)
    tops = np.array([R.top[i] for i in idx])
    for M, area, an in zip(hold_mats, HOLD_AREAS, area_near):
        M = np.asarray(M, float)
        p = M[:3, 3]
        fwd = -M[:3, 2]
        d = np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0), axis=1)
        ahead = (c - p) @ fwd > -r
        lim = np.where(tops == area, an, near)
        out |= (d <= lim) & ahead
    return out


def around_holds(R, idx, hold_mats, reach):
    """Records whose box comes within `reach` m of a hold camera in any direction (the page lets the visitor turn
    the view all the way round while the camera stands still)."""
    out = np.zeros(len(idx), bool)
    if len(idx) == 0:
        return out
    lo, hi = R.lo[idx], R.hi[idx]
    for M in hold_mats:
        p = np.asarray(M, float)[:3, 3]
        out |= np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0), axis=1) <= reach
    return out


def slender_mask(R, idx):
    """Tall thin pieces (rock spires, pillars): collapse decimation turns them into wide pyramids."""
    if len(idx) == 0:
        return np.zeros(0, bool)
    s = R.hi[idx] - R.lo[idx]
    foot = np.maximum(np.maximum(s[:, 0], s[:, 1]), 1e-3)
    return (s[:, 2] > SLENDER * foot) & (s[:, 2] > 8.0) & (R.tris[idx] > 200)


def kd_chunks(centers, faces, max_faces):
    """Face index lists of at most max_faces each, spatially compact: median cuts on the longest axis."""
    out, stack = [], [np.asarray(faces)]
    while stack:
        f = stack.pop()
        if len(f) == 0:
            continue
        if len(f) <= max_faces:
            out.append(f)
            continue
        c = centers[f]
        ax = int(np.argmax(c.max(0) - c.min(0)))
        o = np.argsort(c[:, ax], kind="stable")
        h = len(f) // 2
        stack += [f[o[:h]], f[o[h:]]]
    return out


def glow_class(mat_name):
    """(strength, tint hex or None, class key) for a glowing source material."""
    low = mat_name.lower()
    for k, s, t in GLOW_CLASSES:
        if k in low:
            return s, t, k
    return GLOW_FALLBACK[0], GLOW_FALLBACK[1], "other"


def detail_class(mat_name, tag=None):
    """'rock', 'ground' or None for a source material: by its sect_material tag when it has one, else by its name
    without the 'M.' prefix and a Blender duplicate suffix ('.001')."""
    nm = tag or mat_name or ""
    if not tag:
        if nm.startswith(MAT_PREFIX):
            nm = nm[len(MAT_PREFIX):]
        base, dot, suf = nm.rpartition(".")
        if dot and suf.isdigit():
            nm = base
    for k, names in DETAIL_CLASSES:
        if nm in names:
            return k
    if nm.startswith(TILE_PREFIX):
        return "tiles"
    return None


def _base_name(mat_name, tag=None):
    """A source material's registered name: its sect_material tag, else its name without the 'M.' prefix and a
    Blender duplicate suffix ('.001')."""
    nm = tag or mat_name or ""
    if not tag:
        if nm.startswith(MAT_PREFIX):
            nm = nm[len(MAT_PREFIX):]
        base, dot, suf = nm.rpartition(".")
        if dot and suf.isdigit():
            nm = base
    return nm


def surface_class(mat_name, tag=None):
    """'metal', 'glaze' or None for a source material (SURFACE_CLASSES: exact names, then name prefixes)."""
    nm = _base_name(mat_name, tag)
    for k, names, prefixes in SURFACE_CLASSES:
        if nm in names or nm.startswith(prefixes):
            return k
    return None


def zone_of_records(R, idx, cam_pos, frames):
    """'gate' when the record is nearest the camera during the gate section, else 'mirror'. Full profile: the id
    of the area whose frame range holds the frame where the record is nearest the camera."""
    lo, hi = R.lo[idx], R.hi[idx]
    best_d = np.full(len(idx), np.inf)
    best_f = np.zeros(len(idx), int)
    for f, p in zip(frames, cam_pos):
        d = np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0), axis=1)
        b = d < best_d
        best_d[b] = d[b]
        best_f[b] = f
    if PROFILE == "full":
        ids = np.array([x["id"] for x in EW.AREAS])
        return ids[EW._area_index_array(np.maximum(best_f, 1))]
    return np.where(best_f <= GATE_END, "gate", "mirror")


def zone_of_point(p, cam_pos, frames):
    d = np.linalg.norm(np.asarray(cam_pos) - np.asarray(p), axis=1)
    f = frames[int(np.argmin(d))]
    if PROFILE == "full":
        return EW.AREAS[EW.area_of_frame(int(f))]["id"]
    return "gate" if f <= GATE_END else "mirror"


# ---- joined mesh ------------------------------------------------------------------------------

def concat(items, slot_fn, scale_about_centre=False):
    """Concatenate items into world space. Returns dict of arrays (co, vi, ls, mi, per-loop/vertex data)."""
    co, vi, ls, mi, cn, uv0, uvb, ocoo, ogen = [], [], [], [], [], [], [], [], []
    vitem, fitem = [], []
    attrs = collections.defaultdict(list)
    attr_dom = {}
    for nm in COPY_ATTRS:
        for it in items:
            A = ma(it.mesh)
            if nm in A.attrs:
                attr_dom[nm] = (A.attrs[nm][0], A.attrs[nm][1].shape[1] if A.attrs[nm][1].ndim > 1 else 1)
                break
    vo = lo = 0
    for k, it in enumerate(items):
        A = ma(it.mesh)
        M = np.asarray(it.M, np.float64)
        L = M[:3, :3]
        w = A.co @ L.T + M[:3, 3]
        if scale_about_centre:
            c = 0.5 * (w.min(0) + w.max(0)) if len(w) else np.zeros(3)
            w = c + (w - c) * it.rho
        det = np.linalg.det(L)
        perm = A.flip_perm() if det < 0 else None
        lvi = A.vi if perm is None else A.vi[perm]
        co.append(w.astype(np.float32))
        vi.append(lvi + vo)
        ls.append(A.ls + lo)
        mi.append(np.array([slot_fn(it, A.mats[j] if j < len(A.mats) else "") for j in range(max(len(A.mats), 1))],
                           np.int32)[np.clip(A.mi, 0, max(len(A.mats) - 1, 0))])
        if not scale_about_centre:
            try:
                nmat = np.linalg.inv(L).T
            except np.linalg.LinAlgError:
                nmat = np.eye(3)
            n = A.cn @ nmat.T
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            cn.append((n if perm is None else n[perm]).astype(np.float32))
            u = A.uv0 if A.uv0 is not None else np.zeros((A.nl, 2), np.float32)
            uv0.append(u if perm is None else u[perm])
            if it.uv is not None:
                uvb.append(it.uv if perm is None else it.uv[perm])
            ocoo.append(A.co)
            ogen.append(A.gen)
            for nm, (dom, width) in attr_dom.items():
                if nm in A.attrs:
                    d = A.attrs[nm][1]
                    if dom == "CORNER" and perm is not None:
                        d = d[perm]
                else:
                    n_ = {"POINT": A.nv, "FACE": A.np, "CORNER": A.nl}[dom]
                    d = np.zeros((n_, width) if width > 1 else n_, np.float32)
                attrs[nm].append(d)
        vitem.append(np.full(A.nv, k, np.int32))
        fitem.append(np.full(A.np, k, np.int32))
        vo += A.nv
        lo += A.nl
    out = dict(co=np.concatenate(co), vi=np.concatenate(vi), ls=np.concatenate(ls), mi=np.concatenate(mi),
               vitem=np.concatenate(vitem), fitem=np.concatenate(fitem))
    if not scale_about_centre:
        out.update(cn=np.concatenate(cn), uv0=np.concatenate(uv0), o_co=np.concatenate(ocoo),
                   o_gen=np.concatenate(ogen))
        if uvb:
            out["uvb"] = np.concatenate(uvb)
        out["attrs"] = {nm: (attr_dom[nm][0], np.concatenate(v)) for nm, v in attrs.items()}
    return out


DEBUG_PROXY = os.environ.get("BAKE_DEBUG_PROXY") == "1"
GROUP_BY_MATERIAL = True       # pack each atlas material by material (pack_shelf face_group)
GROUP_MAX_TEXELS = 32.0
MIN_ISLAND_TEXELS = 2.5        # full profile: islands are at least this many texels across (pack_shelf min_texels)        # islands larger than this (layout texels) are packed together, not by material
PACK_MARGIN = 1.25             # texels between islands (with ~115k small islands, 2 cost a third of the atlas)
SOFT_MIN_TEXELS = 1.5          # full: the stretch for islands of glowing faces only (pack_shelf soft): one texel centre
                               # each is enough for one emitted colour, and the material packing puts glyph beside glyph
CELL_TEXELS = 300.0            # unwrap proxy is cut on a 3D grid of this many texels, so no island is longer


def cut_grid(co, vi, ls, cell):
    """Split vertices shared by faces in different grid cells (proxy space = texels), so UV islands cannot
    run longer than a cell. Long coplanar strips (railings, stair edges) otherwise become islands thousands
    of texels long and the packer shrinks everything else to nothing."""
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    face_of_loop = np.repeat(np.arange(len(ls)), lt)
    fc = np.add.reduceat(co[vi], ls) / lt[:, None]
    cidx = np.floor(fc / cell).astype(np.int64)
    h = (cidx[:, 0] * 73856093) ^ (cidx[:, 1] * 19349663) ^ (cidx[:, 2] * 83492791)
    key = (vi.astype(np.int64) << 24) | (h[face_of_loop] & 0xFFFFFF)
    uk, inv = np.unique(key, return_inverse=True)
    new_co = co[(uk >> 24).astype(np.int64)]
    return new_co, inv.astype(np.int32)


_D26 = np.array([(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)],
                float)
_D26 /= np.linalg.norm(_D26, axis=1, keepdims=True)
_U26 = np.cross(_D26, np.where(np.abs(_D26[:, 2:3]) > 0.9, [[1.0, 0.0, 0.0]], [[0.0, 0.0, 1.0]]))
_U26 /= np.linalg.norm(_U26, axis=1, keepdims=True)
_V26 = np.cross(_D26, _U26)


def project_box26(co, vi, ls):
    """Lightmap projection without Blender's unwrapper: every face is projected onto the plane of the nearest
    of 26 directions (at most 22.5 deg off, under 8 % stretch); loops of a vertex in different direction
    clusters get different UVs, so islands split there. Float64 throughout."""
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    p = co[vi].astype(np.float64)
    fn = np.zeros((len(ls), 3))
    for k in range(1, int(lt.max()) - 1):
        m = lt > k + 1
        s0 = ls[m]
        fn[m] += np.cross(p[s0 + k] - p[s0], p[s0 + k + 1] - p[s0])
    nrm = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.where(nrm > 1e-12, fn / np.maximum(nrm, 1e-12), [[0.0, 0.0, 1.0]])
    cl = np.argmax(fn @ _D26.T, axis=1)
    cll = np.repeat(cl, lt)
    return np.stack([(p * _U26[cll]).sum(1), (p * _V26[cll]).sum(1)], 1)


def uv_islands(u, vi, ls):
    """Island id per face: faces are connected when they share an edge whose two ends have identical UVs.
    (Connecting on a single shared vertex chained faces of one projection direction diagonally across bumpy
    surfaces into sparse islands whose bounding boxes were mostly empty: terrain atlases packed at 35 %.)"""
    nl = len(vi)
    nf = len(ls)
    lt = np.diff(np.append(ls, nl))
    f_of_l = np.repeat(np.arange(nf), lt)
    ub = np.ascontiguousarray(u, np.float32).view(np.int32)
    key = np.stack([vi.astype(np.int64), ub[:, 0].astype(np.int64), ub[:, 1].astype(np.int64)], 1)
    _, uvv = np.unique(key, axis=0, return_inverse=True)
    uvv = uvv.ravel().astype(np.int64)
    nxt = np.arange(nl) + 1
    nxt[ls + lt - 1] = ls
    a, b = uvv, uvv[nxt]
    _, eid = np.unique(np.minimum(a, b) * (int(uvv.max()) + 1) + np.maximum(a, b), return_inverse=True)
    eid = eid.ravel()
    ne = int(eid.max()) + 1
    lab = np.arange(nf)
    big = np.iinfo(np.int64).max
    for _ in range(10000):
        le = np.full(ne, big, np.int64)
        np.minimum.at(le, eid, lab[f_of_l])
        nf_lab = np.minimum.reduceat(le[eid], ls)
        new = np.minimum(lab, nf_lab)
        while True:                     # pointer jumping
            j = new[new]
            if (j == new).all():
                break
            new = j
        if (new == lab).all():
            break
        lab = new
    _, isl = np.unique(lab, return_inverse=True)
    return isl.ravel(), f_of_l


def pack_shelf(u, co, vi, ls, atlas_px, margin=2.0, face_group=None, min_texels=0.0, soft=None):
    """Own island packer (Blender's packer collapses with tens of thousands of islands): rescale every island
    so its UV area equals its proxy (texel-unit) area, rotate it to its principal axis, shelf-pack all
    islands sorted by height with `margin` texels around each, and fit the square layout to the atlas.
    face_group (int per face, e.g. the source material): islands are packed group by group (height order
    inside a group), so texture filtering and mipmaps blend an island only with islands of the same material
    (mixed neighbours bled red / white / teal streaks into dark roof tiles).
    min_texels: islands thinner than this (layout texels, after the rotation) are stretched across to it, so every
    island holds texel centres: a strip narrower than a texel gets no baked texel of its own and shows what the
    margin fill copied from its neighbours (bright crest lines and red board dashes on the forge roof).
    soft (per face, optional): islands made only of such faces (glowing glyph strokes, runes: one emitted colour,
    packed beside their own material) are stretched to SOFT_MIN_TEXELS only."""
    isl, f_of_l = uv_islands(u, vi, ls)
    ni = int(isl.max()) + 1
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    # areas per face (3D proxy units and UV)
    p = co[vi]
    a3 = np.zeros(len(ls))
    auv = np.zeros(len(ls))
    for k in range(1, int(lt.max()) - 1):
        m = lt > k + 1
        s0 = ls[m]
        e1 = p[s0 + k] - p[s0]
        e2 = p[s0 + k + 1] - p[s0]
        a3[m] += 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
        d1 = u[s0 + k] - u[s0]
        d2 = u[s0 + k + 1] - u[s0]
        auv[m] += 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    A3 = np.bincount(isl, a3, ni)
    AU = np.bincount(isl, auv, ni)
    k = np.sqrt(np.where(AU > 1e-20, A3 / np.maximum(AU, 1e-30), 0.0))
    ratio_spread = np.percentile(k[AU > 1e-20], [5, 50, 95]) if (AU > 1e-20).any() else [0, 0, 0]
    il = isl[f_of_l]                                   # island per loop
    order = np.argsort(il, kind="stable")
    ils = il[order]
    starts = np.searchsorted(ils, np.arange(ni))
    cnt = np.bincount(il, minlength=ni).astype(float)
    uu = u[order].astype(np.float64) * k[ils][:, None]
    mean = np.add.reduceat(uu, starts) / cnt[:, None]
    d = uu - mean[ils]
    cxx = np.add.reduceat(d[:, 0] * d[:, 0], starts)
    cyy = np.add.reduceat(d[:, 1] * d[:, 1], starts)
    cxy = np.add.reduceat(d[:, 0] * d[:, 1], starts)
    th = 0.5 * np.arctan2(2 * cxy, cxx - cyy)
    c, s_ = np.cos(-th)[ils], np.sin(-th)[ils]
    r = np.stack([d[:, 0] * c - d[:, 1] * s_, d[:, 0] * s_ + d[:, 1] * c], 1)
    lo = np.minimum.reduceat(r, starts)
    hi = np.maximum.reduceat(r, starts)
    wh = hi - lo
    swap = wh[:, 1] > wh[:, 0]                       # long side horizontal
    r[swap[ils]] = r[swap[ils]][:, ::-1]
    lo[swap] = lo[swap][:, ::-1]
    wh[swap] = wh[swap][:, ::-1]
    wh_pre = wh.copy()
    if min_texels > 0:
        mt = np.full((ni, 1), float(min_texels))
        if soft is not None:
            all_soft = np.bincount(isl, ~np.asarray(soft, bool), ni) == 0
            mt[all_soft] = min(SOFT_MIN_TEXELS, min_texels)
        f = np.clip(mt / np.maximum(wh, 1e-6), 1.0, 16.0)               # per island, per axis
        r = lo[ils] + (r - lo[ils]) * f[ils]
        wh = wh * f
        hi = lo + wh
    # full profile: islands of MARGIN_BIG_TEXELS or more get MARGIN_BIG texels around them, the small ones `margin`
    mg = np.full(ni, float(margin))
    if PROFILE == "full" and MARGIN_BIG > margin:
        mg[wh.max(1) >= MARGIN_BIG_TEXELS] = MARGIN_BIG
    W = wh[:, 0] + 2 * mg
    H = wh[:, 1] + 2 * mg
    side = math.sqrt(float((W * H).sum()) / 0.93)
    side = max(side, float(W.max()))
    pos = np.zeros((ni, 2))

    def shelf(ids, width):
        """Shelf-pack islands `ids` (tallest first) into rows `width` wide: (positions, used width, height)."""
        out = np.zeros((len(ids), 2))
        x = y = sh = wmax = 0.0
        for j, i in enumerate(ids[np.argsort(-H[ids], kind="stable")] if len(ids) else ids):
            if x + W[i] > width and x > 0:
                y += sh
                x = sh = 0.0
            out[j] = (x, y)
            x += W[i]
            wmax = max(wmax, x)
            sh = max(sh, H[i])
        order_ = ids[np.argsort(-H[ids], kind="stable")] if len(ids) else ids
        return order_, out, wmax, y + sh
    if face_group is None:
        side = math.sqrt(float((W * H).sum()) / 0.93)
        side = max(side, float(W.max()))
        o_, p_, _, total_h = shelf(np.arange(ni), side)
        pos[o_] = p_
    else:
        # the large islands first (shelves across the whole width, tallest first), then the small ones material by
        # material: each material's small islands are shelf-packed into a block of one common width, and the blocks
        # are stacked in columns (always onto the shortest column). Neighbouring islands then share a material, so
        # texture filtering and mipmaps no longer blend e.g. red beams and white marble into dark roof tiles
        # (bright streaks). Large islands only bleed at their borders.
        g = np.zeros(ni, np.int64)
        g[isl] = np.asarray(face_group, np.int64)
        big = np.maximum(W, H) > GROUP_MAX_TEXELS
        bi = np.nonzero(big)[0]
        bi = bi[np.argsort(-H[bi], kind="stable")]
        si = np.nonzero(~big)[0]
        gs = np.unique(g[si]) if len(si) else np.zeros(0, np.int64)
        garea = np.array([float((W[si][g[si] == q] * H[si][g[si] == q]).sum()) for q in gs])
        g_ids = [si[g[si] == gid] for gid in gs[np.argsort(-garea, kind="stable")]]     # the biggest materials first
        g_ids = [ids[np.argsort(-H[ids], kind="stable")] for ids in g_ids]

        def grouped(side):
            """(positions, total height) of the grouped layout `side` wide."""
            pos = np.zeros((ni, 2))
            x = y = sh = 0.0
            for i in bi:
                if x + W[i] > side and x > 0:
                    y += sh
                    x = sh = 0.0
                pos[i] = (x, y)
                x += W[i]
                sh = max(sh, H[i])
            y0 = y + sh
            if not len(si):
                return pos, y0
            ncol = int(max(1, min(16, side // max(4.0 * GROUP_MAX_TEXELS, 1.0))))
            B = side / ncol
            colh = np.zeros(ncol)
            T = float((W[si] * H[si]).sum()) / side / 0.9       # column height when the columns come out even
            for ids in g_ids:
                c = int(np.argmin(colh))
                x = sh = 0.0
                yy = colh[c]
                for i in ids:
                    if x + W[i] > B and x > 0:
                        yy += sh
                        x = sh = 0.0
                        if yy >= T and colh.min() < T:          # this column is full: go on in the shortest one
                            colh[c] = yy
                            c = int(np.argmin(colh))
                            yy = colh[c]
                    pos[i] = (c * B + x, y0 + yy)
                    x += W[i]
                    sh = max(sh, H[i])
                colh[c] = yy + sh
            return pos, y0 + float(colh.max())
        side0 = max(math.sqrt(float((W * H).sum()) / 0.93), float(W.max()))
        # the layout comes out taller than wide when the columns run uneven (forge_A0: 5163 x 5971, 13 % of the atlas
        # empty): full profile, a few wider layouts are tried and the squarest kept (the atlas is square)
        tries = (1.0, 1.04, 1.08, 1.12, 1.17) if PROFILE == "full" else (1.0,)
        best = None
        for f_ in tries:
            sd = max(side0 * f_, float(W.max()))
            p_, th_ = grouped(sd)
            if best is None or max(sd, th_) < best[0]:
                best = (max(sd, th_), sd, p_, th_)
            if th_ <= sd:
                break
        _, side, pos, total_h = best
    extent = max(side, total_h)
    scale = 1.0 / extent
    out = np.empty_like(u, dtype=np.float64)
    out[order] = (r - lo[ils] + mg[ils][:, None] + pos[ils]) * scale
    info = dict(islands=ni, layout=[round(side), round(total_h)], texels_per_unit=round(atlas_px * scale, 3),
                margin_px=round(margin * atlas_px * scale, 2), fill=round(float((wh[:, 0] * wh[:, 1]).sum()) *
                                                                           scale * scale, 3),
                uv_per_3d_spread=[float(x) for x in np.round(ratio_spread, 4)],
                big_margin_islands=int((mg > margin).sum()), scale=float(scale))
    # check-first: islands by (long, short) side before the stretch (layout texels): count, share of the layout area
    # they take with stretch and margins, share of the surface (3D area)
    ln, sh_ = wh_pre.max(1), wh_pre.min(1)
    tot_wh = float((W * H).sum())
    bins = {"tiny<4": ln < 4, "thin<2.5": (ln >= 4) & (sh_ < 2.5), "small<8": (ln >= 4) & (sh_ >= 2.5) & (ln < 8),
            "mid<32": (ln >= 8) & (sh_ >= 2.5) & (ln < 32), "big": (ln >= 32) & (sh_ >= 2.5)}
    info["size_bins"] = {k: [int(m.sum()), round(float((W * H)[m].sum()) / tot_wh, 3), round(float(A3[m].sum()) /
                                                                                         max(float(A3.sum()), 1e-9), 3)]
                         for k, m in bins.items()}
    return out.astype(np.float32), info


UNWRAP_INFO = {}               # atlas name -> pack_shelf's info (texels_per_unit for the atlas sizing in bake_chunk)


def is_sheet(it):
    """A roof tile sheet (arch._roof_top_mesh: '<roof>.tiles', split_heavy pieces '<roof>.tiles.s<n>')."""
    return it.name.endswith(".tiles") or ".tiles." in it.name


def _loop_subset(vi, ls, faces):
    """(corner vertex indices, loop starts, corner indices) of the polygons `faces` of a (vi, ls) mesh."""
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    t = lt[faces]
    lsel = np.repeat(ls[faces] - np.concatenate([[0], np.cumsum(t)[:-1]]), t) + np.arange(int(t.sum()))
    return vi[lsel], np.concatenate([[0], np.cumsum(t)[:-1]]).astype(ls.dtype), lsel


def _sheet_faces(C, items):
    """Per face of a concat() mesh: True on roof sheets (is_sheet)."""
    sh = np.array([is_sheet(it) for it in items] + [False], bool)
    return sh[C["fitem"]]


def sheet_uv(C, items, u0):
    """SHEET_UNWRAP: the corners of roof tile sheets get their slope's planar projection (bake_rules.sheet_project, one
    sheet = one edge-connected part of a '.tiles' piece) in place of project_box26's; faces it leaves out (steeper
    than its limit, or turned over) keep u0. C: concat() proxy arrays (texel units). Returns (uv, sheet faces)."""
    if not SHEET_UNWRAP or not len(C["ls"]):
        return u0, 0
    sh = np.array([is_sheet(it) for it in items] + [False], bool)
    fs = np.nonzero(sh[C["fitem"]])[0]
    if not len(fs):
        return u0, 0
    vi_s, ls_s, lsel = _loop_subset(C["vi"], C["ls"], fs)
    part, _ = uv_islands(np.zeros((len(vi_s), 2), np.float32), vi_s, ls_s)     # edge-connected parts
    uv, ok = BR.sheet_project(C["co"], vi_s, ls_s, part)
    lt = np.diff(np.append(ls_s, len(vi_s)))
    okl = np.repeat(ok, lt)
    out = np.array(u0, np.float64, copy=True)
    out[lsel[okl]] = uv[okl]
    return out, int(ok.sum())


CHART_MERGE = True             # full: thin box26 islands (short side under CHART_THIN layout texels: the 1-2 texel strips
CHART_THIN = 3.0               # project_box26 cuts columns, round beams and bevels into) merge with their neighbours across
CHART_PAIR_DEG = 92.0          # convex folds into charts of at most three neighbouring directions (pairwise at most
                               # CHART_PAIR_DEG apart), each projected onto its own mean plane. A convex patch whose normals
                               # lie in one hemisphere projects without overlap; concave folds (mouldings, eaves) never merge.
                               # forge_A0: thin strips took 18 % of the layout for 5 % of the surface
CHART_FOLD_DEG = 50.0          # and only across folds of at most this (the two faces' normals): rounded columns, beams and
                               # bevels. Across square corners the strips chained round a stair's sides into charts that
                               # overlapped themselves (riser texels shared with the step undersides: black risers on the
                               # mission stair at 660), and a strip under a texel wide shows its neighbour's light anyway
_PAIR_OK = {}


def _dirs_ok(m):
    """True when every pair of the box26 directions in bit mask m lies within CHART_PAIR_DEG."""
    r = _PAIR_OK.get(m)
    if r is None:
        ids = [k for k in range(26) if m >> k & 1]
        c = math.cos(math.radians(CHART_PAIR_DEG))
        r = all(float(_D26[i] @ _D26[j]) >= c - 1e-9 for x, i in enumerate(ids) for j in ids[x + 1:])
        _PAIR_OK[m] = r
    return r


def merge_charts(co, vi, ls, u0, fixed=None):
    """CHART_MERGE on a proxy mesh (texel units) and its project_box26 / sheet_uv corner UVs u0: returns (uv, merged
    faces). fixed (per face): faces whose islands never merge (the roof sheets, already one island per slope)."""
    if not CHART_MERGE or not len(ls):
        return u0, 0
    t0 = time.time()
    ls = np.asarray(ls)
    nl = len(vi)
    isl, f_of_l = uv_islands(np.ascontiguousarray(u0, np.float32), vi, ls)
    ni = int(isl.max()) + 1
    dims = BR.island_dims(u0, isl[f_of_l], ni)
    thin = dims[:, 1] < CHART_THIN
    fn, fa = BR.poly_normals(co, vi, ls)
    cl = np.argmax(fn @ _D26.T, axis=1)
    icl = np.zeros(ni, np.int64)
    icl[isl] = cl
    bad = np.zeros(ni, bool)
    bad[isl[cl != icl[isl]]] = True               # mixed directions (a sheet): left alone
    if fixed is not None:
        bad[isl[np.asarray(fixed, bool)]] = True
    if not (thin & ~bad).any():
        return u0, 0
    # edges shared by two faces of different islands, and whether the fold there is convex
    lt = np.diff(np.append(ls, nl))
    nxt = np.arange(nl) + 1
    nxt[ls + lt - 1] = ls
    a, b = np.minimum(vi, vi[nxt]).astype(np.int64), np.maximum(vi, vi[nxt]).astype(np.int64)
    key = a * (int(vi.max()) + 1) + b
    o = np.argsort(key, kind="stable")
    ks = key[o]
    same = np.nonzero(ks[1:] == ks[:-1])[0]
    l1, l2 = o[same], o[same + 1]
    f1, f2 = f_of_l[l1], f_of_l[l2]
    i1, i2 = isl[f1], isl[f2]
    m = (i1 != i2) & ~bad[i1] & ~bad[i2] & (thin[i1] | thin[i2])
    if not m.any():
        return u0, 0
    l1, f1, f2, i1, i2 = l1[m], f1[m], f2[m], i1[m], i2[m]
    p = co[vi].astype(np.float64)
    cen = np.add.reduceat(p, ls) / lt[:, None]
    size = np.sqrt(np.maximum(fa, 1e-12))
    tol = 1e-3 * np.maximum(size[f1], size[f2])
    convex = (((cen[f2] - cen[f1]) * fn[f1]).sum(1) <= tol) & (((cen[f1] - cen[f2]) * fn[f2]).sum(1) <= tol)
    convex &= (fn[f1] * fn[f2]).sum(1) >= math.cos(math.radians(CHART_FOLD_DEG))
    # an island pair merges only when every edge between them is convex (and no sharper than CHART_FOLD_DEG)
    pk = np.minimum(i1, i2) * ni + np.maximum(i1, i2)
    up, inv = np.unique(pk, return_inverse=True)
    all_cvx = np.bincount(inv.ravel(), ~convex, len(up)) == 0
    pairs = up[all_cvx]
    parent = np.arange(ni)
    mask = {}

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r
    for q in pairs.tolist():
        x, y = find(q // ni), find(q % ni)
        if x == y:
            continue
        mm = mask.get(x, 1 << int(icl[x])) | mask.get(y, 1 << int(icl[y]))
        if not _dirs_ok(mm):
            continue
        parent[y] = x
        mask[x] = mm
    root = np.array([find(i) for i in range(ni)])
    cnt = np.bincount(root, minlength=ni)
    comp = np.where(cnt[root[isl]] > 1, root[isl], -1)
    if not (comp >= 0).any():
        return u0, 0
    uv, ok = BR.sheet_project(co, vi, ls, comp, max_tilt_deg=80.0)
    okl = np.repeat(ok, lt)
    out = np.array(u0, np.float64, copy=True)
    out[okl] = uv[okl]
    log("charts: %d thin islands of %d, %d pairs, %d charts from %d islands, %d faces; %.1f s"
        % (int((thin & ~bad).sum()), ni, len(pairs), len(set(root[cnt[root] > 1].tolist())),
           int((cnt[root] > 1).sum()), int(ok.sum()), time.time() - t0))
    return out, int(ok.sum())


def unwrap_group(items, label, atlas_px):
    """Smart UV project of a proxy mesh whose pieces are scaled by their texel density; the packed result
    (one 0-1 square) is split back into per-item loop UVs."""
    t0 = time.time()
    mat_ids = {}
    C = concat(items, lambda it, m: mat_ids.setdefault(m, len(mat_ids)), scale_about_centre=True)
    co, vi = cut_grid(C["co"], C["vi"], C["ls"], CELL_TEXELS)
    if DEBUG_PROXY:
        os.makedirs(os.path.join(BAKE_OUT, "debug"), exist_ok=True)
        np.savez_compressed(os.path.join(BAKE_OUT, "debug", "proxy_%s.npz" % label), co=co, vi=vi, ls=C["ls"],
                            fitem=C["fitem"], names=np.array([it.name for it in items]),
                            rho=np.array([it.rho for it in items]))
    t1 = time.time()
    u0 = project_box26(co, vi, C["ls"])
    u0, nsheet = sheet_uv(C, items, u0)
    u0, nchart = merge_charts(co, vi, C["ls"], u0, fixed=_sheet_faces(C, items))
    soft = None
    if PROFILE == "full" and _FC.get("minfo"):
        glow_id = np.zeros(max(len(mat_ids), 1) + 1, bool)
        for nm, k in mat_ids.items():
            glow_id[k] = bool(_FC["minfo"].get(nm, {}).get("emission", False))
        soft = glow_id[C["mi"]]
    u, pinfo = pack_shelf(u0, co, vi, C["ls"], atlas_px, margin=PACK_MARGIN,
                          face_group=C["mi"] if GROUP_BY_MATERIAL else None,
                          min_texels=MIN_ISLAND_TEXELS if PROFILE == "full" else 0.0, soft=soft)
    tpack = time.time() - t1
    pinfo["sheet_faces"] = nsheet
    pinfo["chart_faces"] = nchart
    UNWRAP_INFO[label] = pinfo
    log("pack", label, json.dumps(pinfo))
    # utilisation: UV area of all faces
    tri_uv = 0.0
    off = 0
    for it in items:
        A = ma(it.mesh)
        it.uv = u[off:off + A.nl].copy()
        off += A.nl
    used = uv_area(u, C["ls"], len(u))
    log("unwrap", label, "items", len(items), "faces", len(C["ls"]), "uv area %.3f" % used, "pack %.1fs" % tpack,
        "bounds", u.min(0).round(3).tolist(), u.max(0).round(3).tolist(), round(time.time() - t0, 1), "s")
    return used


def deselect_all():
    for o in list(bpy.context.selected_objects):
        o.select_set(False)


def uv_area(u, ls, nl):
    """Sum of UV polygon areas (shoelace on each polygon's loops)."""
    lt = np.diff(np.append(ls, nl))
    nxt = np.arange(nl) + 1
    ends = ls + lt
    nxt[ends - 1] = ls
    x, y = u[:, 0], u[:, 1]
    cross = x * y[nxt] - x[nxt] * y
    return float(abs(np.add.reduceat(cross, ls)).sum() * 0.5)


CAMINFO = {}                   # cmd_bake fills: cam_mats, tan_v, aspect_w (per-face facing test), path (per view: a
                               # path frame, not a look-around view; missing = all path)


def _closed_faces(C):
    """Per face of a concat() mesh: True when its item is closed (every edge shared by two or more of the item's
    faces). concat keeps each item's own vertices, so an edge never joins two items."""
    vi, ls = C["vi"], C["ls"]
    nl, nf = len(vi), len(ls)
    if nf == 0:
        return np.zeros(0, bool)
    lt = np.diff(np.append(ls, nl))
    nxt = np.arange(nl) + 1
    nxt[ls + lt - 1] = ls
    e = np.sort(np.stack([vi, vi[nxt]], 1), axis=1)
    _, inv, cnt = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    open_loop = cnt[inv.ravel()] < 2
    fitem = C["fitem"]
    open_item = np.zeros(int(fitem.max()) + 1, bool)
    open_item[fitem[np.repeat(np.arange(nf), lt)[open_loop]]] = True
    return ~open_item[fitem]


FLIP_DEPTH = True              # facing_flip counts a sighting from behind only when nothing of the bake mesh lies between
                               # the camera and the face's centre (BVH ray test): without it the path "saw" the far side of
                               # every bridge pier and stair it drove past through the stone, and flipped it to bake the
                               # dark inside (black piers and stair sides when the visitor looks round, 1.2-3.4 % of the
                               # screen in 4 of 23 turned views)
FLIP_RAYS = 24                 # back sightings tested per face at most (spread over its views)
FLIP_BY_PATCH = True           # one flip decision per UV island / coplanar patch (_flip_groups)


def _flip_groups(C):
    """Island id per face of a concat() mesh: its bake UV islands when it has them ('uvb'), else project_box26's
    islands of its world positions (coplanar-ish connected patches)."""
    u = C.get("uvb")
    if u is None:
        u = project_box26(C["co"], C["vi"], C["ls"]).astype(np.float32)
    isl, _ = uv_islands(np.ascontiguousarray(u, np.float32), C["vi"], C["ls"])
    return isl


def _flip_depth(C, cen, fn, flip, seen_path, front, back, mats, path, tv, aw, occ=None):
    """facing_flip's occlusion test: of the faces `flip` marks, keep those that some view sees from behind with a
    clear line to the face's centre (the bake mesh itself as the occluder: the chunk's pieces and its split terrain;
    occ: further concat() meshes that block, e.g. the atlas mesh for the small pieces' vertex-colour mesh).
    The path's sightings decide when the path saw the face; else, or when every path sighting from behind is
    blocked and no look view saw its front, the look views'. Returns the new flip mask."""
    from mathutils.bvhtree import BVHTree
    t0 = time.time()
    co, vi, ls = C["co"], C["vi"], C["ls"]
    cand = np.nonzero(flip)[0]
    co_b, vi_b, ls_b = [np.asarray(co, np.float64)], [np.asarray(vi)], [np.asarray(ls)]
    for O in occ or ():
        n0, l0 = sum(len(x) for x in co_b), sum(len(x) for x in vi_b)
        co_b.append(np.asarray(O["co"], np.float64))
        vi_b.append(np.asarray(O["vi"]) + n0)
        ls_b.append(np.asarray(O["ls"]) + l0)
    vi_all, ls_all = np.concatenate(vi_b), np.concatenate(ls_b)
    polys = [x.tolist() for x in np.split(vi_all, ls_all[1:])]
    bvh = BVHTree.FromPolygons(np.concatenate(co_b).tolist(), polys)
    del polys
    nvw = len(mats)
    cams = np.array([np.asarray(M, float)[:3, 3] for M in mats])
    bk = np.zeros((len(cand), nvw), bool)
    c = cen[cand]
    for j, Mc in enumerate(mats):
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = c @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            inside = (z > 0.1) & (np.abs(v[:, 0] / z) <= 1.15 * tv * aw) & (np.abs(v[:, 1] / z) <= 1.15 * tv)
        bk[:, j] = inside & (((Mc[:3, 3] - c) * fn[cand]).sum(1) < 0)
    on_path = np.asarray(path, bool)
    keep = np.zeros(len(cand), bool)
    rays = 0

    def clear(ci, views):
        nonlocal rays
        if len(views) > FLIP_RAYS:
            views = views[np.linspace(0, len(views) - 1, FLIP_RAYS).astype(int)]
        cc = c[ci]
        for j in views:
            o = cams[j]
            dv = cc - o
            dist = float(np.sqrt(dv @ dv))
            if dist < 1e-3:
                continue
            rays += 1
            hit = bvh.ray_cast(o.tolist(), (dv / dist).tolist(), dist - max(0.01, 1e-3 * dist))
            if hit[0] is None:
                return True
        return False
    for ci, f in enumerate(cand):
        if seen_path[f]:
            if clear(ci, np.nonzero(bk[ci] & on_path)[0]):
                keep[ci] = True
                continue
            if front[1][f] > 0 or back[1][f] == 0:
                continue
        keep[ci] = clear(ci, np.nonzero(bk[ci] & ~on_path)[0])
    out = np.zeros(len(flip), bool)
    out[cand[keep]] = True
    log("facing_flip: depth test kept", int(keep.sum()), "of", len(cand), "flips;", rays, "rays,",
        round(time.time() - t0, 1), "s")
    return out


def facing_flip(C, skip=None, occ=None):
    """Flip faces the camera only ever sees from behind (seen back side in the frustum, never the front).
    A bake lights the side the normal points to; a camera render shades back faces too, so inside-out
    shells (open rock undersides, mixed winding) look fine in the film but bake black. The path views decide
    first; the look-around views decide only for faces the path never had in its frustum (the visitor sees
    those only when turning round), and on closed pieces a look view's front sighting blocks a path flip.
    FLIP_DEPTH: a sighting from behind counts only with a clear line to the face (_flip_depth); FLIP_BY_PATCH: one
    decision per UV island or coplanar patch (_flip_groups, majority by area).
    skip (per face): never flipped (turning objects show every side)."""
    if not CAMINFO:
        return 0
    co, vi, ls = C["co"], C["vi"], C["ls"]
    nl = len(vi)
    lt = np.diff(np.append(ls, nl))
    p = co[vi].astype(np.float64)
    cen = np.add.reduceat(p, ls) / lt[:, None]
    fn = np.zeros((len(ls), 3))
    for k in range(1, int(lt.max()) - 1):
        m = lt > k + 1
        s0 = ls[m]
        fn[m] += np.cross(p[s0 + k] - p[s0], p[s0 + k + 1] - p[s0])
    front = np.zeros((2, len(ls)), np.int32)          # row 0: path views, row 1: look-around views
    back = np.zeros((2, len(ls)), np.int32)
    tv, aw = CAMINFO["tan_v"], CAMINFO["aspect_w"]
    mats = CAMINFO["cam_mats"]
    path = CAMINFO.get("path")
    path = np.ones(len(mats), bool) if path is None else np.asarray(path, bool)
    for Mc, on_path in zip(mats, path):
        Mc = np.asarray(Mc, float)
        inv = np.linalg.inv(Mc)
        v = cen @ inv[:3, :3].T + inv[:3, 3]
        z = -v[:, 2]
        with np.errstate(all="ignore"):
            inside = (z > 0.1) & (np.abs(v[:, 0] / z) <= 1.15 * tv * aw) & (np.abs(v[:, 1] / z) <= 1.15 * tv)
        d = ((Mc[:3, 3] - cen) * fn).sum(1)
        r = 0 if on_path else 1
        front[r] += inside & (d > 0)
        back[r] += inside & (d < 0)
    seen_path = (front[0] + back[0]) > 0
    flip = np.where(seen_path, (back[0] > 0) & (front[0] == 0), (back[1] > 0) & (front[1] == 0))
    # the frustum test alone has no occlusion: the path "sees" the far side of every solid piece it drives past from
    # behind. On closed pieces (fix_normals already pointed their faces out) a look view that sees the front keeps the
    # face as it is: the visitor turning round at a hold sees exactly that side. Open shells keep path-first.
    closed = _closed_faces(C)
    saved = flip & seen_path & closed & (front[1] > 0)
    flip &= ~saved
    if saved.any():
        log("facing_flip: look views kept", int(saved.sum()), "closed-mesh faces the path saw only from behind")
    if skip is not None:
        flip &= ~np.asarray(skip, bool)
    # never flip one face of a two-sided pair (coincident faces with opposite normals): it would z-fight
    # with its correctly lit twin
    key = np.round(cen * 200.0).astype(np.int64)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    pair = cnt[inv.ravel()] >= 2
    flip &= ~pair
    if FLIP_DEPTH and flip.any():
        flip = _flip_depth(C, cen, fn, flip, seen_path, front, back, mats, path, tv, aw, occ=occ)
    if FLIP_BY_PATCH and flip.any():
        # one decision per UV island (the atlas mesh) or coplanar patch (box26 islands, the vertex-colour mesh): the
        # area-weighted majority of its faces any view saw. Decided face by face, the two triangles of one stair tread
        # landed on either side of a frustum edge and baked as a black zebra (scroll 1103, looking back)
        grp = _flip_groups(C)
        seen = (front.sum(0) + back.sum(0)) > 0
        n0 = int(flip.sum())
        flip = BR.group_vote(grp, flip, 0.5 * np.linalg.norm(fn, axis=1) * seen)
        if skip is not None:
            flip &= ~np.asarray(skip, bool)
        flip &= ~pair
        log("facing_flip: by patch", n0, "->", int(flip.sum()), "faces")
    if not flip.any():
        return 0
    perm = np.arange(nl)
    fl = np.nonzero(flip)[0]
    for f in fl:
        s0, t = ls[f], lt[f]
        perm[s0:s0 + t] = perm[s0:s0 + t][::-1]
    C["vi"] = vi[perm]
    for k in ("cn", "uv0", "uvb"):
        if k in C:
            C[k] = C[k][perm]
    flip_l = np.repeat(flip, lt)
    if "cn" in C:
        C["cn"][flip_l] *= -1.0
    for nm, (dom, d) in list(C.get("attrs", {}).items()):
        if dom == "CORNER":
            C["attrs"][nm] = (dom, d[perm])
    return int(flip.sum())


def build_bake_object(name, items, slot_fn, mats, prop_names, coll, stage=None, occ=None):
    """The joined world-space bake mesh. ``stage`` (item index -> 4x4) moves those items' vertices (and turns their
    normals) for the bake only; unstage() puts them back before the export."""
    C = concat(items, slot_fn)
    turning = EW.turning_owners()
    turn = np.array([it.owner in turning for it in items] + [False], bool)
    # the split terrain (full_ctx's big meshes, export_web chunk -3: world.range, world.roots) keeps its source
    # winding, which points out and is consistent. facing_flip has no occlusion test: path frames that look at a
    # peak "see" its far side from behind through the rock, and the terrain pieces are open (cut per chunk), so
    # a look view's front sighting cannot save them. Flipped, a third of the terrain baked the zero light inside
    # the mountain (black on atlases, dark red on vertex colours when the visitor turns round).
    split = {_FC["R"].owner[i] for i in _FC["big"]} if _FC.get("big") else set()
    keep = turn | np.array([it.owner in split for it in items] + [False], bool)
    nflip = facing_flip(C, skip=keep[C["fitem"]], occ=occ)
    log(name, "flipped", nflip, "back-facing faces; turning faces left as they are:", int(turn[C["fitem"]].sum()),
        "split terrain faces left as they are:", int((keep & ~turn)[C["fitem"]].sum()))
    if stage:
        C["co_rest"], C["cn_rest"] = C["co"].copy(), C["cn"].copy()
        for i, S in stage.items():
            S = np.asarray(S, float)
            vm = C["vitem"] == i
            lm = vm[C["vi"]]
            C["co"][vm] = C["co"][vm] @ S[:3, :3].T + S[:3, 3]
            C["cn"][lm] = C["cn"][lm] @ S[:3, :3].T
        log(name, "staged", len(stage), "items for the bake")
    me = make_mesh(name, C["co"], C["vi"], C["ls"], C["mi"])
    for m in mats:
        me.materials.append(m)
    nv, nl, npl = len(C["co"]), len(C["vi"]), len(C["ls"])
    set_attr(me, "o_co", "FLOAT_VECTOR", "POINT", C["o_co"])
    set_attr(me, "o_gen", "FLOAT_VECTOR", "POINT", C["o_gen"])
    vit = C["vitem"]
    sc = np.array([it.scale for it in items], np.float32)
    set_attr(me, "o_scale", "FLOAT_VECTOR", "POINT", sc[vit])
    rnd = np.array([it.rand for it in items], np.float32)
    set_attr(me, "o_rand", "FLOAT", "POINT", rnd[vit])
    loc = np.array([np.asarray(it.M, float)[:3, 3] for it in items], np.float32)
    set_attr(me, "o_loc", "FLOAT_VECTOR", "POINT", loc[vit])
    for p in prop_names:
        if p in ("scale", "location"):
            continue
        if p == "dimensions":
            v = np.array([it.props.get("__dims", (0.0, 0.0, 0.0)) for it in items], np.float32)
            set_attr(me, "o_dimensions", "FLOAT_VECTOR", "POINT", v[vit])
            continue
        v = np.array([it.props.get(p, 0.0) for it in items], np.float32)
        set_attr(me, "o_" + p, "FLOAT", "POINT", v[vit])
    for nm, (dom, d) in C["attrs"].items():
        typ = "FLOAT_VECTOR" if d.ndim > 1 else "FLOAT"
        set_attr(me, nm, typ, dom, d)
    set_attr(me, "w_item", "INT", "FACE", C["fitem"])
    uv0 = me.uv_layers.new(name="UVMap")
    uv0.data.foreach_set("uv", np.ascontiguousarray(C["uv0"], np.float32).ravel())
    if "uvb" in C:
        ub = me.uv_layers.new(name="bake")
        ub.data.foreach_set("uv", np.ascontiguousarray(C["uvb"], np.float32).ravel())
        me.uv_layers.active = ub
    uv0.active_render = True
    try:
        me.normals_split_custom_set(C["cn"])
    except Exception as e:
        log("WARN custom normals", e)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    log("built", name, "verts", nv, "faces", npl, "loops", nl, "materials", len(mats))
    return ob, C


# ---- lighting / render setup ------------------------------------------------------------------

# Bake quality (--quality dev|production; one table for bake_web.py and bake_trees.py). 'dev' is the fast bake used
# while the content still changes: exactly the values every bake used before the switch. 'production' is for one
# final bake once the content is final. It raises only what sets the noise; the chunk plan, LODs, texel density,
# atlas sizes, UV packing and download size are the same in both, and so is the brightness: light clamping
# (BAKE_CLAMP_INDIRECT) and the bounce counts (BAKE_BOUNCES) stay as they are, because a higher clamp or more bounces
# change how bright the bake is (and a higher clamp adds fireflies), they do not take noise away.
#   samples / vc_samples   atlas and vertex-colour samples per profile (--samples / --vc-samples override). Production
#                          768 atlas (4.8x dev: noise x0.46 before the denoiser; 1024 would cut it only 13 % more for
#                          ~20 extra minutes), 1024 vertex colours (4x: noise halved; they get no denoiser, so the most)
#   albedo / normal        samples of the denoiser's guide passes (albedo 16 -> 64, normal 4 -> 16): cleaner guides
#                          let the denoiser keep edges; a few seconds per chunk
#   tree_mesh / tree_albedo / tree_sprite   bake_trees.py: mesh-variant bakes 128 -> 512, their albedo guide 8 -> 32,
#                          card sprites 48 -> 192 (all 4x, noise halved)
#   adaptive               None leaves the scene's own setting (Cycles default: on, noise threshold 0.01, at least 64
#                          samples per texel; Cycles bakes use adaptive sampling since 3.0, so a dev texel may stop
#                          between 64 and its sample count). False turns it off: every texel gets all its samples.
#   denoise_pin            pin the denoisers to their best settings (compositor Denoise node quality High; the tree
#                          sprites' Cycles denoiser OIDN, prefilter Accurate, quality High, albedo + normal guides).
#                          These are today's defaults already; production pins them so a changed default cannot lower
#                          them. The atlases' denoiser already runs HDR + albedo + normal guides, prefilter Accurate.
BAKE_QUALITY = {
    "dev": dict(samples=dict(proto=512, full=160), vc_samples=dict(proto=512, full=256), albedo=16, normal=4,
                tree_mesh=128, tree_albedo=8, tree_sprite=48, adaptive=None, denoise_pin=False),
    "production": dict(samples=dict(proto=768, full=768), vc_samples=dict(proto=1024, full=1024), albedo=64, normal=16,
                       tree_mesh=512, tree_albedo=32, tree_sprite=192, adaptive=False, denoise_pin=True),
}
BAKE_BOUNCES = dict(max=6, diffuse=3, glossy=1, transmission=4, transparent=8)
BAKE_CLAMP_INDIRECT = 4.0      # fireflies (white speckles on red lacquer and roof tiles): a few very bright indirect paths


def bake_settings(a, sc=None):
    """The effective noise settings of this run: logged at the start, stored in every chunk's bake_meta.json and
    bake/chunks/<id>.json. Adaptive sampling is read from the scene when the quality leaves it alone (dev)."""
    Q = BAKE_QUALITY[a.quality]
    sc = sc or bpy.context.scene
    cy = getattr(sc, "cycles", None)
    if Q["adaptive"] is None:
        if cy is None:
            adaptive = "scene"
        elif cy.use_adaptive_sampling:
            adaptive = "on %g" % cy.adaptive_threshold + (" min %d" % cy.adaptive_min_samples
                                                          if cy.adaptive_min_samples else "")
        else:
            adaptive = "off"
    else:
        adaptive = "on" if Q["adaptive"] else "off"
    return dict(quality=a.quality, samples=a.samples, vc_samples=a.vc_samples, albedo_samples=Q["albedo"],
                normal_samples=Q["normal"], adaptive=adaptive, clamp_indirect=BAKE_CLAMP_INDIRECT,
                bounces=dict(BAKE_BOUNCES),
                denoise="OIDN hdr+albedo+normal prefilter Accurate quality %s"
                        % ("High" if Q["denoise_pin"] else "default"))


def log_bake_quality(a):
    s = bake_settings(a)
    b = s["bounces"]
    log("quality", s["quality"], "samples", s["samples"], "vc", s["vc_samples"], "albedo", s["albedo_samples"],
        "normal", s["normal_samples"], "adaptive", s["adaptive"], "clamp_indirect", s["clamp_indirect"],
        "bounces %d/%d/%d/%d/%d" % (b["max"], b["diffuse"], b["glossy"], b["transmission"], b["transparent"]),
        "denoise", s["denoise"])


def setup_cycles(sc, samples, quality="dev"):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    # OptiX first; some rented boxes ship the driver without libnvoptix, and then Cycles would
    # silently bake on the CPU (about 50x slower), so fall back to CUDA, and fail loudly with no GPU.
    kind = None
    for k in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = k
            prefs.get_devices()
        except (TypeError, ValueError):
            continue
        if any(d.type == k for d in prefs.devices):
            kind = k
            break
    if kind is None:
        raise RuntimeError("no OptiX or CUDA device: refusing to bake on the CPU")
    for d in prefs.devices:
        d.use = d.type == kind
    log("cycles device", kind, [d.name for d in prefs.devices if d.use])
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    B = BAKE_BOUNCES
    sc.cycles.max_bounces = B["max"]
    sc.cycles.diffuse_bounces = B["diffuse"]
    sc.cycles.glossy_bounces = B["glossy"]
    sc.cycles.transmission_bounces = B["transmission"]
    sc.cycles.transparent_max_bounces = B["transparent"]
    # fireflies (white speckles on red lacquer and roof tiles) come from a few very bright indirect paths
    sc.cycles.sample_clamp_indirect = BAKE_CLAMP_INDIRECT
    Q = BAKE_QUALITY[quality]
    if Q["adaptive"] is not None:              # dev leaves the scene's own setting
        sc.cycles.use_adaptive_sampling = Q["adaptive"]
    if Q["denoise_pin"]:
        # only renders that turn use_denoising on use these (the tree sprites); bakes denoise in post_scene
        for k, v in (("denoiser", "OPENIMAGEDENOISE"), ("denoising_prefilter", "ACCURATE"),
                     ("denoising_quality", "HIGH"), ("denoising_input_passes", "RGB_ALBEDO_NORMAL")):
            try:
                setattr(sc.cycles, k, v)
            except Exception as e:
                log("WARN could not pin", k, v, e)


def bake_lighting(sc):
    """Sky fill x1.3 warmed + a soft warm fill sun from the sun's side (see BAKE_LIGHT)."""
    L = BAKE_LIGHT
    nt = sc.world.node_tree
    bg = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBackground")
    bg.inputs["Strength"].default_value = L["world_strength"]
    if bg.inputs["Color"].is_linked:
        src = bg.inputs["Color"].links[0].from_socket
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = L["world_tint"]
        nt.links.new(src, mul.inputs[0])
        nt.links.new(mul.outputs[0], bg.inputs["Color"])
    sun = bpy.data.objects["look.sun"]
    sdir = sun.matrix_world.to_3x3().col[2].normalized()
    az = math.atan2(sdir.y, sdir.x)
    e = math.radians(L["fill_elev_deg"])
    v = Vector((math.cos(az) * math.cos(e), math.sin(az) * math.cos(e), math.sin(e)))
    fd = bpy.data.lights.new("bake.fill", "SUN")
    fd.energy = L["fill_energy"]
    fd.angle = math.radians(L["fill_angle_deg"])
    fd.color = L["fill_color"]
    fo = bpy.data.objects.new("bake.fill", fd)
    sc.collection.objects.link(fo)
    fo.rotation_mode = "QUATERNION"
    fo.rotation_quaternion = v.to_track_quat("Z", "Y")
    return fo


def hide_for_bake(sc):
    """Flyer, haze/cloud volumes, additive FX: not part of the baked light."""
    n = EW.hide_flyer(sc)
    cache = {}

    def info(m):
        if m.name not in cache:
            cache[m.name] = EW.material_info(m)
        return cache[m.name]
    for ob in sc.objects:
        nm = ob.name
        infos = [info(s.material) for s in ob.material_slots if s.material]
        vol = bool(infos) and all(i["volume_only"] for i in infos)
        fx = bool(infos) and all(EW._is_fx(i) for i in infos)
        if vol or fx or nm.startswith(("world.haze", "world.cloud_fog", "world.cloud.", "world.moon_halo",
                                        "world.cirrus")):
            if not ob.hide_render:
                ob.hide_render = True
                n += 1
    return n


# ---- bake ---------------------------------------------------------------------------------------

def cmd_bake(a):
    sc = bpy.context.scene
    T = {}
    t0 = time.time()
    R = EW.gather(sc)
    S, cache_frames = EW.load_cache(R)
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: EW.material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    ex = EW.export_mask(R, minfo)
    px = S["pxmax"].astype(float)
    veg = np.array([is_veg_rec(R, i) for i in range(len(R))], bool)
    falls = np.array([is_fall(R, i) for i in range(len(R))], bool)
    sel = S["any"] & (px >= EW.MIN_PX) & ~ex & ~veg & ~falls
    diag = np.linalg.norm(R.hi - R.lo, axis=1)
    big = sel & ~R.inst & (R.tris >= EW.SPLIT_MIN_TRIS) & (diag >= EW.SPLIT_MIN_DIAG)
    dmin = S["dmin"]
    at_idx = np.nonzero(sel & ~big & (dmin <= ATLAS_MAX_D))[0]
    vc_idx = np.nonzero(sel & ~big & (dmin > ATLAS_MAX_D) & (px >= VC_MIN_PX))[0]
    big_idx = np.nonzero(big)[0]
    log("selected atlas", len(at_idx), int(R.tris[at_idx].sum()), "vc", len(vc_idx), int(R.tris[vc_idx].sum()),
        "big", [R.name[i] for i in big_idx], "veg skipped", int((S["any"] & veg).sum()),
        "falls skipped", int((S["any"] & falls).sum()))
    cam = bpy.data.objects[EW.CAMERA]
    views = EW.load_views(cam)                    # the audit's views: path frames, then any look-around views
    frames = [int(f) for f in views.frames]
    cam_mats = views.mats
    cam_pos = views.pos
    th, tv = EW.camera_tan(cam)
    aspect_w = EW.DEPTH_RES[0] / EW.DEPTH_RES[1]
    CAMINFO.update(cam_mats=cam_mats, tan_v=tv, aspect_w=aspect_w, path=views.path)
    bases = capture([R.tkey[i] for i in np.concatenate([at_idx, vc_idx, big_idx])])
    dec = Decimator(sc)
    T["select_capture"] = round(time.time() - t0, 1)

    members = EW.hotspot_members()
    items_at, items_vc, occluders = [], [], []

    def orig_obj(i):
        nm = R.tkey[i][1:] if R.tkey[i].startswith("#") else R.tkey[i]
        return bpy.data.objects.get(nm)

    def item_for(i, me, kind, M=None, d=None, name=None, zone=None):
        ob = orig_obj(i)
        scale, props = mat_slots_and_props(ob)
        if ob is not None:
            props["__dims"] = tuple(ob.dimensions)
        key = R.key[i] if name is None else name
        if M is None:
            M = R.mw[i]
            lift = PATH_LIFT.get(R.owner[i]) or PATH_LIFT.get(R.name[i])
            if lift:
                # path strips overlap at their junctions: coplanar faces bake each other's contact shadow and
                # z-fight in the browser; a centimetre or two apart fixes both
                M = np.array(M, float)
                M[2, 3] += lift
        return Item(mesh=me, M=M, kind=kind, zone=zone, hot=members.get(R.owner[i], ""),
                    top=R.top[i], owner=R.owner[i], name=name or R.name[i], key=key,
                    dmin=float(dmin[i] if d is None else d), scale=scale, props=props,
                    rand=(zlib.crc32(key.encode()) & 0xffffff) / float(0xffffff), atlas=None, uv=None)

    # big meshes (terrain): decimate whole, then split faces by distance to the path
    used_at = used_vc = 0
    for i in big_idx:
        base = bases.get(R.tkey[i])
        if base is None:
            continue
        me = decimate_weighted(dec, R.tkey[i] + ".big", base, R.mw[i], cam_mats, tv, aspect_w,
                               BIG_RATIO if dmin[i] <= 150 else 0.1, dscale=views.dscale)
        fd = face_dmin(me, R.mw[i], cam_mats, tv, aspect_w, views.dscale)
        seen = np.isfinite(fd)
        z = zone_of_point(0.5 * (R.lo[i] + R.hi[i]), cam_pos, frames)
        bins = list(BIG_BINS) + [np.inf]
        for b0, b1 in zip(bins[:-1], bins[1:]):
            m = seen & (fd >= b0) & (fd < b1)
            if not m.any():
                continue
            sub = submesh(me, m, "%s.d%d" % (R.name[i], int(b0)))
            kind = "atlas" if b1 <= ATLAS_MAX_D else "vc"
            it = item_for(i, sub, kind, d=max(b0, 8.0), name="%s.d%d" % (R.name[i], int(b0)), zone=z)
            # zone per piece from its own faces
            c = np.empty(len(sub.polygons) * 3)
            sub.polygons.foreach_get("center", c)
            Mi = np.asarray(R.mw[i], float)
            cc = c.reshape(-1, 3).mean(0) @ Mi[:3, :3].T + Mi[:3, 3]
            it.zone = zone_of_point(cc, cam_pos, frames)
            (items_at if kind == "atlas" else items_vc).append(it)
            t = EW._mesh_tris(sub)[0]
            if kind == "atlas":
                used_at += t
            else:
                used_vc += t
            log("big", R.name[i], "bin", b0, b1, "faces", int(m.sum()), "tris", t, kind, it.zone)
        if (~seen).any():
            occ = submesh(me, ~seen, R.name[i] + ".occluder")
            occluders.append((occ, R.mw[i], R.name[i]))
    # LODs for the rest
    picker = EW.MeshPicker(bases, dec)
    w_at = EW.lod_weights(R, at_idx, members)
    fl = EW.lod_floor(R, at_idx, S, EW.NEAR_MAX)
    # never decimate glyphs (collapse eats their strokes) or banners (their gold trim is separate faces with
    # its own material; collapse merges triangles across that border and the trim turns into wedges)
    protect = np.array([no_decimate(R.name[i], R.owner[i], dmin[i]) for i in at_idx], bool)
    fl = np.maximum(fl, protect.astype(float))
    log("protected from decimation:", int(protect.sum()), "pieces,", int(R.tris[at_idx][protect].sum()), "tris")
    # props near the two hold cameras (lanterns, lions, censer, mirror finials, balusters, lattice panels): the
    # reader studies these while the camera stands still, and collapse decimation crumples them
    hold_mats = EW.sample_matrices(cam, list(HOLD_FRAMES))
    near_h = near_holds(R, at_idx, hold_mats)
    close_h = near_holds(R, at_idx, hold_mats, area_near=(HOLD_NEAR,) * len(HOLD_FRAMES))
    tri_at = R.tris[at_idx]
    # within HOLD_NEAR: full detail up to HOLD_FULL_TRIS, else >= 50 %; farther pieces of the hold's own area
    # (the mirror terrace 40-95 m off): small props (finials, censer, balusters) full, big ones >= 25 %
    fl_hold = np.where(close_h, np.where(tri_at <= HOLD_FULL_TRIS, 1.0, HOLD_MIN_RATIO),
                       np.where(near_h, np.where(tri_at <= 8000, 1.0, 0.25), 0.0))
    lattice = np.array([dmin[i] <= 120.0 and ("lattice" in R.name[i] or "lattice" in R.owner[i]) for i in at_idx],
                       bool)
    fl_hold = np.maximum(fl_hold, np.where(lattice, HOLD_MIN_RATIO, 0.0))
    # small props a little farther off (lanterns, lions, censers, finials, balusters): full detail
    props_word = np.array([any(w in R.name[i] or w in R.owner[i] for w in HOLD_PROP_WORDS) for i in at_idx], bool)
    props_h = near_holds(R, at_idx, hold_mats, near=HOLD_PROP_NEAR, area_near=(HOLD_PROP_NEAR, HOLD_AREA_NEAR[1]))
    props_h &= props_word & (tri_at <= HOLD_FULL_TRIS)
    fl_hold = np.maximum(fl_hold, np.where(props_h, 1.0, 0.0))
    near_h = near_h | props_h
    sl_at = slender_mask(R, at_idx)
    fl = np.maximum(np.maximum(fl, fl_hold), np.where(sl_at, SLENDER_FLOOR, 0.0))
    log("near the holds:", int(near_h.sum()), "pieces,", int(R.tris[at_idx][near_h].sum()), "tris; slender:",
        int(sl_at.sum()), [R.name[i] for i in at_idx[sl_at]][:20])
    k_at, lv_at, tot_at = EW.fit_budget(R, px, at_idx, a.atlas_tris - used_at, w_at, picker, "atlas", floor=fl)
    w_vc = EW.lod_weights(R, vc_idx, members)
    sl_vc = slender_mask(R, vc_idx)
    log("slender far pieces:", int(sl_vc.sum()), [R.name[i] for i in vc_idx[sl_vc]][:20])
    k_vc, lv_vc, tot_vc = EW.fit_budget(R, px, vc_idx, a.vc_tris - used_vc, w_vc, picker, "vc",
                                        floor=np.where(sl_vc, SLENDER_FLOOR, 0.0))
    plan = []
    for j, (i, li) in enumerate(zip(at_idx, lv_at)):
        if near_h[j] or sl_at[j]:
            plan.append(dict(name=R.name[i], owner=R.owner[i], tris=int(R.tris[i]), ratio=float(EW.LEVELS[li]),
                             floor=round(float(fl[j]), 2), dmin=round(float(dmin[i]), 1), hold=bool(near_h[j])))
    plan.sort(key=lambda d: -d["tris"] * d["ratio"])
    dump(os.path.join(BAKE_OUT, "lod_plan.json"), dict(near_hold=plan, atlas_tris=int(tot_at + used_at),
                                                        vc_tris=int(tot_vc + used_vc)))
    zones_at = zone_of_records(R, at_idx, cam_pos, frames)
    zones_vc = zone_of_records(R, vc_idx, cam_pos, frames)
    for i, li, z in zip(at_idx, lv_at, zones_at):
        me = picker.get(R.tkey[i], float(EW.LEVELS[li]))
        if me is not None and len(me.polygons):
            items_at.append(item_for(i, me, "atlas", zone=str(z)))
    for i, li, z in zip(vc_idx, lv_vc, zones_vc):
        me = picker.get(R.tkey[i], float(EW.LEVELS[li]))
        if me is not None and len(me.polygons):
            items_vc.append(item_for(i, me, "vc", zone=str(z)))
    T["lod"] = round(time.time() - t0 - T["select_capture"], 1)
    log("items atlas", len(items_at), "vc", len(items_vc), "occluders", len(occluders),
        "tris atlas", tot_at + used_at, "vc", tot_vc + used_vc, "decimated", dec.n, round(dec.t, 1), "s")

    # drop sliver faces (packing), then texel density and atlas assignment
    nb = 0
    for lst in (items_at, items_vc):
        keep = []
        for it in lst:
            m2 = clean_mesh(it.mesh)
            if m2 is None:
                continue
            if m2 is not it.mesh:
                nb += 1
            it.mesh = m2
            keep.append(it)
        lst[:] = keep
    log("cleaned sliver faces in", nb, "pieces; flipped inward normals in", len(_FLIPPED), "meshes",
        json.dumps(_FLIPPED[:30]))
    for it in items_at:
        A = ma(it.mesh)
        L = np.asarray(it.M, float)[:3, :3]
        s2 = abs(np.linalg.det(L)) ** (2.0 / 3.0)
        it.rho = rho_of(it.dmin) * detail_boost(it.name)
        it.demand = A.area * s2 * it.rho ** 2
    items_at = split_heavy(items_at, cam_mats, tv, aspect_w, views.dscale)
    cap = ATLAS_PX * ATLAS_PX * ATLAS_FILL
    total = sum(it.demand for it in items_at)
    top = sorted(items_at, key=lambda it: -it.demand)[:25]
    log("top demand", json.dumps([(it.name, int(it.demand), round(it.rho, 1), round(it.dmin, 1)) for it in top]))
    limit = a.max_atlases * cap
    gscale = 1.0
    if total > limit:
        gscale = math.sqrt(limit / total)
        for it in items_at:
            it.rho = max(it.rho * gscale, RHO_MIN)
            A = ma(it.mesh)
            L = np.asarray(it.M, float)[:3, :3]
            it.demand = A.area * abs(np.linalg.det(L)) ** (2.0 / 3.0) * it.rho ** 2
    log("texel demand %.1fM (limit %.1fM), density scale %.3f" % (total / 1e6, limit / 1e6, gscale))
    zorder = {"gate": 0, "mirror": 1}
    items_at.sort(key=lambda it: (zorder.get(it.zone, 2), it.hot == "", it.top, it.owner, it.name))
    groups = []
    cur = None
    for it in items_at:
        if cur is None or cur["zone"] != it.zone or (cur["demand"] + it.demand > cap and cur["demand"] > 0):
            cur = dict(zone=it.zone, demand=0.0, items=[])
            groups.append(cur)
        cur["items"].append(it)
        cur["demand"] += it.demand
    atlases = []
    for k, g in enumerate(groups):
        size = ATLAS_PX
        while size > 1024 and g["demand"] <= (size // 2) ** 2 * ATLAS_FILL:
            size //= 2
        name = "%s_A%d" % (g["zone"], k)
        for it in g["items"]:
            it.atlas = k
        atlases.append(dict(name=name, zone=g["zone"], size=size, demand=round(g["demand"]), items=len(g["items"]),
                            tris=int(sum(ma(it.mesh).np for it in g["items"]))))
    log("atlases", json.dumps(atlases))
    t1 = time.time()
    for k, g in enumerate(groups):
        atlases[k]["uv_area"] = round(unwrap_group(g["items"], atlases[k]["name"], atlases[k]["size"]), 3)
    T["unwrap"] = round(time.time() - t1, 1)
    if a.plan_only:
        dump(os.path.join(BAKE_OUT, "plan_atlases.json"), dict(atlases=atlases, times=T, gscale=gscale))
        log("plan only: stopping before the bake", json.dumps(atlases))
        return

    # materials: rewritten copies; atlas copies carry the bake target image node
    used_mats = set()
    for it in items_at + items_vc:
        used_mats.update(ma(it.mesh).mats)
    used_mats.discard("")
    src_mats = {m: bpy.data.materials.get(m) for m in used_mats}
    prop_names = object_attr_names(src_mats.values())
    log("materials", len(used_mats), "object attrs", sorted(prop_names))
    fallback = bpy.data.materials.new("bake.none")
    fallback.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    rw = {}
    for m, src in src_mats.items():
        rw[m] = rewrite_material(src, m + "@bake") if src is not None else fallback
    rw[""] = fallback
    images, albedo = [], []
    for at in atlases:
        images.append(bpy.data.images.new(at["name"], at["size"], at["size"], alpha=False, float_buffer=True))
        albedo.append(bpy.data.images.new(at["name"] + "_albedo", at["size"], at["size"], alpha=False,
                                          float_buffer=True))
    slot_list, slot_idx, img_nodes = [], {}, []

    def slot_at(it, mname):
        key = (it.atlas, mname)
        if key not in slot_idx:
            m = rw.get(mname, fallback).copy()
            m.name = "%s@%s" % (mname or "none", atlases[it.atlas]["name"])
            nt = m.node_tree
            if nt is None:
                _use_nodes(m)
                nt = m.node_tree
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = images[it.atlas]
            nt.nodes.active = tn
            img_nodes.append((tn, it.atlas))
            slot_idx[key] = len(slot_list)
            slot_list.append(m)
        return slot_idx[key]

    vc_slots, vc_idx_map = [], {}

    def slot_vc(it, mname):
        if mname not in vc_idx_map:
            vc_idx_map[mname] = len(vc_slots)
            vc_slots.append(rw.get(mname, fallback))
        return vc_idx_map[mname]

    coll = bpy.data.collections.new("bake.objects")
    sc.collection.children.link(coll)
    t1 = time.time()
    ob_at, C_at = build_bake_object("bake.atlas", items_at, slot_at, [], prop_names, coll)
    for m in slot_list:
        ob_at.data.materials.append(m)
    ob_vc, C_vc = build_bake_object("bake.vc", items_vc, slot_vc, [], prop_names, coll)
    for m in vc_slots:
        ob_vc.data.materials.append(m)
    for occ, M, nm in occluders:
        o = bpy.data.objects.new("bake.occluder." + nm, occ)
        o.matrix_world = Matrix(np.asarray(M, float).tolist())
        coll.objects.link(o)
    T["build"] = round(time.time() - t1, 1)

    # per-face glow flag and atlas index (for the post step)
    for ob, C, items in ((ob_at, C_at, items_at), (ob_vc, C_vc, items_vc)):
        mats = [m.name for m in ob.data.materials]
        emis = np.array([minfo.get(m.split("@")[0], {}).get("emission", False) for m in mats] + [False], bool)
        set_attr(ob.data, "w_glow", "INT", "FACE", emis[C["mi"]].astype(np.int32))
        if ob is ob_at:
            fa = np.array([it.atlas for it in items], np.int32)[C["fitem"]]
            set_attr(ob.data, "w_atlas", "INT", "FACE", fa)

    # hide what the bake objects replace, and the volumes/FX/flyer
    owners = {it.owner for it in items_at + items_vc}
    nh = 0
    for o in owners:
        ob = bpy.data.objects.get(o)
        if ob is not None and not ob.hide_render:
            ob.hide_render = True
            nh += 1
    for i in big_idx:
        ob = bpy.data.objects.get(R.name[i])
        if ob is not None:
            ob.hide_render = True
    nfx = hide_for_bake(sc)
    log("hid", nh, "replaced owners,", nfx, "flyer/volume/fx objects")
    bake_lighting(sc)

    # bake: COMBINED into the atlases, DIFFUSE COLOR into the albedo guides, COMBINED into vertex colours
    os.makedirs(CACHE_DIR, exist_ok=True)
    setup_cycles(sc, a.samples, a.quality)
    deselect_all()
    ob_at.select_set(True)
    bpy.context.view_layer.objects.active = ob_at
    t1 = time.time()
    bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT"}, uv_layer="bake",
                        margin=BAKE_MARGIN, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
    T["bake_atlas"] = round(time.time() - t1, 1)
    log("baked atlases in", T["bake_atlas"], "s")
    for tn, k in img_nodes:
        tn.image = albedo[k]
    sc.cycles.samples = BAKE_QUALITY[a.quality]["albedo"]
    t1 = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, uv_layer="bake", margin=BAKE_MARGIN,
                        margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
    T["bake_albedo"] = round(time.time() - t1, 1)
    for tn, k in img_nodes:
        tn.image = images[k]
    for im in images + albedo:
        im.filepath_raw = os.path.join(CACHE_DIR, im.name + ".exr")
        im.file_format = "OPEN_EXR"
        im.save()
    # previews of the raw bake (exposure-free, simple sRGB clamp) for a quick look
    os.makedirs(os.path.join(BAKE_OUT, "raw_preview"), exist_ok=True)
    for im in images:
        preview(im, os.path.join(BAKE_OUT, "raw_preview", im.name + ".png"))
    me_vc = ob_vc.data
    ca = me_vc.color_attributes.new("bake_col", "FLOAT_COLOR", "CORNER")
    me_vc.color_attributes.active_color = ca
    try:
        me_vc.color_attributes.render_color_index = me_vc.color_attributes.active_color_index
    except Exception:
        pass
    ob_at.select_set(False)
    ob_vc.select_set(True)
    bpy.context.view_layer.objects.active = ob_vc
    sc.cycles.samples = a.vc_samples
    t1 = time.time()
    bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT"},
                        target="VERTEX_COLORS")
    T["bake_vc"] = round(time.time() - t1, 1)
    log("baked vertex colours in", T["bake_vc"], "s")

    # save what the post step needs
    items_json = []
    for kind, items, C in (("atlas", items_at, C_at), ("vc", items_vc, C_vc)):
        for k, it in enumerate(items):
            items_json.append(dict(kind=kind, index=k, zone=it.zone, hot=it.hot, top=it.top, owner=it.owner,
                                   name=it.name, atlas=it.atlas, dmin=round(it.dmin, 1),
                                   rho=round(it.rho, 2) if it.rho else None))
    hot_labels = {h[0]: h[1] for h in EW.all_hotspots()}
    meta = dict(atlases=atlases, hotspots=hot_labels, samples=a.samples, vc_samples=a.vc_samples,
                quality=a.quality, bake_settings=bake_settings(a, sc), light=BAKE_LIGHT, times=T, gscale=gscale,
                tris=dict(atlas=int(sum(ma(it.mesh).np for it in items_at)),
                          vc=int(sum(ma(it.mesh).np for it in items_vc))),
                polys_atlas=len(C_at["ls"]), polys_vc=len(C_vc["ls"]))
    dump(os.path.join(CACHE_DIR, "items.json"), items_json, indent=None)
    dump(os.path.join(CACHE_DIR, "bake_meta.json"), meta)
    p = os.path.join(CACHE_DIR, "export.blend")
    bpy.data.libraries.write(p, {ob_at, ob_vc}, fake_user=True)
    T["total"] = round(time.time() - t0, 1)
    meta["times"] = T
    dump(os.path.join(BAKE_OUT, "bake_stats.json"), meta)
    log("BAKE done", json.dumps(T))


def preview(im, path, size=1024):
    """Downscaled sRGB-clamped PNG of a float image (raw radiance, no view transform)."""
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    f = max(1, w // size)
    small = px[::f, ::f, :3]
    c = np.clip(small, 0, 1)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    out = bpy.data.images.new("pv_" + im.name, s.shape[1], s.shape[0], alpha=False)
    rgba = np.concatenate([s, np.ones(s.shape[:2] + (1,), np.float32)], 2)
    out.pixels.foreach_set(rgba.ravel())
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)


# ---- post: denoise, grade, export -------------------------------------------------------------

def post_scene(size, exposure, sat, denoise=True, quality="dev"):
    from sect.lib import look as LK
    LOOK = LK.LOOK
    post = bpy.data.scenes.get("bakepost") or bpy.data.scenes.new("bakepost")
    post.render.engine = "CYCLES"
    post.cycles.samples = 1
    post.cycles.device = "CPU"
    post.render.resolution_x, post.render.resolution_y = size
    post.render.resolution_percentage = 100
    post.view_settings.view_transform = LOOK["view_transform"]
    post.view_settings.look = LOOK["look"]
    post.view_settings.exposure = exposure
    post.view_settings.gamma = 1.0
    post.display_settings.display_device = "sRGB"
    ims = post.render.image_settings
    ims.file_format = "PNG"
    ims.color_mode = "RGB"
    ims.color_depth = "8"
    if post.camera is None:
        cam = bpy.data.objects.new("post.cam", bpy.data.cameras.new("post.cam"))
        post.collection.objects.link(cam)
        post.camera = cam
    ng = bpy.data.node_groups.get("bakepost") or bpy.data.node_groups.new("bakepost", "CompositorNodeTree")
    ng.nodes.clear()
    for item in list(ng.interface.items_tree):
        ng.interface.remove(item)
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, Lk = ng.nodes, ng.links
    n_im = N.new("CompositorNodeImage")
    n_al = N.new("CompositorNodeImage")
    src = n_im.outputs["Image"]
    if denoise:
        dn = N.new("CompositorNodeDenoise")
        Lk.new(n_im.outputs["Image"], dn.inputs["Image"])
        Lk.new(n_al.outputs["Image"], dn.inputs["Albedo"])
        dn.inputs["HDR"].default_value = True
        try:
            dn.inputs["Prefilter"].default_value = "Accurate"
        except Exception:
            pass
        if BAKE_QUALITY[quality]["denoise_pin"]:
            # High is already the default for a final render (the node follows the scene's final quality); pin it
            try:
                post.render.compositor_denoise_final_quality = "HIGH"
            except Exception as e:
                log("WARN could not pin the scene's denoise quality:", e)
            q = dn.inputs.get("Quality")
            if q is not None:
                try:
                    q.default_value = "High"
                except Exception as e:
                    log("WARN could not pin the Denoise node's quality:", e)
        src = dn.outputs["Image"]
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
    Lk.new(src, grade.inputs["Image"])
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
    post.compositing_node_group = ng
    post.render.use_compositing = True
    return post, n_im, n_al


def run_post(post, path):
    post.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=post.name)
    return path


def load_png_linear_bytes(path):
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)


def submesh_arrays(me, fmask, keep_uv=None, keep_col=None):
    """Arrays of the faces in fmask (vertices re-indexed)."""
    nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(nv, 3)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    ls = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npl, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    fsel = np.nonzero(fmask)[0]
    lsel = np.concatenate([np.arange(s, s + t) for s, t in zip(ls[fsel], lt[fsel])]) if len(fsel) else np.zeros(0, int)
    vsel, inv = np.unique(vi[lsel], return_inverse=True)
    new_ls = np.concatenate([[0], np.cumsum(lt[fsel])[:-1]]).astype(np.int32) if len(fsel) else np.zeros(0, np.int32)
    return dict(co=co[vsel], vi=inv.astype(np.int32), ls=new_ls, lsel=lsel, fsel=fsel)


def cmd_post(a):
    from sect.lib import look as LK
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    with open(os.path.join(CACHE_DIR, "bake_meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(CACHE_DIR, "items.json"), encoding="utf-8") as fh:
        items = json.load(fh)
    with bpy.data.libraries.load(os.path.join(CACHE_DIR, "export.blend")) as (src, dst):
        dst.objects = ["bake.atlas", "bake.vc"]
    ob_at, ob_vc = dst.objects
    atlases = meta["atlases"]
    tex_dir = os.path.join(BAKE_OUT, "tex")
    pv_dir = os.path.join(BAKE_OUT, "preview")
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(pv_dir, exist_ok=True)
    T = {}
    t0 = time.time()
    # 1. atlases
    pngs = []
    for at in atlases:
        if a.skip_atlas:
            pngs.append(os.path.join(tex_dir, at["name"] + ".png"))
            continue
        post, n_im, n_al = post_scene((at["size"], at["size"]), a.exposure, a.sat, denoise=True, quality=a.quality)
        n_im.image = bpy.data.images.load(os.path.join(CACHE_DIR, at["name"] + ".exr"), check_existing=False)
        n_al.image = bpy.data.images.load(os.path.join(CACHE_DIR, at["name"] + "_albedo.exr"), check_existing=False)
        t1 = time.time()
        p = run_post(post, os.path.join(tex_dir, at["name"] + ".png"))
        pngs.append(p)
        im = bpy.data.images.load(p, check_existing=False)
        sm = im.copy()
        sm.scale(1024, 1024)
        sm.filepath_raw = os.path.join(pv_dir, at["name"] + ".png")
        sm.file_format = "PNG"
        sm.save()
        log("post atlas", at["name"], at["size"], round(time.time() - t1, 1), "s")
    T["atlases"] = round(time.time() - t0, 1)
    # 2. vertex colours through the same grade (no denoise)
    me_vc = ob_vc.data
    nl = len(me_vc.loops)
    if nl:
        col = get_attr(me_vc, "bake_col", nl, 4)
        if VC_WELD:
            col, _ = _weld_vc(me_vc, col)
        W = 2048
        H = int(math.ceil(nl / W))
        buf = np.zeros((H * W, 4), np.float32)
        buf[:nl] = col
        buf[:, 3] = 1.0
        vim = bpy.data.images.new("vc_lin", W, H, alpha=False, float_buffer=True)
        vim.pixels.foreach_set(buf.ravel())
        vim.filepath_raw = os.path.join(CACHE_DIR, "vc_lin.exr")
        vim.file_format = "OPEN_EXR"
        vim.save()
        post, n_im, n_al = post_scene((W, H), a.exposure, a.sat, denoise=False)
        n_im.image = bpy.data.images.load(vim.filepath_raw, check_existing=False)
        p = run_post(post, os.path.join(CACHE_DIR, "vc_graded.png"))
        g = load_png_linear_bytes(p).reshape(-1, 4)[:nl]     # same row order as the buffer written
        cattr = me_vc.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        g[:, 3] = 1.0
        cattr.data.foreach_set("color_srgb", np.ascontiguousarray(g, np.float32).ravel())
        log("graded", nl, "vertex colours; mean sRGB", g[:, :3].mean(0).round(3).tolist())
    T["vc"] = round(time.time() - t0 - T["atlases"], 1)

    # 3. export objects: split the joined meshes by (zone, atlas, hotspot, glow)
    sc = bpy.context.scene
    coll = bpy.data.collections.new("web.baked")
    sc.collection.children.link(coll)
    mats = {}
    glow_strength = {}

    def baked_mat(at_idx, glow):
        """glow: None, or a GLOW_CLASSES key (one material per class, its strength and tint in the extras)."""
        key = (at_idx, glow)
        if key in mats:
            return mats[key]
        nm = "baked.%s%s" % (atlases[at_idx]["name"], (".glow." + glow) if glow else "")
        m = bpy.data.materials.new(nm)
        _use_nodes(m)
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        tn = nt.nodes.new("ShaderNodeTexImage")
        img = bpy.data.images.get(atlases[at_idx]["name"] + ".png") or bpy.data.images.load(pngs[at_idx])
        img.colorspace_settings.name = "sRGB"
        tn.image = img
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "bake"
        nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
        nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 1.0
        b.inputs["Metallic"].default_value = 0.0
        if glow:
            s, tint = glow_strength[glow]
            m["glow"] = s
            if tint:
                m["glowTint"] = tint
        m["baked"] = True
        mats[key] = m
        return m

    def vc_mat(glow):
        key = ("vc", glow)
        if key in mats:
            return mats[key]
        m = bpy.data.materials.new("baked.vc" + (".glow" if glow else ""))
        _use_nodes(m)
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 1.0
        if glow:
            m["glow"] = 2.0
        m["baked"] = True
        mats[key] = m
        return m

    def emit(name, me_src, fmask, mat_of_face, uv=True, col=False, extras=None):
        A = submesh_arrays(me_src, fmask)
        if not len(A["fsel"]):
            return None
        ms = sorted(set(mat_of_face[A["fsel"]].tolist()), key=lambda m: m.name)
        mi = np.array([ms.index(m) for m in mat_of_face[A["fsel"]]], np.int32)
        me = make_mesh(name, A["co"], A["vi"], A["ls"], mi)
        for m in ms:
            me.materials.append(m)
        if uv:
            src_uv = np.empty(len(me_src.loops) * 2, np.float32)
            me_src.uv_layers["bake"].data.foreach_get("uv", src_uv)
            lay = me.uv_layers.new(name="bake")
            lay.data.foreach_set("uv", src_uv.reshape(-1, 2)[A["lsel"]].ravel())
        if col:
            c = np.empty(len(me_src.loops) * 4, np.float32)
            me_src.color_attributes["Col"].data.foreach_get("color_srgb", c)
            ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
            ca.data.foreach_set("color_srgb", c.reshape(-1, 4)[A["lsel"]].ravel())
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        for k, v in (extras or {}).items():
            ob[k] = v
        return ob

    at_items = [it for it in items if it["kind"] == "atlas"]
    vc_items = [it for it in items if it["kind"] == "vc"]
    out_objs = collections.defaultdict(list)
    stats = collections.Counter()
    me = ob_at.data
    npl = len(me.polygons)
    if npl:
        fitem = get_attr(me, "w_item", npl, 1)
        fglow = get_attr(me, "w_glow", npl, 1).astype(bool)
        fatl = get_attr(me, "w_atlas", npl, 1)
        zone = np.array([it["zone"] for it in at_items])[fitem]
        hot = np.array([it["hot"] for it in at_items])[fitem]
        # glow class per face from its source material (slot names are '<source>@<atlas>')
        fmi = np.empty(npl, np.int32)
        me.polygons.foreach_get("material_index", fmi)
        slot_cls = []
        for sm in me.materials:
            src = sm.name.split("@")[0] if sm is not None else ""
            s, tint, ck = glow_class(src)
            glow_strength[ck] = (s, tint)
            slot_cls.append(ck)
        fcls = np.array(slot_cls + ["other"], object)[np.clip(fmi, 0, len(slot_cls))]
        fcls = np.where(fglow, fcls, "")
        stats["glow_classes"] = dict(collections.Counter(fcls[fglow].tolist()))
        mat_of_face = np.empty(npl, object)
        for k in range(len(atlases)):
            for g in sorted(set(fcls.tolist())):
                msk = (fatl == k) & (fcls == g)
                if msk.any():
                    mat_of_face[msk] = baked_mat(k, g or None)
        for hid in sorted(set(hot.tolist()) - {""}):
            m = hot == hid
            z = collections.Counter(zone[m].tolist()).most_common(1)[0][0]
            ob = emit("hotspot." + hid, me, m, mat_of_face,
                      extras=dict(hotspot=hid, label=meta["hotspots"].get(hid, hid)))
            if ob is not None:
                out_objs[z].append(ob)
                stats["hotspot_nodes"] += 1
        # plain faces in spatial chunks (one material each, so they cost a few draw calls but let the browser
        # skip what is off screen); glow faces per class
        fc = np.empty(npl * 3, np.float32)
        me.polygons.foreach_get("center", fc)
        fc = fc.reshape(-1, 3)
        for k, at in enumerate(atlases):
            short = at["name"].split("_")[-1]
            f0 = np.nonzero((hot == "") & (fatl == k) & (fcls == ""))[0]
            for ci, fs in enumerate(kd_chunks(fc, f0, CHUNK_FACES)):
                m = np.zeros(npl, bool)
                m[fs] = True
                ob = emit("%s.baked.%s.c%d" % (at["zone"], short, ci), me, m, mat_of_face, extras=dict(chunk=1))
                if ob is not None:
                    out_objs[at["zone"]].append(ob)
                    stats["chunks"] += 1
            for g in sorted(set(fcls.tolist()) - {""}):
                m = (hot == "") & (fatl == k) & (fcls == g)
                if not m.any():
                    continue
                s, tint = glow_strength[g]
                ob = emit("%s.baked.%s.glow.%s" % (at["zone"], short, g), me, m, mat_of_face,
                          extras=dict(glow=s, **({"glowTint": tint} if tint else {})))
                if ob is not None:
                    out_objs[at["zone"]].append(ob)
    me = ob_vc.data
    npl = len(me.polygons)
    if npl:
        fitem = get_attr(me, "w_item", npl, 1)
        fglow = get_attr(me, "w_glow", npl, 1).astype(bool)
        top = np.array([it["top"] for it in vc_items])[fitem]
        mat_of_face = np.empty(npl, object)
        mat_of_face[~fglow] = vc_mat(False)
        if fglow.any():
            mat_of_face[fglow] = vc_mat(True)
        fc = np.empty(npl * 3, np.float32)
        me.polygons.foreach_get("center", fc)
        fc = fc.reshape(-1, 3)
        for ci, fs in enumerate(kd_chunks(fc, np.nonzero(~fglow)[0], CHUNK_FACES)):
            m = np.zeros(npl, bool)
            m[fs] = True
            ob = emit("backdrop.c%d" % ci, me, m, mat_of_face, uv=False, col=True, extras=dict(chunk=1))
            if ob is not None:
                out_objs["backdrop"].append(ob)
        if fglow.any():
            ob = emit("backdrop.glow", me, fglow, mat_of_face, uv=False, col=True, extras=dict(glow=2.0))
            if ob is not None:
                out_objs["backdrop"].append(ob)
    bpy.data.objects.remove(ob_at)
    bpy.data.objects.remove(ob_vc)
    os.makedirs(RAW, exist_ok=True)
    files = {}
    for zone, objs in out_objs.items():
        p = os.path.join(RAW, zone + ".glb")
        export_baked(p, objs)
        st = EW.glb_stats(p)
        files[zone + ".glb"] = st
        log("exported", zone, json.dumps(st))
    T["export"] = round(time.time() - t0 - T["atlases"] - T["vc"], 1)
    dump(os.path.join(BAKE_OUT, "post_stats.json"), dict(files=files, times=T, exposure=a.exposure, sat=a.sat,
                                                           atlases=atlases, stats=dict(stats)))


def export_baked(path, objects):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    deselect_all()
    for ob in objects:
        ob.select_set(True)
    kw = dict(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True, export_extras=True,
              export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
              export_animations=False, export_materials="EXPORT", export_texcoords=True, export_normals=False,
              export_tangents=False, export_vertex_color="MATERIAL", export_image_format="AUTO",
              export_draco_mesh_compression_enable=False, export_gpu_instances=False)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    for k in list(kw):
        if k not in props:
            log("glTF option missing:", k)
            kw.pop(k)
    bpy.ops.export_scene.gltf(**kw)
    log("wrote", path, os.path.getsize(path))


# ---- water: waterfall sheets and streams as real geometry, light beams as data -------------------

WATER_NEAR = 350.0             # m: sheets nearer than this go into their own (finer) mesh
BEAM_MATS = ("light_beam", "formation_beam", "props_beam")


def _three(p):
    return [round(float(p[0]), 3), round(float(p[2]), 3), round(float(-p[1]), 3)]


G_ACC = 9.81                   # m/s2
WATER_UV1 = "UVFlow"           # full water: the second UV set (TEXCOORD_1, three.js uv1), see _water_uv1
WATER_LAYER_B = {"core": 0.0, "side": 0.5, "veil": 1.0}   # full water: COLOR_0.b per sheet role (nature.SHEET_ROLES)
WATER_EXIT_SPEED = 1.3         # m/s over the lip for a sheet without obj['exit_speed'] (nature.waterfall: 1.1-2.2)
WATER_STREAM_SPEED = 3.0       # m/s along a feeder stream: its uv1 time counts up from 0 at the head (the page's
                               # FALL.streamSpeed, lib/sect/waterfall.ts, turns it back into metres: keep them equal)
WATER_ROW_U = True             # sheets: UV0 u = fraction across the vertex's own row, so 0 and 1 are the sheet's
                               # edges all the way down (False: across the bounding box, as before 2026-10-20: the
                               # sheets widen 1.2-1.9x, so at the lip their edges sat at u ~0.1-0.25 / 0.75-0.9)


def _is_stream(name):
    return ".stream" in name or name.startswith("world.stream")


def _sheet_rows(co):
    """Rows of a row-built sheet (nature._sheet_bm, world._fall_sheet: every row has one local z): (row index per
    vertex, row z ascending, row x min, row x max), or None when the mesh is not built that way."""
    z = np.round(np.asarray(co[:, 2], float), 3)
    uz, inv = np.unique(z, return_inverse=True)
    if len(uz) < 2 or len(uz) * 2 > len(z):
        return None
    lo = np.full(len(uz), np.inf)
    hi = np.full(len(uz), -np.inf)
    np.minimum.at(lo, inv, co[:, 0])
    np.maximum.at(hi, inv, co[:, 0])
    return inv, uz, lo, hi


def _row_fraction(co, rows):
    """Per vertex: fraction across its own row (0 left edge, 1 right edge; 0.5 on a one-point row)."""
    inv, _, lo, hi = rows
    span = (hi - lo)[inv]
    return np.where(span > 1e-6, (co[:, 0] - lo[inv]) / np.maximum(span, 1e-6), 0.5)


def _water_uv(name, co, gen=None):
    """Per-vertex (u, v): u across the water, v along it (1 at the lip or the stream's head, 0 at the foot; the glTF
    exporter flips v, so three.js uv.y is 0 at the lip and 1 at the foot). Sheets: v from Blender's generated
    coordinates (z up, the bounding box), u the fraction across the vertex's own row (WATER_ROW_U; else generated x).
    Streams (world.stream, a strip of vertex pairs from the terrace edge to the lip): pair side and row."""
    n = len(co)
    if _is_stream(name):
        if n % 2 == 0 and n >= 4:
            row = np.arange(n) // 2
            return np.stack([(np.arange(n) % 2).astype(np.float32), 1.0 - row / max(row.max(), 1)], 1)
    if gen is None:
        lo, hi = co.min(0), co.max(0)
        gen = (co - lo) / np.maximum(hi - lo, 1e-6)
    u = gen[:, 0]
    if WATER_ROW_U:
        rows = _sheet_rows(co)
        if rows is not None:
            u = _row_fraction(co, rows)
    return np.clip(np.stack([u, gen[:, 2]], 1), 0.0, 1.0).astype(np.float32)


def _water_uv1(name, co, M, exit_speed=None):
    """Per-vertex second UV set (WATER_UV1) in metres and seconds, (x, t), for the web shader to size streaks in
    metres and move them at the speed of falling water.
    Sheets (local x across, pouring toward -Y, lip at the origin): x = the fraction across the vertex's own row,
    centred, times the width of the top row in metres (metres across at the lip, carried down the flow lines, so
    the streaks fan out with the sheet); t = seconds since the water left the lip: sqrt(2 d / g) d metres under the
    lip, and on the lead-in over the lip (nature sheets: two rows up to 0.7 m back) minus the metres behind the lip
    over ``exit_speed`` (m/s, else WATER_EXIT_SPEED). Not row-built: the bounding box across, its top as the lip.
    Streams: x = metres across from the centre line, t = (metres from the head along the strip) / WATER_STREAM_SPEED
    (0 at the head, the most at the lip: the page reads max(t, 0) x its stream speed as metres from the head).
    Returned in Blender UV space, v = 1 - t: the glTF exporter flips v, so the file and three.js uv1 hold t."""
    n = len(co)
    co = np.asarray(co, float)
    M = np.asarray(M, float)
    sx, sy, sz = (max(float(np.linalg.norm(M[:3, k])), 1e-9) for k in range(3))
    x = np.zeros(n)
    t = np.zeros(n)
    if _is_stream(name):
        if n % 2 == 0 and n >= 4:
            w = co @ M[:3, :3].T + M[:3, 3]
            a, b = w[0::2], w[1::2]
            c = (a + b) * 0.5
            half = np.linalg.norm(a - b, axis=1) * 0.5
            s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
            row = np.arange(n) // 2
            x = np.where(np.arange(n) % 2 == 0, -half[row], half[row])
            t = s[row] / WATER_STREAM_SPEED
    else:
        rows = _sheet_rows(co)
        if rows is not None:
            f = _row_fraction(co, rows)
            _, uz, lo, hi = rows
            top = float(hi[-1] - lo[-1])
            width = top if top > 1e-6 else float(np.max(hi - lo))
        else:
            lo3, hi3 = co.min(0), co.max(0)
            f = (co[:, 0] - lo3[0]) / max(float(hi3[0] - lo3[0]), 1e-6)
            width = float(hi3[0] - lo3[0])
        x = (f - 0.5) * width * sx
        zmax = float(co[:, 2].max())
        z0 = 0.0 if -1e-3 <= zmax <= 0.1 else zmax          # the lip: the origin, else the top
        d = (z0 - co[:, 2]) * sz
        t = np.sqrt(2.0 * np.maximum(d, 0.0) / G_ACC)
        lead = co[:, 2] > z0 + 1e-4
        if lead.any():
            lip = np.abs(co[:, 2] - z0) < 5e-4
            y_lip = float(co[lip, 1].mean()) if lip.any() else 0.0
            v0 = float(exit_speed) if exit_speed else WATER_EXIT_SPEED
            t[lead] = -np.maximum(co[lead, 1] - y_lip, 0.0) * sy / max(v0, 0.1)
    return np.stack([x, 1.0 - t], 1).astype(np.float32)


def _water_layer(ob):
    """A sheet's role: obj['water_layer'] (nature.waterfall, world.build_waterfalls, sect/patch_water.py), else its
    place among its parent's waterfall sheets by name (build order) as nature.sheet_roles gives it; 'core' when it
    has no parent (streams, loose sheets)."""
    role = ob.get("water_layer")
    if role in WATER_LAYER_B:
        return role
    par = ob.parent
    if par is None:
        return "core"
    sibs = sorted(c.name for c in par.children if c.type == "MESH" and any(
        s.material is not None and "waterfall" in s.material.name for s in c.material_slots))
    if ob.name not in sibs:
        return "core"
    k, nsib = sibs.index(ob.name), len(sibs)
    roles = {1: ("core",), 2: ("core", "veil"), 3: ("core", "side", "veil")}.get(nsib) or (
        ("core",) + tuple(("side", "veil")[(j - 1) % 2] for j in range(1, nsib)))
    return roles[k]


def cmd_water(a):
    """Waterfall sheets and streams seen along the path -> out/web/raw/water.glb (decimated, UV u across / v
    along the flow, COLOR_0 = (seed, flow / 2, 0)); lip/foot corners and the glowing light beams (additive FX,
    not in the bake) -> out/web/water_meta.json. sect_pack.py merges the latter into meta.json."""
    sc = bpy.context.scene
    R = EW.gather(sc)
    S, _ = EW.load_cache(R)
    dg = bpy.context.evaluated_depsgraph_get()
    dec = Decimator(sc)
    groups = collections.defaultdict(lambda: dict(co=[], vi=[], ls=[], uv=[], col=[], n=0, nl=0))
    falls, beams, seen = [], [], set()
    for i in range(len(R)):
        mats = [m for m in R.tinfo[R.tkey[i]][2] if m]
        is_fall = any("waterfall" in m for m in mats)
        is_beam = any(any(b in m for b in BEAM_MATS) for m in mats)
        if not (is_fall or is_beam) or not S["any"][i] or S["dmin"][i] > a.water_max:
            continue
        nm = R.name[i] if not R.inst[i] else R.key[i]
        if nm in seen:
            continue
        seen.add(nm)
        d = float(S["dmin"][i])
        if is_beam:
            if R.top[i] == EW.FLYER_COLL or R.owner[i].startswith("flyer"):
                continue
            # the beam's own axis (beams run up into the sky or between satellites): principal axis of its
            # vertices, end to end, and the spread around it as the radius
            obb = bpy.data.objects.get(R.name[i])
            if obb is None or obb.type != "MESH":
                continue
            co = np.array([v.co[:] for v in obb.data.vertices], float)
            if len(co) < 2:
                continue
            M = np.asarray(R.mw[i], float)
            w = co @ M[:3, :3].T + M[:3, 3]
            c = w.mean(0)
            _, _, vt = np.linalg.svd(w - c, full_matrices=False)
            ax = vt[0]
            if ax[2] < 0:
                ax = -ax
            t = (w - c) @ ax
            rad = float(np.percentile(np.linalg.norm((w - c) - np.outer(t, ax), axis=1), 90))
            mat = bpy.data.materials.get(next(m for m in mats if any(b in m for b in BEAM_MATS)))
            col = EW.hexcol(mat.diffuse_color) if mat is not None else "#9ff3ff"
            beams.append(dict(name=nm, base=_three(c + ax * t.min()), top=_three(c + ax * t.max()),
                              radius=round(max(rad, 0.05), 2), color=col,
                              material=mat.name if mat is not None else None, nearestM=round(d, 1)))
            continue
        ob = bpy.data.objects.get(R.name[i])
        if ob is None:
            continue
        me0 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        A0 = MA(me0)
        uv_v = _water_uv(nm, A0.co, A0.gen)
        lay = me0.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", np.ascontiguousarray(uv_v[A0.vi], np.float32).ravel())
        tris = EW._mesh_tris(me0)[0]
        target = 3000 if d < 150 else 1500 if d < WATER_NEAR else 600
        me = dec.get(nm + ".water", me0, min(1.0, target / max(tris, 1))) if tris > target * 1.2 else me0
        nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(nv, 3)
        vi = np.empty(nl, np.int32)
        me.loops.foreach_get("vertex_index", vi)
        ls = np.empty(npl, np.int32)
        me.polygons.foreach_get("loop_start", ls)
        uv = np.empty(nl * 2, np.float32)
        me.uv_layers["UVMap"].data.foreach_get("uv", uv)
        M = np.asarray(R.mw[i], float)
        w = co @ M[:3, :3].T + M[:3, 3]
        kind = "stream" if "stream" in nm else "sheet"
        g = groups[(kind, "near" if d < WATER_NEAR else "far")]
        seed = (zlib.crc32(nm.encode()) & 0xffff) / 65535.0
        flow = float(ob.get("flow", 1.0))
        g["co"].append(w)
        g["vi"].append(vi + g["n"])
        g["ls"].append(ls + g["nl"])
        g["uv"].append(uv.reshape(-1, 2))
        g["col"].append(np.tile([seed, min(flow / 2.0, 1.0), 0.0, 1.0], (nl, 1)).astype(np.float32))
        g["n"] += nv
        g["nl"] += nl
        # lip and foot (three space) from the world vertices: the top and bottom bands, spread along the
        # object's local X (across the fall)
        xd = M[:3, 0] / max(np.linalg.norm(M[:3, 0]), 1e-9)
        zr = w[:, 2]
        h = float(zr.max() - zr.min())
        top = w[zr >= zr.max() - 0.04 * max(h, 1.0)]
        bot = w[zr <= zr.min() + 0.04 * max(h, 1.0)]

        def ends(P):
            s = P @ xd
            return P[np.argmin(s)], P[np.argmax(s)]
        tl, tr = ends(top)
        bl, br = ends(bot)
        falls.append(dict(name=nm, kind=kind, corners=[_three(tl), _three(tr), _three(br), _three(bl)],
                          lip=_three(top.mean(0)), foot=_three(bot.mean(0)), height=round(h, 2),
                          sizeLocal=[round(float(x), 3) for x in (ob.dimensions.x, ob.dimensions.z, ob.dimensions.y)],
                          flow=flow, nearestM=round(d, 1), faces=int(npl)))
    sc_out = bpy.data.collections.new("web.water")
    sc.collection.children.link(sc_out)
    objs = []
    for (kind, band), g in sorted(groups.items()):
        m = bpy.data.materials.get("water." + kind) or bpy.data.materials.new("water." + kind)
        _use_nodes(m)
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        nt.links.new(ca.outputs["Color"], b.inputs["Base Color"])
        me = make_mesh("water.%s.%s" % (kind, band), np.concatenate(g["co"]), np.concatenate(g["vi"]),
                       np.concatenate(g["ls"]))
        me.materials.append(m)
        lay = me.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", np.concatenate(g["uv"]).ravel())
        col = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        col.data.foreach_set("color", np.concatenate(g["col"]).ravel())
        ob = bpy.data.objects.new("water.%s.%s" % (kind, band), me)
        sc_out.objects.link(ob)
        ob["water"] = kind
        objs.append(ob)
        log("water", kind, band, "faces", len(me.polygons))
    os.makedirs(RAW, exist_ok=True)
    if objs:
        export_baked(os.path.join(RAW, "water.glb"), objs)
    dump(os.path.join(OUT_WEB, "water_meta.json"),
         dict(units="three.js world (Y up), metres", falls=falls, beams=beams,
              note="corners: lip-left, lip-right, foot-right, foot-left; sizeLocal: the object's own "
                   "dimensions on the three axes (x across, y up, z through)"), indent=1)
    log("water: falls", len(falls), "beams", len(beams))


# ---- verify -------------------------------------------------------------------------------------

def cmd_verify(a):
    """Import GLBs, emission-only shading (the textures are display-referred), Standard view, chase camera
    from camera.json, sky panorama as the world."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    sc = bpy.context.scene
    gdir = a.glb_dir
    with open(os.path.join(a.out, "camera.json"), encoding="utf-8") as fh:
        camj = json.load(fh)
    t0 = time.time()
    for g in a.glbs.split(","):
        p = os.path.join(gdir, g)
        if os.path.isfile(p):
            bpy.ops.import_scene.gltf(filepath=p)
            log("imported", g, len(bpy.data.objects), "objects")
    tris = 0
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        nt = m.node_tree
        outn = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if outn is None:
            continue
        b = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        src = None
        if b is not None and b.inputs["Base Color"].is_linked:
            src = b.inputs["Base Color"].links[0].from_socket
        em = nt.nodes.new("ShaderNodeEmission")
        if src is not None:
            nt.links.new(src, em.inputs["Color"])
        elif b is not None:
            em.inputs["Color"].default_value = b.inputs["Base Color"].default_value
        if b is not None and b.inputs["Alpha"].is_linked:
            mix = nt.nodes.new("ShaderNodeMixShader")
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            nt.links.new(b.inputs["Alpha"].links[0].from_socket, mix.inputs["Fac"])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], outn.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], outn.inputs["Surface"])
    world = bpy.data.worlds.new("verify.world")
    _use_nodes(world)
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky = os.path.join(a.out, "sky.png")
    if os.path.isfile(sky):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(sky)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    sc.world = world
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    w, h = (int(x) for x in a.res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.image_settings.file_format = "PNG"
    cd = bpy.data.cameras.new("verify.cam")
    cam = bpy.data.objects.new("verify.cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cd.sensor_fit = "VERTICAL"
    cd.clip_start, cd.clip_end = 0.5, 9000.0
    out = os.path.join(BAKE_OUT, "verify" + (("_" + a.tag) if a.tag else ""))
    os.makedirs(out, exist_ok=True)
    from mathutils import Quaternion
    for f in [int(x) for x in a.ref_frames.split(",")]:
        row = camj["frames"][f - camj["frameStart"]]
        p, q = row["p"], row["q"]
        cam.location = (p[0], -p[2], p[1])
        R3 = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = (EW.C3.transposed() @ R3).to_quaternion()
        cd.sensor_height = 36.0 * 9 / 16
        cd.lens = (cd.sensor_height / 2) / math.tan(math.radians(row["fovY"]) / 2)
        sc.render.filepath = os.path.join(out, "baked_%d.png" % f)
        bpy.ops.render.render(write_still=True)
        log("verify", f, sc.render.filepath, round(time.time() - t0, 1))


# ==== FULL PATH (--profile full): every area chunk of out/web/full/chunks.json ==========================
#
# One Blender session loads the sect once and bakes the chunks in the order given (--chunks, default flight order
# then the backdrop). Per chunk: the pieces export_web assigned to it (chunks.npz; vegetation -> bake_trees.py,
# waterfalls -> 'water'), LOD to --atlas-tris, texel density from each piece's nearest distance to the camera
# path (x HOLD_RHO within HOLD_RHO_NEAR m in front of a hold camera), scaled to the chunk's texel budget, the
# prototype's own unwrap/packer, one joined bake mesh, COMBINED + albedo bake, then right away the post step
# (OIDN denoise, look.py grade, AgX Punchy, exposure) and out/web/full/raw/<area>.glb. The range and the hanging
# roots are decimated once for the whole path (weights protect the faces near it) and split face by face.
# While a chunk bakes, everything else of the sect stays in the scene for shadows and bounce: the owners whose
# pieces the bake mesh replaces are hidden, and their other pieces (other chunks, vegetation) come back as
# occluder copies; the split meshes come back as the faces outside the chunk.
# Backdrop (vertex colours): the far set (pieces seen only beyond 400 m) plus one reduced proxy per area
# (Empty 'proxy.<area>', extras {"proxyOf": area}); baked with the area originals hidden, the proxies standing in.

FULL_ATLAS_TRIS = 700_000      # Blender-side triangles per chunk (the glTF exporter drops some decimated faces)
FULL_ATLASES = 1.25            # texel budget per chunk in 4096^2 atlases: one 4096 + one 2048
FULL_ATLASES_BY_AREA = {"gate": 2.0,   # the opening view keeps the prototype's density (two 4096 atlases)
                        # the softest holds, measured per pixel (36 / 33 / 27 % of their pixels over 3 screen px a
                        # texel; density scale 0.36 / 0.82 / 0.46): the same two 4096 atlases, about 1-2 MB more each
                        "steles": 2.0, "summit": 2.0, "forge": 2.0}
HOLD_RHO = 1.5                 # texel density factor for pieces within HOLD_RHO_NEAR m in front of a hold camera
HOLD_RHO_NEAR = 120.0
HOLD_AROUND_NEAR = 40.0        # m from a hold camera in any direction (the view turns all the way round there):
HOLD_AROUND_FLOOR = 0.5        # LOD floor (the forward rule keeps 1.0 up to HOLD_FULL_TRIS)
HOLD_RHO_AROUND = 1.25         # texel density factor (the forward rule gives HOLD_RHO)
STAGE_OWNERS = "forge.artifact."   # the forge ring's artifacts turn all the way round on the web (idle motion):
                                   # each bakes as if it stood at the ring's front, see ring_stage()
STAGE_STEP = 9.0                   # m: the staged artifacts stack straight up, this far apart (a 7 deg sun casts no
                                   # shadow between them; the one above hides ~5 % of the sky)
OCC_PAD = 300.0                # m: a hidden owner's other pieces within this of the chunk come back as occluders
FLOOR_SHARE_MAX = 0.6          # LOD floors may take at most this share of a chunk's budget (the budget grows <= 1.6x)
FLOOR_GROWTH_MAX = 1.6
ROOM_MIN = 0.12                # (r37) once every floor is set, the floors at the levels they really get (each rounds up
ROOM_GROWTH_MAX = 2.0          # to a LEVEL) leave at least this share of the budget to the screen-size rule: the budget
                               # grows for it, up to ROOM_GROWTH_MAX x the chunk's base budget. Round 12's heavier props
                               # filled gate, forge, mission, library, steles and scroll with floors: k fell to its 1e-7
                               # minimum and every unfloored piece went to the lowest level (the gate stair to ramps)
STRUCT_SUFFIX = (".steps", ".ramp", "stairs", ".walls", ".beams", ".bargeboard", ".gable",
                 ".rails", ".piers", ".arch", ".foot_landing", ".foot_rail", ".rest_landing", ".rest_rail",
                 ".rest_pier", ".bridge.deck", ".bridge.boards", ".bridge.posts")
STRUCT_FLOOR = 1.0             # (r37) stairs, walls, beams, gables and a link's structure (PROXY_WHOLE_PARTS) within
STRUCT_NEAR = 150.0            # STRUCT_NEAR keep full detail, never scaled (~90k triangles over the 11 chunks): collapse
                               # turned them into ramps, torn wall triangles and treads with gaps
CUT_TAG = "sect_r12"           # (r37) a mesh tagged CUT_TAG = "cut" (lib/props.py _stele_cut, _scroll_cut, _slips_cut)
CUT_WORDS = ("props.stele.border",)   # has holes its inlay fills edge to edge (the stele border: the slab's holes
CUT_NEAR = 80.0                # under its strokes): within CUT_NEAR never decimated, like NO_DECIMATE (at 0.5 a stele
                               # still showed ~0.1 m2 of holes and z-fighting strokes per slab, at 0.25 ~0.9 m2)
TILE_FLOOR_NEAR = 120.0        # m: roof tile meshes ('.tiles', black / teal tiles over red boards in one mesh) this near
TILE_FLOOR_TRIS = 60000        # a hold camera keep full detail up to this size (decimated, red boards poked through
                               # the tiles as streaks on the forge hall), 0.5 above
BIG_RATIO_FULL = 0.6           # range / roots: one weighted decimation for the whole path (0.35 left 75k range
                               # triangles: 15-21 m rock facets where the holds look)
RANGE_NEAR = 150.0             # m: range vertices this near a view keep their detail (the holds see the range from
RANGE_FAR = 1000.0             # 150-400 m); decimated freely from RANGE_FAR on (decimate_weighted near / far)
W_NRM = "w_nrm"                # CORNER attribute of the decimated range: its smooth corner normals, which every piece
                               # cut out of it shades with (carry_normals), so no tone step runs along the cut lines
RANGE_SHARP_DEG = 90.0         # deg: range folds sharper than this stay split (smooth_range): the knife-edge lips where
                               # a terrace top meets its underside (median fold 154 deg). Smoothed, a lip vertex's normal
                               # points sideways and the top faces on the lip shade 35 deg off (62 at p90; 13 / 28 kept
                               # split); the grass/rock border (p90 fold 70 deg) stays smooth, as the rim band needs
TERMINATOR_OFFSET = 0.6        # Object.shadow_terminator_geometry_offset of the joined bake objects (Cycles default
                               # 0.1): smooth normals on coarse rock under a 7 deg sun cast a faceted terminator
ISLAND_FLOOR_K = 0.15          # floating islands / islets: LOD floor triangles = clip(K * px^2, LO, HI), px = the
ISLAND_FLOOR_LO = 400.0        # largest on-screen size over the chunk's own views (bake_rules.projected_px); they kept
ISLAND_FLOOR_HI = 6000.0       # 0.8-6 % of their triangles (a 29 m island 265 m from the gate camera: 118 of 15k)
ISLAND_FLOOR_CAP = 40_000      # island floor triangles per area chunk at most (all scaled down evenly beyond)
ISLAND_FLOOR_CAP_FAR = 80_000  # backdrop far set: islands + far rock together
ISLAND_FLOOR_SHARE_PROXY = 0.3    # per area proxy: at most this share of its record budget (its islands, measured over
                                  # the views where the proxy stands in; they kept a median of ~7 triangles)
FAR_ROCK_K = 0.08              # far-set rock pieces of at least FAR_ROCK_MIN_PX (the distant massifs): triangles =
FAR_ROCK_MIN_PX = 60.0         # K * px^2, at most ISLAND_FLOOR_HI
ISLAND_EXCLUDE = VEG_KINDS + ROOT_WORDS + ("fall", "mist")   # island-named pieces that are not the rock
FAR_TRIS_FULL = 360_000        # backdrop far set
PROXY_TRIS_FULL = 30_000       # backdrop proxy per area (records; the area's terrain faces come on top)
PROXY_MIN_DIAG = 3.0
PROXY_MAX_RECS = 900
PROXY_WHOLE_PARTS = ("stairs", "rails", "piers", "arch", "foot_landing", "foot_rail", "rest_landing", "rest_rail",
                     "rest_pier", "bridge.deck", "bridge.boards", "bridge.posts")
                               # round 11 (S3): these parts of world.link.<a>_<b> go into the area proxies whole
                               # (proxy_whole), on top of PROXY_TRIS_FULL: about 63k triangles in all (the 8 stairways
                               # after patch_r11_links, 57k, and the chain bridge's planks and posts)


def proxy_whole(name, inst=False):
    """True for a link's structure (world.link.<a>_<b>.<part>, part in PROXY_WHOLE_PARTS, not an instance): the
    backdrop's area proxies carry it undecimated. Each link stair belongs to one area chunk, so wherever that chunk
    is not loaded (after a jump or a fresh load, while chunks stream in, always on phones, and when the quality
    ladder turns stand-ins on) the proxy draws it; decimated to the area's 30k budget the parapets turned into shards
    and white teeth, then popped into the real stair when the chunk came. The archways and pavilions on a link
    (.foot_gate, .rest_pavilion) and the stepping stones keep the area's LOD rules."""
    if inst or not name.startswith("world.link."):
        return False
    link, _, part = name[len("world.link."):].partition(".")
    return "_" in link and part in PROXY_WHOLE_PARTS
FAR_MIN_PX_FULL = 3.0
_FC = {}                       # full-path session state (full_ctx)


def use_profile(name):
    """'proto' keeps the first test's defaults; 'full' = the whole path (export_web's full profile, outputs under
    out/web/full/{raw,bake}, raw EXRs under bakecache/full/<chunk>/, holds = the 11 area holds)."""
    global PROFILE, BAKE_OUT, RAW, CACHE_DIR, HOLD_FRAMES, HOLD_AREAS, HOLD_AREA_NEAR
    EW.use_profile(name)
    if name != "full":
        return
    PROFILE = "full"
    BAKE_OUT = os.path.join(EW.FULL, "bake")
    RAW = os.path.join(EW.FULL, "raw")
    CACHE_DIR = os.path.join(ROOT, "bakecache", "full")
    HOLD_FRAMES = tuple(int(x["holdFrame"]) for x in EW.AREAS)
    HOLD_AREAS = tuple(x["id"] for x in EW.AREAS)
    HOLD_AREA_NEAR = tuple(HOLD_AREA_NEAR[1] for _ in HOLD_AREAS)   # refined per area in full_ctx


def _tris(me):
    return int(EW._mesh_tris(me)[0]) if me is not None else 0


def full_ctx(want_chunks):
    """Gather, visibility cache, chunk plan, base meshes (captured once for the requested chunks, the backdrop and
    the occluders), the split meshes; shared by every chunk of the session."""
    global HOLD_AREA_NEAR
    if _FC:
        return _FC
    sc = bpy.context.scene
    t0 = time.time()
    R = EW.gather(sc)
    S, frames = EW.load_cache(R)
    ch, ids = EW.load_chunks(R)
    used = set()
    for t in R.tinfo.values():
        used.update(m for m in t[2] if m)
    minfo = {m: EW.material_info(bpy.data.materials[m]) for m in used if m in bpy.data.materials}
    ex = EW.export_mask(R, minfo)
    n = len(R)
    veg = np.array([is_veg_rec(R, i) for i in range(n)], bool)
    falls = np.array([is_fall(R, i) for i in range(n)], bool)
    px = S["px_eff"].astype(float)               # path pxmax, or the weighted look views' when larger
    bakeable = ~ex & ~veg & ~falls
    # group per record: chunk index (baked into that chunk), -1 far set (backdrop), -3 split, None ignored (FX),
    # -9 stays in the scene as it is (vegetation, waterfalls, unseen pieces)
    grp = np.full(n, -9, np.int32)
    grp[bakeable & (ch >= 0)] = ch[bakeable & (ch >= 0)]
    grp[bakeable & (ch == -1) & (px >= FAR_MIN_PX_FULL)] = -1
    grp[ch == -3] = -3
    grp[ex] = -99
    orecs = collections.defaultdict(list)
    for i in range(n):
        orecs[R.owner[i]].append(i)
    mixed = set()
    for o, recs in orecs.items():
        g = set(int(grp[i]) for i in recs) - {-99}
        if len(g) > 1 and (g & (set(range(len(ids))) | {-1})):
            mixed.add(o)
    cam = bpy.data.objects[EW.CAMERA]
    views = EW.load_views(cam)                    # the audit's views: path frames, then the look-around views
    frames, cam_mats = views.frames, views.mats
    th, tv = EW.camera_tan(cam)
    aw = EW.DEPTH_RES[0] / EW.DEPTH_RES[1]
    hold_mats = EW.sample_matrices(cam, list(HOLD_FRAMES))
    hold_pos = np.array([np.asarray(M, float)[:3, 3] for M in hold_mats])
    members = EW.hotspot_members()
    # per area: how far its own pieces may be from the hold camera and still count as "studied" (HOLD_AREA_NEAR):
    # the box distance to the area's main hotspot + 30 m, clamped to 40-140 m
    an = []
    for k, aid in enumerate(HOLD_AREAS):
        recs = [i for i in range(n) if members.get(R.owner[i]) == aid]
        if recs:
            r = np.array(recs)
            p = hold_pos[k]
            d = np.linalg.norm(np.maximum(np.maximum(R.lo[r] - p, p - R.hi[r]), 0.0), axis=1).min()
            an.append(float(np.clip(d + 30.0, 40.0, 140.0)))
        else:
            an.append(95.0)
    HOLD_AREA_NEAR = tuple(an)
    log("hold area reach (m):", json.dumps(dict(zip(HOLD_AREAS, [round(x) for x in an]))))
    want_idx = set()
    for cid in want_chunks:
        if cid == "backdrop":
            want_idx.update(np.nonzero((grp >= 0) | (grp == -1))[0].tolist())
        elif cid in ids:
            want_idx.update(np.nonzero(grp == ids.index(cid))[0].tolist())
    want_idx.update(np.nonzero(grp == -3)[0].tolist())
    for o in mixed:
        want_idx.update(i for i in orecs[o] if grp[i] != -99)
    bases = capture(sorted({R.tkey[i] for i in want_idx}))
    dec = Decimator(sc)
    _FC.update(sc=sc, R=R, S=S, frames=frames, views=views, ch=ch, ids=ids, minfo=minfo, ex=ex, veg=veg, falls=falls,
               px=px,
               grp=grp, orecs=orecs, mixed=mixed, cam=cam, cam_mats=cam_mats, tv=tv, aw=aw, hold_mats=hold_mats,
               hold_pos=hold_pos, members=members, bases=bases, dec=dec, picker=EW.MeshPicker(bases, dec), big={},
               rw={}, lit=False, hidden_fx=0, t_setup=0.0,
               hot_labels={h[0]: h[1] for h in EW.all_hotspots()},
               hot_kind={h["id"]: h["kind"] for h in EW.HOTSPOT_DEFS},
               hot_area={h["id"]: h["area"] for h in EW.HOTSPOT_DEFS if not h.get("metaOnly")})
    log("full ctx: records", n, "mixed owners", len(mixed), sorted(mixed)[:40], "captured", len(bases))
    # split meshes (range, roots): one weighted decimation for the whole path, faces assigned to chunks. The range
    # (the only one decimated) keeps its grass/rock border vertices and gets smooth whole-mesh normals (smooth_range)
    for i in np.nonzero(grp == -3)[0]:
        base = bases.get(R.tkey[i])
        if base is None:
            continue
        ratio = BIG_RATIO_FULL if len(base.polygons) > 20000 else 1.0     # world.roots: 2.9k faces, keep
        if ratio < 1.0:
            border = range_border(base)
            me = decimate_weighted(dec, R.tkey[i] + ".big", base, R.mw[i], cam_mats, tv, aw, ratio, near=RANGE_NEAR,
                                   far=RANGE_FAR, dscale=views.dscale, keep=border)
            smooth_range(me, R.name[i])
        else:
            me = decimate_weighted(dec, R.tkey[i] + ".big", base, R.mw[i], cam_mats, tv, aw, ratio,
                                   dscale=views.dscale)
        fch, fd, _, _ = EW.face_assign(me, R.mw[i], cam_mats, frames, tv, aw, dscale=views.dscale)
        _FC["big"][int(i)] = (me, fch, fd)
        log("split", R.name[i], len(me.polygons), "faces", {(ids[k] if k >= 0 else int(k)): int((fch == k).sum())
                                                            for k in sorted(set(fch.tolist()))})
    _FC["t_setup"] = round(time.time() - t0, 1)
    return _FC


def range_border(me):
    """Per vertex of the range: on the grass/rock border (bake_rules.border_vertices). Grass = the material slots of
    the ground detail class (world.range: nature_soil_moss; rock_cliff and world_rock_under are the rest)."""
    A = ma(me)
    grass = [k for k, m in enumerate(me.materials)
             if m is not None and detail_class(m.name, m.get(MAT_TAG)) == "ground"]
    if not grass or A.nl == 0:
        log("WARN", me.name, "has no ground-class material slot: no grass/rock border kept")
        return None
    b = BR.border_vertices((A.vi, A.ls), A.mi, grass=grass, nv=A.nv)
    log("range border", me.name, "grass slots", grass, "border verts", int(b.sum()), "of", A.nv,
        "(%.1f%%)" % (100.0 * b.mean()))
    _FC.setdefault("check", {})["range_border"] = dict(verts=int(b.sum()), of=A.nv)
    return b


def _full_item(F, i, me, kind, zone, d=None, name=None):
    R = F["R"]
    nm = R.tkey[i][1:] if R.tkey[i].startswith("#") else R.tkey[i]
    ob = bpy.data.objects.get(nm)
    scale, props = mat_slots_and_props(ob)
    if ob is not None:
        props["__dims"] = tuple(ob.dimensions)
    key = R.key[i] if name is None else name
    M = R.mw[i]
    lift = PATH_LIFT.get(R.owner[i]) or PATH_LIFT.get(R.name[i])
    if lift:
        M = np.array(M, float)
        M[2, 3] += lift
    return Item(mesh=me, M=M, kind=kind, zone=zone, hot=F["members"].get(R.owner[i], ""), top=R.top[i],
                owner=R.owner[i], name=name or R.name[i], key=key,
                dmin=float(F["S"]["d_eff"][i] if d is None else d), scale=scale, props=props,
                rand=(zlib.crc32(key.encode()) & 0xffffff) / float(0xffffff), atlas=None, uv=None, boost=1.0)


def _item_box(it):
    A = ma(it.mesh)
    M = np.asarray(it.M, float)
    w = A.co @ M[:3, :3].T + M[:3, 3]
    return w.min(0), w.max(0)


def _near_hold_box(F, lo, hi, reach):
    """Texel density factor near the holds: HOLD_RHO when the box comes within `reach` m of a hold camera in front
    of it, HOLD_RHO_AROUND within HOLD_AROUND_NEAR m in any other direction (not after a path-only audit), else 1."""
    c = 0.5 * (lo + hi)
    r = 0.5 * float(np.linalg.norm(hi - lo))
    around = F["S"].get("look", "none") != "none"
    out = 1.0
    for M in F["hold_mats"]:
        M = np.asarray(M, float)
        p = M[:3, 3]
        d = float(np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0)))
        if d <= reach and float((c - p) @ (-M[:3, 2])) > -r:
            return HOLD_RHO
        if around and d <= HOLD_AROUND_NEAR:
            out = HOLD_RHO_AROUND
    return out


def _occluder_objects(F, recs, coll, tag):
    """Linked copies of the captured meshes at the records' matrices (pieces of hidden owners that this bake
    does not replace: they keep casting shadows and bouncing light)."""
    R = F["R"]
    made = []
    for j in recs:
        me = F["bases"].get(R.tkey[j])
        if me is None:
            continue
        o = bpy.data.objects.new("occ.%s.%d" % (tag, j), me)
        o.matrix_world = Matrix(np.asarray(R.mw[j], float).tolist())
        coll.objects.link(o)
        made.append(o)
    return made


def _hide(names_or_objs, store):
    for x in names_or_objs:
        ob = bpy.data.objects.get(x) if isinstance(x, str) else x
        if ob is None or ob.name in store:
            continue
        store[ob.name] = ob.hide_render
        ob.hide_render = True


def _restore(store):
    for nm, prev in store.items():
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            ob.hide_render = prev


def _bake_setup(F, a):
    win = bpy.context.window
    if win is not None and win.scene != F["sc"]:
        log("WARN context scene was", win.scene.name, "- back to", F["sc"].name)
        win.scene = F["sc"]
    if F["lit"]:
        return
    F["hidden_fx"] = hide_for_bake(F["sc"])
    bake_lighting(F["sc"])
    setup_cycles(F["sc"], a.samples, a.quality)
    F["lit"] = True
    log("bake lighting set; hid", F["hidden_fx"], "flyer/volume/fx objects")


def _src_materials(F, items):
    used = set()
    for it in items:
        used.update(ma(it.mesh).mats)
    used.discard("")
    src = {m: bpy.data.materials.get(m) for m in used}
    fallback = bpy.data.materials.get("bake.none")
    if fallback is None:
        fallback = bpy.data.materials.new("bake.none")
        fallback.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    for m, s in src.items():
        if m not in F["rw"]:
            F["rw"][m] = rewrite_material(s, m + "@bake") if s is not None else fallback
    F["rw"][""] = fallback
    return src, fallback


def _mat_class(F, name):
    """detail_class of a source material name (its sect_material tag when the material has one), memoized."""
    mc = F.setdefault("mat_class", {})
    if name not in mc:
        m = bpy.data.materials.get(name)
        mc[name] = detail_class(name, m.get(MAT_TAG) if m is not None else None)
    return mc[name]


def _island_floors(F, idx, vmask, cap, far_rock, label):
    """LOD floor ratios (per record of idx) for floating islands / islets and, with far_rock, for rock pieces of at
    least FAR_ROCK_MIN_PX (bake_rules): px = the largest on-screen size over the views in vmask (a mask over
    F["views"]) where the audit saw the piece, all floors scaled down by one factor to keep at most `cap` triangles.
    Returns (ratios, rows for the log: [record, px, floor])."""
    R, S, V = F["R"], F["S"], F["views"]
    idx = np.asarray(idx, int)
    names = [R.name[i] for i in idx]
    owners = [R.owner[i] for i in idx]
    tri = R.tris[idx].astype(float)
    isl = BR.island_mask(names, owners, tri, exclude=ISLAND_EXCLUDE)
    rock = np.zeros(len(idx), bool)
    if far_rock:
        rock = np.array([any(_mat_class(F, m) == "rock" for m in R.tinfo[R.tkey[i]][2] if m) for i in idx], bool)
        rock &= ~isl & (tri > BR.ISLAND_MIN_TRIS) & (F["px"][idx] >= 0.5 * FAR_ROCK_MIN_PX)
        rock &= np.array([not any(x in n or x in o for x in ISLAND_EXCLUDE) for n, o in zip(names, owners)], bool)
    cand = isl | rock
    px = np.zeros(len(idx))
    vmask = np.asarray(vmask, bool)
    if cand.any() and vmask.any():
        if "view_np" not in F:
            F["view_np"] = np.array([np.asarray(m, float) for m in V.mats]).reshape(-1, 4, 4)
        rec = idx[cand]
        vis = S.get("vis")
        vis = vis[rec][:, vmask] if vis is not None and vis.shape[1] == len(V) else None
        px[cand] = BR.projected_px(R.lo[rec], R.hi[rec], F["view_np"][vmask], F["tv"], F["aw"],
                                   dscale=V.dscale[vmask], vis=vis)
    r_i = BR.floor_ratios(tri, px, isl, ISLAND_FLOOR_K, ISLAND_FLOOR_LO, ISLAND_FLOOR_HI)
    r = np.maximum(r_i, BR.floor_ratios(tri, px, rock & (px >= FAR_ROCK_MIN_PX), FAR_ROCK_K, 0.0, ISLAND_FLOOR_HI))
    # over the cap the near islands' big floors give way first: every island keeps its ISLAND_FLOOR_LO while it can
    r, info = BR.cap_floors(r, tri, cap, EW.LEVELS, base=BR.floor_base(r_i, tri, ISLAND_FLOOR_LO))
    log(label, "island floors: islands", int(isl.sum()), "far rock", int(rock.sum()), "floored", info["n"],
        "keep", info["tris"], "tris (wanted", info["want"], "cap", int(cap), "scale", info["scale"], ")")
    rows = [(int(i), float(p), float(f)) for i, p, f, c in zip(idx, px, r, cand) if c]
    return r, rows


_CUT = {}                      # _cut_mask memo: tkey -> cut


def _cut_mask(R, idx):
    """Per record of idx: its mesh has holes cut for an inlay (data[CUT_TAG] == "cut") or is named in CUT_WORDS."""
    cache = _CUT
    out = np.zeros(len(idx), bool)
    for j, i in enumerate(idx):
        tk = R.tkey[i]
        if tk not in cache:
            ob = bpy.data.objects.get(tk.lstrip("#"))
            me = ob.data if ob is not None and ob.type == "MESH" else None
            cache[tk] = bool(me is not None and me.get(CUT_TAG) == "cut") or any(w in tk for w in CUT_WORDS)
        out[j] = cache[tk]
    return out


def _lod_items(F, idx, cid, budget, label, floors=True, w=None, px=None, isl_views=None, isl_cap=ISLAND_FLOOR_CAP,
               far_rock=False):
    """LOD pick for records idx to `budget` triangles (prototype rules: glyph/banner protection, hold floors, item
    hotspots, slender pieces), returns [(record, mesh)] and the measured triangles. isl_views (a mask over F["views"]):
    island floors (and with far_rock the far-rock floors) measured over those views (_island_floors), applied with
    or without `floors` and never scaled down by FLOOR_SHARE_MAX."""
    R, S = F["R"], F["S"]
    budget_in = budget
    px = F["px"] if px is None else px
    dmin = S["d_eff"]
    members = F["members"]
    if len(idx) == 0:
        return [], 0
    fl = np.zeros(len(idx))
    if floors:
        fl = EW.lod_floor(R, idx, S, EW.NEAR_MAX)
        protect = np.array([no_decimate(R.name[i], R.owner[i], dmin[i]) for i in idx], bool)
        cut = _cut_mask(R, idx) & np.array([dmin[i] <= CUT_NEAR for i in idx], bool)
        protect |= cut
        struct = np.array([dmin[i] <= STRUCT_NEAR and re.sub(r"\.\d{3}$", "", R.name[i]).endswith(STRUCT_SUFFIX)
                           for i in idx], bool)
        hm = F["hold_mats"]
        near_h = near_holds(R, idx, hm)
        close_h = near_holds(R, idx, hm, area_near=(HOLD_NEAR,) * len(HOLD_FRAMES))
        tri = R.tris[idx]
        fl_hold = np.where(close_h, np.where(tri <= HOLD_FULL_TRIS, 1.0, HOLD_MIN_RATIO),
                           np.where(near_h, np.where(tri <= 8000, 1.0, 0.25), 0.0))
        lattice = np.array([dmin[i] <= 120.0 and ("lattice" in R.name[i] or "lattice" in R.owner[i]) for i in idx],
                           bool)
        fl_hold = np.maximum(fl_hold, np.where(lattice, HOLD_MIN_RATIO, 0.0))
        props_word = np.array([any(x in R.name[i] or x in R.owner[i] for x in HOLD_PROP_WORDS) for i in idx], bool)
        props_h = near_holds(R, idx, hm, near=HOLD_PROP_NEAR,
                             area_near=tuple(max(HOLD_PROP_NEAR, x) for x in HOLD_AREA_NEAR))
        props_h &= props_word & (tri <= HOLD_FULL_TRIS)
        fl_hold = np.maximum(fl_hold, np.where(props_h, 1.0, 0.0))
        # the view turns all the way round at the holds: pieces close behind or beside the camera keep up to half.
        # Added after the budget test below, so it only fills the room left and never grows the budget.
        around_h = around_holds(R, idx, hm, HOLD_AROUND_NEAR) & ~close_h
        if S.get("look", "none") == "none":       # a path-only audit: the old rules
            around_h[:] = False
        # the content pieces (artifacts, banners, tablets, stele faces, pillars): keep their shape
        item = np.array([F["hot_kind"].get(members.get(R.owner[i], ""), "") == "item" for i in idx], bool)
        fl_item = np.where(item, np.where(tri <= 8000, 1.0, np.where(tri <= 30000, 0.5, 0.25)), 0.0)
        tiles = np.array([R.name[i].endswith(".tiles") for i in idx], bool)
        fl_tile = np.zeros(len(idx))
        if tiles.any():
            near_t = near_holds(R, idx, hm, near=TILE_FLOOR_NEAR, area_near=(TILE_FLOOR_NEAR,) * len(HOLD_FRAMES))
            fl_tile = np.where(tiles & near_t, np.where(tri <= TILE_FLOOR_TRIS, 1.0, 0.5), 0.0)
        sl = slender_mask(R, idx)
        fl = np.maximum.reduce([fl, fl_hold, fl_item, np.where(sl, SLENDER_FLOOR, 0.0)])
        # turning objects show every side: one floor per group (the highest of its pieces)
        turning = EW.turning_owners()
        tg = np.array([turning.get(R.owner[i], "") for i in idx])
        for g in set(tg.tolist()) - {""}:
            fl[tg == g] = fl[tg == g].max()
        fl_tris = float((R.tris[idx] * fl).sum())
        if fl_tris > FLOOR_SHARE_MAX * budget:
            nb = min(fl_tris / FLOOR_SHARE_MAX, FLOOR_GROWTH_MAX * budget)
            log(label, "floors take", int(fl_tris), "tris: budget", int(budget), "->", int(nb))
            budget = nb
            if fl_tris > FLOOR_SHARE_MAX * budget:
                fl = fl * (FLOOR_SHARE_MAX * budget / fl_tris)
                fl_tris = FLOOR_SHARE_MAX * budget
        # the around-hold floor takes only the floor room that is left (scaled down when short)
        add = np.maximum(np.where(around_h, HOLD_AROUND_FLOOR, 0.0) - fl, 0.0)
        add_tris = float((R.tris[idx] * add).sum())
        room = max(FLOOR_SHARE_MAX * budget - fl_tris, 0.0)
        s_add = 1.0 if add_tris <= room else room / add_tris
        fl = fl + add * s_add
        for g in set(tg.tolist()) - {""}:
            fl[tg == g] = fl[tg == g].max()
        log(label, "around-hold floors:", int(add_tris), "tris wanted, scale", round(s_add, 3))
        fl = np.maximum.reduce([fl, protect.astype(float), fl_tile,
                                np.where(struct, STRUCT_FLOOR, 0.0)])     # never scaled down
        log(label, "floors: protected", int(protect.sum()), "(cut", int(cut.sum()), ") structure", int(struct.sum()),
            "roof tiles", int((fl_tile > 0).sum()), "near holds", int((near_h | props_h).sum()),
            "around holds", int(around_h.sum()), "turning", int((tg != "").sum()),
            "items", int(item.sum()), "slender", int(sl.sum()), "floored tris", int((R.tris[idx] * fl).sum()))
    roots = np.array([any(x in R.name[i] or x in R.owner[i] for x in ROOT_WORDS) for i in idx], bool)
    fl = np.maximum(fl, np.where(roots, ROOT_FLOOR, 0.0))
    isl_rows = []
    if isl_views is not None:
        fl_i, isl_rows = _island_floors(F, idx, isl_views, isl_cap, far_rock, label)
        fl = np.maximum(fl, fl_i)
    if floors and ROOM_MIN > 0:
        # room for the screen-size rule: the floors' real cost (each rounds up to a LEVEL)
        li = np.maximum((EW.LEVELS[None, :] >= fl[:, None]).sum(1) - 1, 0)
        real = float((R.tris[idx] * np.where(fl > 0, EW.LEVELS[li], 0.0)).sum())
        nb = min(real / (1.0 - ROOM_MIN), ROOM_GROWTH_MAX * budget_in)
        if nb > budget:
            log(label, "room: floors keep", int(real), "tris: budget", int(budget), "->", int(nb))
            budget = nb
    k, lv, tot = EW.fit_budget(R, px, idx, budget, w, F["picker"], label, floor=fl)
    out = []
    pick = {}
    for i, li in zip(idx, lv):
        me = F["picker"].get(R.tkey[i], float(EW.LEVELS[li]))
        pick[int(i)] = (float(EW.LEVELS[li]), me)
        if me is not None and len(me.polygons):
            out.append((int(i), me))
    if isl_rows:
        # check-first: per island / far rock piece the px the LOD rule uses (px_eff; proxies: 2 x box diagonal), px
        # (the floor's views), source triangles, the floor, the chosen level and the triangles it keeps
        rows = [dict(name=R.name[i], px_lod=round(float(px[i])), px=round(p), src=int(R.tris[i]), floor=round(f, 4),
                     level=pick[i][0], tris=F["picker"].tris(pick[i][1]) if pick[i][1] is not None else 0)
                for i, p, f in sorted(isl_rows, key=lambda x: -x[1])]
        log(label, "islands:", json.dumps(rows, separators=(",", ":")))
        F.setdefault("check", {}).setdefault("islands", {})[label] = dict(
            n=len(rows), tris=int(sum(r["tris"] for r in rows)), src=int(sum(r["src"] for r in rows)),
            under_300=int(sum(1 for r in rows if r["tris"] < 300 and r["px"] > 0)))
    return out, tot


def _clean_items(lst, label=None):
    keep = []
    for it in lst:
        m2 = clean_mesh(it.mesh)
        if m2 is None:
            continue
        it.mesh = m2
        keep.append(it)
    lst[:] = keep
    if label is not None and DEDUPE:
        _dedupe_items(lst, label)


DEDUPE = True                  # full: faces repeating another face's corners (any item, any winding) and faces under
                               # bake_rules.TINY_AREA are dropped before the unwrap (the raw bake had 121k exact duplicate
                               # and 37.7k zero-area triangles; the abode's Cliff Inscription showed 7.8 m2 of its visible
                               # copy 25 % darker than its twin, z-fighting)


def _dedupe_items(lst, label):
    """Drop duplicate and tiny faces across the items (world space, bake_rules.duplicate_faces / tiny_faces). The
    copy kept is the first in (hotspot pieces first, then the list's order); an item left with no face is dropped."""
    if not lst:
        return
    t0 = time.time()
    order = sorted(range(len(lst)), key=lambda j: (lst[j].hot == "", j))
    co, vi, ls, fo = [], [], [], []
    vo = lo = 0
    for j in order:
        A = ma(lst[j].mesh)
        M = np.asarray(lst[j].M, np.float64)
        co.append(A.co @ M[:3, :3].T + M[:3, 3])
        vi.append(A.vi + vo)
        ls.append(A.ls + lo)
        fo.append(np.full(A.np, j, np.int64))
        vo += A.nv
        lo += A.nl
    co, vi, ls, fo = np.concatenate(co), np.concatenate(vi), np.concatenate(ls), np.concatenate(fo)
    dup = BR.duplicate_faces(co, vi, ls)
    tiny = BR.tiny_faces(co, vi, ls) & ~dup
    bad = dup | tiny
    if not bad.any():
        log(label, "dedupe: no duplicate or tiny faces;", round(time.time() - t0, 1), "s")
        return
    gone = set()
    nd = 0
    for j in np.unique(fo[bad]):
        it = lst[j]
        m = bad[fo == j]                          # this item's faces in its own order (concat keeps it)
        if m.all():
            gone.add(int(j))
            continue
        it.mesh = submesh(it.mesh, ~m, it.name[:50] + ".dd")
        nd += 1
    lst[:] = [it for j, it in enumerate(lst) if j not in gone]
    log(label, "dedupe: dropped", int(dup.sum()), "duplicate and", int(tiny.sum()), "tiny faces;", nd,
        "pieces cut,", len(gone), "dropped whole;", round(time.time() - t0, 1), "s")
    _FC.setdefault("check", {}).setdefault("dedupe", {})[label] = dict(duplicate=int(dup.sum()), tiny=int(tiny.sum()))


def ring_stage(F, items):
    """item index -> 4x4 for the forge ring's artifacts (owners STAGE_OWNERS): turn each about the ring's axis to the
    ring's front (the point nearest the forge hold camera), then lift artifact k straight up by (k + 1) * STAGE_STEP.
    The page turns the ring all the way round, so every artifact bakes lit as it looks at the front; baked where it
    stood, the ones behind the ding came round in its shadow, facing away from the sun."""
    tilt = bpy.data.objects.get("forge.ring_tilt")
    owners = sorted({it.owner for it in items if it.owner.startswith(STAGE_OWNERS)})
    if tilt is None or not owners:
        return {}
    W = np.asarray(tilt.matrix_world, float)
    o = W[:3, 3]
    n = W[:3, 2] / np.linalg.norm(W[:3, 2])
    hold = next(x["holdFrame"] for x in EW.AREAS if x["id"] == "forge")
    pv = np.nonzero(F["views"].path)[0]                       # path frames only (the look views come after them)
    fi = int(pv[np.argmin(np.abs(np.asarray(F["frames"])[pv] - hold))])
    cam = np.asarray(F["cam_mats"][fi], float)[:3, 3]

    def unit_in_plane(v):
        v = v - n * (v @ n)
        return v / np.linalg.norm(v)
    front = unit_in_plane(cam - o)
    out = {}
    for k, own in enumerate(owners):
        js = [j for j, it in enumerate(items) if it.owner == own]
        p = np.mean([np.asarray(items[j].M, float)[:3, 3] for j in js], axis=0)
        r = unit_in_plane(p - o)
        th = math.atan2(float(np.cross(r, front) @ n), float(r @ front))
        S = np.asarray(Matrix.Translation(Vector(o + np.array([0.0, 0.0, (k + 1) * STAGE_STEP]))) @
                       Matrix.Rotation(th, 4, Vector(n)) @ Matrix.Translation(Vector(-o)), float)
        for j in js:
            out[j] = S
        log("stage", own, "turned %.0f deg, lifted %.0f m" % (math.degrees(th), (k + 1) * STAGE_STEP))
    return out


def unstage(ob, C):
    """Put staged vertices (build_bake_object's ``stage``) back where they belong."""
    if "co_rest" not in C:
        return
    me = ob.data
    me.vertices.foreach_set("co", np.ascontiguousarray(C["co_rest"], np.float32).ravel())
    me.update()
    try:
        me.normals_split_custom_set(C["cn_rest"])
    except Exception as e:
        log("WARN custom normals", e)
    C["co"], C["cn"] = C.pop("co_rest"), C.pop("cn_rest")


def vc_eligible(F, items):
    """Per item: may bake as vertex colours (VC_SMALL). Not hotspot items (the content the reader studies), turning
    objects (staged for the bake), the split terrain, roof sheets, and no piece with a glowing or detail-class
    (rock / ground / paving) material."""
    R = F["R"]
    split = {R.owner[i] for i in F["big"]}
    turning = EW.turning_owners()
    out = np.zeros(len(items), bool)
    for j, it in enumerate(items):
        if it.hot or it.owner in turning or it.owner in split or is_sheet(it):
            continue
        mats = [m for m in ma(it.mesh).mats if m]
        if any(F["minfo"].get(m, {}).get("emission", False) or _mat_class(F, m) for m in mats):
            continue
        out[j] = True
    return out


def small_share(items, g):
    """Per item: the share of its surface in UV islands under VC_ISLAND_TEXELS long, laid out as unwrap_group lays
    them (project_box26 on the CELL_TEXELS grid, roof sheets by slope) at each item's density x g."""
    if not items:
        return np.zeros(0)
    rho = [it.rho for it in items]
    for it in items:
        it.rho = max(it.rho * g, RHO_MIN)
    try:
        C = concat(items, lambda it, m: 0, scale_about_centre=True)
    finally:
        for it, r in zip(items, rho):
            it.rho = r
    if not len(C["ls"]):
        return np.zeros(len(items))
    co, vi = cut_grid(C["co"], C["vi"], C["ls"], CELL_TEXELS)
    u0 = project_box26(co, vi, C["ls"])
    u0, _ = sheet_uv(C, items, u0)
    u0, _ = merge_charts(co, vi, C["ls"], u0, fixed=_sheet_faces(C, items))
    isl, f_of_l = uv_islands(np.ascontiguousarray(u0, np.float32), vi, C["ls"])
    dims = BR.island_dims(u0, isl[f_of_l], int(isl.max()) + 1)
    small = dims[isl, 0] < VC_ISLAND_TEXELS
    _, a3 = BR.poly_normals(co, vi, C["ls"])
    tot = np.bincount(C["fitem"], a3, len(items))
    sm = np.bincount(C["fitem"], a3 * small, len(items))
    return np.where(tot > 0, sm / np.maximum(tot, 1e-30), 0.0)


def split_small(F, items, g, label):
    """VC_SMALL: (atlas items, vertex-colour items): the eligible items (vc_eligible) with at least VC_SMALL_SHARE of
    their surface in islands under VC_ISLAND_TEXELS at density scale g (small_share) bake as vertex colours."""
    if not VC_SMALL or not items:
        return items, []
    t0 = time.time()
    idx = np.nonzero(vc_eligible(F, items))[0]
    if not len(idx):
        return items, []
    share = small_share([items[j] for j in idx], g)
    to = set(idx[share >= VC_SMALL_SHARE].tolist())
    log(label, "small-piece test at density x%.3f:" % g, len(idx), "eligible,", len(to), "as vertex colours;",
        round(time.time() - t0, 1), "s")
    return [it for j, it in enumerate(items) if j not in to], [it for j, it in enumerate(items) if j in to]


def even_atlases(atlases, label):
    """After packing: halve an atlas while its density (texels_per_unit) stays at least ATLAS_EVEN x the lowest of the
    chunk's atlases (its UVs are 0-1, so only the image shrinks). The texel budget goes by demand before the pack,
    and a small group packs looser than its demand says."""
    tpu = [a_["texels_per_unit"] for a_ in atlases if a_.get("texels_per_unit")]
    if len(tpu) < 2:
        return
    lo = min(tpu)
    for at in atlases:
        t = at.get("texels_per_unit")
        if not t:
            continue
        size0 = at["size"]
        while at["size"] > 1024 and t * 0.5 >= ATLAS_EVEN * lo:
            at["size"] //= 2
            t *= 0.5
        if at["size"] != size0:
            at["texels_per_unit"] = round(t, 3)
            log(label, "atlas", at["name"], size0, "->", at["size"], "px (density %.3f, the chunk's lowest %.3f)"
                % (t, lo))


def bake_chunk(F, cid, a):
    """Bake one area chunk -> CACHE_DIR/<cid>/ (EXRs, export.blend, items.json, bake_meta.json); post -> raw."""
    R, ids = F["R"], F["ids"]
    k = ids.index(cid)
    T = {}
    t0 = time.time()
    sc = F["sc"]
    plan = next(c for c in _plan()["chunks"] if c["id"] == cid)
    n0, n1 = plan["need"]
    vneed = (F["frames"] >= n0) & (F["frames"] <= n1)
    cv = F["views"].subset(vneed)                     # path and look views inside the need range
    cmats = cv.mats
    CAMINFO.update(cam_mats=cmats, path=cv.path, tan_v=F["tv"], aspect_w=F["aw"])
    idx = np.nonzero(F["grp"] == k)[0]
    items = []
    used = 0
    split_tris = {}
    occ_meshes = []
    for i, (me, fch, fd) in F["big"].items():
        mk = fch == k
        if mk.any():
            bins = list(BIG_BINS) + [np.inf]
            for b0, b1 in zip(bins[:-1], bins[1:]):
                m = mk & (fd >= b0) & (fd < b1)
                if not m.any():
                    continue
                nm = "%s.%s.d%d" % (R.name[i], cid, int(b0))
                sub = submesh(me, m, nm)
                items.append(_full_item(F, i, sub, "atlas", cid, d=max(b0, 8.0), name=nm))
                t = _tris(sub)
                used += t
                split_tris[R.name[i]] = split_tris.get(R.name[i], 0) + t
        if (~mk).any():
            occ_meshes.append((submesh(me, ~mk, R.name[i] + ".occ." + cid), R.mw[i], R.name[i]))
    log(cid, "split terrain triangles in the chunk:", json.dumps(split_tris))
    w = EW.lod_weights(R, idx, F["members"])
    own = np.array([R.top[i] == cid or R.owner[i] in F["members"] for i in idx], bool)
    other = np.array([R.top[i] in EW.AREA_NAMES and R.top[i] != cid for i in idx], bool)
    w = np.where(own, EW.LOD_WEIGHTS["focus"], np.where(other, EW.LOD_WEIGHTS["other"], w))
    picked, tot = _lod_items(F, idx, cid, max(a.atlas_tris - used, 50_000), cid, w=w, isl_views=vneed,
                             isl_cap=ISLAND_FLOOR_CAP)
    for i, me in picked:
        items.append(_full_item(F, i, me, "atlas", cid))
    T["lod"] = round(time.time() - t0, 1)
    _clean_items(items, cid)
    reach = {aid: x for aid, x in zip(HOLD_AREAS, HOLD_AREA_NEAR)}
    turning = EW.turning_owners()
    nb = 0
    for it in items:
        lo, hi = _item_box(it)
        # turning objects show every side wherever the ring or the flight puts them: the hold density throughout
        if it.owner in turning:
            it.boost = HOLD_RHO
        else:
            it.boost = _near_hold_box(F, lo, hi, max(HOLD_RHO_NEAR, reach.get(cid, 0.0)))
        nb += int(it.boost > 1.0)
        A = ma(it.mesh)
        L = np.asarray(it.M, float)[:3, :3]
        it.rho = rho_of(it.dmin) * detail_boost(it.name) * it.boost
        it.demand = A.area * abs(np.linalg.det(L)) ** (2.0 / 3.0) * it.rho ** 2
    items = split_heavy(items, cmats, F["tv"], F["aw"], dscale=cv.dscale)
    cap = ATLAS_PX * ATLAS_PX * ATLAS_FILL
    units = a.chunk_atlases if a.chunk_atlases else FULL_ATLASES_BY_AREA.get(cid, FULL_ATLASES)
    limit = units * cap
    items_vc = []
    vc_info = {}
    if VC_SMALL:
        # measured at the density scale the atlas would give with every piece in it; the pieces that move free texels,
        # so the rest are measured again at the larger scale and the ones whose islands grew past the limit go back
        total0 = sum(it.demand for it in items)
        g0 = min(1.0, math.sqrt(limit / total0)) if total0 > 0 else 1.0
        items, items_vc = split_small(F, items, g0, cid)
        total1 = sum(it.demand for it in items)
        g1 = min(1.0, math.sqrt(limit / total1)) if total1 > 0 else 1.0
        if items_vc and g1 > g0 * 1.02:
            back, items_vc = split_small(F, items_vc, g1, cid)
            items += back
        vc_info = dict(items=len(items_vc), tris=int(sum(_tris(it.mesh) for it in items_vc)),
                       demand=round(sum(it.demand for it in items_vc)), g0=round(g0, 3), g1=round(g1, 3))
        log(cid, "small pieces as vertex colours:", json.dumps(vc_info))
    total = sum(it.demand for it in items)
    gscale = 1.0
    if total > limit:
        gscale = math.sqrt(limit / total)
        for it in items:
            it.rho = max(it.rho * gscale, RHO_MIN)
            A = ma(it.mesh)
            L = np.asarray(it.M, float)[:3, :3]
            it.demand = A.area * abs(np.linalg.det(L)) ** (2.0 / 3.0) * it.rho ** 2
    log(cid, "items", len(items), "near holds", nb, "texel demand %.1fM (limit %.1fM) density scale %.3f"
        % (total / 1e6, limit / 1e6, gscale))
    items.sort(key=lambda it: (it.hot == "", it.top, it.owner, it.name))
    groups = []
    cur = None
    for it in items:
        if cur is None or (cur["demand"] + it.demand > cap and cur["demand"] > 0):
            cur = dict(demand=0.0, items=[])
            groups.append(cur)
        cur["items"].append(it)
        cur["demand"] += it.demand
    if len(groups) > 1 and groups[-1]["demand"] < 0.15 * cap:
        # a few spill-over pieces: into the previous atlas (the packer shrinks its layout to fit) rather than a
        # nearly empty atlas of their own
        last = groups.pop()
        groups[-1]["items"] += last["items"]
        groups[-1]["demand"] += last["demand"]
    atlases = []
    for j, g in enumerate(groups):
        size = ATLAS_PX
        while size > 1024 and g["demand"] <= 1.3 * (size // 2) ** 2 * ATLAS_FILL:
            size //= 2
        for it in g["items"]:
            it.atlas = j
        atlases.append(dict(name="%s_A%d" % (cid, j), zone=cid, size=size, demand=round(g["demand"]),
                            items=len(g["items"]), tris=int(sum(_tris(it.mesh) for it in g["items"]))))
    t1 = time.time()
    for j, g in enumerate(groups):
        atlases[j]["uv_area"] = round(unwrap_group(g["items"], atlases[j]["name"], atlases[j]["size"]), 3)
        pi = UNWRAP_INFO.get(atlases[j]["name"], {})
        atlases[j]["texels_per_unit"] = pi.get("texels_per_unit")
        atlases[j]["islands"] = pi.get("islands")
        atlases[j]["sheet_faces"] = pi.get("sheet_faces", 0)
    even_atlases(atlases, cid)
    T["unwrap"] = round(time.time() - t1, 1)
    log(cid, "atlases", json.dumps(atlases))
    hot_here = sorted({it.hot for it in items} - {""})
    want_hot = sorted(h for h, ar in F["hot_area"].items() if ar == cid)
    missing_hot = [h for h in want_hot if h not in hot_here]
    if missing_hot:
        log("WARN", cid, "hotspots without baked faces (vegetation or nothing visible):", missing_hot)
    if a.plan_only:
        tris_items = int(sum(_tris(it.mesh) for it in items + items_vc))
        isl = F.get("check", {}).get("islands", {}).get(cid, {})
        out = dict(id=cid, plan_only=True, atlases=atlases, gscale=gscale, units=units, items=len(items),
                   tris_blender=tris_items, split_tris=split_tris, lod_tris=int(tot), islands=isl,
                   missing_hotspots=missing_hot, prev=_prev_chunk_stats(cid), vc_small=vc_info,
                   dedupe=F.get("check", {}).get("dedupe", {}).get(cid, {}))
        dump(os.path.join(BAKE_OUT, "plan_%s.json" % cid), out)
        p = out["prev"]
        log("PLAN", cid, "triangles", tris_items, "(split terrain %s)" % json.dumps(split_tris), "gscale %.3f" % gscale,
            ("(last bake %.3f, %+.1f%%)" % (p["gscale"], 100.0 * (gscale / p["gscale"] - 1.0))
             if p.get("gscale") else ""),
            "uv_area", [x["uv_area"] for x in atlases], ("(last bake %s)" % p["uv_area"]) if p.get("uv_area") else "",
            "islands", json.dumps(isl))
        return out

    # materials and the bake object
    src, fallback = _src_materials(F, items + items_vc)
    prop_names = object_attr_names(src.values())
    images, albedo, normals = [], [], []
    for at in atlases:
        images.append(bpy.data.images.new(at["name"], at["size"], at["size"], alpha=False, float_buffer=True))
        albedo.append(bpy.data.images.new(at["name"] + "_albedo", at["size"], at["size"], alpha=False,
                                          float_buffer=True))
        if DENOISE_NORMAL:
            normals.append(bpy.data.images.new(at["name"] + "_normal", at["size"], at["size"], alpha=False,
                                               float_buffer=True))
    slot_list, slot_idx, img_nodes = [], {}, []

    def slot_at(it, mname):
        key = (it.atlas, mname)
        if key not in slot_idx:
            m = F["rw"].get(mname, fallback).copy()
            m.name = "%s@%s" % (mname or "none", atlases[it.atlas]["name"])
            nt = m.node_tree
            if nt is None:
                _use_nodes(m)
                nt = m.node_tree
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = images[it.atlas]
            nt.nodes.active = tn
            img_nodes.append((tn, it.atlas))
            slot_idx[key] = len(slot_list)
            slot_list.append(m)
        return slot_idx[key]

    vc_slots, vc_map = [], {}

    def slot_vc(it, mname):
        if mname not in vc_map:
            vc_map[mname] = len(vc_slots)
            vc_slots.append(F["rw"].get(mname, fallback))
        return vc_map[mname]

    coll = bpy.data.collections.new("bake.objects." + cid)
    sc.collection.children.link(coll)
    t1 = time.time()
    ob_at, C_at = build_bake_object("bake.atlas." + cid, items, slot_at, [], prop_names, coll,
                                    stage=ring_stage(F, items))
    ob_at.shadow_terminator_geometry_offset = TERMINATOR_OFFSET
    for m in slot_list:
        ob_at.data.materials.append(m)
    mats = [m.name for m in ob_at.data.materials]
    emis = np.array([F["minfo"].get(m.split("@")[0], {}).get("emission", False) for m in mats] + [False], bool)
    set_attr(ob_at.data, "w_glow", "INT", "FACE", emis[C_at["mi"]].astype(np.int32))
    fa = np.array([it.atlas for it in items], np.int32)[C_at["fitem"]]
    set_attr(ob_at.data, "w_atlas", "INT", "FACE", fa)
    # the small pieces (VC_SMALL): their own vertex-colour bake object; both stay in the scene for both bakes
    ob_vc = C_vc = None
    if items_vc:
        ob_vc, C_vc = build_bake_object("bake.vc." + cid, items_vc, slot_vc, [], prop_names, coll, occ=[C_at])
        ob_vc.shadow_terminator_geometry_offset = TERMINATOR_OFFSET
        set_attr(ob_vc.data, VC_BAKE_ATTR, "FLOAT", "POINT", np.ones(len(ob_vc.data.vertices), np.float32))
        for m in vc_slots:
            ob_vc.data.materials.append(m)
        set_attr(ob_vc.data, "w_glow", "INT", "FACE", np.zeros(len(C_vc["ls"]), np.int32))
    # the scene around it: hide what the bake object replaces, bring back what those owners also carry
    hid = {}
    owners = {it.owner for it in items + items_vc}
    _hide(owners, hid)
    _hide([R.name[i] for i in F["big"]], hid)
    occ_coll = bpy.data.collections.new("bake.occ." + cid)
    sc.collection.children.link(occ_coll)
    occ_objs = []
    for me, M, nm in occ_meshes:
        o = bpy.data.objects.new("bake.occluder." + nm, me)
        o.matrix_world = Matrix(np.asarray(M, float).tolist())
        occ_coll.objects.link(o)
        occ_objs.append(o)
    lo = R.lo[idx].min(0) - OCC_PAD if len(idx) else np.full(3, -1e9)
    hi = R.hi[idx].max(0) + OCC_PAD if len(idx) else np.full(3, 1e9)
    grp = F["grp"]
    occ_recs = []
    for o in owners:
        if o not in F["mixed"]:
            continue
        for j in F["orecs"][o]:
            if grp[j] in (k, -99, -3) or F["ex"][j]:
                continue
            if (R.hi[j] >= lo).all() and (R.lo[j] <= hi).all():
                occ_recs.append(j)
    occ_objs += _occluder_objects(F, occ_recs, occ_coll, cid)
    log(cid, "hid", len(hid), "objects; occluder copies", len(occ_recs), "+", len(occ_meshes), "split rests")
    T["build"] = round(time.time() - t1, 1)
    _bake_setup(F, a)
    cdir = os.path.join(CACHE_DIR, cid)
    os.makedirs(cdir, exist_ok=True)
    deselect_all()
    ob_at.select_set(True)
    bpy.context.view_layer.objects.active = ob_at
    sc.cycles.samples = a.samples
    t1 = time.time()
    bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT"}, uv_layer="bake",
                        margin=BAKE_MARGIN, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
    T["bake_atlas"] = round(time.time() - t1, 1)
    log(cid, "baked atlases in", T["bake_atlas"], "s")
    for tn, j in img_nodes:
        tn.image = albedo[j]
    sc.cycles.samples = BAKE_QUALITY[a.quality]["albedo"]
    t1 = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, uv_layer="bake", margin=BAKE_MARGIN,
                        margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")
    T["bake_albedo"] = round(time.time() - t1, 1)
    if normals:
        # the denoiser's normal guide (world space: the bake object has no transform), so its filter also stops at
        # island edges where the surface turns, not only where the albedo changes
        for tn, j in img_nodes:
            tn.image = normals[j]
        sc.cycles.samples = BAKE_QUALITY[a.quality]["normal"]
        t1 = time.time()
        try:
            bpy.ops.object.bake(type="NORMAL", normal_space="OBJECT", normal_r="POS_X", normal_g="POS_Y",
                                normal_b="POS_Z", uv_layer="bake", margin=BAKE_MARGIN, margin_type="EXTEND",
                                use_clear=True, target="IMAGE_TEXTURES")
        except Exception as e:
            log("WARN", cid, "normal bake failed (denoise without the normal guide):", e)
            normals = []
        T["bake_normal"] = round(time.time() - t1, 1)
    sc.cycles.samples = a.samples
    unstage(ob_at, C_at)
    if ob_vc is not None:
        # after unstage: the ring's artifacts stand where they belong while the small pieces bake
        me_vc = ob_vc.data
        ca = me_vc.color_attributes.new("bake_col", "FLOAT_COLOR", "CORNER")
        me_vc.color_attributes.active_color = ca
        try:
            me_vc.color_attributes.render_color_index = me_vc.color_attributes.active_color_index
        except Exception:
            pass
        deselect_all()
        ob_vc.select_set(True)
        bpy.context.view_layer.objects.active = ob_vc
        sc.cycles.samples = a.vc_samples
        t1 = time.time()
        bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT"},
                            target="VERTEX_COLORS")
        sc.cycles.samples = a.samples
        T["bake_vc"] = round(time.time() - t1, 1)
        log(cid, "baked the small pieces as vertex colours in", T["bake_vc"], "s")
    for tn, j in img_nodes:
        tn.image = images[j]
    for im in images + albedo + normals:
        im.filepath_raw = os.path.join(cdir, im.name + ".exr")
        im.file_format = "OPEN_EXR"
        im.save()
    os.makedirs(os.path.join(BAKE_OUT, "raw_preview"), exist_ok=True)
    for im in images:
        preview(im, os.path.join(BAKE_OUT, "raw_preview", im.name + ".png"))
    items_json = [dict(kind="atlas", index=j, zone=it.zone, hot=it.hot, top=it.top, owner=it.owner, name=it.name,
                       atlas=it.atlas, dmin=round(min(it.dmin, 1e6), 1), rho=round(it.rho, 2))
                  for j, it in enumerate(items)]
    vc_json = [dict(kind="vc", index=j, zone=it.zone, hot="", top=it.top, owner=it.owner, name=it.name,
                    dmin=round(min(it.dmin, 1e6), 1)) for j, it in enumerate(items_vc)]
    meta = dict(chunk=cid, atlases=atlases, hotspots=F["hot_labels"], samples=a.samples, light=BAKE_LIGHT,
                gscale=gscale, units=units, tris=dict(atlas=int(sum(_tris(it.mesh) for it in items)),
                                                      vc=int(sum(_tris(it.mesh) for it in items_vc))),
                missing_hotspots=missing_hot, need=plan["need"], hold=plan["hold"], vc_small=vc_info,
                vc_samples=a.vc_samples, normal_guide=bool(normals), quality=a.quality,
                bake_settings=bake_settings(a, sc))
    dump(os.path.join(cdir, "items.json"), items_json, indent=None)
    dump(os.path.join(cdir, "items_vc.json"), vc_json, indent=None)
    bpy.data.libraries.write(os.path.join(cdir, "export.blend"), {ob_at} | ({ob_vc} if ob_vc is not None else set()),
                             fake_user=True)
    # put the scene back for the next chunk
    _restore(hid)
    for o in occ_objs:
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(occ_coll)
    T["bake_total"] = round(time.time() - t0, 1)
    out = dict(id=cid, atlases=atlases, gscale=gscale, units=units, times=T, items=len(items),
               quality=a.quality, bake_settings=meta["bake_settings"],
               tris_blender=meta["tris"]["atlas"] + meta["tris"]["vc"], tris_vc=meta["tris"]["vc"],
               vc_small=vc_info, missing_hotspots=missing_hot, hidden=len(hid), occluders=len(occ_objs),
               dedupe=F.get("check", {}).get("dedupe", {}).get(cid, {}))
    if not a.no_post:
        t1 = time.time()
        try:
            out["glb"] = post_chunk(cid, ob_at, items_json, meta, a, in_session=True, ob_vc=ob_vc)
        except Exception as e:                         # the EXRs and export.blend are kept: 'post' can redo it
            import traceback
            traceback.print_exc()
            log("WARN post failed for", cid, e)
            out["post_error"] = str(e)
        T["post"] = round(time.time() - t1, 1)
    meta["times"] = T
    dump(os.path.join(cdir, "bake_meta.json"), meta)
    # free this chunk's data
    me_at = ob_at.data
    bpy.data.objects.remove(ob_at)
    bpy.data.meshes.remove(me_at)
    if ob_vc is not None:
        me_vc = ob_vc.data
        bpy.data.objects.remove(ob_vc)
        bpy.data.meshes.remove(me_vc)
    for m in slot_list:
        bpy.data.materials.remove(m)
    for im in images + albedo + normals:
        bpy.data.images.remove(im)
    for me, _, _ in occ_meshes:
        bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)
    T["total"] = round(time.time() - t0, 1)
    out["times"] = T
    os.makedirs(os.path.join(BAKE_OUT, "chunks"), exist_ok=True)
    dump(os.path.join(BAKE_OUT, "chunks", cid + ".json"), out, indent=1)
    log("CHUNK DONE", cid, json.dumps(T))
    return out


def _prev_chunk_stats(cid):
    """gscale, atlas uv_area and triangles of the last real bake of chunk cid (bake/chunks/<cid>.json), for the
    plan-only comparison; {} when there is none."""
    p = os.path.join(BAKE_OUT, "chunks", cid + ".json")
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            r = json.load(fh)
    except Exception:
        return {}
    if r.get("plan_only"):
        return {}
    return dict(gscale=r.get("gscale"), uv_area=[x.get("uv_area") for x in r.get("atlases", [])],
                tris_blender=r.get("tris_blender"), glb_tris=(r.get("glb") or {}).get("triangles"))


_PLAN = {}


def _plan():
    if not _PLAN:
        with open(os.path.join(EW.WORK, "chunks.json"), encoding="utf-8") as fh:
            _PLAN.update(json.load(fh))
    return _PLAN


def bake_backdrop(F, a):
    """Far set + one proxy per area as vertex colours -> raw/backdrop.glb (proxies under 'proxy.<area>' Empties with
    extras {"proxyOf": area}). The area originals are hidden while it bakes: the proxies stand in for them."""
    R, ids, grp = F["R"], F["ids"], F["grp"]
    t0 = time.time()
    T = {}
    CAMINFO.update(cam_mats=F["cam_mats"], path=F["views"].path, tan_v=F["tv"], aspect_w=F["aw"])
    items = []
    used_far = 0
    used_px = collections.Counter()
    diag = np.linalg.norm(R.hi - R.lo, axis=1)
    for i, (me, fch, fd) in F["big"].items():
        for kk in sorted(set(fch.tolist())):
            if kk == -2:
                continue
            zone = "far" if kk < 0 else "proxy." + ids[kk]
            nm = "%s.%s" % (R.name[i], zone)
            sub = submesh(me, fch == kk, nm)
            items.append(_full_item(F, i, sub, "vc", zone, d=1e4, name=nm))
            if kk < 0:
                used_far += _tris(sub)
            else:
                used_px[kk] += _tris(sub)
    far_idx = np.nonzero(grp == -1)[0]
    sl = slender_mask(R, far_idx)
    # island and far-rock floors over every view: px_eff saturates at ~1536 px for nearly every island (export_web.
    # project counts a box across a look view's camera plane as filling the frame), so the floors measure their own px
    all_views = np.ones(len(F["views"]), bool)
    picked, tot_far = _lod_items(F, far_idx, "far", max(a.far_tris - used_far, 50_000), "far", floors=False,
                                 isl_views=all_views, isl_cap=ISLAND_FLOOR_CAP_FAR, far_rock=True)
    for i, me in picked:
        items.append(_full_item(F, i, me, "vc", "far"))
    log("backdrop far set", len(far_idx), "records,", tot_far + used_far, "tris (slender", int(sl.sum()), ")")
    tot_px = {}
    link_px = {}
    for kk, cid in enumerate(ids):
        idx = np.nonzero(grp == kk)[0]
        # (round 11, S3) the link stairs' structure goes in whole, outside the budget (proxy_whole)
        whole = np.array([proxy_whole(R.name[i], bool(R.inst[i])) for i in idx], bool)
        wt = 0
        for i in idx[whole]:
            me = F["picker"].get(R.tkey[i], 1.0)
            if me is not None and len(me.polygons):
                items.append(_full_item(F, i, me, "vc", "proxy." + cid))
                wt += _tris(me)
        link_px[cid] = dict(records=int(whole.sum()), tris=int(wt))
        idx = idx[~whole]
        cand = idx[diag[idx] >= PROXY_MIN_DIAG]
        score = diag[cand] * np.where([R.top[i] == cid for i in cand], 3.0, 1.0)
        cand = cand[np.argsort(-score)][:PROXY_MAX_RECS]
        pxp = np.zeros(len(R))
        pxp[cand] = diag[cand] * 2.0
        # the proxy stands in for the area outside its need range: its island floors are measured over those views
        n0, n1 = next(c["need"] for c in _plan()["chunks"] if c["id"] == cid)
        away = ~((F["frames"] >= n0) & (F["frames"] <= n1))
        bp = max(a.proxy_tris - used_px[kk], 5000)
        picked, totp = _lod_items(F, cand, cid, bp, "proxy." + cid, floors=False, px=pxp, isl_views=away,
                                  isl_cap=ISLAND_FLOOR_SHARE_PROXY * bp)
        for i, me in picked:
            items.append(_full_item(F, i, me, "vc", "proxy." + cid))
        tot_px[cid] = int(totp + used_px[kk] + wt)
        log("proxy", cid, len(cand), "records,", totp, "+", used_px[kk], "terrain tris +", wt, "whole link tris in",
            link_px[cid]["records"], "records")
    log("proxies: whole link structure", sum(v["tris"] for v in link_px.values()), "tris", json.dumps(link_px))
    _clean_items(items, "backdrop")
    T["lod"] = round(time.time() - t0, 1)
    if a.plan_only:
        out = dict(id="backdrop", plan_only=True, items=len(items),
                   tris_blender=int(sum(ma(it.mesh).np for it in items)), far_tris=int(tot_far + used_far),
                   proxy_tris=tot_px, proxy_link_tris=link_px, split_far=int(used_far),
                   islands=F.get("check", {}).get("islands", {}), prev=_prev_chunk_stats("backdrop"), times=T)
        dump(os.path.join(BAKE_OUT, "plan_backdrop.json"), out)
        log("PLAN backdrop triangles", out["tris_blender"], "(last bake %s)" % out["prev"].get("tris_blender"),
            "far", out["far_tris"], "proxies", json.dumps(tot_px))
        return out
    src, fallback = _src_materials(F, items)
    prop_names = object_attr_names(src.values())
    vc_slots, vc_map = [], {}

    def slot_vc(it, mname):
        if mname not in vc_map:
            vc_map[mname] = len(vc_slots)
            vc_slots.append(F["rw"].get(mname, fallback))
        return vc_map[mname]
    sc = F["sc"]
    coll = bpy.data.collections.new("bake.objects.backdrop")
    sc.collection.children.link(coll)
    ob_vc, C_vc = build_bake_object("bake.vc.backdrop", items, slot_vc, [], prop_names, coll)
    ob_vc.shadow_terminator_geometry_offset = TERMINATOR_OFFSET
    set_attr(ob_vc.data, VC_BAKE_ATTR, "FLOAT", "POINT", np.ones(len(ob_vc.data.vertices), np.float32))
    for m in vc_slots:
        ob_vc.data.materials.append(m)
    mats = [m.name for m in ob_vc.data.materials]
    emis = np.array([F["minfo"].get(m.split("@")[0], {}).get("emission", False) for m in mats] + [False], bool)
    set_attr(ob_vc.data, "w_glow", "INT", "FACE", emis[C_vc["mi"]].astype(np.int32))
    hid = {}
    baked = (grp >= 0) | (grp == -1)
    owners = {R.owner[i] for i in np.nonzero(baked)[0]}
    _hide(owners, hid)
    _hide([R.name[i] for i in F["big"]], hid)
    occ_coll = bpy.data.collections.new("bake.occ.backdrop")
    sc.collection.children.link(occ_coll)
    occ_recs = [j for o in owners if o in F["mixed"] for j in F["orecs"][o]
                if grp[j] == -9 and not F["ex"][j]]
    occ_objs = _occluder_objects(F, occ_recs, occ_coll, "bd")
    log("backdrop: hid", len(hid), "objects; occluder copies", len(occ_recs))
    _bake_setup(F, a)
    me_vc = ob_vc.data
    ca = me_vc.color_attributes.new("bake_col", "FLOAT_COLOR", "CORNER")
    me_vc.color_attributes.active_color = ca
    try:
        me_vc.color_attributes.render_color_index = me_vc.color_attributes.active_color_index
    except Exception:
        pass
    deselect_all()
    ob_vc.select_set(True)
    bpy.context.view_layer.objects.active = ob_vc
    sc.cycles.samples = a.vc_samples
    t1 = time.time()
    bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "EMIT"},
                        target="VERTEX_COLORS")
    sc.cycles.samples = a.samples
    T["bake_vc"] = round(time.time() - t1, 1)
    log("backdrop baked vertex colours in", T["bake_vc"], "s")
    cdir = os.path.join(CACHE_DIR, "backdrop")
    os.makedirs(cdir, exist_ok=True)
    items_json = [dict(kind="vc", index=j, zone=it.zone, hot="", top=it.top, owner=it.owner, name=it.name)
                  for j, it in enumerate(items)]
    meta = dict(chunk="backdrop", atlases=[], vc_samples=a.vc_samples, light=BAKE_LIGHT,
                quality=a.quality, bake_settings=bake_settings(a, sc),
                tris=dict(vc=int(sum(ma(it.mesh).np for it in items))))
    dump(os.path.join(cdir, "items.json"), items_json, indent=None)
    bpy.data.libraries.write(os.path.join(cdir, "export.blend"), {ob_vc}, fake_user=True)
    _restore(hid)
    for o in occ_objs:
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(occ_coll)
    out = dict(id="backdrop", items=len(items), tris_blender=meta["tris"]["vc"], hidden=len(hid),
               occluders=len(occ_objs), quality=a.quality, bake_settings=meta["bake_settings"], proxy_link_tris=link_px)
    if not a.no_post:
        t1 = time.time()
        try:
            out["glb"] = post_chunk("backdrop", ob_vc, items_json, meta, a, in_session=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            log("WARN post failed for backdrop", e)
            out["post_error"] = str(e)
        T["post"] = round(time.time() - t1, 1)
    meta["times"] = T
    dump(os.path.join(cdir, "bake_meta.json"), meta)
    me = ob_vc.data
    bpy.data.objects.remove(ob_vc)
    bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)
    T["total"] = round(time.time() - t0, 1)
    out["times"] = T
    os.makedirs(os.path.join(BAKE_OUT, "chunks"), exist_ok=True)
    dump(os.path.join(BAKE_OUT, "chunks", "backdrop.json"), out, indent=1)
    log("CHUNK DONE backdrop", json.dumps(T))
    return out


def cmd_bakefull(a):
    """Bake the requested chunks (--chunks, default: flight order, then the backdrop) in one session."""
    if PROFILE != "full":
        raise SystemExit("bakefull needs --profile full")
    order = [x["id"] for x in EW.AREAS] + ["backdrop"]
    want = [c for c in (a.chunks.split(",") if a.chunks else order) if c]
    for c in want:
        if c not in order:
            raise SystemExit("unknown chunk %r (one of %s)" % (c, ", ".join(order)))
    F = full_ctx(want)
    log("setup", F["t_setup"], "s; chunks", want)
    done = []
    for c in want:
        r = bake_backdrop(F, a) if c == "backdrop" else bake_chunk(F, c, a)
        done.append(r)
        log("PROGRESS", len(done), "of", len(want), c, json.dumps(r.get("times", {})))
    if a.plan_only:
        # no bake: the plan and the check-first numbers go to plan_stats.json (bake_stats.json keeps the last bake)
        out = dict(check=F.get("check", {}), chunks={r["id"]: r for r in done}, range_ratio=BIG_RATIO_FULL,
                   range_near=RANGE_NEAR, range_far=RANGE_FAR, terminator=TERMINATOR_OFFSET)
        dump(os.path.join(BAKE_OUT, "plan_stats.json"), out, indent=1)
        chk = F.get("check", {})
        log("PLAN SUMMARY range", json.dumps(chk.get("range_normals", {})), "border",
            json.dumps(chk.get("range_border", {})))
        for r in done:
            p = r.get("prev") or {}
            g, g0 = r.get("gscale"), p.get("gscale")
            log("PLAN SUMMARY", r["id"], "tris", r.get("tris_blender"), "(last %s)" % p.get("tris_blender"),
                "gscale", ("%.3f (last %.3f, %+.1f%%)" % (g, g0, 100.0 * (g / g0 - 1.0))) if g and g0 else g,
                "split", json.dumps(r.get("split_tris", r.get("split_far", {}))))
        return
    p = os.path.join(BAKE_OUT, "bake_stats.json")
    old = {}
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            old = json.load(fh)
    old.setdefault("chunks", {})
    for r in done:
        old["chunks"][r["id"]] = r
    old["light"] = BAKE_LIGHT
    old["samples"] = a.samples
    # the last run's quality; a partial run can mix qualities: each chunk's own entry says which it was baked at
    old["quality"] = a.quality
    old["bake_settings"] = bake_settings(a, F["sc"])
    dump(p, old, indent=1)


# ---- full post: denoise, grade, split by atlas / hotspot / glow, export -----------------------------------

def _post_atlas_pngs(atlases, cdir, a):
    tex_dir = os.path.join(BAKE_OUT, "tex")
    pv_dir = os.path.join(BAKE_OUT, "preview")
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(pv_dir, exist_ok=True)
    pngs = []
    for at in atlases:
        p = os.path.join(tex_dir, at["name"] + ".png")
        if a.skip_atlas and os.path.isfile(p):
            pngs.append(p)
            continue
        post, n_im, n_al = post_scene((at["size"], at["size"]), a.exposure, a.sat, denoise=True, quality=a.quality)
        n_im.image = bpy.data.images.load(os.path.join(cdir, at["name"] + ".exr"), check_existing=False)
        n_al.image = bpy.data.images.load(os.path.join(cdir, at["name"] + "_albedo.exr"), check_existing=False)
        nrm = _normal_guide(post, os.path.join(cdir, at["name"] + "_normal.exr"))
        t1 = time.time()
        run_post(post, p)
        pngs.append(p)
        bpy.data.images.remove(n_im.image)
        bpy.data.images.remove(n_al.image)
        if nrm is not None:
            bpy.data.images.remove(nrm)
        im = bpy.data.images.load(p, check_existing=False)
        sm = im.copy()
        sm.scale(min(1024, at["size"]), min(1024, at["size"]))
        sm.filepath_raw = os.path.join(pv_dir, at["name"] + ".png")
        sm.file_format = "PNG"
        sm.save()
        bpy.data.images.remove(sm)
        bpy.data.images.remove(im)
        log("post atlas", at["name"], at["size"], round(time.time() - t1, 1), "s")
    return pngs


def _normal_guide(post, path):
    """The baked NORMAL pass (colours 0-1, world space) as unit normals (-1..1) on the Denoise node's Normal input of
    the post scene's compositor; None (no guide) when the file is missing or the node has no such input."""
    if not os.path.isfile(path):
        return None
    ng = post.compositing_node_group
    dn = next((n for n in ng.nodes if n.bl_idname == "CompositorNodeDenoise"), None)
    if dn is None or dn.inputs.get("Normal") is None:
        return None
    src = bpy.data.images.load(path, check_existing=False)
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    bpy.data.images.remove(src)
    px = px.reshape(-1, 4)
    n = px[:, :3] * 2.0 - 1.0
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    px[:, :3] = np.where(ln > 1e-3, n / np.maximum(ln, 1e-6), 0.0)
    px[:, 3] = 1.0
    im = bpy.data.images.new("post_normal", w, h, alpha=False, float_buffer=True)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(px.ravel())
    node = ng.nodes.new("CompositorNodeImage")
    node.image = im
    ng.links.new(node.outputs["Image"], dn.inputs["Normal"])
    return im


def _weld_vc(me_vc, col):
    """bake_rules.weld_corner_colours on the joined vertex-colour bake mesh (world space): the corners at one point
    (positions within VC_WELD_TOL, across items, so chunk and distance cuts join), on one side of a crease (the bake
    mesh's own corner normals, within VC_WELD_DEG) and of the same glow class get one colour; unsampled black corners
    take their neighbours' colour. Returns (colours, info)."""
    t0 = time.time()
    nv, nl, npl = len(me_vc.vertices), len(me_vc.loops), len(me_vc.polygons)
    co = np.empty(nv * 3, np.float32)
    me_vc.vertices.foreach_get("co", co)
    vi = np.empty(nl, np.int32)
    me_vc.loops.foreach_get("vertex_index", vi)
    ls = np.empty(npl, np.int32)
    me_vc.polygons.foreach_get("loop_start", ls)
    cn = np.empty(nl * 3, np.float32)
    try:
        me_vc.corner_normals.foreach_get("vector", cn)
        cn = cn.reshape(nl, 3)
    except Exception as e:
        log("WARN vc weld: no corner normals (%s); smooth normals from the positions instead" % e)
        cn = None
    grp = get_attr(me_vc, "w_glow", npl, 1) if me_vc.attributes.get("w_glow") is not None else None
    out, info = BR.weld_corner_colours(co.reshape(nv, 3), vi, ls, col, cn=cn, group=grp)
    info.update(tol=BR.VC_WELD_TOL, deg=BR.VC_WELD_DEG, seconds=round(time.time() - t0, 1))
    log("vc weld:", json.dumps(info))
    return np.ascontiguousarray(out, np.float32), info


def _post_vc(me_vc, cdir, a, fill=False, tag="vc"):
    """Weld (VC_WELD), grade and write the bake's corner colours ('bake_col', linear) to 'Col' (sRGB bytes). The
    export.blend in bakecache keeps the raw 'bake_col', so a post-only run redoes this from the bake. fill: corners the
    bake left unsampled take their neighbours' colour first (bake_rules.fill_missing_corners; the areas' small pieces,
    whose feet sit in floors and beams). tag: the file stem of the graded buffers in cdir. Returns the weld's info
    (empty when VC_WELD is off), with the fill's under "fill"."""
    nl = len(me_vc.loops)
    if not nl:
        return {}
    col = get_attr(me_vc, "bake_col", nl, 4)
    info = {}
    if VC_WELD:
        col, info = _weld_vc(me_vc, col)
    if fill:
        nv, npl = len(me_vc.vertices), len(me_vc.polygons)
        co = np.empty(nv * 3, np.float32)
        me_vc.vertices.foreach_get("co", co)
        vi = np.empty(nl, np.int32)
        me_vc.loops.foreach_get("vertex_index", vi)
        ls = np.empty(npl, np.int32)
        me_vc.polygons.foreach_get("loop_start", ls)
        col, finfo = BR.fill_missing_corners(co.reshape(nv, 3), vi, ls, col)
        col = np.ascontiguousarray(col, np.float32)
        info = dict(info, fill=finfo)
        log("vc fill:", json.dumps(finfo))
    W = 2048
    H = int(math.ceil(nl / W))
    buf = np.zeros((H * W, 4), np.float32)
    buf[:nl] = col
    buf[:, 3] = 1.0
    vim = bpy.data.images.new(tag + "_lin", W, H, alpha=False, float_buffer=True)
    vim.pixels.foreach_set(buf.ravel())
    vim.filepath_raw = os.path.join(cdir, tag + "_lin.exr")
    vim.file_format = "OPEN_EXR"
    vim.save()
    post, n_im, n_al = post_scene((W, H), a.exposure, a.sat, denoise=False)
    n_im.image = bpy.data.images.load(vim.filepath_raw, check_existing=False)
    p = run_post(post, os.path.join(cdir, tag + "_graded.png"))
    g = load_png_linear_bytes(p).reshape(-1, 4)[:nl]
    old = me_vc.color_attributes.get("Col")
    if old is not None:
        me_vc.color_attributes.remove(old)
    cattr = me_vc.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    g[:, 3] = 1.0
    cattr.data.foreach_set("color_srgb", np.ascontiguousarray(g, np.float32).ravel())
    bpy.data.images.remove(n_im.image)
    bpy.data.images.remove(vim)
    log("graded", nl, "vertex colours; mean sRGB", g[:, :3].mean(0).round(3).tolist())
    return info


def _emit_small(cid, mv, cdir, a, emit, mats, stats):
    """post_chunk's small pieces (VC_SMALL): weld, fill and grade the vertex colours of the bake mesh mv, then emit
    them in spatial chunk pieces, one 'baked.vc' material per surface class (extras sectSurface on metal / glaze)."""
    info = _post_vc(mv, cdir, a, fill=True, tag="vc_small")
    stats["vc_small"] = info
    npl = len(mv.polygons)
    fmi = np.empty(npl, np.int32)
    mv.polygons.foreach_get("material_index", fmi)
    srf = []
    for sm in mv.materials:
        src = sm.name.split("@")[0] if sm is not None else ""
        srf.append(surface_class(src, sm.get(MAT_TAG) if sm is not None else None) or "")
    fsrf = np.array(srf + [""], object)[np.clip(fmi, 0, len(srf))]

    def vc_area_mat(sf):
        key = ("vc_small", sf)
        if key not in mats:
            m = bpy.data.materials.new("baked.vc" + ((".surface." + sf) if sf else ""))
            _use_nodes(m)
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            vc = nt.nodes.new("ShaderNodeVertexColor")
            vc.layer_name = "Col"
            nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
            b.inputs["Roughness"].default_value = 1.0
            if sf:
                m["sectSurface"] = sf
            m["baked"] = True
            mats[key] = m
        return mats[key]
    mat_of_face = np.empty(npl, object)
    for sf in sorted(set(fsrf.tolist())):
        mat_of_face[fsrf == sf] = vc_area_mat(sf)
    fc = np.empty(npl * 3, np.float32)
    mv.polygons.foreach_get("center", fc)
    fc = fc.reshape(-1, 3)
    for sf in sorted(set(fsrf.tolist())):
        stem = "%s.baked.vc%s" % (cid, (".surface." + sf) if sf else "")
        for ci, fs in enumerate(kd_chunks(fc, np.nonzero(fsrf == sf)[0], CHUNK_FACES)):
            m = np.zeros(npl, bool)
            m[fs] = True
            if emit("%s.c%d" % (stem, ci), m, mat_of_face, uv=False, col=True, extras=dict(chunk=1),
                    src=mv) is not None:
                stats["vc_chunks"] += 1
    stats["vc_faces"] = dict(collections.Counter(np.where(fsrf == "", "plain", fsrf).tolist()))


def export_post_scene(path, objects):
    """glTF of `objects` alone: they move into the scene 'web.post', which is the active scene for the exporter
    (the 5.2 exporter must see one scene; the sect's own scene stays out of it)."""
    ps = bpy.data.scenes.get("web.post") or bpy.data.scenes.new("web.post")
    for ob in list(ps.collection.objects):
        ps.collection.objects.unlink(ob)
    for ob in objects:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        ps.collection.objects.link(ob)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kw = dict(filepath=path, export_format="GLB", use_selection=False, use_active_scene=True, export_extras=True,
              export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
              export_animations=False, export_materials="EXPORT", export_texcoords=True, export_normals=False,
              export_tangents=False, export_vertex_color="MATERIAL", export_image_format="AUTO",
              export_draco_mesh_compression_enable=False, export_gpu_instances=False)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    for k in list(kw):
        if k not in props:
            kw.pop(k)
    win = bpy.context.window
    prev = win.scene if win is not None else None
    try:
        # the exporter itself sets window.scene per glTF scene and puts back the context scene it started with,
        # so switch the window's scene (a temp_override would leave 'web.post' as the session's scene)
        if win is not None:
            win.scene = ps
            bpy.ops.export_scene.gltf(**kw)
        else:
            with bpy.context.temp_override(scene=ps, view_layer=ps.view_layers[0]):
                bpy.ops.export_scene.gltf(**kw)
    except Exception as e:
        if win is not None:
            win.scene = prev
        # fallback: the objects in the context scene, selected (the prototype's export_baked)
        log("WARN scene override export failed (%s); exporting the selection from the context scene" % e)
        for ob in objects:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            bpy.context.scene.collection.objects.link(ob)
        export_baked(path, objects)
        for ob in objects:
            bpy.context.scene.collection.objects.unlink(ob)
            ps.collection.objects.link(ob)
    if win is not None and prev is not None:
        win.scene = prev
    log("wrote", path, os.path.getsize(path))


def post_chunk(cid, ob_bake, items, meta, a, in_session=False, ob_vc=None):
    """Denoise + grade the chunk's atlases (or its vertex colours), split the bake mesh into export objects and
    write raw/<cid>.glb. ob_vc: the chunk's small pieces (VC_SMALL), welded, filled and graded like the backdrop's
    vertex colours and exported as '<cid>.baked.vc[.surface.<class>].c<n>' ('baked.vc' materials). Paving faces carry
    PAVE_UV, metal and glaze faces their own materials (extras sectSurface). Returns glb_stats."""
    cdir = os.path.join(CACHE_DIR, cid)
    atlases = meta.get("atlases") or []
    T = {}
    t0 = time.time()
    me = ob_bake.data
    npl = len(me.polygons)
    made = []
    mats = {}
    glow_strength = {}
    imgs = []

    def new_ob(name, data, extras=None, parent=None):
        ob = bpy.data.objects.new(name, data)
        for kk, v in (extras or {}).items():
            ob[kk] = v
        if parent is not None:
            ob.parent = parent
        made.append(ob)
        return ob

    pave = {}                                     # mesh name -> per-loop paving coordinates (PAVE_UV)

    def emit(name, fmask, mat_of_face, uv=True, col=False, extras=None, parent=None, src=None, pave_faces=None):
        """pave_faces (per face of the source, optional): when any face of the mask is paving or tiles, the piece gets
        PAVE_UV (TEXCOORD_1, the exporter writes v as 1 - v): paving corners the source object's local x, y ('o_co'),
        tiles corners the sheet's own UVs ('UVMap'), other corners 0."""
        sm = me if src is None else src
        A = submesh_arrays(sm, fmask)
        if not len(A["fsel"]):
            return None
        ms = sorted(set(mat_of_face[A["fsel"]].tolist()), key=lambda m: m.name)
        mi = np.array([ms.index(m) for m in mat_of_face[A["fsel"]]], np.int32)
        m2 = make_mesh(name, A["co"], A["vi"], A["ls"], mi)
        for m in ms:
            m2.materials.append(m)
        if uv:
            src_uv = np.empty(len(sm.loops) * 2, np.float32)
            sm.uv_layers["bake"].data.foreach_get("uv", src_uv)
            lay = m2.uv_layers.new(name="bake")
            lay.data.foreach_set("uv", src_uv.reshape(-1, 2)[A["lsel"]].ravel())
            if pave_faces is not None and pave_faces[A["fsel"]].any() and sm.attributes.get("o_co") is not None:
                if sm.name not in pave:
                    nv_, nl_, np_ = len(sm.vertices), len(sm.loops), len(sm.polygons)
                    oc = get_attr(sm, "o_co", nv_, 3)
                    vi_ = np.empty(nl_, np.int32)
                    sm.loops.foreach_get("vertex_index", vi_)
                    ls_ = np.empty(np_, np.int32)
                    sm.polygons.foreach_get("loop_start", ls_)
                    lf_ = np.repeat(np.arange(np_), np.diff(np.append(ls_, nl_)))
                    puv = np.zeros((nl_, 2), np.float32)
                    pl = (fdet_all == "paving")[lf_]
                    puv[pl] = oc[vi_][pl][:, :2]
                    tl = (fdet_all == "tiles")[lf_]
                    if tl.any() and sm.uv_layers.get("UVMap") is not None:
                        u0_ = np.empty(nl_ * 2, np.float32)
                        sm.uv_layers["UVMap"].data.foreach_get("uv", u0_)
                        puv[tl] = u0_.reshape(-1, 2)[tl]
                    pave[sm.name] = puv
                lay2 = m2.uv_layers.new(name=PAVE_UV)
                lay2.data.foreach_set("uv", pave[sm.name][A["lsel"]].ravel())
                m2.uv_layers.active = m2.uv_layers["bake"]
                stats["pave_pieces"] += 1
        if col:
            c = np.empty(len(sm.loops) * 4, np.float32)
            sm.color_attributes["Col"].data.foreach_get("color_srgb", c)
            ca = m2.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
            ca.data.foreach_set("color_srgb", c.reshape(-1, 4)[A["lsel"]].ravel())
        return new_ob(name, m2, extras, parent)

    fc = np.empty(npl * 3, np.float32)
    me.polygons.foreach_get("center", fc)
    fc = fc.reshape(-1, 3)
    stats = collections.Counter()
    if atlases:
        pngs = _post_atlas_pngs(atlases, cdir, a)
        T["atlases"] = round(time.time() - t0, 1)

        def baked_mat(at_idx, glow, detail=None, surface=None):
            """glow: None or a GLOW_CLASSES key; detail: None or a DETAIL_CLASSES key; surface: None or a
            SURFACE_CLASSES key (at most one of the three)."""
            key = (at_idx, glow, detail, surface)
            if key in mats:
                return mats[key]
            nm = "baked.%s%s%s" % (atlases[at_idx]["name"],
                                   (".glow." + glow) if glow else (".detail." + detail) if detail else "",
                                   (".surface." + surface) if surface and not glow else "")
            m = bpy.data.materials.new(nm)
            _use_nodes(m)
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            tn = nt.nodes.new("ShaderNodeTexImage")
            img = next((x for x in imgs if x.name == atlases[at_idx]["name"] + ".png"), None)
            if img is None:
                img = bpy.data.images.load(pngs[at_idx], check_existing=False)
                img.name = atlases[at_idx]["name"] + ".png"
                imgs.append(img)
            img.colorspace_settings.name = "sRGB"
            tn.image = img
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.uv_map = "bake"
            nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
            nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
            b.inputs["Roughness"].default_value = 1.0
            b.inputs["Metallic"].default_value = 0.0
            if glow:
                s, tint = glow_strength[glow]
                m["glow"] = s
                if tint:
                    m["glowTint"] = tint
            elif detail:
                m["detail"] = detail
            if surface and not glow:
                m["sectSurface"] = surface
            m["baked"] = True
            mats[key] = m
            return m
        fitem = get_attr(me, "w_item", npl, 1)
        fglow = get_attr(me, "w_glow", npl, 1).astype(bool)
        fatl = get_attr(me, "w_atlas", npl, 1)
        hot = np.array([it["hot"] for it in items])[fitem]
        fmi = np.empty(npl, np.int32)
        me.polygons.foreach_get("material_index", fmi)
        slot_cls, slot_det, slot_srf, rock_unlisted = [], [], [], set()
        for sm in me.materials:
            src = sm.name.split("@")[0] if sm is not None else ""
            s, tint, ck = glow_class(src)
            glow_strength[ck] = (s, tint)
            slot_cls.append(ck)
            tag = sm.get(MAT_TAG) if sm is not None else None
            slot_det.append(detail_class(src, tag) or "")
            slot_srf.append(surface_class(src, tag) or "")
            if not slot_det[-1] and "rock" in (tag or src).lower():
                rock_unlisted.add(tag or src)
        if rock_unlisted:   # a new rock_cliff variant gets no detail texture until it is listed
            log("WARN", cid, "rock materials without a detail class (list them in DETAIL_CLASSES):",
                sorted(rock_unlisted))
        fslot = np.clip(fmi, 0, len(slot_cls))
        fcls = np.array(slot_cls + ["other"], object)[fslot]
        fcls = np.where(fglow, fcls, "")
        # detail class per face from its source material (rock / ground); a glow class wins
        fdet = np.array(slot_det + [""], object)[fslot]
        fdet = np.where(fglow, "", fdet)
        # surface class (metal / glaze) per face; glow and detail classes win
        fsrf = np.array(slot_srf + [""], object)[fslot]
        fsrf = np.where(fglow | ((fdet != "") & (fdet != "tiles")), "", fsrf)      # glazed roof tiles keep "glaze"
        stats["glow_classes"] = dict(collections.Counter(fcls[fglow].tolist()))
        stats["detail_faces"] = dict(collections.Counter(fdet[fdet != ""].tolist()))
        stats["surface_faces"] = dict(collections.Counter(fsrf[fsrf != ""].tolist()))
        stats["detail_chunks"] = 0
        stats["surface_chunks"] = 0
        fpave = (fdet == "paving") | (fdet == "tiles")
        fdet_all = fdet
        mat_of_face = np.empty(npl, object)
        for kk in range(len(atlases)):
            for g in sorted(set(fcls.tolist())):
                for d in sorted(set(fdet.tolist())):
                    for sf in sorted(set(fsrf.tolist())):
                        msk = (fatl == kk) & (fcls == g) & (fdet == d) & (fsrf == sf)
                        if msk.any():
                            mat_of_face[msk] = baked_mat(kk, g or None, d or None, sf or None)
        # hotspot nodes keep every face of their hotspot; their rock / ground faces use the detail materials
        labels = meta.get("hotspots", {})
        for hid in sorted(set(hot.tolist()) - {""}):
            ob = emit("hotspot." + hid, hot == hid, mat_of_face, extras=dict(hotspot=hid, label=labels.get(hid, hid)),
                      pave_faces=fpave)
            if ob is not None:
                stats["hotspot_nodes"] += 1
        for kk, at in enumerate(atlases):
            short = at["name"].split("_")[-1]
            # plain faces, then each detail class and each surface class in its own chunk pieces (one material each)
            parts = sorted(set(zip(fdet.tolist(), fsrf.tolist())))
            for d, sf in parts:
                f0 = np.nonzero((hot == "") & (fatl == kk) & (fcls == "") & (fdet == d) & (fsrf == sf))[0]
                stem = "%s.baked.%s%s%s" % (cid, short, (".detail." + d) if d else "", (".surface." + sf) if sf else "")
                for ci, fs in enumerate(kd_chunks(fc, f0, CHUNK_FACES)):
                    m = np.zeros(npl, bool)
                    m[fs] = True
                    if emit("%s.c%d" % (stem, ci), m, mat_of_face, extras=dict(chunk=1),
                            pave_faces=fpave if d in ("paving", "tiles") else None) is not None:
                        stats["chunks"] += 1
                        if d:
                            stats["detail_chunks"] += 1
                        if sf:
                            stats["surface_chunks"] += 1
            for g in sorted(set(fcls.tolist()) - {""}):
                m = (hot == "") & (fatl == kk) & (fcls == g)
                if not m.any():
                    continue
                s, tint = glow_strength[g]
                emit("%s.baked.%s.glow.%s" % (cid, short, g), m, mat_of_face,
                     extras=dict(glow=s, **({"glowTint": tint} if tint else {})))
        if ob_vc is not None and len(ob_vc.data.polygons):
            _emit_small(cid, ob_vc.data, cdir, a, emit, mats, stats)
            T["vc"] = round(time.time() - t0 - T["atlases"], 1)
    else:
        weld = _post_vc(me, cdir, a)
        if weld:
            stats["vc_weld"] = weld
        T["vc"] = round(time.time() - t0, 1)

        def vc_mat(glow):
            key = ("vc", glow)
            if key in mats:
                return mats[key]
            m = bpy.data.materials.new("baked.vc" + (".glow" if glow else ""))
            _use_nodes(m)
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            vc = nt.nodes.new("ShaderNodeVertexColor")
            vc.layer_name = "Col"
            nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
            b.inputs["Roughness"].default_value = 1.0
            if glow:
                m["glow"] = 2.0
            m["baked"] = True
            mats[key] = m
            return m
        fitem = get_attr(me, "w_item", npl, 1)
        fglow = get_attr(me, "w_glow", npl, 1).astype(bool)
        zone = np.array([it["zone"] for it in items])[fitem]
        mat_of_face = np.empty(npl, object)
        mat_of_face[~fglow] = vc_mat(False)
        if fglow.any():
            mat_of_face[fglow] = vc_mat(True)
        for z in sorted(set(zone.tolist())):
            if z == "far":
                root = new_ob("backdrop.far", None)
            else:
                root = new_ob(z, None, extras=dict(proxyOf=z.split(".", 1)[1]))
            zm = zone == z
            for ci, fs in enumerate(kd_chunks(fc, np.nonzero(zm & ~fglow)[0], CHUNK_FACES)):
                m = np.zeros(npl, bool)
                m[fs] = True
                if emit("%s.c%d" % (z, ci), m, mat_of_face, uv=False, col=True, extras=dict(chunk=1),
                        parent=root) is not None:
                    stats["chunks"] += 1
            if (zm & fglow).any():
                emit("%s.glow" % z, zm & fglow, mat_of_face, uv=False, col=True, extras=dict(glow=2.0), parent=root)
            stats["groups"] += 1
    p = os.path.join(RAW, cid + ".glb")
    t1 = time.time()
    export_post_scene(p, made)
    T["export"] = round(time.time() - t1, 1)
    st = EW.glb_stats(p)
    st["stats"] = dict(stats)
    st["times"] = T
    log("exported", cid, json.dumps(st))
    for ob in made:
        d = ob.data
        bpy.data.objects.remove(ob)
        if d is not None and d.users == 0:
            bpy.data.meshes.remove(d)
    for m in mats.values():
        bpy.data.materials.remove(m)
    for im in imgs:
        bpy.data.images.remove(im)
    os.makedirs(os.path.join(BAKE_OUT, "post"), exist_ok=True)
    dump(os.path.join(BAKE_OUT, "post", cid + ".json"), dict(file=os.path.basename(p), exposure=a.exposure,
                                                             sat=a.sat, atlases=atlases, **st), indent=1)
    return st


def cmd_post_full(a):
    """Factory startup: redo the post step of chunks (--chunks) from bakecache/full/<chunk>/ (export.blend, EXRs)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    want = [c for c in a.chunks.split(",") if c] if a.chunks else sorted(os.listdir(CACHE_DIR))
    for cid in want:
        cdir = os.path.join(CACHE_DIR, cid)
        if not os.path.isfile(os.path.join(cdir, "export.blend")):
            log("WARN no bake for", cid)
            continue
        with open(os.path.join(cdir, "bake_meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        with open(os.path.join(cdir, "items.json"), encoding="utf-8") as fh:
            items = json.load(fh)
        name = "bake.vc.backdrop" if cid == "backdrop" else "bake.atlas." + cid
        with bpy.data.libraries.load(os.path.join(cdir, "export.blend")) as (src, dst):
            names = [name]
            if cid != "backdrop" and "bake.vc." + cid in src.objects:     # the small pieces (VC_SMALL)
                names.append("bake.vc." + cid)
            dst.objects = names
        ob = dst.objects[0]
        ob_vc = dst.objects[1] if len(dst.objects) > 1 else None
        bpy.context.scene.collection.objects.link(ob)
        if ob_vc is not None:
            bpy.context.scene.collection.objects.link(ob_vc)
        post_chunk(cid, ob, items, meta, a, ob_vc=ob_vc)
        bpy.data.objects.remove(ob)
        if ob_vc is not None:
            bpy.data.objects.remove(ob_vc)


# ---- full water: sheets and streams per chunk -------------------------------------------------------------

def cmd_water_full(a):
    """Waterfall sheets and streams seen along the path -> raw/<area>_water.glb per chunk (the chunk export_web
    assigned them to) and raw/backdrop_water.glb (seen only beyond 400 m, and the long streams that span several
    areas); same geometry rules as the prototype's 'water'. Lip/foot corners -> out/web/full/water_meta.json.
    Per vertex: TEXCOORD_0 (_water_uv: u across 0-1, v 0 at the lip / 1 at the foot in three.js), TEXCOORD_1 (three.js
    uv1, _water_uv1: metres across, seconds since the lip), COLOR_0 = (per-sheet seed, flow / 2, layer: 0 core,
    0.5 side curtain, 1 front veil; WATER_LAYER_B; streams 0). No normals (export_post_scene)."""
    sc = bpy.context.scene
    R = EW.gather(sc)
    S, _ = EW.load_cache(R)
    ch, ids = EW.load_chunks(R)
    dg = bpy.context.evaluated_depsgraph_get()
    dec = Decimator(sc)
    groups = collections.defaultdict(lambda: dict(co=[], vi=[], ls=[], uv=[], uv1=[], col=[], n=0, nl=0))
    falls, seen = [], set()
    for i in range(len(R)):
        mats = [m for m in R.tinfo[R.tkey[i]][2] if m]
        if not any("waterfall" in m for m in mats) or not S["any"][i] or S["d_eff"][i] > a.water_max:
            continue
        if R.top[i] == EW.FLYER_COLL:
            continue
        nm = R.name[i] if not R.inst[i] else R.key[i]
        if nm in seen:
            continue
        seen.add(nm)
        kk = int(ch[i])
        if kk == -2:
            continue
        fid = ids[kk] if kk >= 0 else "backdrop"
        d = float(S["d_eff"][i])                 # look-around views included (weighted)
        ob = bpy.data.objects.get(R.name[i])
        if ob is None:
            continue
        me0 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        A0 = MA(me0)
        M = np.asarray(R.mw[i], float)
        kind = "stream" if "stream" in nm else "sheet"
        exit_speed = ob.get("exit_speed")
        uv_v = _water_uv(nm, A0.co, A0.gen)
        lay = me0.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", np.ascontiguousarray(uv_v[A0.vi], np.float32).ravel())
        # names read back (a source layer would have taken 'UVMap'), each right after its layer is made: adding a
        # layer can move the mesh's layer list, so a reference held from before it may point at freed memory
        uv_names = [lay.name]
        uv1_v = _water_uv1(nm, A0.co, M, exit_speed)
        lay1 = me0.uv_layers.new(name=WATER_UV1)
        lay1.data.foreach_set("uv", np.ascontiguousarray(uv1_v[A0.vi], np.float32).ravel())
        uv_names.append(lay1.name)
        tris = EW._mesh_tris(me0)[0]
        target = 3000 if d < 150 else 1500 if d < WATER_NEAR else 600
        me = dec.get(nm + ".water", me0, min(1.0, target / max(tris, 1))) if tris > target * 1.2 else me0
        nv, nl, npl = len(me.vertices), len(me.loops), len(me.polygons)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(nv, 3)
        vi = np.empty(nl, np.int32)
        me.loops.foreach_get("vertex_index", vi)
        ls = np.empty(npl, np.int32)
        me.polygons.foreach_get("loop_start", ls)
        uv = np.empty(nl * 2, np.float32)
        me.uv_layers[uv_names[0]].data.foreach_get("uv", uv)
        uv1 = np.empty(nl * 2, np.float32)
        me.uv_layers[uv_names[1]].data.foreach_get("uv", uv1)
        w = co @ M[:3, :3].T + M[:3, 3]
        g = groups[(fid, kind, "near" if d < WATER_NEAR else "far")]
        seed = (zlib.crc32(nm.encode()) & 0xffff) / 65535.0
        flow = float(ob.get("flow", 1.0))
        layer = "core" if kind == "stream" else _water_layer(ob)
        g["co"].append(w)
        g["vi"].append(vi + g["n"])
        g["ls"].append(ls + g["nl"])
        g["uv"].append(uv.reshape(-1, 2))
        g["uv1"].append(uv1.reshape(-1, 2))
        g["col"].append(np.tile([seed, min(flow / 2.0, 1.0), WATER_LAYER_B[layer], 1.0], (nl, 1)).astype(np.float32))
        g["n"] += nv
        g["nl"] += nl
        tq = 1.0 - uv1_v[:, 1]                   # seconds since the lip, before thinning
        xd = M[:3, 0] / max(np.linalg.norm(M[:3, 0]), 1e-9)
        zr = w[:, 2]
        h = float(zr.max() - zr.min())
        top = w[zr >= zr.max() - 0.04 * max(h, 1.0)]
        bot = w[zr <= zr.min() + 0.04 * max(h, 1.0)]

        def ends(P):
            s = P @ xd
            return P[np.argmin(s)], P[np.argmax(s)]
        tl, tr = ends(top)
        bl, br = ends(bot)
        falls.append(dict(name=nm, kind=kind, chunk=fid, corners=[_three(tl), _three(tr), _three(br), _three(bl)],
                          lip=_three(top.mean(0)), foot=_three(bot.mean(0)), height=round(h, 2),
                          sizeLocal=[round(float(x), 3) for x in (ob.dimensions.x, ob.dimensions.z, ob.dimensions.y)],
                          flow=flow, nearestM=round(d, 1), faces=int(npl), layer=layer,
                          exitSpeed=round(float(exit_speed), 3) if exit_speed else None,
                          seconds=[round(float(tq.min()), 3), round(float(tq.max()), 3)],
                          widthM=round(float(np.ptp(uv1_v[:, 0])), 3)))
    files = collections.defaultdict(list)
    sc_out = bpy.data.collections.new("web.water")
    sc.collection.children.link(sc_out)
    for (fid, kind, band), g in sorted(groups.items()):
        m = bpy.data.materials.get("water." + kind)
        if m is None:
            m = bpy.data.materials.new("water." + kind)
            _use_nodes(m)
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            ca = nt.nodes.new("ShaderNodeVertexColor")
            ca.layer_name = "Col"
            nt.links.new(ca.outputs["Color"], b.inputs["Base Color"])
        nm = "water.%s.%s.%s" % (fid, kind, band)
        me = make_mesh(nm, np.concatenate(g["co"]), np.concatenate(g["vi"]), np.concatenate(g["ls"]))
        me.materials.append(m)
        lay = me.uv_layers.new(name="UVMap")                 # TEXCOORD_0
        lay.data.foreach_set("uv", np.concatenate(g["uv"]).ravel())
        lay1 = me.uv_layers.new(name=WATER_UV1)              # TEXCOORD_1 (the exporter writes them in this order)
        lay1.data.foreach_set("uv", np.concatenate(g["uv1"]).ravel())
        col = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        col.data.foreach_set("color", np.concatenate(g["col"]).ravel())
        ob = bpy.data.objects.new(nm, me)
        sc_out.objects.link(ob)
        ob["water"] = kind
        files[fid].append(ob)
        lb = np.concatenate(g["col"])[:, 2]
        log("water", fid, kind, band, "faces", len(me.polygons), "corners core/side/veil",
            [int(np.sum(np.isclose(lb, b))) for b in (0.0, 0.5, 1.0)])
    os.makedirs(RAW, exist_ok=True)
    stats = {}
    for fid, objs in sorted(files.items()):
        p = os.path.join(RAW, fid + "_water.glb")
        export_post_scene(p, objs)
        stats[fid] = EW.glb_stats(p)
    dump(os.path.join(EW.WORK, "water_meta.json"),
         dict(units="three.js world (Y up), metres", falls=falls, files={k: k + "_water.glb" for k in files},
              note="corners: lip-left, lip-right, foot-right, foot-left; sizeLocal: the object's own dimensions on "
                   "the three axes (x across, y up, z through); chunk: the file it is in (<chunk>_water.glb); "
                   "layer: core / side / veil (COLOR_0.b 0 / 0.5 / 1); seconds: uv1.y range (since the lip, "
                   "negative on the lead-in; streams: since the head); widthM: uv1.x range (metres across at the lip)",
              attributes=dict(TEXCOORD_0="u across 0-1 (each row's own edges), v 0 at the lip .. 1 at the foot",
                              TEXCOORD_1="uv1: x metres across (flow lines, centred), y seconds since the lip "
                                         "(sqrt(2 d / 9.81) d m under it; streams: m from the head / %.1f)"
                                         % WATER_STREAM_SPEED,
                              COLOR_0="r per-sheet seed, g flow / 2, b layer (0 core, 0.5 side curtain, 1 front veil)")),
         indent=1)
    dump(os.path.join(BAKE_OUT, "water_stats.json"), stats, indent=1)
    log("water: falls", len(falls), "files", json.dumps({k: v["triangles"] for k, v in stats.items()}))


# ---- full verify: re-import the raw GLBs, render the holds -------------------------------------------------

def cmd_verify_full(a):
    """Factory startup. Imports raw/backdrop.glb and every baked raw/<area>.glb (+ <area>_trees.glb when the trees
    agent has written it) whose need range holds one of the frames, shows per frame the chunks drawn there (their
    proxies hidden, the other proxies shown) like the page, rebuilds chase.cam from camera.json and renders
    emission-only -> out/web/full/bake/verify/hold_<frame>.png. Frames: --ref-frames, else the holds of --chunks."""
    from mathutils import Quaternion
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    sc = bpy.context.scene
    plan = _plan()
    need = {c["id"]: c["need"] for c in plan["chunks"]}
    holds = {c["id"]: c["hold"] for c in plan["chunks"]}
    with open(a.camera_json or os.path.join(EW.SITE, "camera.json"), encoding="utf-8") as fh:
        camj = json.load(fh)
    if a.ref_frames:
        frames = [int(x) for x in a.ref_frames.split(",")]
    else:
        frames = [holds[c] for c in (a.chunks.split(",") if a.chunks else holds)]
    t0 = time.time()

    def imp(p):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=p)
        return [o for o in bpy.data.objects if o not in before]
    proxies = {}
    for g in ("backdrop.glb", "backdrop_trees.glb"):
        p = os.path.join(RAW, g)
        if os.path.isfile(p):
            for o in imp(p):
                px = o.get("proxyOf")
                if px:
                    proxies.setdefault(px, []).extend([o] + list(o.children_recursive))
    chunk_objs = {}
    for cid, (n0, n1) in need.items():
        if not any(n0 <= f <= n1 for f in frames):
            continue
        p = os.path.join(RAW, cid + ".glb")
        if not os.path.isfile(p):
            continue
        chunk_objs[cid] = imp(p)
        pt = os.path.join(RAW, cid + "_trees.glb")
        if os.path.isfile(pt):
            chunk_objs[cid] += imp(pt)
    log("verify: imported", len(bpy.data.objects), "objects; chunks", sorted(chunk_objs), "proxies", sorted(proxies),
        round(time.time() - t0, 1), "s")
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        nt = m.node_tree
        outn = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if outn is None:
            continue
        b = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        src = b.inputs["Base Color"].links[0].from_socket if b is not None and b.inputs["Base Color"].is_linked else None
        em = nt.nodes.new("ShaderNodeEmission")
        if src is not None:
            nt.links.new(src, em.inputs["Color"])
        elif b is not None:
            em.inputs["Color"].default_value = b.inputs["Base Color"].default_value
        if m.name.startswith("water."):
            em.inputs["Color"].default_value = (0.75, 0.82, 0.86, 1.0)
            for l in list(em.inputs["Color"].links):
                nt.links.remove(l)
        if b is not None and b.inputs["Alpha"].is_linked:
            mix = nt.nodes.new("ShaderNodeMixShader")
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            nt.links.new(b.inputs["Alpha"].links[0].from_socket, mix.inputs["Fac"])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], outn.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], outn.inputs["Surface"])
    world = bpy.data.worlds.new("verify.world")
    _use_nodes(world)
    nt = world.node_tree
    bg = nt.nodes["Background"]
    for sky in (os.path.join(EW.SITE, "sky.webp"), os.path.join(EW.SITE, "sky.png")):
        if os.path.isfile(sky):
            env = nt.nodes.new("ShaderNodeTexEnvironment")
            env.image = bpy.data.images.load(sky)
            # three.js equirect: u = 0.5 is +X; Blender's: u = 0.5 is -X (rotate half a turn about Z)
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Rotation"].default_value = (0.0, 0.0, math.pi)
            nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
            nt.links.new(env.outputs["Color"], bg.inputs["Color"])
            break
    sc.world = world
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    w, h = (int(x) for x in a.res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.image_settings.file_format = "PNG"
    cd = bpy.data.cameras.new("verify.cam")
    cam = bpy.data.objects.new("verify.cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cd.sensor_fit = "VERTICAL"
    cd.clip_start, cd.clip_end = 0.5, 9000.0
    out = os.path.join(BAKE_OUT, "verify")
    os.makedirs(out, exist_ok=True)
    report = []
    for f in frames:
        drawn = [cid for cid, (n0, n1) in need.items() if n0 <= f <= n1]
        for cid, objs in chunk_objs.items():
            for o in objs:
                o.hide_render = cid not in drawn
        for cid, objs in proxies.items():
            for o in objs:
                o.hide_render = cid in drawn and cid in chunk_objs
        row = camj["frames"][f - camj["frameStart"]]
        p, q = row["p"], row["q"]
        cam.location = (p[0], -p[2], p[1])
        R3 = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = (EW.C3.transposed() @ R3).to_quaternion()
        cd.sensor_height = 36.0 * 9 / 16
        cd.lens = (cd.sensor_height / 2) / math.tan(math.radians(row["fovY"]) / 2)
        sc.render.filepath = os.path.join(out, "hold_%d.png" % f)
        bpy.ops.render.render(write_still=True)
        report.append(dict(frame=f, drawn=drawn, baked=[c for c in drawn if c in chunk_objs],
                           proxies=[c for c in drawn if c not in chunk_objs]))
        log("verify", f, "baked", report[-1]["baked"], "proxies for", report[-1]["proxies"],
            round(time.time() - t0, 1), "s")
    dump(os.path.join(out, "verify_%s.json" % "_".join(str(f) for f in frames)), report, indent=1)


# ---- main ---------------------------------------------------------------------------------------

def main():
    global BAKE_OUT, RAW, CACHE_DIR
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="bake_web.py")
    ap.add_argument("command", help="bake, post, trees, verify, water, bakefull (full profile); several may be "
                                    "joined by commas and run in order in one session")
    ap.add_argument("--profile", default="proto", choices=["proto", "full"],
                    help="proto: the first test (gate/mirror, out/web/raw); full: all 11 areas (out/web/full/raw)")
    ap.add_argument("--chunks", default="", help="full: chunk ids in bake order (default: flight order, backdrop)")
    ap.add_argument("--chunk-atlases", type=float, default=0.0,
                    help="full: texel budget per chunk in 4096^2 atlases (default FULL_ATLASES / _BY_AREA)")
    ap.add_argument("--no-post", action="store_true", help="full bakefull: skip the in-session post step")
    ap.add_argument("--far-tris", type=int, default=FAR_TRIS_FULL, help="full backdrop: far set triangles")
    ap.add_argument("--proxy-tris", type=int, default=PROXY_TRIS_FULL, help="full backdrop: per-area proxy")
    ap.add_argument("--camera-json", default="", help="full verify: camera.json (default out/web/full/site)")
    ap.add_argument("--water-max", type=float, default=2500.0, help="water: farthest waterfall/beam kept (m)")
    ap.add_argument("--quality", default="dev", choices=sorted(BAKE_QUALITY),
                    help="dev: the fast bake (default); production: one final bake, less noise, same files and sizes "
                         "(BAKE_QUALITY; about 2x the time, see 'Quality' in the docstring)")
    ap.add_argument("--samples", type=int, default=0,
                    help="atlas samples (default from --quality: dev proto 512 / full 160, production 768)")
    ap.add_argument("--plan-only", action="store_true",
                    help="bake / bakefull: stop after LOD, atlas grouping and unwrap (bakefull: bake/plan_<chunk>.json, "
                         "bake/plan_stats.json with the range normal / border / island checks; no bake, no post)")
    ap.add_argument("--debug-proxy", action="store_true", help="bake: save the unwrap proxies (out/web/bake/debug)")
    ap.add_argument("--vc-samples", type=int, default=0,
                    help="vertex colour samples (default from --quality: dev proto 512 / full 256, production 1024)")
    ap.add_argument("--atlas-tris", type=int, default=0, help="proto: 1M for both areas; full: per chunk (700k)")
    ap.add_argument("--vc-tris", type=int, default=220_000)
    ap.add_argument("--max-atlases", type=float, default=3.0, help="texel budget in 4096^2 atlases")
    ap.add_argument("--exposure", type=float, default=1.2)
    ap.add_argument("--sat", type=float, default=1.15)
    ap.add_argument("--skip-atlas", action="store_true")
    ap.add_argument("--glb-dir", default="")
    ap.add_argument("--glbs", default="gate.glb,mirror.glb,backdrop.glb,trees.glb")
    ap.add_argument("--out", default=EW.PROTO)
    ap.add_argument("--ref-frames", default="")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--tag", default="")
    ap.add_argument("--tree-near", type=float, default=70.0)
    ap.add_argument("--tree-px", type=int, default=256)
    ap.add_argument("--out-dir", default="",
                    help="full bakefull / post / verify: a test run writes its raw GLBs, bake stats, textures and EXRs "
                         "under out/<dir>/{raw,bake} and bakecache/<dir>/ instead of the live out/web/full and "
                         "bakecache/full (one-chunk tests beside a real bake; not with 'water' or 'trees')")
    a, extra = ap.parse_known_args(argv)
    a.extra = extra                    # options other scripts (bake_trees) may read
    if extra:
        log("options not parsed here (left in a.extra):", extra)
    use_profile(a.profile)
    full = PROFILE == "full"
    if a.out_dir:
        if not full or {"water", "trees"} & set(a.command.split(",")):
            raise SystemExit("--out-dir is for full bakefull / post / verify runs only")
        d = a.out_dir.strip("/\\")
        BAKE_OUT = os.path.join(ROOT, "out", d, "bake")
        RAW = os.path.join(ROOT, "out", d, "raw")
        CACHE_DIR = os.path.join(ROOT, "bakecache", d)
        log("test outputs:", BAKE_OUT, RAW, CACHE_DIR)
    Q = BAKE_QUALITY[a.quality]
    a.samples = a.samples or Q["samples"][PROFILE]
    a.vc_samples = a.vc_samples or Q["vc_samples"][PROFILE]
    log_bake_quality(a)
    a.atlas_tris = a.atlas_tris or (FULL_ATLAS_TRIS if full else 1_000_000)
    a.out = EW.fix_path(a.out)
    a.glb_dir = EW.fix_path(a.glb_dir) if a.glb_dir else RAW
    a.camera_json = EW.fix_path(a.camera_json) if a.camera_json else ""
    if a.debug_proxy:
        global DEBUG_PROXY
        DEBUG_PROXY = True
    for cmd in a.command.split(","):
        t0 = time.time()
        if cmd == "trees":
            from sect import bake_trees
            bake_trees.cmd_trees(a)
        elif full and cmd in ("post", "water", "verify"):
            globals()["cmd_%s_full" % cmd](a)
        elif cmd == "bakefull":
            cmd_bakefull(a)
        elif cmd in ("bake", "post", "verify", "water"):
            if cmd == "verify" and not a.ref_frames:
                a.ref_frames = "93,217"
            globals()["cmd_" + cmd](a)
        else:
            raise SystemExit("unknown command %r" % cmd)
        log("done", cmd, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
