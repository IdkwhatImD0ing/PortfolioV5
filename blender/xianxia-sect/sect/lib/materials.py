"""Every shared procedural material of the Moonlit Sect, by name.

    from sect.lib import materials as M
    mat = M.get("lacquer_red")        # created once, then reused (cached by name)
    M.NAMES                           # every registered name
    M.banner_cloth(7)                 # one of 8 harmonious banner colours
    M.register("my_mat", builder)     # module-specific material (builder(g) gets a Graph)
    M.variant("lacquer_blue", "lacquer_red", c1="#1b2a4a", c2="#24365c")

All materials are procedural, meter-scaled, and built for EEVEE 5.2 under a low golden-hour sun.
Texture space: ``Graph.coord('object')`` = object coordinates times the object's scale, i.e. meters
along the object's own axes, so patterns stick to moving/instanced objects and stay the same size
on scaled ones. Bump only, never displacement. The one exception to "no images": rock_cliff (and
its variants), grass and nature_soil_moss blend CC0 photo scans from assets/web (SCAN_DIR) into
their procedural colour, projected in world space (see "photo scans" below); rock_cliff's moss
layer also reads Moss001 ("rock life" below). grass and nature_soil_moss add world-space patches,
clumps, a rim band and flowers ("ground life" below).

Per-object controls read through Attribute nodes (all optional):
  obj["glow"]     multiplies emission of glowing materials (default 1)
  obj["density"]  multiplies density of volume materials (default 1)
  mesh face attribute "edge" (written by util.bevel_mesh) -> edge wear on worn/metal materials
  Object Info > Random gives each object / instance a subtle colour shift.
"""

import math
import os

import bpy

PREFIX = "M."
TAG = "sect_material"

# Spec palette (sRGB hex, spec.md section 3) for modules that need raw colours (lights, sky...).
PALETTE = dict(
    vermilion="#9b1c1c", vermilion_light="#b32a1f", tile_teal="#1f4f4b", tile_black="#2a2c30",
    tile_moon="#d9dde6", bracket_green="#2f6f73", bracket_teal="#3d8a7a", bracket_gold="#c9a24a",
    gold="#d4af37", bronze="#7a5a2e", verdigris="#4f8a7a", marble="#e8e4da", rock_light="#8a8172",
    rock_dark="#5e5a52", moss="#4b6b3a", jade_cyan="#6fffd8", moon_silver="#cfe3ff", glow_gold="#ffd27a",
    lantern="#ffb46b",
)

# ---- photo scans: CC0 sets (assets/CREDITS.md) as 2048 px JPGs in assets/web. Builders blend them into their
# procedural colour at the procedural brightness and feed their height into the bump chain. Tiles are the real
# sizes in metres, strengths 0-1. Builders read these when they build, so sect/patch_nature_look.py KEY=value
# can override them for a patch run.
SCAN_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "web"))
ROCK_SCANS = dict(   # _rock(scan=...): world triplanar; relief = bump distance (m) of the whole 0-1 height range
    marble_cliff_06=dict(diff="marble_cliff_06_diff.jpg", disp="marble_cliff_06_disp.jpg", tile=(8.14, 8.14),
                         relief=0.3),
    rock063=dict(diff="rock063_color.jpg", disp="rock063_disp.jpg", tile=(4.0, 2.0), relief=0.15),
)
ROCK_SCAN_MIX = 0.6          # share of the scan's colour in the rock albedo
ROCK_SCAN_CONTRAST = 1.0     # 1 = the scan's full brightness variation, 0 = its hue only (same for LAWN_/GROUND_)
ROCK_SCAN_HUE = 1.0          # share of the scan's own colour (below 1 the procedural hue stays; same for LAWN_/GROUND_)
ROCK_SCAN_BUMP = 0.4         # bump strength of the scan height
ROCK_SCAN_SHARP = 4.0        # triplanar blend exponent on |world normal|
ROCK_SMALL_SCAN_SCALE = 0.5  # nature_rock_small's scan tile factor (boulders are 1-5 m, like its finer strata)
LAWN_SCANS = dict(leafy="leafy_grass_diff.jpg", sparse="sparse_grass_diff.jpg", mask="sparse_grass_mask.jpg")
LAWN_TILE = 2.0              # m, both grass sets (top-down)
LAWN_SCAN_MIX = 0.6
LAWN_SCAN_CONTRAST = 1.0
LAWN_SCAN_HUE = 0.25         # leafy_grass is yellower than the lawn palette; keep the palette's green
GROUND_SCANS = dict(grass="grass_ground_diff.jpg", moss="moss001_color.jpg")
GROUND_TILE = 2.51           # m, grass_ground (top-down)
MOSS_TILE = 1.5              # m, Moss001 (top-down)
GROUND_SCAN_MIX = 0.6
GROUND_SCAN_CONTRAST = 1.0
GROUND_SCAN_HUE = 0.4
GROUND_FLAT = (0.55, 0.85)   # world normal z over which the ground photo fades in (top-down stretches on slopes)
GROUND_MOSS = (0.48, 0.62)   # procedural ramp position over which Moss001 takes over from grass_ground
GROUND_SCAN_BUMP = 0.15      # bump strength of the lawn / ground photo's luminance
LUMA = (0.2126, 0.7152, 0.0722)   # linear Rec.709 luminance weights

# ---- rock life (_rock_life): moss, damp streaks and lichen so the cliffs read as old and alive, not bare grey.
# Laid over _rock's colour in WORLD space (Geometry Position / Normal: the film, and bake_web's joined bake mesh, which
# rewrite_material leaves alone), so the patterns line up across objects with world.py's 11 m rock layers. Strengths
# are 0-1 shares unless noted. sect/patch_rock_life.py KEY=value overrides any of them for a patch run.
ROCK_LIFE = True              # False: _rock builds its earlier graph (its own up-facing moss) exactly as before
ROCK_LIFE_SCALE = 1.0         # pattern size factor (2 = every patch half as big); the moss photo keeps its real size
ROCK_LIFE_VARIANTS = dict(    # per material tag: multipliers of moss / streak / lichen / damp / ledge / lip, a scale
    world_rock_under=dict(moss=0.5, streak=1.1, lichen=0.5, damp=1.3, lip=0.0),   # the range's underside (faces down)
    # 1-5 m boulders: no 11 m ledge cushions (a boulder has no rock layers; a world z = 11 n line would cut a
    # straight moss edge across it), no lip moss (a boulder's top is not a grass rim)
    nature_rock_small=dict(moss=1.15, streak=0.35, lichen=1.2, scale=2.5, ledge=0.0, lip=0.0),
)
ROCK_LAYER = 11.0             # m: world.py's rock layer height (_strata(h, 11.0)); ledge lines at z = n * ROCK_LAYER
ROCK_LAYER_WARP = 2.0         # m: +- warp of those lines (about 50 m wavelength) so they never read as ruled
ROCK_MOSS = 1.0               # moss strength (0 = none)
ROCK_MOSS_UP = (0.33, 0.52)   # world normal z over which moss takes over, before the edge and patch noise move it
#                               (was (0.27, 0.45): the 0.30 terrace skirt cones sat on the switch, and steep walls
#                               wore a blanket of moss)
ROCK_MOSS_EDGE = 0.45         # organic edge: how far 2-5 m noise (plus a quarter as much 1 m noise) moves that
#                               threshold, in normal-z units
ROCK_MOSS_PATCH = 0.35        # lush and sparse regions (~30 m): how far they move it
ROCK_MOSS_ALT = (120.0, 330.0, 0.15)   # threshold raised by the third value from z0 to z1 (m): mist-fed slopes
#                                        lower down are lusher, the high crags drier (and richer in lichen)
ROCK_MOSS_BARE = (0.555, 0.6)   # noise ramp of bare rock outcrops (~20 %) inside the moss, even on the flattest rock
ROCK_MOSS_LEDGE = 0.9         # moss cushions along every ledge line, also on steep faces (0 = none)
ROCK_MOSS_LEDGE_W = (3.0, 1.0)   # m per unit of clump strength: cushion height above a ledge line, fringe below its lip
ROCK_MOSS_DRAPE = (0.7, 4.0)  # green drapes trailing from the cushions: strength, and length (m per unit of strength)
ROCK_MOSS_RIM = 0.3           # dark humus fringe just outside each up-facing moss patch
ROCK_MOSS_COLOURS = ((0.35, "#36503a"), (0.5, "#53673a"), (0.68, "#86884a"))   # jade shade, olive moss, sunlit gold
ROCK_MOSS_SCAN_MIX = 0.7      # Moss001 photo (GROUND_SCANS["moss"], world triplanar at MOSS_TILE) in the moss colour
ROCK_MOSS_SCAN_HUE = 0.35     # share of the photo's own hue (the rest stays ROCK_MOSS_COLOURS)
ROCK_MOSS_BUMP = 0.0          # moss cushion bump (raised patch edges, 5 cm); 0 = no Bump node. Off by default:
#                               Cycles copies everything a Bump's Height depends on twice (dx, dy), here the
#                               whole moss mask, ~+70 % rock shader cost, for a sub-texel effect in the web atlases
#                               (15-60 cm texels at 100-400 m)
ROCK_MOSS_PHOTO_BUMP = 0.0    # Moss001 luminance bump under the moss (1.5 cm); 0 = no Bump node (same cost reason)
ROCK_MOSS_SOFTEN = 0.6        # share of the rock's own bump that moss hides
ROCK_STREAK = 0.85            # dark damp streaks hanging from the ledge lines on steep faces, gathered in wet courses
ROCK_STREAK_LEN = (0.3, 0.95)   # share of a layer a streak runs down (varies streak to streak)
ROCK_STREAK_WIDTH = 0.6       # streak frequency across a face (1/m; streaks ~1 m wide, so the bake keeps them)
ROCK_STREAK_WASH = 0.25       # faint darkening of the whole upper part of each layer, under the lip
ROCK_STREAK_ALGAE = 0.5       # green-black algae tint on part of the streaks
ROCK_STREAK_JADE = 0.2        # rare jade (copper-mineral) tint on damp seeps, the xianxia accent
ROCK_DAMP = 0.3               # albedo darkening of damp rock: overhang undersides (and recesses with ROCK_DAMP_AO)
ROCK_DAMP_AO = (2.5, 0)       # recess ambient occlusion (distance m, samples); 0 samples = no AO node. Ray traced:
#                               a slower bake, and below about 16 samples its noise reaches the albedo guide (OIDN)
ROCK_MOSS_RECESS = 0.5        # with ROCK_DAMP_AO only: dark algae-moss in recesses on steep faces
ROCK_LICHEN = 0.45            # lichen crusts on dry rock (ochre, grey-green); fewer on damp streaks
ROCK_LICHEN_COLOURS = ("#a8884f", "#a3a78c")   # ochre-gold crust, sage grey-green foliose (at half strength)
ROCK_LIP_MOSS = dict(         # moss creeping over the lip: the top of the rock under a grass rim
    amount=0.9,               # strength (0 = none); scaled like the other moss (ROCK_MOSS, the variant's moss and lip)
    up=(0.55, 0.72),          # smooth normal z from none to full. With smooth range normals the grass/rock border
    #                           vertices average both sides (normal z ~0.66-0.95), so this covers the top of the first
    #                           rock row and fades down it
    tongue=(1.5, 0.12),       # xy noise (m; constant down a vertical line) moving that edge by +- the second value
    #                           (normal z), so the green hangs over the lip in tongues
    grass=0.5,                # share of the moss colour pulled toward `colours`, the cap's own greens
    colours=((0.35, "#4b5a2e"), (0.68, "#5f7236")),   # nature_soil_moss's green stops (on the same tone noise)
)

# ---- ground life (_ground_life): the lawns (grass) and the soil-moss caps (nature_soil_moss) at 0.5-40 m and at their
# rims, so a cap reads as living ground, not a painted lid: dry and lush patches with damp hollows, 0.6 m grass clumps,
# flower drifts, and a dry-grass, humus and moss band where the ground rolls over a rim. Like the rock life it works in
# WORLD space (Geometry Position and smooth Normal), so the patterns run on across objects and over bake_web's joined
# bake mesh; with smooth range normals the grass/rock border vertices average both sides, so the rim band (and
# ROCK_LIP_MOSS on the rock side) fades across the last 5 m grid row instead of switching per face. Each dict's "amount"
# scales its layer and 0 builds none of its nodes. sect/patch_nature_look.py KEY=value overrides any of them, and a dict
# override keeps the keys it leaves out (_conf), e.g. GROUND_FLOWERS="{'amount': 0}".
GROUND_LIFE = True            # False: grass and nature_soil_moss build their earlier graph exactly as before
GROUND_MACRO = dict(          # 10-40 m patches
    amount=1.0,
    scales=(38.0, 13.0),      # m: the two patch noises, weighted 0.65 / 0.35
    dry="#8f8650", lush="#3f5e2a",   # hues of the dry and the lush patches, at the ground's own brightness
    mix=0.55,                 # their strongest share (about a third of the ground leans dry, a third lush)
    value=0.12,               # +- brightness from a third noise (~20 m); dry patches a little lighter, lush darker
    damp=0.82,                # brightness of the damp hollows (~15 % of the ground, ~25 m), which also lean lush
)
GROUND_CLUMP = dict(          # grass clumps: one Voronoi cell (world xy) per clump, crowns lit and gaps dark
    amount=0.6,
    cell=0.6,                 # m
    gap=0.75, top=1.08,       # brightness between the clumps and on their crowns (renormalised: the mean stays)
    vary=0.06,                # +- brightness per clump
    bump=0.0,                 # Bump strength of the crowns (0 = no Bump node: Cycles copies a Bump's Height graph
    #                           twice, see ROCK_MOSS_BUMP; the 7 deg sun would make them high-contrast)
)
GROUND_FLOWERS = dict(        # flower drifts: dots inside large drift patches, one species leading each drift
    amount=0.5,
    size=0.25,                # m: dot diameter
    cell=0.55,                # m: one candidate dot per Voronoi cell
    share=0.6,                # share of the cells inside a drift that flower
    drift=25.0,               # m: the drift noise
    cover=(0.62, 0.70),       # its ramp (about 5 % of the ground)
    colours=("#efe8dc", "#e9b3c2", "#b6a3d9", "#e2bf5c"),   # white, pink, violet, gold
)                             # only on gentle green ground (not in the rim band, not on the brown end of the ramp)
GROUND_POINT_BAKE = "w_vc"    # bake_web.VC_BAKE_ATTR: the vertex-colour bake mesh (backdrop) sets this POINT attribute to
#                               1. A vertex colour samples one point, so a dot under a vertex lit its whole fan (~1 % of
#                               the far ground's vertices); no flowers there. Missing elsewhere: reads 0, flowers on
GROUND_RIM = dict(            # where the smooth normal turns down over a rim: dry grass, humus, then moss at the edge
    amount=0.8,
    up=(0.90, 0.80),          # smooth normal z where the dry band starts and where it is full: about the last 1-4 m
    #                           of a cap (on the range, 79 % of it lies in the last 5 m grid row; 0.93 put 34 % on
    #                           plain 25-37 deg slopes), less where grass meets rock on an even slope
    warp=(2.0, 0.06),         # noise (m) moving these edges by +- the second value (normal z)
    dry="#8a8350", dry_value=1.1,     # dry grass hue, brightness factor
    soil_up=(0.82, 0.76),     # humus where the normal turns further: only on real lips (border normal z under ~0.8,
    #                           a quarter of the range's grass/rock border), a strip 1.5-2.5 m in from a sharp lip
    soil="#4a3a28", soil_value=0.6,   # humus hue, brightness factor (dark, but never black: the web's grass tufts
    #                                   treat black texels as covered ground)
    soil_patch=(6.0, 0.46, 0.54),     # humus in patches: noise (m) and ramp (about half the lip's length)
    moss_up=(0.74, 0.64),     # moss where the normal turns steeper still: the last metre of a sharp lip, and the
    #                           steep grass triangles that hang from some rims ("teeth"), so they run on into the
    #                           rock's lip moss (ROCK_LIP_MOSS, full from 0.72) instead of standing out as triangles
    moss="#53673a", moss_value=1.25,  # ROCK_MOSS_COLOURS' olive moss hue, brightness factor (rock moss is lighter);
    #                                   it carries the rock moss's Moss001 photo (ROCK_MOSS_SCAN_*, world triplanar)
)

_REGISTRY = {}   # name -> (builder, params)
NAMES = []       # kept in registration order; the same list object is updated by register()
_CACHE = {}
# import-time copies of the dict constants that a KEY=value override may name only in part (see _conf)
_DEFAULTS = {k: dict(globals()[k]) for k in ("ROCK_LIP_MOSS", "GROUND_MACRO", "GROUND_CLUMP", "GROUND_FLOWERS",
                                             "GROUND_RIM")}


def _conf(name):
    """Dict constant ``name`` laid over its import-time value: sect/patch_nature_look.py GROUND_FLOWERS="{'amount': 0}"
    switches the flowers off and keeps their other keys."""
    d = dict(_DEFAULTS[name])
    d.update(globals()[name])
    return d


# ============================================================ colour helpers

def _s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(value, alpha=1.0):
    """Linear RGBA from '#rrggbb' (sRGB), an (r, g, b[, a]) tuple (already linear) or a grey float."""
    if isinstance(value, str):
        h = value.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return (_s2l(r), _s2l(g), _s2l(b), alpha)
    if isinstance(value, (int, float)):
        return (float(value), float(value), float(value), alpha)
    v = tuple(value)
    return v if len(v) == 4 else (v[0], v[1], v[2], alpha)


# ============================================================ node graph helper

def _key(s):
    return s.lower().replace(" ", "_")


class Graph:
    """Tiny node-building helper handed to every material builder.

    Every helper returns an output *socket*; any input argument may be a socket (linked),
    a number, a tuple, or a '#hex' colour string (set as default value)."""

    def __init__(self, mat):
        self.mat = mat
        if mat.node_tree is None:
            mat.use_nodes = True
        self.nt = mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self.nodes.clear()
        self.out = self.nodes.new("ShaderNodeOutputMaterial")
        self.out.location = (1400, 0)
        self._shared = {}
        self._n = 0

    # ---- plumbing
    def set(self, sock, value):
        """Link ``value`` into ``sock`` if it is a socket/node, else set it as default value."""
        if value is None:
            return
        if isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, sock)
            return
        if isinstance(value, bpy.types.Node):
            self.links.new(value.outputs[0], sock)
            return
        t = sock.type
        if t == 'RGBA':
            value = rgb(value)
        elif t == 'VECTOR' and isinstance(value, (int, float)):
            value = (value, value, value)
        elif t in ('VALUE', 'INT') and isinstance(value, str):
            raise TypeError("colour given to a value socket: %s" % sock.name)
        sock.default_value = value

    @staticmethod
    def _sock(node, key, outputs=False):
        socks = node.outputs if outputs else node.inputs
        if isinstance(key, int):
            return socks[key]
        for s in socks:
            if s.identifier == key and not s.is_unavailable:
                return s
        k = _key(key)
        for s in socks:
            if _key(s.name) == k and not s.is_unavailable:
                return s
        for s in socks:
            if _key(s.name) == k:
                return s
        raise KeyError("%s has no socket %r (have %s)" % (node.bl_idname, key, [s.name for s in socks]))

    def node(self, idname, inputs=None, **props):
        """Create a node, set RNA ``props`` then ``inputs`` {socket name/identifier: value}."""
        n = self.nodes.new(idname)
        self._n += 1
        n.location = (-200 * (self._n % 7), -180 * (self._n // 7))
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(self._sock(n, k), v)
        return n

    def _shared_node(self, idname, **props):
        key = (idname, tuple(sorted(props.items())))
        if key not in self._shared:
            self._shared[key] = self.node(idname, **props)
        return self._shared[key]

    # ---- inputs
    def coord(self, space="object", scale=None, offset=None, rotation=None):
        """Texture coordinates. space: 'object' (object coords x object scale = meters on the
        object's axes), 'object_raw', 'world' (world position, meters), 'generated' (0-1 box),
        'uv', 'normal' (world normal). Optional Mapping scale/offset/rotation."""
        if space == "object":
            key = "objm"
            if key not in self._shared:
                tc = self._shared_node("ShaderNodeTexCoord")
                at = self._shared_node("ShaderNodeAttribute", attribute_type='OBJECT', attribute_name="scale")
                self._shared[key] = self.vmath('MULTIPLY', tc.outputs["Object"], at.outputs["Vector"])
            v = self._shared[key]
        elif space == "object_raw":
            v = self._shared_node("ShaderNodeTexCoord").outputs["Object"]
        elif space == "generated":
            v = self._shared_node("ShaderNodeTexCoord").outputs["Generated"]
        elif space == "uv":
            v = self._shared_node("ShaderNodeTexCoord").outputs["UV"]
        elif space == "world":
            v = self._shared_node("ShaderNodeNewGeometry").outputs["Position"]
        elif space == "normal":
            v = self._shared_node("ShaderNodeNewGeometry").outputs["Normal"]
        else:
            raise ValueError("unknown coord space %r" % space)
        if scale is None and offset is None and rotation is None:
            return v
        return self.mapping(v, scale=scale, offset=offset, rotation=rotation)

    def mapping(self, vec, scale=None, offset=None, rotation=None):
        """Mapping node (POINT): scale, then rotate (radians XYZ), then add offset."""
        inputs = {"Vector": vec}
        if scale is not None:
            inputs["Scale"] = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
        if offset is not None:
            inputs["Location"] = offset
        if rotation is not None:
            inputs["Rotation"] = rotation
        return self.node("ShaderNodeMapping", inputs, vector_type='POINT').outputs[0]

    def geometry(self, out="Normal"):
        """Geometry node output: Position, Normal (world), True Normal, Incoming, Backfacing..."""
        return self._shared_node("ShaderNodeNewGeometry").outputs[out]

    def obj_random(self):
        """Object Info > Random (0-1, differs per object and per instance)."""
        return self._shared_node("ShaderNodeObjectInfo").outputs["Random"]

    def obj_rand3(self):
        """Three decorrelated per-object randoms as a colour/vector socket (0-1 each)."""
        if "rand3" not in self._shared:
            wn = self.node("ShaderNodeTexWhiteNoise", {"W": self.obj_random()}, noise_dimensions='1D')
            self._shared["rand3"] = wn.outputs["Color"]
        return self._shared["rand3"]

    def attr(self, name, kind='GEOMETRY', out="Fac"):
        """Attribute node output (missing attributes read as 0)."""
        n = self._shared_node("ShaderNodeAttribute", attribute_type=kind, attribute_name=name)
        return self._sock(n, out, outputs=True)

    def obj_prop(self, name, default=1.0):
        """Object custom property ``obj[name]`` as a value; ``default`` when it is missing (or 0)."""
        a = self.attr(name, kind='OBJECT')
        missing = self.math('COMPARE', a, 0.0, 1e-6)
        return self.math('MULTIPLY_ADD', missing, default, a)

    def edge(self):
        """1 on bevel faces written by util.bevel_mesh(), else 0."""
        return self.attr("edge")

    def layer_weight(self, blend=0.5, out="Facing"):
        return self._sock(self.node("ShaderNodeLayerWeight", {"Blend": blend}), out, outputs=True)

    def fresnel(self, ior=1.45):
        return self.node("ShaderNodeFresnel", {"IOR": ior}).outputs[0]

    def ao(self, distance=0.3, only_local=False):
        """Ambient occlusion factor (1 open, 0 occluded). EEVEE: screen-space horizon scan."""
        n = self.node("ShaderNodeAmbientOcclusion", {"Distance": distance}, samples=8, only_local=only_local)
        return n.outputs["AO"]

    def frame_driven(self, sock, expr="frame", index=None):
        """Drive a socket's default value with a simple expression of ``frame`` (animates in renders)."""
        fc = sock.driver_add("default_value", index) if index is not None else sock.driver_add("default_value")
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = expr
        return sock

    def flow(self, vec, velocity=(0, 0, 0.0)):
        """Offset coordinates by velocity * frame (meters per frame); animates textures."""
        n = self.node("ShaderNodeMapping", {"Vector": vec}, vector_type='POINT')
        loc = n.inputs["Location"]
        for i, v in enumerate(velocity):
            if v:
                self.frame_driven(loc, "frame*%r" % float(v), i)
        return n.outputs[0]

    # ---- textures
    def noise(self, vec, scale=1.0, detail=2.0, roughness=0.5, lacunarity=2.0, distortion=0.0,
              dims='3D', ntype='FBM', w=None, color=False, normalize=True):
        """Noise texture; returns Fac (0-1) or Color."""
        inputs = {"Vector": vec, "Scale": scale, "Detail": detail, "Roughness": roughness,
                  "Lacunarity": lacunarity, "Distortion": distortion}
        if w is not None:
            inputs["W"] = w
        n = self.node("ShaderNodeTexNoise", inputs, noise_dimensions=dims, noise_type=ntype, normalize=normalize)
        return n.outputs[1] if color else n.outputs[0]

    def voronoi(self, vec, scale=1.0, feature='F1', distance='EUCLIDEAN', randomness=1.0, out="Distance",
                dims='3D', w=None, detail=0.0):
        """Voronoi texture; out: Distance, Color, Position, Radius."""
        inputs = {"Vector": vec, "Scale": scale, "Randomness": randomness, "Detail": detail}
        if w is not None:
            inputs["W"] = w
        n = self.node("ShaderNodeTexVoronoi", inputs, feature=feature, distance=distance, voronoi_dimensions=dims)
        return self._sock(n, out, outputs=True)

    def wave(self, vec, scale=1.0, distortion=0.0, detail=2.0, detail_scale=1.0, kind='BANDS',
             direction='Z', profile='SIN', phase=0.0):
        """Wave texture Fac. BANDS along X/Y/Z/DIAGONAL or RINGS around X/Y/Z/SPHERICAL.
        Period = 0.314 / scale (in the units of ``vec``)."""
        props = dict(wave_type=kind, wave_profile=profile)
        if kind == 'BANDS':
            props["bands_direction"] = direction
        else:
            props["rings_direction"] = direction
        n = self.node("ShaderNodeTexWave", {"Vector": vec, "Scale": scale, "Distortion": distortion,
                                            "Detail": detail, "Detail Scale": detail_scale,
                                            "Phase Offset": phase}, **props)
        return n.outputs[1]

    def image(self, img, vec, out="Color", interpolation='Linear'):
        """Image Texture of ``img`` (a bpy Image, see scan_image) at ``vec`` (FLAT: x, y; repeats); Color or
        Alpha. ``vec`` is required: the web bake gives meshes without UVs a (0, 0) UV, so an unwired node would
        sample a single texel."""
        if vec is None:
            raise ValueError("image(): pass texture coordinates, never the implicit UV")
        n = self.node("ShaderNodeTexImage", {"Vector": vec}, image=img, interpolation=interpolation,
                      projection='FLAT', extension='REPEAT')
        return self._sock(n, out, outputs=True)

    def triplanar(self, images, tile=1.0, sharp=4.0):
        """World-space triplanar lookup: one blended colour socket per image in ``images``. Three flat lookups of
        world (y, z), (x, z) and (x, y) divided by ``tile`` (m, or (u, v) m for non-square images), blended by
        |world normal|^sharp. Geometry Position / Normal are world space in the film and in bake_web's joined
        bake mesh, and bake_web.rewrite_material leaves them alone (it redirects object coords)."""
        tu, tv = (tile, tile) if isinstance(tile, (int, float)) else tile
        px, py, pz = self.sep(self.coord("world"))
        offs = ((0.0, 0.0), (0.37, 0.61), (0.71, 0.13))   # decorrelates the three planes where they blend
        uvs = [self.mapping(self.comb(a, b), scale=(1.0 / tu, 1.0 / tv, 1.0), offset=(ox, oy, 0.0))
               for (a, b), (ox, oy) in zip(((py, pz), (px, pz), (px, py)), offs)]
        ws = [self.math('POWER', self.math('ABSOLUTE', c), sharp) for c in self.sep(self.geometry("Normal"))]
        tot = self.add(self.add(ws[0], ws[1]), ws[2])
        ws = [self.math('DIVIDE', w, tot) for w in ws]
        outs = []
        for img in images:
            acc = None
            for uv, w in zip(uvs, ws):
                c = self.vmath('SCALE', self.image(img, uv), scale=w)
                acc = c if acc is None else self.vmath('ADD', acc, c)
            outs.append(acc)
        return outs

    def ramp(self, fac, stops, interp='LINEAR', alpha=False):
        """Color ramp from [(position, colour), ...]; returns Color (or Alpha)."""
        n = self.node("ShaderNodeValToRGB", {"Fac": fac})
        cr = n.color_ramp
        cr.interpolation = interp
        els = cr.elements
        while len(els) > 1:
            els.remove(els[-1])
        stops = sorted(stops, key=lambda s: s[0])
        els[0].position = stops[0][0]
        for pos, _ in stops[1:]:
            els.new(pos)
        for el, (pos, col) in zip(sorted(els, key=lambda e: e.position), stops):
            el.position = pos
            el.color = rgb(col)
        return n.outputs[1] if alpha else n.outputs[0]

    # ---- math
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if c is not None:
            self.set(n.inputs[2], c)
        return n.outputs[0]

    def mul(self, a, b, clamp=False):
        return self.math('MULTIPLY', a, b, clamp=clamp)

    def add(self, a, b, clamp=False):
        return self.math('ADD', a, b, clamp=clamp)

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if scale is not None:
            self.set(self._sock(n, "Scale"), scale)
        return n.outputs["Value"] if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else n.outputs["Vector"]

    def sep(self, vec):
        """Separate XYZ -> (x, y, z) sockets."""
        n = self.node("ShaderNodeSeparateXYZ", {"Vector": vec})
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x=0.0, y=0.0, z=0.0):
        return self.node("ShaderNodeCombineXYZ", {"X": x, "Y": y, "Z": z}).outputs[0]

    def maprange(self, v, from_min=0.0, from_max=1.0, to_min=0.0, to_max=1.0, clamp=True, interp='LINEAR'):
        n = self.node("ShaderNodeMapRange", clamp=clamp, interpolation_type=interp, data_type='FLOAT')
        for i, val in enumerate((v, from_min, from_max, to_min, to_max)):
            self.set(n.inputs[i], val)
        return n.outputs[0]

    def smooth(self, v, edge0, edge1):
        """Smoothstep of v from edge0 to edge1 (0-1)."""
        return self.maprange(v, edge0, edge1, 0.0, 1.0, True, 'SMOOTHSTEP')

    def mix(self, a, b, fac, blend='MIX', clamp=True):
        """Mix two colours (A at fac 0, B at fac 1)."""
        n = self.node("ShaderNodeMix", data_type='RGBA', blend_type=blend, clamp_result=clamp)
        self.set(self._sock(n, "Factor_Float"), fac)
        self.set(self._sock(n, "A_Color"), a)
        self.set(self._sock(n, "B_Color"), b)
        return self._sock(n, "Result_Color", outputs=True)

    def mixf(self, a, b, fac):
        """Mix two floats."""
        n = self.node("ShaderNodeMix", data_type='FLOAT')
        self.set(self._sock(n, "Factor_Float"), fac)
        self.set(self._sock(n, "A_Float"), a)
        self.set(self._sock(n, "B_Float"), b)
        return self._sock(n, "Result_Float", outputs=True)

    def hsv(self, color, hue=0.5, sat=1.0, val=1.0, fac=1.0):
        return self.node("ShaderNodeHueSaturation", {"Hue": hue, "Saturation": sat, "Value": val,
                                                     "Fac": fac, "Color": color}).outputs[0]

    def tint_per_object(self, color, hue=0.01, sat=0.08, val=0.10):
        """Shift ``color`` per object/instance by up to +-hue, +-sat, +-val (relative)."""
        r = self.obj_rand3()
        rx, ry, rz = self.sep(r)
        h = self.maprange(rx, 0, 1, 0.5 - hue, 0.5 + hue)
        s = self.maprange(ry, 0, 1, 1 - sat, 1 + sat)
        v = self.maprange(rz, 0, 1, 1 - val, 1 + val)
        return self.hsv(color, h, s, v)

    def bump(self, height, strength=0.2, distance=0.02, normal=None, invert=False):
        """Bump node -> normal socket. Chain by passing a previous bump as ``normal``."""
        n = self.node("ShaderNodeBump", {"Strength": strength, "Distance": distance, "Height": height},
                      invert=invert)
        if normal is not None:
            self.set(n.inputs["Normal"], normal)
        return n.outputs[0]

    # ---- shaders
    def principled(self, **inputs):
        """Principled BSDF; keyword names are socket names in snake_case (base_color, roughness,
        coat_weight, sheen_weight, subsurface_weight, emission_color, emission_strength, alpha...)."""
        n = self.node("ShaderNodeBsdfPrincipled")
        for k, v in inputs.items():
            self.set(self._sock(n, k), v)
        return n.outputs[0]

    def volume(self, **inputs):
        """Principled Volume; keywords: color, density, anisotropy, absorption_color, emission_strength..."""
        n = self.node("ShaderNodeVolumePrincipled")
        for k, v in inputs.items():
            self.set(self._sock(n, k), v)
        return n.outputs[0]

    def emission(self, color, strength=1.0):
        return self.node("ShaderNodeEmission", {"Color": color, "Strength": strength}).outputs[0]

    def transparent(self, color=(1, 1, 1, 1)):
        return self.node("ShaderNodeBsdfTransparent", {"Color": color}).outputs[0]

    def translucent(self, color, normal=None):
        n = self.node("ShaderNodeBsdfTranslucent", {"Color": color})
        if normal is not None:
            self.set(n.inputs["Normal"], normal)
        return n.outputs[0]

    def add_shader(self, a, b):
        n = self.node("ShaderNodeAddShader")
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def mix_shader(self, fac, a, b):
        n = self.node("ShaderNodeMixShader")
        self.set(n.inputs[0], fac)
        self.set(n.inputs[1], a)
        self.set(n.inputs[2], b)
        return n.outputs[0]

    def output(self, surface=None, volume=None):
        if surface is not None:
            self.set(self.out.inputs["Surface"], surface)
        if volume is not None:
            self.set(self.out.inputs["Volume"], volume)
        return self.out

    # ---- material settings
    def viewport(self, color, roughness=0.5, metallic=0.0):
        """Solid-view colour (does not affect renders)."""
        c = rgb(color)
        self.mat.diffuse_color = c
        self.mat.roughness = roughness
        self.mat.metallic = metallic

    def blended(self, shadows=False):
        """EEVEE forward-rendered transparency (coloured/additive). shadows=False: casts none."""
        m = self.mat
        m.surface_render_method = 'BLENDED'
        m.use_backface_culling = False
        m.use_transparency_overlap = True
        m.use_transparent_shadow = True
        if hasattr(m, "use_backface_culling_shadow"):
            m.use_backface_culling_shadow = False
        # shadows=False relies on a fully transparent BSDF + transparent shadows (no occlusion);
        # for speed also call util.set_visibility(obj, shadow=False) on such objects.
        m.use_transparent_shadow = True if not shadows else m.use_transparent_shadow


# ============================================================ registry API

def register(name, builder, overwrite=False, **params):
    """Register material ``name`` built by ``builder(g, **params)`` (g is a Graph on a fresh
    material). Lets any module add materials without editing this file. Returns ``name``."""
    if name in _REGISTRY and not overwrite:
        return name
    _REGISTRY[name] = (builder, params)
    if name not in NAMES:
        NAMES.append(name)
    if overwrite:  # rebuild an already-built material in place so existing users update
        for m in bpy.data.materials:
            if m.get(TAG) == name and m.library is None:
                builder(Graph(m), **params)
    return name


def variant(name, base, **params):
    """Register ``name`` as ``base`` with some builder parameters overridden, e.g.
    variant('lacquer_black', 'lacquer_red', c1='#121010', c2='#1e1a18'). Returns ``name``."""
    builder, p = _REGISTRY[base]
    merged = dict(p)
    merged.update(params)
    return register(name, builder, **merged)


def has(name):
    """True if ``name`` is a registered material name."""
    return name in _REGISTRY


def get(name):
    """Shared material ``name`` (built on first use, then reused). KeyError lists valid names."""
    mat = _CACHE.get(name)
    if mat is not None:
        try:
            if mat.get(TAG) == name:
                return mat
        except ReferenceError:
            pass
    if name not in _REGISTRY:
        raise KeyError("unknown material %r; valid names: %s" % (name, ", ".join(NAMES)))
    for m in bpy.data.materials:
        if m.get(TAG) == name and m.library is None:
            _CACHE[name] = m
            return m
    builder, params = _REGISTRY[name]
    mat = bpy.data.materials.new(PREFIX + name)
    mat[TAG] = name
    g = Graph(mat)
    builder(g, **params)
    _CACHE[name] = mat
    return mat


def rebuild(name):
    """Rebuild an existing material's node tree in place (objects keep using it)."""
    mat = get(name)
    builder, params = _REGISTRY[name]
    builder(Graph(mat), **params)
    return mat


def get_all():
    """Build and return every registered material (useful for swatch boards)."""
    return [get(n) for n in NAMES]


BANNER_COLOURS = [
    ("vermilion", "#a8231c"),
    ("imperial_gold", "#c9962e"),
    ("jade", "#2f7a5f"),
    ("teal", "#245f63"),
    ("indigo", "#22386a"),
    ("moon_white", "#e3ddd0"),
    ("plum", "#6b2a4c"),
    ("ink_black", "#1d1c20"),
]


def banner_cloth(i):
    """Banner cloth material ``i`` (any int; wraps around 8 harmonious colours)."""
    return get("banner_%d" % (int(i) % len(BANNER_COLOURS)))


# ============================================================ shared building blocks

def _fine_bump(g, v, scale=40.0, strength=0.05, distance=0.01, normal=None):
    return g.bump(g.noise(v, scale, detail=3.0, roughness=0.6), strength, distance, normal)


def _soft_box(g, edge=0.18, top=0.35, bottom=0.12):
    """0-1 mask that fades a volume to zero toward its bounding box (generated coords), so a
    cube domain reads as a soft cloud. Radial in XY, separate top/bottom fades."""
    gen = g.coord("generated")
    x, y, z = g.sep(gen)
    cx = g.math('SUBTRACT', x, 0.5)
    cy = g.math('SUBTRACT', y, 0.5)
    r = g.math('SQRT', g.add(g.mul(cx, cx), g.mul(cy, cy)))
    radial = g.smooth(r, 0.5, 0.5 - edge)
    zb = g.smooth(z, 0.0, max(bottom, 1e-3))
    zt = g.smooth(z, 1.0, 1.0 - max(top, 1e-3))
    return g.mul(g.mul(radial, zb), zt)


# ============================================================ photo scans

_SCAN_MEAN = {}


def scan_files():
    """Every file name the scan layers read from SCAN_DIR."""
    rock = [s[k] for s in ROCK_SCANS.values() for k in ("diff", "disp")]
    return rock + list(LAWN_SCANS.values()) + list(GROUND_SCANS.values())


def scan_image(fname, data=False):
    """Image ``SCAN_DIR/fname`` (absolute path, loaded once: check_existing). ``data``: height or mask map
    (Non-Color) instead of an sRGB colour map. None, with a warning, when the file is missing, so a builder keeps
    its procedural look (sect/patch_nature_look.py refuses to run without the files)."""
    path = os.path.join(SCAN_DIR, fname)
    if not os.path.isfile(path):
        print("WARN materials: scan missing, photo layer skipped:", path, flush=True)
        return None
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return img


def scan_mean(img, weight=None):
    """Mean linear luminance of colour image ``img``, weighted by the first channel of ``weight`` (a mask of the
    same size) when given. Read once per session from the pixels; 0.18 when they cannot be read."""
    key = (img.filepath, weight.filepath if weight is not None else "")
    if key in _SCAN_MEAN:
        return _SCAN_MEAN[key]
    mean = 0.18
    try:
        import numpy as np

        def pixels(im):
            a = np.empty(im.size[0] * im.size[1] * im.channels, np.float32)
            if not a.size:
                raise RuntimeError("no pixels")
            im.pixels.foreach_get(a)   # byte images: raw 0-1 values, i.e. still sRGB-encoded
            return a.reshape(-1, im.channels)[::5]

        px = pixels(img)
        c = px[:, :3] if px.shape[1] >= 3 else np.repeat(px[:, :1], 3, axis=1)
        if not img.is_float:
            c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        lum = c @ np.array(LUMA, np.float32)
        w = pixels(weight)[:, 0] if weight is not None and tuple(weight.size) == tuple(img.size) else None
        mean = float(lum.mean()) if w is None else float((lum * w).sum() / max(float(w.sum()), 1e-6))
        mean = max(mean, 1e-3)
        print("materials: scan mean luminance %s%s = %.4f" % (img.name, " / " + weight.name if w is not None
                                                                else "", mean), flush=True)
    except Exception as e:   # no numpy or an unreadable file: only the normalisation is lost
        print("WARN materials: scan mean of %s failed (%s), using %.2f" % (img.name, e, mean), flush=True)
    _SCAN_MEAN[key] = mean
    return mean


def _photo_mix(g, col, rel, amount, contrast=1.0, hue=1.0):
    """Mix a photo into ``col`` by ``amount`` (0-1 or socket) at the procedural brightness. ``rel`` is the photo
    divided by its mean luminance (mean 1); 1 - ``contrast`` pulls it toward its own hue at luminance 1
    ((rel + e) / (lum(rel) + e)), and it is multiplied by the luminance of ``col``, so the photo brings hue and
    fine structure while large tonal zones, strata, stains and patches keep their brightness. ``hue`` below 1
    keeps that share of the procedural hue: the photo's luminance still modulates ``col`` by ``amount``, but only
    ``amount * hue`` of the photo's own colour comes in (a yellow-green lawn scan on a greener palette)."""
    if contrast != 1.0:
        e = 0.05   # LUMA sums to 1, so the hue keeps luminance 1; e keeps near-black texels neutral, not noisy
        tint = g.vmath('SCALE', g.vmath('ADD', rel, (e, e, e)),
                       scale=g.math('DIVIDE', 1.0, g.add(g.vmath('DOT_PRODUCT', rel, LUMA), e)))
        rel = g.mix(tint, rel, contrast, clamp=False)
    lum = g.vmath('DOT_PRODUCT', col, LUMA)
    photo = g.vmath('SCALE', rel, scale=lum)
    if hue >= 1.0:
        return g.mix(col, photo, amount)
    shade = g.mixf(1.0, g.vmath('DOT_PRODUCT', rel, LUMA), amount)   # 1 + amount * (lum(rel) - 1)
    return g.mix(g.vmath('SCALE', col, scale=shade), photo, g.mul(amount, hue))


def _rock_scan(g, col, scan, scale=1.0):
    """_rock's photo layer: ROCK_SCANS[scan] in world triplanar, its tile times ``scale`` -> (colour, height
    socket or None)."""
    s = ROCK_SCANS[scan]
    diff = scan_image(s["diff"])
    if diff is None:
        return col, None
    disp = scan_image(s["disp"], data=True)
    tile = (s["tile"][0] * scale, s["tile"][1] * scale)
    outs = g.triplanar([diff] + ([disp] if disp is not None else []), tile, ROCK_SCAN_SHARP)
    rel = g.vmath('SCALE', outs[0], scale=1.0 / scan_mean(diff))
    col = _photo_mix(g, col, rel, ROCK_SCAN_MIX, ROCK_SCAN_CONTRAST, ROCK_SCAN_HUE)
    return col, (g.sep(outs[1])[0] if disp is not None else None)


def _rock_life(g, col, moss_amt=1.0):
    """_rock's life layer (ROCK_* constants) over colour ``col``, in world space: damp undersides, dark streaks
    dripping from every ledge line (z = n * ROCK_LAYER, warped), ochre and grey-green lichen on the dry rock, then
    moss with a noisy edge on up-facing rock, in clumps along the ledge lines and over the lip under a grass rim
    (ROCK_LIP_MOSS), all times ``moss_amt``, _rock's parameter. The material's tag picks its ROCK_LIFE_VARIANTS
    multipliers. -> dict(col, moss, wet, moss_h): colour, moss and wetness masks (0-1) and the moss photo's luminance
    for the bump chain (None without it)."""
    p = dict(moss=1.0, streak=1.0, lichen=1.0, damp=1.0, scale=1.0, ledge=1.0, lip=1.0)
    p.update(ROCK_LIFE_VARIANTS.get(g.mat.get(TAG), {}))
    k = float(ROCK_LIFE_SCALE) * float(p["scale"])
    P = g.coord("world")
    px, py, pz = g.sep(P)
    Pk = P if k == 1.0 else g.vmath('SCALE', P, scale=k)
    xy = g.comb(px, py)                       # constant down a vertical line: per-streak values
    up = g.sep(g.geometry("Normal"))[2]
    steep = g.smooth(g.math('ABSOLUTE', up), 0.85, 0.45)

    def shifted(off):
        return g.vmath('ADD', Pk, off)        # decorrelates noises that share a scale

    # ledge lines: phase 0 on a line, rising to 1 just under the lip of the next one up; each layer (floor index)
    # and each line (nearest index) gets its own random field, so no two read alike
    L = float(ROCK_LAYER)
    zw = g.math('MULTIPLY_ADD', g.math('SUBTRACT', g.noise(xy, 0.02 * k, detail=2.0), 0.5), 2.0 * ROCK_LAYER_WARP, pz)
    zl = g.math('DIVIDE', zw, L)
    ph = g.math('FRACT', zl)
    layer = g.math('SUBTRACT', zl, ph)
    line = g.math('ROUND', zl)

    # damp: overhang undersides, plus recesses when the (ray-traced) AO node is on
    damp = g.smooth(up, -0.1, -0.6)
    recess = None
    ao_dist, ao_samples = ROCK_DAMP_AO
    if ao_samples:
        ao = g.node("ShaderNodeAmbientOcclusion", {"Distance": float(ao_dist)}, samples=int(ao_samples),
                    only_local=False)
        recess = g.smooth(ao.outputs["AO"], 0.85, 0.4)
        damp = g.math('MAXIMUM', damp, recess)

    # streaks: vertical noise columns, each running a different share of the layer down from the lip above
    # and gathered into wet courses (vertical bands of cliff, xy-only noise) where some run the whole height
    core = g.smooth(g.noise(g.mapping(Pk, scale=(ROCK_STREAK_WIDTH, ROCK_STREAK_WIDTH, 0.05)), 1.0, detail=4.0,
                            roughness=0.55, distortion=0.15), 0.46, 0.55)
    curtain = g.smooth(g.noise(g.mapping(shifted((4.4, 8.8, 2.2)), scale=(0.18, 0.18, 0.015)), 1.0, detail=2.0,
                               distortion=0.1), 0.48, 0.6)                   # broad 3-6 m stains the bake keeps
    core = g.math('MAXIMUM', core, g.mul(curtain, 0.85))
    span = g.maprange(g.noise(g.comb(g.mul(px, 0.45 * k), g.mul(py, 0.45 * k), g.mul(layer, 2.3)), 1.0, detail=1.0),
                      0.35, 0.65, ROCK_STREAK_LEN[0], ROCK_STREAK_LEN[1])
    drip = g.smooth(ph, g.math('SUBTRACT', 1.0, span), 1.0)
    course = g.noise(xy, 0.04 * k, detail=2.0)
    drip = g.math('MAXIMUM', drip, g.mul(g.smooth(g.noise(xy, 0.35 * k, detail=1.0), 0.58, 0.64),
                                         g.smooth(course, 0.5, 0.62)))          # full-height curtains
    drip = g.mul(drip, g.maprange(course, 0.38, 0.6, 0.2, 1.0))                # dry and wet stretches of cliff
    if recess is not None:
        drip = g.math('MAXIMUM', drip, g.mul(recess, 0.8))
    s_amt = float(ROCK_STREAK) * p["streak"]
    streak = g.mul(g.mul(g.mul(core, drip), steep), g.math('MULTIPLY_ADD', damp, 0.25 * s_amt, 0.75 * s_amt),
                   clamp=True)
    wash = g.mul(g.mul(drip, steep), g.maprange(g.noise(shifted((7.1, 3.9, 1.7)), 0.05, detail=2.0), 0.3, 0.7,
                                                0.0, float(ROCK_STREAK_WASH) * p["streak"]))
    dark = g.hsv(col, 0.5, 0.85, 0.33)
    algae = g.mul(g.smooth(g.noise(shifted((2.3, 19.7, 4.1)), 0.07, detail=2.0), 0.42, 0.6), ROCK_STREAK_ALGAE)
    dark = g.mix(dark, "#b4cca0", algae, blend='MULTIPLY')
    jade = g.mul(g.smooth(g.noise(shifted((31.7, 11.3, 5.9)), 0.03, detail=2.0), 0.56, 0.66), ROCK_STREAK_JADE)
    dark = g.mix(dark, "#4f9a88", jade, blend='COLOR')
    col = g.mix(col, dark, wash)
    col = g.mix(col, dark, streak)
    col = g.mix(col, g.hsv(col, 0.5, 0.95, 0.7), g.mul(damp, float(ROCK_DAMP) * p["damp"]))
    wet = g.math('MAXIMUM', streak, g.mul(damp, 0.5))

    # lichen on the dry rock: ochre crusts on lichen-rich faces, grey-green elsewhere; more of it high up
    dry = g.math('SUBTRACT', 1.0, g.math('MAXIMUM', streak, damp), clamp=True)
    alt = g.maprange(pz, ROCK_MOSS_ALT[0], ROCK_MOSS_ALT[1], 0.0, 1.0)
    l_amt = g.mul(g.mul(dry, g.maprange(alt, 0.0, 1.0, 0.8, 1.2)), float(ROCK_LICHEN) * p["lichen"])
    region = g.smooth(g.noise(shifted((5.3, 17.9, 2.1)), 0.045, detail=2.0), 0.38, 0.62)
    l1 = g.mul(g.smooth(g.noise(Pk, 0.55, detail=5.0, roughness=0.6, distortion=0.7), 0.565, 0.61), region)
    l2 = g.mul(g.smooth(g.noise(shifted((13.7, 2.9, 8.3)), 0.8, detail=5.0, distortion=0.5), 0.57, 0.61),
               g.math('MULTIPLY_ADD', region, -0.65, 1.0))
    col = g.mix(col, ROCK_LICHEN_COLOURS[0], g.mul(l1, l_amt))
    col = g.mix(col, ROCK_LICHEN_COLOURS[1], g.mul(g.mul(l2, l_amt), 0.5))

    # moss on up-facing rock: past a normal-z threshold that 2-5 m noise (patch shapes, ragged by 1 m noise), regional
    # noise (lush / sparse) and height move; bare outcrops break it even on the flattest rock
    e_mid = g.noise(Pk, 0.22, detail=3.0, roughness=0.55, distortion=0.4)      # patch shapes (2-5 m)
    e_fine = g.noise(shifted((6.1, 12.7, 0.9)), 1.1, detail=3.0, distortion=0.6)   # ragged edges
    e_big = g.noise(shifted((13.1, 7.7, 3.3)), 0.035, detail=3.0)
    lift = g.mul(alt, ROCK_MOSS_ALT[2])
    f = g.math('MULTIPLY_ADD', g.math('SUBTRACT', e_mid, 0.5), 2.0 * ROCK_MOSS_EDGE, up)
    f = g.math('MULTIPLY_ADD', g.math('SUBTRACT', e_fine, 0.5), 0.5 * ROCK_MOSS_EDGE, f)
    f = g.math('MULTIPLY_ADD', g.math('SUBTRACT', e_big, 0.5), 2.0 * ROCK_MOSS_PATCH, g.math('SUBTRACT', f, lift))
    lo, hi = ROCK_MOSS_UP
    bare = g.smooth(g.noise(shifted((23.3, 1.9, 11.1)), 0.3, detail=4.0, roughness=0.6, distortion=0.5),
                    ROCK_MOSS_BARE[0], ROCK_MOSS_BARE[1])
    m_up = g.mul(g.smooth(f, lo, hi), g.math('SUBTRACT', 1.0, bare))
    halo = g.mul(g.smooth(f, lo - 0.15, lo), g.math('SUBTRACT', 1.0, m_up))

    # ledge clumps: moss cushions sitting on every ledge line, their height (m) varying along the line, from line to
    # line and with the slope (on about 15 % of a line's length on a vertical wall, 25 % at normal z 0.15, 40 % on a
    # 0.28 cone wall, 65 % at 0.5); a shorter fringe hangs below the lip, and green drapes trail down from some
    ledge_amt = float(ROCK_MOSS_LEDGE) * float(p["ledge"])
    m_drape = None
    moss = m_up
    if ledge_amt > 0.0:
        n_along = g.noise(shifted((17.3, 29.1, 0.7)), 0.12, detail=3.0)
        per_line = g.noise(g.comb(g.mul(px, 0.012 * k), g.mul(py, 0.012 * k), g.mul(line, 1.7)), 1.0, detail=1.0)
        h = g.maprange(up, -0.3, 0.6, -0.94, 0.32)
        h = g.math('MULTIPLY_ADD', g.math('SUBTRACT', n_along, 0.5), 6.0, h)
        h = g.math('MULTIPLY_ADD', g.math('SUBTRACT', per_line, 0.5), 4.0, h)
        h = g.math('SUBTRACT', h, g.add(g.mul(lift, 3.0), g.maprange(up, -0.45, -0.25, 3.0, 0.0)))   # none underneath
        h = g.math('MINIMUM', h, 1.5)             # cushions and drapes stay inside the half layer their line owns
        fr = g.mul(g.math('SUBTRACT', g.noise(shifted((3.1, 5.3, 23.9)), 1.1, detail=3.0, distortion=0.5), 0.5), 4.0)
        above = g.mul(ph, L)                                               # m above the ledge line under this point
        below = g.mul(g.math('SUBTRACT', 1.0, ph), L)                      # m below the lip over it
        h_up = g.math('MULTIPLY_ADD', h, ROCK_MOSS_LEDGE_W[0], fr)         # lumpy cushion tops
        h_dn = g.math('MULTIPLY_ADD', h, ROCK_MOSS_LEDGE_W[1], g.mul(fr, 0.5))
        m_band = g.math('MAXIMUM', g.smooth(above, h_up, g.math('SUBTRACT', h_up, 0.15)),
                        g.smooth(below, h_dn, g.math('SUBTRACT', h_dn, 0.1)))
        drape_col = g.smooth(g.noise(g.mapping(shifted((9.7, 4.1, 0.3)), scale=(1.6, 1.6, 0.08)), 1.0, detail=3.0,
                                     distortion=0.2), 0.53, 0.6)
        h_drape = g.mul(g.mul(g.math('MAXIMUM', h, 0.0), ROCK_MOSS_DRAPE[1]),
                        g.math('MULTIPLY_ADD', drape_col, 0.6, 0.4))
        h_drape = g.math('MINIMUM', h_drape, 0.45 * L)
        # (+0.01: with h <= 0 both edges would be 0, and Cycles' smoothstep of equal edges is 1, not 0)
        m_drape = g.mul(g.mul(g.smooth(below, g.add(h_drape, 0.01), g.mul(h_drape, 0.4)), drape_col),
                        ROCK_MOSS_DRAPE[0])
        m_band = g.mul(g.math('MAXIMUM', m_band, m_drape), ledge_amt)
        moss = g.math('MAXIMUM', m_up, m_band)
    # lip moss: the top of the rock under a grass rim (and other rock nearly flat enough for grass) mossed over, its
    # lower edge hanging down in tongues; half the bare outcrops stay. Tinted toward the cap's greens (below), so the
    # grass runs on into the moss instead of ending on a line
    lip = None
    lp = _conf("ROCK_LIP_MOSS")
    lip_amt = float(lp["amount"]) * float(p["lip"])
    if lip_amt > 0.0:
        tw, ta = lp["tongue"]
        fl = g.math('MULTIPLY_ADD', g.math('SUBTRACT', g.noise(xy, k / float(tw), detail=2.0), 0.5), 2.0 * ta, up)
        fl = g.math('MULTIPLY_ADD', g.math('SUBTRACT', e_fine, 0.5), 0.5 * ta, fl)
        lip = g.mul(g.smooth(fl, lp["up"][0], lp["up"][1]), g.math('MULTIPLY_ADD', bare, -0.5, 1.0))
        moss = g.math('MAXIMUM', moss, g.mul(lip, lip_amt))
    if recess is not None and ROCK_MOSS_RECESS:
        m_rec = g.smooth(g.math('MULTIPLY_ADD', g.math('SUBTRACT', e_fine, 0.5), 0.6, recess), 0.45, 0.7)
        moss = g.math('MAXIMUM', moss, g.mul(g.mul(m_rec, steep), ROCK_MOSS_RECESS))
    moss = g.mul(moss, float(ROCK_MOSS) * p["moss"] * float(moss_amt), clamp=True)

    tone = g.add(g.mul(g.noise(shifted((3.7, 29.1, 8.3)), 0.06, detail=2.0), 0.7),
                 g.mul(g.noise(shifted((8.9, 1.3, 15.7)), 0.45, detail=3.0), 0.3))
    mcol = g.ramp(tone, ROCK_MOSS_COLOURS)
    if m_drape is not None:
        mcol = g.mix(mcol, g.hsv(mcol, 0.5, 0.9, 0.7), g.mul(m_drape, 0.6))   # drapes: the damper, darker moss
    if lip is not None and lp["grass"]:
        mcol = g.mix(mcol, g.ramp(tone, lp["colours"]), g.mul(lip, float(lp["grass"])))
    moss_h = None
    img = scan_image(GROUND_SCANS["moss"])
    if img is not None:
        rel = g.vmath('SCALE', g.triplanar([img], MOSS_TILE, ROCK_SCAN_SHARP)[0], scale=1.0 / scan_mean(img))
        mcol = _photo_mix(g, mcol, rel, ROCK_MOSS_SCAN_MIX, 1.0, ROCK_MOSS_SCAN_HUE)
        moss_h = g.vmath('DOT_PRODUCT', rel, LUMA)
    col = g.mix(col, g.hsv(col, 0.5, 0.9, 0.6), g.mul(halo, float(ROCK_MOSS_RIM) * float(ROCK_MOSS) * p["moss"] *
                                                      float(moss_amt), clamp=True))
    col = g.mix(col, mcol, moss)
    return dict(col=col, moss=moss, wet=wet, moss_h=moss_h)


def _lawn_scan(g, col):
    """grass's photo layer, top-down: leafy_grass, with sparse_grass's tufts where its mask is set (that set turned
    against the first so the two tiles never line up) -> (colour, height socket or None)."""
    leafy = scan_image(LAWN_SCANS["leafy"])
    sparse = scan_image(LAWN_SCANS["sparse"])
    mask = scan_image(LAWN_SCANS["mask"], data=True)
    if leafy is None or sparse is None or mask is None:
        return col, None
    k = 1.0 / LAWN_TILE
    va = g.coord("world", scale=(k, k, 1.0))
    vb = g.coord("world", scale=(k, k, 1.0), rotation=(0.0, 0.0, 1.1), offset=(0.43, 0.29, 0.0))
    m = g.sep(g.image(mask, vb))[0]
    rel = g.mix(g.vmath('SCALE', g.image(leafy, va), scale=1.0 / scan_mean(leafy)),
                g.vmath('SCALE', g.image(sparse, vb), scale=1.0 / scan_mean(sparse, mask)), m, clamp=False)
    col = _photo_mix(g, col, rel, LAWN_SCAN_MIX, LAWN_SCAN_CONTRAST, LAWN_SCAN_HUE)
    return col, g.vmath('DOT_PRODUCT', rel, LUMA)


def _ground_scan(g, col, fac):
    """nature_soil_moss's photo layer, top-down: grass_ground, Moss001 where the procedural ramp position ``fac``
    is green (GROUND_MOSS), faded out on steep faces (GROUND_FLAT) -> (colour, height socket or None)."""
    grass = scan_image(GROUND_SCANS["grass"])
    moss = scan_image(GROUND_SCANS["moss"])
    if grass is None or moss is None:
        return col, None
    kg, km = 1.0 / GROUND_TILE, 1.0 / MOSS_TILE
    vg = g.coord("world", scale=(kg, kg, 1.0))
    vm = g.coord("world", scale=(km, km, 1.0), rotation=(0.0, 0.0, 0.7), offset=(0.31, 0.57, 0.0))
    green = g.smooth(fac, *GROUND_MOSS)
    rel = g.mix(g.vmath('SCALE', g.image(grass, vg), scale=1.0 / scan_mean(grass)),
                g.vmath('SCALE', g.image(moss, vm), scale=1.0 / scan_mean(moss)), green, clamp=False)
    flat = g.smooth(g.sep(g.geometry("Normal"))[2], *GROUND_FLAT)
    col = _photo_mix(g, col, rel, g.mul(flat, GROUND_SCAN_MIX), GROUND_SCAN_CONTRAST, GROUND_SCAN_HUE)
    return col, g.mul(g.vmath('DOT_PRODUCT', rel, LUMA), flat)


# ============================================================ ground life

def _ss(x, e0, e1):
    """Python twin of Graph.smooth (Cycles' Map Range smoothstep, reversed when e0 > e1)."""
    if e0 > e1:
        return 1.0 - _ss(x, e1, e0)
    if x < e0:
        return 0.0
    if x >= e1:
        return 1.0
    t = (x - e0) / (e1 - e0)
    return t * t * (3.0 - 2.0 * t)


def _lum(c):
    """Linear luminance of anything rgb() reads."""
    r, gr, b = rgb(c)[:3]
    return LUMA[0] * r + LUMA[1] * gr + LUMA[2] * b


def _hue_of(g, col, hexc, value=1.0):
    """``hexc``'s hue and saturation at the luminance of colour socket ``col`` times ``value``: a tint target that keeps
    col's brightness pattern (photo, clumps) and only moves its colour."""
    c = rgb(hexc)
    k = 1.0 / max(_lum(c), 1e-4)
    lum = g.vmath('DOT_PRODUCT', col, LUMA)
    return g.vmath('SCALE', (c[0] * k, c[1] * k, c[2] * k), scale=lum if value == 1.0 else g.mul(lum, float(value)))


def _f1_mean(fn, n=48):
    """Mean of ``fn(d)`` over a 2D F1 Voronoi texture (randomness 1, Euclidean), ``d`` its Distance in cell units:
    an n x n grid of points over an 8 x 8 cell tile of seeded feature points (one per cell, as Blender places them)."""
    import random
    rnd = random.Random(5)
    pts = {(i, j): (i + rnd.random(), j + rnd.random()) for i in range(-1, 9) for j in range(-1, 9)}
    tot = 0.0
    for a in range(n):
        for b in range(n):
            x, y = (a + 0.5) * 8.0 / n, (b + 0.5) * 8.0 / n
            near = [pts[(int(x) + i, int(y) + j)] for i in (-1, 0, 1) for j in (-1, 0, 1)]
            tot += fn(min(math.hypot(x - px, y - py) for px, py in near))
    return tot / (n * n)


def _ground_life(g, col, fac):
    """grass's and nature_soil_moss's life layer (GROUND_* constants) over colour ``col``, in world space: dry and lush
    patches with damp hollows, grass clumps, a dry-grass, humus and moss band where the smooth normal turns down over a
    rim, and flower drifts on the gentle green ground. ``fac`` is the procedural ramp position (low = its brown end). ->
    (colour, clump height for the bump chain or None)."""
    P = g.coord("world")
    up = g.sep(g.geometry("Normal"))[2]

    def shifted(off):
        return g.vmath('ADD', P, off)         # decorrelates noises that share a scale

    # dry and lush patches (m: mean 0.5, sd ~0.065), brightness, damp hollows that lean lush
    gm = _conf("GROUND_MACRO")
    a = float(gm["amount"])
    if a > 0.0:
        s1, s2 = gm["scales"]
        m = g.math('MULTIPLY_ADD', g.noise(shifted((17.3, 5.1, 0.0)), 1.0 / s1, detail=2.0), 0.65,
                   g.mul(g.noise(shifted((3.9, 41.7, 0.0)), 1.0 / s2, detail=2.0), 0.35))
        share = float(gm["mix"]) * a
        dry = g.mul(g.smooth(m, 0.515, 0.575), share)
        lush = g.mul(g.smooth(m, 0.485, 0.425), share)
        damp = g.mul(g.smooth(g.noise(shifted((29.3, 11.9, 0.0)), 0.04, detail=2.0), 0.58, 0.66), a)
        col = g.mix(col, _hue_of(g, col, gm["dry"]), dry)
        col = g.mix(col, _hue_of(g, col, gm["lush"]), g.math('MAXIMUM', lush, g.mul(damp, 0.5)))
        v = float(gm["value"]) * a
        bright = g.maprange(g.noise(shifted((11.1, 23.3, 0.0)), 0.05, detail=2.0), 0.38, 0.62, 1.0 - v, 1.0 + v)
        bright = g.math('MULTIPLY_ADD', g.math('SUBTRACT', dry, lush), 0.5 * float(gm["value"]), bright)
        bright = g.mul(bright, g.math('MULTIPLY_ADD', damp, float(gm["damp"]) - 1.0, 1.0))
        col = g.vmath('SCALE', col, scale=bright)

    # clumps: Voronoi cells on world xy, lit crowns, dark gaps, each clump a little lighter or darker; divided by the
    # pattern's mean so the ground keeps its brightness
    gc = _conf("GROUND_CLUMP")
    a = float(gc["amount"])
    clump_h = None
    if a > 0.0:
        vor = g.node("ShaderNodeTexVoronoi", {"Vector": P, "Scale": 1.0 / float(gc["cell"]), "Randomness": 1.0},
                     feature='F1', distance='EUCLIDEAN', voronoi_dimensions='2D')
        d = vor.outputs["Distance"]           # in cell units
        crown = g.smooth(d, 0.45, 0.1)
        kt, kg = a * (float(gc["top"]) - 1.0), a * (float(gc["gap"]) - 1.0)
        mean = 1.0 + _f1_mean(lambda x: kt * _ss(x, 0.45, 0.1) + kg * _ss(x, 0.4, 0.65))
        kc = g.math('MULTIPLY_ADD', crown, kt, g.mul(g.smooth(d, 0.4, 0.65), kg))
        per = g.math('SUBTRACT', g.sep(vor.outputs["Color"])[0], 0.5)          # this clump's own random
        kc = g.math('MULTIPLY_ADD', per, 2.0 * a * float(gc["vary"]), kc)
        col = g.vmath('SCALE', col, scale=g.math('MULTIPLY_ADD', kc, 1.0 / mean, 1.0 / mean))
        if gc["bump"]:
            clump_h = crown

    # rim band: dry grass where the smooth normal starts to turn down, humus patches toward the edge, moss at the edge
    gr = _conf("GROUND_RIM")
    a = float(gr["amount"])
    rim = None
    if a > 0.0:
        ws, wa = gr["warp"]
        warp = g.math('SUBTRACT', g.noise(shifted((5.7, 37.1, 0.0)), 1.0 / float(ws), detail=2.0), 0.5)
        f = g.math('MULTIPLY_ADD', warp, 2.0 * float(wa), up)
        rim = g.smooth(f, gr["up"][0], gr["up"][1])       # 0 inland, 1 toward the rim
        ps, p0, p1 = gr["soil_patch"]
        soil = g.mul(g.smooth(f, gr["soil_up"][0], gr["soil_up"][1]),
                     g.smooth(g.noise(shifted((41.3, 2.7, 0.0)), 1.0 / float(ps), detail=2.0), p0, p1))
        mcol = _hue_of(g, col, gr["moss"], gr["moss_value"])
        img = scan_image(GROUND_SCANS["moss"])
        if img is not None:   # the rock moss's own photo (world triplanar), so this moss matches the lip moss below
            rel = g.vmath('SCALE', g.triplanar([img], MOSS_TILE, ROCK_SCAN_SHARP)[0], scale=1.0 / scan_mean(img))
            mcol = _photo_mix(g, mcol, rel, ROCK_MOSS_SCAN_MIX, 1.0, ROCK_MOSS_SCAN_HUE)
        col = g.mix(col, _hue_of(g, col, gr["dry"], gr["dry_value"]), g.mul(rim, a))
        col = g.mix(col, _hue_of(g, col, gr["soil"], gr["soil_value"]), g.mul(soil, a))
        col = g.mix(col, mcol, g.mul(g.smooth(f, gr["moss_up"][0], gr["moss_up"][1]), a))

    # flower drifts: a dot in some Voronoi cells inside drift patches, on gentle green ground; a second drift-sized
    # noise picks the leading species, each cell's own random adds a few others
    gf = _conf("GROUND_FLOWERS")
    a = float(gf["amount"])
    if a > 0.0:
        cell = float(gf["cell"])
        vor = g.node("ShaderNodeTexVoronoi", {"Vector": shifted((0.37, 0.71, 0.0)), "Scale": 1.0 / cell,
                                              "Randomness": 1.0},
                     feature='F1', distance='EUCLIDEAN', voronoi_dimensions='2D')
        r = 0.5 * float(gf["size"]) / cell
        _cx, cy, cz = g.sep(vor.outputs["Color"])
        on = g.mul(g.smooth(vor.outputs["Distance"], r + 0.04, r - 0.04), g.math('LESS_THAN', cy, float(gf["share"])))
        drift = g.smooth(g.noise(shifted((13.9, 3.1, 0.0)), 1.0 / float(gf["drift"]), detail=1.0), *gf["cover"])
        on = g.mul(g.mul(on, drift), g.mul(g.smooth(up, 0.86, 0.94), g.smooth(fac, 0.35, 0.5)))
        if rim is not None:
            on = g.mul(on, g.math('SUBTRACT', 1.0, rim))
        on = g.mul(on, g.math('SUBTRACT', 1.0, g.attr(GROUND_POINT_BAKE)))   # none in a vertex-colour bake
        sp = g.maprange(g.noise(shifted((7.3, 17.9, 0.0)), 1.0 / float(gf["drift"]), detail=1.0), 0.4, 0.6, 0.0, 1.0)
        cols = gf["colours"]
        fcol = g.ramp(g.mixf(sp, cz, 0.3), [(i / len(cols), c) for i, c in enumerate(cols)], interp='CONSTANT')
        col = g.mix(col, fcol, g.mul(on, a))
    return col, clump_h


# ============================================================ builders: lacquer & wood

def _lacquer(g, c1="#9b1c1c", c2="#b32a1f", worn=False, rough=(0.30, 0.42), coat=0.3):
    v = g.coord("object")
    big = g.noise(v, 0.35, detail=3.0, roughness=0.55)
    streak = g.noise(g.mapping(v, scale=(5.0, 5.0, 0.35)), 1.0, detail=4.0, roughness=0.6)
    base = g.ramp(g.add(g.mul(big, 0.7), g.mul(streak, 0.3)), [(0.32, c1), (0.68, c2)])
    base = g.tint_per_object(base, hue=0.006, sat=0.05, val=0.07)
    r = g.maprange(g.noise(v, 2.5, detail=4.0), 0.3, 0.7, rough[0], rough[1])
    nrm = _fine_bump(g, v, 55.0, 0.03, 0.004)
    nrm = g.bump(streak, 0.04, 0.01, nrm)
    if not worn:
        g.viewport(c2, 0.35)
        g.output(g.principled(base_color=base, roughness=r, coat_weight=coat, coat_roughness=0.18,
                              specular_ior_level=0.5, normal=nrm, coat_normal=nrm))
        return
    # ---- worn: sun-faded, dusty tops, craquelure, chips revealing dark wood, edge wear
    up = g.sep(g.geometry("Normal"))[2]
    faded = g.hsv(base, 0.505, 0.62, 1.05)
    fade_mask = g.maprange(g.noise(v, 0.7, detail=4.0), 0.3, 0.7, 0.15, 0.85)
    base = g.mix(base, faded, fade_mask)
    crack = g.voronoi(g.mapping(v, scale=(1.0, 1.0, 0.35)), 32.0, feature='DISTANCE_TO_EDGE', randomness=1.0)
    crack_vis = g.smooth(g.noise(v, 1.4, detail=3.0), 0.45, 0.7)
    crack_m = g.mul(g.smooth(crack, 0.03, 0.0), crack_vis)
    chips_n = g.noise(g.mapping(v, scale=(1.0, 1.0, 0.6)), 2.2, detail=7.0, roughness=0.68, distortion=0.25)
    edge = g.edge()
    low = g.smooth(g.sep(g.coord("object_raw"))[2], 0.6, 0.0)
    chip_level = g.add(g.mul(edge, 0.3), g.mul(low, 0.06))
    chips = g.smooth(g.add(chips_n, chip_level), 0.62, 0.645)
    deep = g.smooth(g.add(chips_n, chip_level), 0.7, 0.73)
    ground = g.ramp(g.noise(v, 9.0, detail=4.0), [(0.3, "#7d6e60"), (0.7, "#9c8c78")])
    wood = g.ramp(g.noise(g.mapping(v, scale=(8, 8, 0.6)), 2.0, detail=4.0),
                  [(0.3, "#2a1a12"), (0.7, "#4a3122")])
    col = g.mix(base, "#4a100c", g.mul(crack_m, 0.45))
    col = g.mix(col, ground, chips)
    col = g.mix(col, wood, deep)
    # lighter worn red on edges where the lacquer has thinned
    thin = g.mul(edge, g.smooth(g.noise(v, 9.0, detail=3.0), 0.35, 0.6))
    col = g.mix(col, "#c4523a", g.mul(thin, 0.55))
    dust = g.mul(g.smooth(up, 0.45, 0.85), g.maprange(g.noise(v, 1.6, detail=4.0), 0.3, 0.7, 0.25, 0.75))
    col = g.mix(col, "#a08470", dust)
    occl = g.ao(0.35)
    col = g.mix(g.mix(col, "#1e0d08", 0.6), col, g.maprange(occl, 0.2, 1.0, 0.0, 1.0))
    r = g.maprange(g.add(g.mul(chips, 0.45), g.mul(dust, 0.4)), 0, 1, 0.42, 0.9)
    nrm = g.bump(crack_m, 0.15, 0.003, nrm, invert=True)
    nrm = g.bump(g.add(chips, deep), 0.3, 0.002, nrm, invert=True)
    g.viewport(c1, 0.55)
    g.output(g.principled(base_color=col, roughness=r, coat_weight=g.mul(g.math('SUBTRACT', 1.0, chips), 0.15),
                          coat_roughness=0.3, specular_ior_level=0.45, normal=nrm))


def _wood(g, c1="#2b1b12", c2="#4f3423", grain="#1a100a", rough=(0.5, 0.7), soot=False, coat=0.0):
    """Wood; grain runs along the object's local Z (columns, posts). Beams built along X/Y still
    read as wood because the ring pattern is 3D."""
    v = g.coord("object")
    vd = g.mapping(v, scale=(1.0, 1.0, 0.12))
    rings = g.wave(vd, 2.2, distortion=7.0, detail=3.0, detail_scale=1.2, kind='RINGS', direction='Z')
    fibres = g.noise(g.mapping(v, scale=(30.0, 30.0, 1.2)), 1.0, detail=5.0, roughness=0.6)
    tone = g.noise(v, 0.8, detail=2.0)
    m = g.add(g.mul(rings, 0.55), g.mul(fibres, 0.45))
    col = g.ramp(m, [(0.15, c1), (0.6, c2), (1.0, c2)])
    col = g.mix(col, grain, g.mul(g.smooth(fibres, 0.55, 0.75), 0.6))
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.75), g.maprange(tone, 0.3, 0.7, 0.0, 1.0))
    col = g.tint_per_object(col, hue=0.01, sat=0.08, val=0.12)
    r = g.maprange(fibres, 0.3, 0.8, rough[0], rough[1])
    nrm = g.bump(fibres, 0.18, 0.004)
    if soot:
        up = g.sep(g.geometry("Normal"))[2]
        soot_n = g.noise(v, 1.3, detail=6.0, roughness=0.7, distortion=0.4)
        soot_m = g.smooth(g.add(soot_n, g.mul(g.math('ABSOLUTE', up), -0.1)), 0.42, 0.62)
        col = g.mix(col, "#0b0908", g.mul(soot_m, 0.85))
        char = g.voronoi(g.mapping(v, scale=(3.0, 3.0, 1.0)), 6.0, feature='DISTANCE_TO_EDGE')
        char_m = g.mul(g.smooth(char, 0.06, 0.0), soot_m)
        col = g.mix(col, "#050404", char_m)
        r = g.maprange(soot_m, 0, 1, rough[0], 0.95)
        nrm = g.bump(char_m, 0.4, 0.004, nrm, invert=True)
    g.viewport(c2, rough[1])
    g.output(g.principled(base_color=col, roughness=r, normal=nrm, coat_weight=coat, coat_roughness=0.25,
                          specular_ior_level=0.45))


# ============================================================ builders: roof tiles & paint

def _tile(g, c1="#1f4f4b", c2="#2a6660", rough=(0.12, 0.28), coat=0.7, coat_tint="#d8ecff",
          grime="#15201f", glazed=True, spec_tint="#c8e4ff"):
    v = g.coord("object")
    n1 = g.noise(v, 0.9, detail=3.0, roughness=0.5)
    col = g.ramp(n1, [(0.3, c1), (0.75, c2)])
    col = g.tint_per_object(col, hue=0.012, sat=0.10, val=0.16)
    # glaze pooling / kiln variation: darker blotches
    blot = g.smooth(g.noise(v, 4.0, detail=4.0, roughness=0.55), 0.5, 0.75)
    col = g.mix(col, g.hsv(col, 0.5, 1.1, 0.7), g.mul(blot, 0.6))
    # weathering streaks running down
    st = g.noise(g.mapping(v, scale=(6.0, 6.0, 0.4)), 1.0, detail=3.0)
    col = g.mix(col, grime, g.mul(g.smooth(st, 0.55, 0.8), 0.35))
    r = g.maprange(g.add(g.mul(blot, 0.5), g.mul(st, 0.5)), 0.2, 0.8, rough[0], rough[1])
    nrm = _fine_bump(g, v, 25.0, 0.04, 0.004)
    g.viewport(c1, rough[0])
    if glazed:
        g.output(g.principled(base_color=col, roughness=r, specular_ior_level=0.6, specular_tint=spec_tint,
                              coat_weight=coat, coat_roughness=0.06, coat_tint=coat_tint, normal=nrm))
    else:
        g.output(g.principled(base_color=col, roughness=r, specular_ior_level=0.4, normal=nrm))


def _bracket_paint(g, greens=("#2f6f73", "#3d8a7a", "#2b5f86"), gold="#c9a24a", line=0.035):
    """Dougong paint: blue-green fields (alternating per piece) with a gold border line and a thin
    dark inner line along the edges of each box-like piece (uses generated coords x dimensions)."""
    v = g.coord("object")
    rnd = g.obj_random()
    field = g.ramp(rnd, [(0.0, greens[0]), (0.45, greens[0]), (0.5, greens[1]), (0.82, greens[1]),
                         (0.86, greens[2]), (1.0, greens[2])], interp='CONSTANT')
    fade = g.noise(v, 3.0, detail=4.0, roughness=0.6)
    field = g.mix(field, g.hsv(field, 0.5, 0.75, 1.2), g.maprange(fade, 0.45, 0.8, 0.0, 0.5))
    # distance (m) to the bounding-box faces along each axis
    gen = g.coord("generated")
    dims = g.attr("dimensions", kind='OBJECT', out="Vector")
    inv = g.vmath('SUBTRACT', (1, 1, 1), gen)
    dmin = g.vmath('MULTIPLY', g.vmath('MINIMUM', gen, inv), dims)
    dx, dy, dz = g.sep(dmin)
    lo = g.math('MINIMUM', g.math('MINIMUM', dx, dy), dz)
    hi = g.math('MAXIMUM', g.math('MAXIMUM', dx, dy), dz)
    mid = g.math('SUBTRACT', g.math('SUBTRACT', g.add(g.add(dx, dy), dz), lo), hi)
    gold_m = g.smooth(mid, line, line * 0.8)
    dark_m = g.mul(g.smooth(mid, line * 1.55, line * 1.35), g.math('SUBTRACT', 1.0, gold_m))
    white_m = g.mul(g.smooth(mid, line * 2.1, line * 1.9), g.math('SUBTRACT', 1.0, g.smooth(mid, line * 1.6, line * 1.5)))
    col = g.mix(field, "#e6dfcc", g.mul(white_m, 0.85))
    col = g.mix(col, "#10171a", dark_m)
    col = g.mix(col, gold, gold_m)
    r = g.mixf(0.62, 0.32, gold_m)
    met = g.mul(gold_m, 0.85)
    g.viewport(greens[0], 0.6)
    g.output(g.principled(base_color=col, roughness=r, metallic=met, normal=_fine_bump(g, v, 30.0, 0.05, 0.003)))


# ============================================================ builders: metals

def _metal(g, base="#e0b34a", dark="#8a6420", rough=(0.18, 0.34), tarnish=0.35, edge_col=None,
           verdigris=None, verdigris_amt=0.0, scale=1.0):
    v = g.coord("object")
    n1 = g.noise(v, 1.6 * scale, detail=5.0, roughness=0.6)
    n2 = g.noise(v, 7.0 * scale, detail=3.0)
    col = g.mix(base, dark, g.mul(g.smooth(n1, 0.45, 0.8), tarnish))
    col = g.tint_per_object(col, hue=0.005, sat=0.05, val=0.06)
    r = g.maprange(g.add(g.mul(n1, 0.6), g.mul(n2, 0.4)), 0.3, 0.75, rough[0], rough[1])
    edge = g.edge()
    if edge_col is not None:
        col = g.mix(col, edge_col, g.mul(edge, 0.8))
        r = g.mixf(r, rough[0] * 0.6, edge)
    met = 1.0
    nrm = g.bump(n2, 0.05, 0.004)
    if verdigris is not None:
        occl = g.ao(0.4)
        crev = g.math('SUBTRACT', 1.0, g.maprange(occl, 0.25, 0.95, 0.0, 1.0))
        patch = g.smooth(g.noise(v, 2.2, detail=6.0, roughness=0.65, distortion=0.25), 0.5, 0.68)
        up = g.sep(g.geometry("Normal"))[2]
        top = g.mul(g.smooth(up, 0.4, 0.9), 0.35)
        m = g.add(g.add(g.mul(crev, 1.3), g.mul(patch, verdigris_amt)), g.mul(top, patch))
        m = g.mul(g.math('MINIMUM', m, 1.0), g.math('SUBTRACT', 1.0, g.mul(edge, 0.9)))
        crust = g.noise(v, 18.0, detail=4.0, roughness=0.7)
        vcol = g.ramp(g.add(g.mul(g.noise(v, 6.0, detail=3.0), 0.6), g.mul(crust, 0.4)),
                      [(0.3, verdigris), (0.6, "#6fa592"), (0.85, "#a3c9b4")])
        col = g.mix(col, vcol, m)
        r = g.mixf(r, 0.88, m)
        met = g.math('SUBTRACT', 1.0, m)
        nrm = g.bump(g.mul(m, g.maprange(crust, 0, 1, 0.6, 1.0)), 0.4, 0.004, nrm)
    g.viewport(base, rough[0], 1.0)
    g.output(g.principled(base_color=col, metallic=met, roughness=r, normal=nrm))


# ============================================================ builders: jade

def _jade(g, deep="#1f6b4c", pale="#7fc4a0", glow=None, strength=4.0, sss=0.7, veins=0.18):
    """Nephrite jade: soft clouds of deep and pale green, faint veins, glassy polish, SSS."""
    v = g.coord("object")
    cloud = g.noise(v, 1.3, detail=5.0, roughness=0.55, distortion=0.6)
    fine = g.noise(v, 7.0, detail=3.0)
    vein = g.noise(v, 0.9, detail=5.0, roughness=0.6, distortion=2.0)
    vein_m = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', vein, 0.5)), 0.03, 0.0)
    col = g.ramp(g.add(g.mul(cloud, 0.8), g.mul(fine, 0.2)),
                 [(0.25, deep), (0.55, g_lerp(deep, pale, 0.5)), (0.85, pale)])
    col = g.mix(col, g.hsv(rgb(pale), 0.5, 0.6, 1.2), g.mul(vein_m, veins))
    col = g.tint_per_object(col, hue=0.015, sat=0.08, val=0.08)
    r = g.maprange(cloud, 0.2, 0.8, 0.06, 0.16)
    kw = dict(base_color=col, roughness=r, subsurface_weight=sss, subsurface_radius=(0.5, 1.0, 0.75),
              subsurface_scale=0.12, coat_weight=0.5, coat_roughness=0.04,
              normal=_fine_bump(g, v, 20.0, 0.015, 0.003))
    if glow is not None:
        k = g.obj_prop("glow", 1.0)
        inner = g.maprange(g.noise(v, 0.8, detail=3.0, distortion=0.4), 0.3, 0.75, 0.25, 1.0)
        kw["emission_color"] = g.mix("#000000", glow, inner)
        kw["emission_strength"] = g.mul(k, strength)
    g.viewport(deep, 0.15)
    g.output(g.principled(**kw))


def g_lerp(a, b, t):
    """Lerp two '#hex' colours in linear space -> RGBA tuple (helper for static colours)."""
    ca, cb = rgb(a), rgb(b)
    return tuple(x + (y - x) * t for x, y in zip(ca, cb))


# ============================================================ builders: stone

def _marble(g, base="#e8e4da", vein="#b9b2a4", warm="#efe6d2", rough=(0.28, 0.45), veins=0.6, grime=0.0):
    v = g.coord("object")
    w = g.noise(v, 0.6, detail=8.0, roughness=0.62, distortion=1.6)
    vein_m = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', w, 0.5)), 0.025, 0.0)
    vein2 = g.noise(v, 2.4, detail=8.0, roughness=0.6, distortion=1.2)
    vein2_m = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', vein2, 0.5)), 0.015, 0.0)
    blot = g.noise(v, 1.1, detail=4.0)
    col = g.mix(base, warm, g.maprange(blot, 0.35, 0.75, 0.0, 0.7))
    col = g.mix(col, vein, g.mul(g.add(vein_m, g.mul(vein2_m, 0.3)), veins))
    speck = g.noise(v, 60.0, detail=1.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.94), g.smooth(speck, 0.55, 0.7))
    col = g.tint_per_object(col, hue=0.006, sat=0.1, val=0.04)
    if grime:
        up = g.sep(g.geometry("Normal"))[2]
        gm = g.mul(g.smooth(g.noise(v, 0.9, detail=5.0, distortion=0.3), 0.45, 0.75), grime)
        col = g.mix(col, "#a39a88", g.mul(gm, g.maprange(up, -1, 1, 1.0, 0.4)))
    r = g.maprange(blot, 0.2, 0.8, rough[0], rough[1])
    nrm = _fine_bump(g, v, 35.0, 0.03, 0.003)
    g.viewport(base, rough[0])
    g.output(g.principled(base_color=col, roughness=r, subsurface_weight=0.08,
                          subsurface_radius=(1.0, 0.85, 0.7), subsurface_scale=0.02,
                          specular_ior_level=0.5, normal=nrm))


def _paving(g, base="#e3ded2", alt="#d6cfbf", grout="#8d8678", slab=(1.2, 0.8), joint=0.012):
    v = g.coord("object")
    b = g.node("ShaderNodeTexBrick", {"Vector": v, "Color1": (0, 0, 0, 1), "Color2": (1, 1, 1, 1),
                                      "Mortar": (0, 0, 0, 1), "Scale": 1.0, "Mortar Size": joint,
                                      "Mortar Smooth": 0.3, "Bias": 0.0, "Brick Width": slab[0],
                                      "Row Height": slab[1]}, offset=0.5, offset_frequency=2)
    per_slab = b.outputs["Color"]
    mortar = b.outputs[1]
    slab_r = g.sep(per_slab)[0]
    col = g.mix(base, alt, g.maprange(slab_r, 0, 1, 0.0, 1.0))
    w = g.noise(v, 0.7, detail=7.0, roughness=0.6, distortion=1.4)
    vein_m = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', w, 0.5)), 0.02, 0.0)
    col = g.mix(col, "#b8b0a0", g.mul(vein_m, 0.4))
    dirt = g.smooth(g.noise(v, 1.5, detail=5.0), 0.5, 0.8)
    col = g.mix(col, "#a69d8c", g.mul(dirt, 0.35))
    col = g.tint_per_object(col, hue=0.004, sat=0.06, val=0.03)
    # slabs darken toward their joints (dirt in the grout line)
    edge_dirt = g.maprange(mortar, 0.0, 0.8, 0.0, 0.5)
    col = g.mix(col, grout, g.math('MAXIMUM', g.smooth(mortar, 0.6, 0.95), g.mul(edge_dirt, 0.4)))
    r = g.mixf(g.maprange(slab_r, 0, 1, 0.32, 0.5), 0.9, mortar)
    nrm = g.bump(mortar, 0.6, 0.006, invert=True)
    nrm = _fine_bump(g, v, 30.0, 0.04, 0.003, nrm)
    g.viewport(base, 0.4)
    g.output(g.principled(base_color=col, roughness=r, normal=nrm, specular_ior_level=0.5))


def _stone(g, c1="#8a8a84", c2="#6e6c66", speck="#3c3a37", rough=(0.62, 0.85), bump=0.25, scale=1.0,
           moss=0.0, light="#b8b3a8", light_amt=0.3):
    v = g.coord("object")
    n1 = g.noise(v, 0.9 * scale, detail=6.0, roughness=0.6)
    n2 = g.noise(v, 6.0 * scale, detail=4.0, roughness=0.55)
    col = g.ramp(g.add(g.mul(n1, 0.7), g.mul(n2, 0.3)), [(0.3, c2), (0.7, c1)])
    sp = g.voronoi(v, 70.0 * scale, randomness=1.0)
    col = g.mix(col, speck, g.mul(g.smooth(sp, 0.18, 0.06), 0.55))
    col = g.mix(col, light, g.mul(g.smooth(n2, 0.72, 0.85), light_amt))
    col = g.tint_per_object(col, hue=0.008, sat=0.1, val=0.08)
    up = g.sep(g.geometry("Normal"))[2]
    if moss:
        mm = g.mul(g.smooth(up, 0.45, 0.85), g.smooth(g.noise(v, 1.8, detail=5.0, distortion=0.4), 0.45, 0.6))
        mm = g.mul(mm, moss)
        col = g.mix(col, g.ramp(n2, [(0.3, "#3d5a2e"), (0.8, "#5f7a3c")]), mm)
    r = g.maprange(n2, 0.3, 0.7, rough[0], rough[1])
    nrm = g.bump(g.add(g.mul(n1, 0.4), g.mul(n2, 0.6)), bump, 0.02)
    nrm = _fine_bump(g, v, 45.0 * scale, 0.08, 0.004, nrm)
    g.viewport(c1, rough[1])
    g.output(g.principled(base_color=col, roughness=r, normal=nrm))


def _rock(g, light="#938d83", mid="#76726b", dark="#54514c", warm="#9a8b76", cool="#7a7d7c",
          moss="#4b6b3a", strata=2.5, moss_amt=1.0, stain=0.6, joints=1.0, scan=None, scan_scale=1.0):
    """Cliff / pillar sandstone (Zhangjiajie-like), meter-scaled on the object's axes:
    irregular sediment layers along local Z, long vertical joints, dark water-stain streaks,
    large grey/warm tonal zones, lichen, moss on up-facing ledges. ``scan``: a ROCK_SCANS key
    whose photo (world triplanar, tile x ``scan_scale``) brings colour and fine structure under
    the lichen, moss and per-object tint, and whose height joins the bump chain. ``scan_scale``
    may name a module constant (e.g. "ROCK_SMALL_SCAN_SCALE"), read at build time. With ROCK_LIFE
    the moss, damp streaks and extra lichen come from _rock_life (world space, ROCK_* constants;
    ``moss`` is then unused, ``moss_amt`` still scales the moss)."""
    if isinstance(scan_scale, str):   # so patch_nature_look.py KEY=value overrides reach it
        scan_scale = globals()[scan_scale]
    v = g.coord("object")
    x, y, z = g.sep(v)
    zone = g.noise(v, 0.04, detail=3.0, roughness=0.5)
    zone2 = g.noise(v, 0.09, detail=3.0, roughness=0.5)
    mottle = g.noise(v, 0.35, detail=6.0, roughness=0.62)
    # sediment layers: 1D fBm along a horizontally warped height -> bands of uneven thickness
    warp = g.noise(g.mapping(v, scale=(1.0, 1.0, 0.3)), 0.04, detail=2.0)
    w = g.add(g.math('DIVIDE', z, strata), g.mul(warp, 2.5))
    layers = g.noise(None, 1.0, detail=4.0, roughness=0.62, dims='1D', w=w)
    bed = g.noise(None, 1.0, detail=2.0, roughness=0.5, dims='1D', w=g.mul(w, 4.3))
    bed_line = g.mul(g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', bed, 0.5)), 0.07, 0.0),
                     g.smooth(g.noise(v, 0.3, detail=2.0), 0.4, 0.7))
    tone = g.add(g.add(g.add(g.mul(layers, 0.5), g.mul(zone, 0.25)), g.mul(mottle, 0.17)), g.mul(bed, 0.08))
    col = g.ramp(tone, [(0.22, dark), (0.5, mid), (0.8, light)])
    col = g.mix(col, warm, g.mul(g.smooth(zone2, 0.5, 0.72), 0.65))
    col = g.mix(col, cool, g.mul(g.smooth(zone2, 0.42, 0.25), 0.5))
    # water stains: long dark vertical streaks, patchy
    streak = g.noise(g.mapping(v, scale=(0.5, 0.5, 0.03)), 1.0, detail=5.0, roughness=0.6)
    stain_m = g.mul(g.smooth(streak, 0.48, 0.68), g.smooth(g.noise(v, 0.06, detail=2.0), 0.3, 0.6))
    col = g.mix(col, "#3d3a35", g.mul(stain_m, stain))
    # vertical joints: voronoi cells hugely stretched in Z, only in places, varying width
    jv = g.voronoi(g.mapping(v, scale=(0.16, 0.16, 0.012)), 1.0, feature='DISTANCE_TO_EDGE', randomness=1.0)
    jn = g.noise(v, 0.6, detail=3.0)
    width = g.maprange(g.noise(v, 0.08, detail=2.0), 0.3, 0.7, 0.008, 0.05)
    jd = g.add(jv, g.mul(g.math('SUBTRACT', jn, 0.5), 0.03))
    up = g.sep(g.geometry("Normal"))[2]
    # joints only on steep faces: on flat tops (pillar tops, look.py's plinth) the Z-stretched
    # voronoi degenerates into a polygon net that reads as crazy paving
    steep = g.smooth(g.math('ABSOLUTE', up), 0.8, 0.5)
    joint_mask = g.mul(g.mul(g.smooth(g.noise(v, 0.05, detail=3.0), 0.42, 0.62), joints), steep)
    joint = g.mul(g.smooth(jd, width, 0.0), joint_mask)
    seep = g.mul(g.smooth(jd, g.mul(width, 5.0), 0.0), joint_mask)
    col = g.mix(col, "#4a4640", g.mul(seep, 0.45))
    col = g.mix(col, "#2a2622", g.mul(joint, 0.7))
    col = g.mix(col, "#4a463f", g.mul(bed_line, 0.25))
    pits = g.smooth(g.voronoi(v, 1.6, randomness=1.0), 0.12, 0.04)
    col = g.mix(col, "#3e3a35", g.mul(pits, g.mul(g.smooth(mottle, 0.5, 0.7), 0.6)))
    fine = g.noise(v, 7.0, detail=6.0, roughness=0.65)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.82), g.mul(g.smooth(fine, 0.55, 0.78), 0.55))
    scan_h = None
    if scan is not None:
        col, scan_h = _rock_scan(g, col, scan, scan_scale)
    lich = g.smooth(g.noise(v, 1.8, detail=5.0, distortion=0.5), 0.66, 0.72)
    col = g.mix(col, "#b0ad98", g.mul(lich, 0.3))
    life = None
    if ROCK_LIFE:   # world-space moss, ledge streaks and lichen (ROCK_* above) in place of the old up-facing moss
        life = _rock_life(g, col, moss_amt)
        col, mossm = life["col"], life["moss"]
    else:
        mossm = g.mul(g.smooth(up, 0.35, 0.8), g.smooth(g.noise(v, 0.5, detail=6.0, distortion=0.5), 0.36, 0.56))
        mossm = g.mul(mossm, moss_amt)
        mcol = g.ramp(fine, [(0.25, "#34502a"), (0.6, moss), (0.9, "#7a8a48")])
        col = g.mix(col, mcol, mossm)
    col = g.tint_per_object(col, hue=0.008, sat=0.08, val=0.08)
    r = g.mixf(g.maprange(fine, 0.2, 0.8, 0.74, 0.92), 0.96, mossm)
    soft = 1.0
    if life is not None:
        r = g.mixf(r, 0.5, g.mul(life["wet"], 0.6))
        soft = g.math('MULTIPLY_ADD', mossm, -float(ROCK_MOSS_SOFTEN), 1.0)

    def st(s):   # rock bump strength, lowered under moss
        return s if life is None else g.mul(soft, s)

    nrm = g.bump(g.add(g.mul(layers, 0.6), g.mul(mottle, 0.4)), st(0.5), 0.35)
    nrm = g.bump(g.add(joint, g.mul(seep, 0.3)), st(0.9), 0.15, nrm, invert=True)
    nrm = g.bump(g.add(bed_line, pits), st(0.3), 0.03, nrm, invert=True)
    nrm = g.bump(fine, st(0.35), 0.02, nrm)
    if scan_h is not None:
        nrm = g.bump(scan_h, st(ROCK_SCAN_BUMP), ROCK_SCANS[scan]["relief"] * scan_scale, nrm)
    if life is not None:   # (each Bump makes Cycles copy its Height's whole dependency graph twice: see ROCK_MOSS_BUMP)
        if ROCK_MOSS_BUMP:
            nrm = g.bump(mossm, ROCK_MOSS_BUMP, 0.05, nrm)
        if ROCK_MOSS_PHOTO_BUMP and life["moss_h"] is not None:
            nrm = g.bump(g.mul(life["moss_h"], mossm), ROCK_MOSS_PHOTO_BUMP, 0.015, nrm)
    g.viewport(mid, 0.85)
    g.output(g.principled(base_color=col, roughness=r, normal=nrm))


# ============================================================ builders: ground & plants

def _organic(g, colours, rough=(0.8, 0.95), sheen=0.0, translucency=0.0, scale=1.0, bump=0.2,
             per_object=(0.02, 0.12, 0.12), spec=0.35, transl_col=None, speckle=None, scan=None):
    """Generic organic surface: noisy blend of ``colours`` [(pos, col)], optional sheen/translucency.
    ``scan``: top-down photo layer under the per-object tint, 'lawn' (grass: LAWN_*) or 'ground'
    (nature_soil_moss: GROUND_*); its luminance joins the bump chain. With a scan the ground life layer
    (GROUND_LIFE: patches, clumps, rim band, flowers) follows it."""
    v = g.coord("object")
    n1 = g.noise(v, 1.3 * scale, detail=5.0, roughness=0.6, distortion=0.3)
    n2 = g.noise(v, 9.0 * scale, detail=4.0, roughness=0.6)
    fac = g.add(g.mul(n1, 0.65), g.mul(n2, 0.35))
    col = g.ramp(fac, colours)
    photo_h = None
    if scan == "lawn":
        col, photo_h = _lawn_scan(g, col)
    elif scan == "ground":
        col, photo_h = _ground_scan(g, col, fac)
    elif scan is not None:
        raise ValueError("unknown organic scan %r" % scan)
    clump_h = None
    if GROUND_LIFE and scan is not None:
        col, clump_h = _ground_life(g, col, fac)
    col = g.tint_per_object(col, *per_object)
    if speckle is not None:
        sp = g.voronoi(v, 18.0 * scale, randomness=1.0)
        col = g.mix(col, speckle[0], g.mul(g.smooth(sp, speckle[1], 0.0), 0.8))
    r = g.maprange(n2, 0.3, 0.7, rough[0], rough[1])
    nrm = g.bump(n2, bump, 0.01)
    if photo_h is not None:
        nrm = g.bump(photo_h, GROUND_SCAN_BUMP, 0.02, nrm)
    if clump_h is not None:
        nrm = g.bump(clump_h, float(_conf("GROUND_CLUMP")["bump"]), 0.08, nrm)
    bsdf = g.principled(base_color=col, roughness=r, sheen_weight=sheen, sheen_roughness=0.5,
                        sheen_tint="#f2f2e6", specular_ior_level=spec, normal=nrm)
    g.viewport(colours[len(colours) // 2][1], rough[1])
    if translucency:
        tc = g.hsv(col, 0.5, 1.25, 1.35) if transl_col is None else g.mix(col, transl_col, 0.6)
        bsdf = g.mix_shader(translucency, bsdf, g.translucent(tc, nrm))
        g.mat.use_backface_culling = False
    g.output(bsdf)


def _bark(g, c1="#5a4537", c2="#7a5a45", crack="#1d1612", plates=True, scale=1.0):
    v = g.coord("object")
    if plates:
        warp = g.noise(v, 4.0 * scale, detail=2.0, color=True)
        vp = g.vmath('ADD', g.mapping(v, scale=(4.0 * scale, 4.0 * scale, 1.5 * scale)),
                     g.vmath('SCALE', warp, scale=0.6))
        cell = g.voronoi(vp, 3.0, randomness=1.0, out="Color")
        edge = g.voronoi(vp, 3.0, feature='DISTANCE_TO_EDGE', randomness=1.0)
        crack_m = g.smooth(edge, 0.07, 0.015)
        tone = g.sep(cell)[0]
    else:
        vp = g.mapping(v, scale=(7.0 * scale, 7.0 * scale, 0.7 * scale))
        rid = g.noise(vp, 1.0, detail=6.0, roughness=0.6, distortion=0.6, ntype='RIDGED_MULTIFRACTAL',
                      normalize=False)
        crack_m = g.smooth(rid, 0.55, 0.95)
        crack_m = g.math('SUBTRACT', 1.0, crack_m)
        tone = g.noise(v, 2.0, detail=3.0)
    fine = g.noise(v, 14.0 * scale, detail=5.0, roughness=0.65)
    col = g.ramp(g.add(g.mul(tone, 0.6), g.mul(fine, 0.4)), [(0.25, c1), (0.8, c2)])
    col = g.mix(col, crack, g.mul(crack_m, 0.9))
    col = g.mix(col, "#8a8274", g.mul(g.smooth(g.noise(v, 3.0, detail=4.0), 0.68, 0.78), 0.3))
    col = g.tint_per_object(col, hue=0.01, sat=0.08, val=0.1)
    nrm = g.bump(crack_m, 0.9, 0.03, invert=True)
    nrm = g.bump(fine, 0.3, 0.008, nrm)
    g.viewport(c1, 0.9)
    g.output(g.principled(base_color=col, roughness=g.maprange(fine, 0, 1, 0.82, 0.96), normal=nrm,
                          specular_ior_level=0.3))


def _bamboo_stalk(g, green="#5f8a35", yellow="#a3a64e", node_spacing=0.42):
    v = g.coord("object")
    z = g.sep(v)[2]
    f = g.math('FRACT', g.math('DIVIDE', z, node_spacing))
    ring = g.add(g.smooth(f, 0.035, 0.0), g.smooth(f, 0.965, 1.0))
    ring_soft = g.add(g.smooth(f, 0.18, 0.0), g.smooth(f, 0.82, 1.0))
    rnd = g.obj_random()
    base = g.mix(green, yellow, g.maprange(rnd, 0.0, 1.0, 0.0, 0.55))
    streak = g.noise(g.mapping(v, scale=(40.0, 40.0, 0.6)), 1.0, detail=3.0)
    col = g.mix(base, g.hsv(base, 0.5, 0.9, 0.8), g.mul(g.smooth(streak, 0.5, 0.75), 0.5))
    col = g.mix(col, "#c9c48a", g.mul(ring_soft, 0.35))
    col = g.mix(col, "#3a4a22", g.mul(ring, 0.8))
    spots = g.smooth(g.noise(v, 7.0, detail=4.0), 0.68, 0.75)
    col = g.mix(col, "#4a3a22", g.mul(spots, 0.35))
    nrm = g.bump(ring, 0.6, 0.01)
    nrm = g.bump(streak, 0.08, 0.003, nrm)
    g.viewport(green, 0.35)
    g.output(g.principled(base_color=col, roughness=g.mixf(0.3, 0.6, spots), coat_weight=0.35,
                          coat_roughness=0.2, normal=nrm))


def _lotus_leaf(g, centre="#7c9e4a", rim="#2f5a2e", vein="#9cbc6a"):
    v = g.coord("object_raw")
    x, y, _z = g.sep(v)
    ang = g.math('ARCTAN2', y, x)
    rad = g.math('SQRT', g.add(g.mul(x, x), g.mul(y, y)))
    gen = g.coord("generated")
    gx, gy, _gz = g.sep(gen)
    rr = g.math('SQRT', g.add(g.mul(g.math('SUBTRACT', gx, 0.5), g.math('SUBTRACT', gx, 0.5)),
                              g.mul(g.math('SUBTRACT', gy, 0.5), g.math('SUBTRACT', gy, 0.5))))
    rr = g.mul(rr, 2.0)
    veins = g.smooth(g.math('ABSOLUTE', g.math('SINE', g.mul(ang, 11.0))), 0.06, 0.0)
    veins = g.mul(veins, g.smooth(rr, 0.08, 0.2))
    col = g.ramp(rr, [(0.0, "#c7c27a"), (0.1, centre), (0.75, rim), (1.0, "#29492a")])
    n = g.noise(g.coord("object"), 3.0, detail=4.0)
    col = g.mix(col, g.hsv(col, 0.52, 1.0, 1.15), g.mul(g.smooth(n, 0.5, 0.75), 0.6))
    col = g.mix(col, vein, g.mul(veins, 0.6))
    burn = g.mul(g.smooth(rr, 0.85, 1.0), g.smooth(g.noise(v, 8.0, detail=3.0), 0.55, 0.7))
    col = g.mix(col, "#5e5a2e", g.mul(burn, 0.5))
    col = g.tint_per_object(col, 0.015, 0.1, 0.1)
    nrm = g.bump(g.add(veins, g.mul(n, 0.3)), 0.25, 0.005)
    bsdf = g.principled(base_color=col, roughness=0.42, sheen_weight=0.35, sheen_tint="#cfe0d8",
                        sheen_roughness=0.35, normal=nrm)
    bsdf = g.mix_shader(0.18, bsdf, g.translucent(g.hsv(col, 0.5, 1.2, 1.4), nrm))
    g.mat.use_backface_culling = False
    g.viewport(centre, 0.42)
    g.output(bsdf)


def _lotus_flower(g, base="#fff2ea", mid="#f4b0c4", tip="#d9567f"):
    gen = g.coord("generated")
    z = g.sep(gen)[2]
    v = g.coord("object")
    n = g.noise(v, 6.0, detail=3.0)
    zz = g.add(z, g.mul(g.math('SUBTRACT', n, 0.5), 0.15))
    col = g.ramp(zz, [(0.0, base), (0.45, base), (0.75, mid), (1.0, tip)])
    veins = g.noise(g.mapping(v, scale=(40.0, 40.0, 3.0)), 1.0, detail=2.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.15, 0.95), g.mul(g.smooth(veins, 0.55, 0.7), 0.4))
    col = g.tint_per_object(col, 0.01, 0.12, 0.05)
    bsdf = g.principled(base_color=col, roughness=0.5, sheen_weight=0.3, subsurface_weight=0.15,
                        subsurface_scale=0.01, normal=g.bump(veins, 0.1, 0.002))
    bsdf = g.mix_shader(0.3, bsdf, g.translucent(g.hsv(col, 0.5, 1.1, 1.3)))
    g.mat.use_backface_culling = False
    g.viewport(mid, 0.5)
    g.output(bsdf)


def _koi(g):
    v = g.coord("object")
    r3 = g.obj_rand3()
    vv = g.vmath('ADD', v, g.vmath('SCALE', r3, scale=37.0))
    red = g.smooth(g.noise(vv, 3.0, detail=3.0, roughness=0.5, distortion=0.4), 0.5, 0.56)
    blk = g.smooth(g.noise(g.vmath('ADD', vv, (11.0, 3.0, 7.0)), 5.0, detail=2.0), 0.7, 0.74)
    scales = g.voronoi(g.mapping(v, scale=(1.0, 1.4, 1.0)), 60.0, feature='DISTANCE_TO_EDGE')
    col = g.mix("#f1ede4", "#e04a1a", red)
    col = g.mix(col, "#151313", g.mul(blk, g.maprange(g.sep(r3)[2], 0, 1, 0.0, 1.0)))
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.8), g.mul(g.smooth(scales, 0.06, 0.0), 0.5))
    g.viewport("#e04a1a", 0.25)
    g.output(g.principled(base_color=col, roughness=0.22, coat_weight=0.6, coat_roughness=0.05,
                          sheen_weight=0.2, normal=g.bump(g.smooth(scales, 0.06, 0.0), 0.15, 0.002)))


# ============================================================ builders: paper, cloth, ink

def _paper(g, base="#e8dec8", fibre="#d6c7a6", lit=None, strength=3.0, translucency=0.35, aged=0.0):
    v = g.coord("object")
    fib = g.noise(g.mapping(v, scale=(1.0, 1.0, 1.0)), 22.0, detail=8.0, roughness=0.7, distortion=0.6)
    blot = g.noise(v, 2.5, detail=4.0)
    col = g.mix(base, fibre, g.maprange(g.add(g.mul(fib, 0.6), g.mul(blot, 0.4)), 0.35, 0.75, 0.0, 0.8))
    if aged:
        fox = g.smooth(g.noise(v, 5.0, detail=5.0, distortion=0.3), 0.62, 0.7)
        col = g.mix(col, "#a8824a", g.mul(fox, aged))
    nrm = g.bump(fib, 0.08, 0.002)
    bsdf = g.principled(base_color=col, roughness=0.85, sheen_weight=0.2, normal=nrm, specular_ior_level=0.3)
    if translucency:
        bsdf = g.mix_shader(translucency, bsdf, g.translucent(g.hsv(col, 0.5, 1.1, 1.0), nrm))
        g.mat.use_backface_culling = False
    if lit is not None:
        k = g.obj_prop("glow", 1.0)
        em = g.mix(lit, g.hsv(rgb(lit), 0.5, 1.1, 0.75), g.maprange(fib, 0.3, 0.8, 0.0, 1.0))
        bsdf = g.add_shader(bsdf, g.emission(em, g.mul(k, strength)))
    g.viewport(base, 0.85)
    g.output(bsdf)


def _lantern(g, paper="#f2dcb4", glow="#ffb46b", hot="#ffe2b0", strength=8.0, ribs=14, silk=False):
    """Glowing lantern skin. Brighter where the view looks straight through, darker ribs (counted
    over the object's height via generated Z), dimmer caps."""
    gen = g.coord("generated")
    z = g.sep(gen)[2]
    rib = g.math('ABSOLUTE', g.math('SINE', g.mul(z, math.pi * ribs)))
    rib_m = g.smooth(rib, 0.12, 0.0)
    caps = g.mul(g.smooth(z, 0.0, 0.14), g.smooth(z, 1.0, 0.86))
    facing = g.layer_weight(0.5, "Facing")
    core = g.math('SUBTRACT', 1.0, facing)
    v = g.coord("object")
    fib = g.noise(v, 18.0, detail=6.0, roughness=0.65)
    inten = g.mul(g.maprange(core, 0.0, 1.0, 0.45, 1.0), caps)
    inten = g.mul(inten, g.math('SUBTRACT', 1.0, g.mul(rib_m, 0.75)))
    inten = g.mul(inten, g.maprange(fib, 0.3, 0.7, 0.85, 1.05))
    em_col = g.mix(glow, hot, g.mul(core, core))
    k = g.obj_prop("glow", 1.0)
    em = g.emission(em_col, g.mul(g.mul(inten, strength), k))
    col = g.mix(paper, "#4a1e10" if silk else "#5a3a22", g.mul(rib_m, 0.8))
    surf = g.principled(base_color=col, roughness=0.75 if not silk else 0.55, sheen_weight=0.4 if silk else 0.1,
                        normal=g.bump(rib_m, 0.3, 0.004))
    g.mat.use_backface_culling = False
    g.viewport(glow, 0.7)
    g.output(g.add_shader(surf, em))


def _cloth(g, colour="#a3201b", sheen=0.5, translucency=0.34, rough=0.78, weave=True, sat_var=0.08):
    v = g.coord("object")
    n1 = g.noise(v, 1.4, detail=4.0, roughness=0.55)
    col = g.mix(colour, g.hsv(rgb(colour), 0.5, 1.05, 0.8), g.maprange(n1, 0.3, 0.75, 0.0, 0.7))
    col = g.tint_per_object(col, hue=0.008, sat=sat_var, val=0.08)
    nrm = None
    if weave:
        wx = g.wave(v, 1.0 / 0.9 * 40.0, kind='BANDS', direction='X', detail=0.0)
        wz = g.wave(v, 1.0 / 0.9 * 40.0, kind='BANDS', direction='Z', detail=0.0)
        nrm = g.bump(g.mul(wx, wz), 0.05, 0.001)
    nrm = g.bump(n1, 0.08, 0.01, nrm)
    bsdf = g.principled(base_color=col, roughness=rough, sheen_weight=sheen, sheen_roughness=0.4,
                        sheen_tint="#ffffff", specular_ior_level=0.3, normal=nrm)
    if translucency:
        bsdf = g.mix_shader(translucency, bsdf, g.translucent(g.hsv(col, 0.5, 1.2, 1.3), nrm))
    g.mat.use_backface_culling = False
    g.viewport(colour, rough)
    g.output(bsdf)


def _ink(g, colour="#0b0b0e"):
    """Wet black ink (strokes, inkstone well): near-black, slightly glossy, faint blue sheen."""
    v = g.coord("object")
    n = g.noise(v, 6.0, detail=3.0)
    col = g.mix(colour, "#14161c", g.maprange(n, 0.3, 0.7, 0.0, 1.0))
    g.viewport(colour, 0.3)
    g.output(g.principled(base_color=col, roughness=g.maprange(n, 0.2, 0.8, 0.18, 0.4),
                          specular_ior_level=0.5, coat_weight=0.2, coat_roughness=0.1))


# ============================================================ builders: glows, fx, water

def _rune(g, colour="#6fffd8", core="#e8fff8", strength=10.0):
    v = g.coord("object")
    n = g.noise(v, 3.0, detail=3.0)
    flick = g.maprange(n, 0.3, 0.7, 0.7, 1.0)
    col = g.mix(colour, core, g.mul(g.smooth(n, 0.6, 0.75), 0.45))
    k = g.obj_prop("glow", 1.0)
    g.viewport(colour, 0.5)
    g.output(g.emission(col, g.mul(g.mul(flick, strength), k)))


def _light_beam(g, colour="#6fffd8", core="#dffff6", strength=6.0, speed=0.02):
    """Additive transparent beam for a (tall) cylinder or cone: fades at the silhouette edges and
    upward along generated Z, with energy streaks drifting upward."""
    g.blended(shadows=False)
    facing = g.layer_weight(0.35, "Facing")
    edge_fade = g.math('POWER', g.math('SUBTRACT', 1.0, facing), 1.6)
    gen = g.coord("generated")
    z = g.sep(gen)[2]
    vfade = g.mul(g.smooth(z, 0.0, 0.04), g.math('POWER', g.math('SUBTRACT', 1.0, z), 1.3))
    v = g.flow(g.coord("object"), (0, 0, -speed))
    streak = g.noise(g.mapping(v, scale=(3.0, 3.0, 0.15)), 1.0, detail=3.0)
    st = g.maprange(streak, 0.3, 0.75, 0.55, 1.15)
    inten = g.mul(g.mul(edge_fade, vfade), st)
    col = g.mix(colour, core, g.mul(edge_fade, edge_fade))
    k = g.obj_prop("glow", 1.0)
    em = g.emission(col, g.mul(g.mul(inten, strength), k))
    g.viewport(colour, 0.5)
    g.output(g.add_shader(g.transparent(), em))


def _glass_shield(g, colour="#6fffd8", strength=2.0, cell=1.6):
    """Faint protective dome: transparent, fresnel rim glow plus faint energy-cell lines, slight gloss."""
    g.blended(shadows=False)
    fres = g.layer_weight(0.25, "Fresnel")
    v = g.coord("object")
    w = g.node("ShaderNodeValue")
    g.frame_driven(w.outputs[0], "frame*0.004")
    cells = g.voronoi(v, 1.0 / cell, feature='DISTANCE_TO_EDGE', dims='4D', w=w.outputs[0])
    lines = g.smooth(cells, 0.05, 0.0)
    shimmer = g.noise(v, 0.15, detail=2.0, dims='4D', w=w.outputs[0])
    inten = g.add(g.mul(g.math('POWER', fres, 1.5), 1.0), g.mul(lines, g.maprange(shimmer, 0.35, 0.7, 0.05, 0.35)))
    k = g.obj_prop("glow", 1.0)
    em = g.emission(g.mix(colour, "#dffff6", g.mul(fres, 0.5)), g.mul(g.mul(inten, strength), k))
    gloss = g.node("ShaderNodeBsdfGlossy", {"Color": g.mix("#000000", "#ffffff", g.mul(fres, 0.3)),
                                            "Roughness": 0.05}).outputs[0]
    surf = g.add_shader(g.transparent(), em)
    g.viewport(colour, 0.1)
    g.output(g.add_shader(surf, gloss))


def _water_pond(g, deep="#0a2321", shallow="#1d4740", speed=0.004):
    v = g.flow(g.coord("object"), (speed, speed * 0.6, 0))
    rip = g.noise(v, 1.8, detail=6.0, roughness=0.55)
    rip2 = g.noise(g.flow(g.coord("object"), (-speed * 0.7, speed, 0)), 6.0, detail=3.0)
    tone = g.noise(g.coord("object"), 0.3, detail=2.0)
    col = g.mix(deep, shallow, g.maprange(tone, 0.3, 0.7, 0.0, 0.6))
    nrm = g.bump(rip, 0.12, 0.02)
    nrm = g.bump(rip2, 0.05, 0.005, nrm)
    g.viewport(deep, 0.03)
    g.output(g.principled(base_color=col, roughness=0.03, ior=1.33, specular_ior_level=0.5, normal=nrm))


def _water_fall(g, water="#5f8f95", foam="#eef5f4", speed=0.12):
    """Falling sheet: streaks along local -Z flowing down, foam and transparency from streaks."""
    g.blended(shadows=True)
    v = g.flow(g.coord("object"), (0, 0, speed))
    st = g.noise(g.mapping(v, scale=(7.0, 7.0, 0.22)), 1.0, detail=5.0, roughness=0.6, distortion=0.4)
    st2 = g.noise(g.mapping(v, scale=(22.0, 22.0, 0.5)), 1.0, detail=3.0)
    foam_m = g.smooth(g.add(g.mul(st, 0.7), g.mul(st2, 0.3)), 0.36, 0.62)
    col = g.mix(water, foam, foam_m)
    gen_z = g.sep(g.coord("generated"))[2]
    edge_fade = g.mul(g.smooth(gen_z, 0.0, 0.06), 1.0)
    alpha = g.mul(g.maprange(foam_m, 0.0, 1.0, 0.55, 1.0), edge_fade)
    k = g.obj_prop("glow", 1.0)
    bsdf = g.principled(base_color=col, roughness=g.mixf(0.08, 0.5, foam_m), alpha=alpha,
                        sheen_weight=0.4, sheen_tint="#ffffff",
                        emission_color=col, emission_strength=g.mul(0.22, k),
                        normal=g.bump(st, 0.3, 0.02))
    g.viewport(foam, 0.3)
    g.output(bsdf)


def _molten(g, strength=18.0, speed=0.01):
    """Churning molten bronze: bright cracks and hot spots, darker cooling crust islands."""
    v = g.coord("object")
    w = g.node("ShaderNodeValue")
    g.frame_driven(w.outputs[0], "frame*%r" % speed)
    t = w.outputs[0]
    heat = g.noise(v, 1.4, detail=5.0, roughness=0.55, distortion=0.6, dims='4D', w=t)
    crust = g.voronoi(v, 2.2, feature='DISTANCE_TO_EDGE', dims='4D', w=t, randomness=0.9)
    cr = g.smooth(crust, 0.02, 0.12)
    crust_m = g.mul(cr, g.smooth(heat, 0.55, 0.38))
    hotv = g.math('SUBTRACT', 1.0, crust_m)
    temp = g.mul(hotv, g.maprange(heat, 0.25, 0.8, 0.45, 1.0))
    col = g.ramp(temp, [(0.0, "#2a0802"), (0.3, "#c42a02"), (0.55, "#ff6a08"), (0.8, "#ffa018"), (1.0, "#ffd860")])
    k = g.obj_prop("glow", 1.0)
    em = g.mul(g.mul(g.math('POWER', temp, 1.5), strength), k)
    g.viewport("#ff5a0a", 0.4)
    g.output(g.principled(base_color="#1a0c06", roughness=g.mixf(0.25, 0.85, crust_m),
                          emission_color=col, emission_strength=em,
                          normal=g.bump(crust_m, 0.4, 0.02)))


def _ember(g, colour="#ff7a1e", hot="#ffd27a", strength=24.0):
    facing = g.layer_weight(0.4, "Facing")
    core = g.math('SUBTRACT', 1.0, facing)
    k = g.obj_prop("glow", 1.0)
    col = g.mix(colour, hot, g.mul(core, core))
    g.viewport(colour, 0.5)
    g.output(g.emission(col, g.mul(g.mul(g.maprange(core, 0, 1, 0.35, 1.0), strength), k)))


def _volume(g, colour="#f2f3f5", density=0.5, anisotropy=0.4, scale=0.5, contrast=(0.35, 0.7),
            space="object", rise=0.0, soft=(0.18, 0.35, 0.12), absorption="#000000", height_bias=0.0,
            emission=None, emission_strength=0.0):
    """Principled Volume with noise-modulated density, faded to zero at the domain's bounding box
    so any box/cylinder domain reads as a soft shape. obj['density'] scales density."""
    v = g.coord(space)
    if rise:
        v = g.flow(v, (rise * 0.3, 0.0, -rise))
    n = g.noise(v, scale, detail=5.0, roughness=0.6, distortion=0.25)
    n2 = g.noise(v, scale * 3.5, detail=3.0)
    d = g.add(g.mul(n, 0.75), g.mul(n2, 0.25))
    if height_bias:
        z = g.sep(g.coord("generated"))[2]
        d = g.math('SUBTRACT', d, g.mul(z, height_bias))
    d = g.smooth(d, contrast[0], contrast[1])
    d = g.mul(d, _soft_box(g, *soft))
    k = g.obj_prop("density", 1.0)
    kw = dict(color=colour, density=g.mul(g.mul(d, density), k), anisotropy=anisotropy,
              absorption_color=absorption)
    if emission is not None:
        kw["emission_color"] = emission
        kw["emission_strength"] = g.mul(d, emission_strength)
    g.viewport(colour, 0.5)
    g.output(volume=g.volume(**kw))


def _moon(g, base="#eef1f7", maria="#98a3b8", strength=3.0):
    """Stylised self-lit moon disc/sphere: maria, crater rings, limb darkening."""
    v = g.coord("object_raw")
    vn = g.vmath('NORMALIZE', v)
    m1 = g.noise(vn, 1.6, detail=5.0, roughness=0.55, distortion=0.5)
    maria_m = g.smooth(m1, 0.5, 0.62)
    cr = g.voronoi(vn, 7.0, randomness=1.0)
    rim = g.mul(g.smooth(cr, 0.16, 0.2), g.smooth(cr, 0.26, 0.2))
    bowl = g.smooth(cr, 0.16, 0.06)
    cr2 = g.voronoi(vn, 22.0, randomness=1.0)
    small = g.smooth(cr2, 0.1, 0.03)
    col = g.mix(base, maria, maria_m)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.86), g.add(g.mul(bowl, 0.6), g.mul(small, 0.4)))
    col = g.mix(col, "#ffffff", g.mul(rim, 0.5))
    fine = g.noise(vn, 30.0, detail=4.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.92), g.smooth(fine, 0.5, 0.7))
    limb = g.maprange(g.layer_weight(0.5, "Facing"), 0.0, 1.0, 1.0, 0.72)
    k = g.obj_prop("glow", 1.0)
    g.viewport(base, 0.8)
    g.output(g.emission(col, g.mul(g.mul(limb, strength), k)))


# ============================================================ registrations (spec names)

def _register_defaults():
    R = register
    # lacquer & wood
    R("lacquer_red", _lacquer, c1="#8e1a19", c2="#a8261e", rough=(0.34, 0.5), coat=0.22)
    R("lacquer_red_worn", _lacquer, c1="#8a1c1a", c2="#a02a20", worn=True, rough=(0.45, 0.62))
    R("wood_dark", _wood, c1="#2a1d15", c2="#4a3426")
    R("wood_light", _wood, c1="#6e5a46", c2="#967d60", grain="#4e3f30", rough=(0.45, 0.65))
    R("wood_soot", _wood, c1="#1d1611", c2="#2e231b", grain="#0e0b09", rough=(0.6, 0.8), soot=True)
    # roofs & paint
    R("roof_tile_teal", _tile)
    R("roof_tile_black", _tile, c1="#25272b", c2="#34363b", rough=(0.45, 0.7), glazed=False, grime="#1a1b1d")
    R("roof_tile_moon", _tile, c1="#cfd4de", c2="#e2e5ec", rough=(0.1, 0.22), coat=0.6, coat_tint="#eef3ff",
      grime="#9ea5b2", spec_tint="#e6eeff")
    R("bracket_paint", _bracket_paint)
    # metals
    R("gold", _metal, base="#f0b84c", dark="#b07a30", rough=(0.16, 0.3), tarnish=0.22, edge_col="#ffd98a", scale=2.5)
    R("silver", _metal, base="#d5d8de", dark="#8e8a84", rough=(0.24, 0.4), tarnish=0.3, edge_col="#f2f4f8")
    R("bronze", _metal, base="#8c7446", dark="#3e3220", rough=(0.34, 0.55), tarnish=0.6, edge_col="#c4a46a")
    R("bronze_verdigris", _metal, base="#86703f", dark="#3a2f1e", rough=(0.36, 0.58), tarnish=0.55,
      edge_col="#c8a86c", verdigris="#4f8a7a", verdigris_amt=0.85)
    # jade
    R("jade", _jade)
    R("jade_glow", _jade, deep="#17654c", pale="#6cc8a4", glow="#20ffb8", strength=1.8, sss=0.5, veins=0.08)
    # stone
    R("marble_white", _marble, veins=0.28)
    R("marble_paving", _paving)
    R("stone_grey", _stone)
    R("stone_dark", _stone, c1="#4a4844", c2="#3a3835", speck="#1e1d1c", rough=(0.45, 0.65), bump=0.12,
      light="#5e5a54", light_amt=0.4)
    R("rock_cliff", _rock, scan="marble_cliff_06")
    # ground & plants
    R("moss", _organic, colours=[(0.2, "#2f4a24"), (0.55, "#4b6b3a"), (0.9, "#76884a")], rough=(0.85, 0.98),
      sheen=0.6, scale=2.0, bump=0.4)
    R("grass", _organic, colours=[(0.15, "#3a5424"), (0.5, "#5a7a35"), (0.8, "#7f8a42"), (1.0, "#9a9150")],
      rough=(0.8, 0.95), sheen=0.3, translucency=0.1, scale=1.0, bump=0.3, scan="lawn")
    R("soil", _organic, colours=[(0.2, "#3a2c20"), (0.6, "#56432f"), (1.0, "#6f5a42")], rough=(0.88, 0.98),
      scale=1.5, bump=0.35, speckle=("#7a7064", 0.1))
    R("foliage_pine", _organic, colours=[(0.2, "#1d3524"), (0.6, "#2c4a2e"), (1.0, "#4c6a3a")],
      rough=(0.55, 0.75), sheen=0.25, translucency=0.18, scale=3.0, bump=0.4, per_object=(0.02, 0.12, 0.15),
      transl_col="#7a9a3a")
    R("foliage_blossom", _organic, colours=[(0.15, "#e07a98"), (0.5, "#f2b4c6"), (0.85, "#fbe4ec"), (1.0, "#fff4f6")],
      rough=(0.5, 0.65), sheen=0.3, translucency=0.3, scale=4.0, bump=0.3, per_object=(0.015, 0.15, 0.08),
      transl_col="#ffc0d0")
    R("foliage_willow", _organic, colours=[(0.2, "#5d7a2e"), (0.6, "#88a646"), (1.0, "#b2c060")],
      rough=(0.5, 0.7), sheen=0.2, translucency=0.32, scale=3.0, bump=0.3, transl_col="#c8d870")
    R("foliage_bamboo", _organic, colours=[(0.2, "#35602a"), (0.6, "#4e7a34"), (1.0, "#73984a")],
      rough=(0.45, 0.65), sheen=0.15, translucency=0.28, scale=3.0, bump=0.25, transl_col="#a8c860")
    R("bark_pine", _bark)
    R("bark_dark", _bark, c1="#3a3029", c2="#5e5046", crack="#140f0c", plates=False)
    R("bamboo_stalk", _bamboo_stalk)
    R("lotus_leaf", _lotus_leaf)
    R("lotus_flower", _lotus_flower)
    R("koi", _koi)
    # paper, cloth, ink
    R("paper_lantern", _lantern, paper="#f0cf9a", glow="#ff7a1e", hot="#ffb04a", strength=3.0)
    R("paper_screen", _paper, translucency=0.5)
    R("paper_screen_lit", _paper, base="#f0e2c4", lit="#ffa654", strength=1.8, translucency=0.25)
    R("plaque_board", _lacquer, c1="#121c33", c2="#1a2946", rough=(0.25, 0.38), coat=0.45)
    R("cloth_red", _cloth, colour="#a3201b")
    R("cloth_gold", _cloth, colour="#c99a2e", sheen=0.7)
    R("cloth_white", _cloth, colour="#e6e1d6", translucency=0.5)
    R("cloth_teal", _cloth, colour="#2b6e6a")
    R("cloth_black", _cloth, colour="#1c1c20", translucency=0.12, sheen=0.6)
    R("ink", _ink)
    # glows & fx
    R("rune_cyan", _rune, colour="#1effc0", core="#b8fff0", strength=4.0)
    R("rune_gold", _rune, colour="#ffaa2a", core="#ffe2a8", strength=4.0)
    R("rune_silver", _rune, colour="#9cc0ff", core="#eef4ff", strength=3.5)
    R("light_beam", _light_beam)
    R("glass_shield", _glass_shield)
    R("water_pond", _water_pond)
    R("water_fall", _water_fall)
    R("molten", _molten, strength=7.0)
    R("ember", _ember)
    R("smoke_volume", _volume, colour="#77716b", density=1.6, anisotropy=0.25, scale=0.9, contrast=(0.3, 0.68),
      rise=0.02, absorption="#2a2420", soft=(0.3, 0.4, 0.1))
    R("mist_volume", _volume, colour="#eef1f4", density=0.5, anisotropy=0.55, scale=0.35, contrast=(0.28, 0.66),
      rise=0.003, soft=(0.25, 0.6, 0.05), height_bias=0.3)
    R("cloud_volume", _volume, colour="#ffffff", density=0.12, anisotropy=0.5, scale=0.022, contrast=(0.38, 0.62),
      space="world", soft=(0.06, 0.6, 0.02), height_bias=0.6)
    R("moon_surface", _moon, strength=2.2)
    # extras every module may want
    R("lantern_red", _lantern, paper="#a51e14", glow="#ff1a06", hot="#ff5a18", strength=2.6, silk=True)
    R("lacquer_black", _lacquer, c1="#121010", c2="#1e1a18", rough=(0.22, 0.35), coat=0.5)
    R("iron", _metal, base="#4a4a4c", dark="#2a2622", rough=(0.45, 0.7), tarnish=0.6, edge_col="#8a8a8e")
    R("steel", _metal, base="#c9ced6", dark="#8a8e94", rough=(0.12, 0.22), tarnish=0.2, edge_col="#f2f4f8")
    R("ceramic_celadon", _tile, c1="#8fb8a4", c2="#a8cbb8", rough=(0.08, 0.16), coat=0.8, coat_tint="#ffffff",
      grime="#6f8f80", spec_tint="#ffffff")
    R("paper_aged", _paper, base="#dccb9f", fibre="#c4ad7e", translucency=0.1, aged=0.5)
    R("jade_slip", _jade, deep="#2a8a6c", pale="#9ee0c4", glow="#30ffc4", strength=1.1, sss=0.4, veins=0.08)
    for i, (_n, col) in enumerate(BANNER_COLOURS):
        R("banner_%d" % i, _cloth, colour=col, translucency=0.38 if i != 7 else 0.15)


_register_defaults()

REQUIRED = [
    "lacquer_red", "lacquer_red_worn", "wood_dark", "wood_light", "wood_soot", "roof_tile_teal",
    "roof_tile_black", "roof_tile_moon", "bracket_paint", "gold", "silver", "bronze", "bronze_verdigris",
    "jade", "jade_glow", "marble_white", "marble_paving", "stone_grey", "stone_dark", "rock_cliff", "moss",
    "grass", "soil", "paper_lantern", "paper_screen", "paper_screen_lit", "plaque_board", "cloth_red",
    "cloth_gold", "cloth_white", "cloth_teal", "cloth_black", "rune_cyan", "rune_gold", "rune_silver",
    "light_beam", "water_pond", "water_fall", "molten", "ember", "smoke_volume", "mist_volume",
    "cloud_volume", "glass_shield", "foliage_pine", "foliage_blossom", "foliage_willow", "foliage_bamboo",
    "bark_pine", "bark_dark", "bamboo_stalk", "lotus_leaf", "lotus_flower", "koi", "ink", "moon_surface",
]
