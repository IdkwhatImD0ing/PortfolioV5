"""Look-dev for the Moonlit Sect: render settings, golden-hour sky + sun + haze,
compositor (bloom, grade, vignette) and the preview harness every module uses.

Run as a script for previews (see ``main``)::

    blender --background --factory-startup --python sect/lib/look.py -- \
        --target sect.lib.arch:showcase --out out/previews/arch --name arch --footprint 40

World convention (spec section 2): metres, Z up, +Y is north (direction of travel),
+X is east. Compass azimuths in this module are degrees clockwise from north (+Y):
0 = north (+Y), 90 = east (+X), 180 = south (-Y), 270 = west (-X).
"""

import json
import math
import os
import sys
import time
import traceback

import bpy
import bmesh
from mathutils import Vector, noise

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLENDER_EXE = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"


# --------------------------------------------------------------------------------------
# Sky geometry constants (shared with world.py)
# --------------------------------------------------------------------------------------

def dir_from_az_el(azimuth_deg, elevation_deg):
    """Unit vector for a compass azimuth (deg, 0 = +Y north, 90 = +X east) and an
    elevation above the horizon (deg)."""
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


SUN_AZIMUTH = 252.0          # deg, west, 18 deg south of due west (rakes the -Y facades)
SUN_ELEVATION = 7.0          # deg above the horizon: golden hour
SUN_DIR = dir_from_az_el(SUN_AZIMUTH, SUN_ELEVATION)     # scene -> sun, unit

MOON_AZIMUTH = 22.5          # deg, north-north-east
MOON_ELEVATION = 16.0        # deg
MOON_DIR = dir_from_az_el(MOON_AZIMUTH, MOON_ELEVATION)  # scene -> moon centre, unit
MOON_ANGULAR_SIZE_DEG = 14.0                              # full apparent diameter
MOON_ANGULAR_SIZE = math.radians(MOON_ANGULAR_SIZE_DEG)  # radians


def moon_placement(distance, origin=(0.0, 0.0, 0.0)):
    """(centre, radius) for a moon disc/sphere `distance` m from `origin` that appears
    MOON_ANGULAR_SIZE wide in direction MOON_DIR."""
    centre = Vector(origin) + MOON_DIR * distance
    return centre, distance * math.tan(MOON_ANGULAR_SIZE * 0.5)


# --------------------------------------------------------------------------------------
# Tuned look values (all in one place so world.py / assemble.py can reuse them)
# --------------------------------------------------------------------------------------

LOOK = dict(
    # colour management
    view_transform="AgX",
    look="AgX - Punchy",       # saturated, contrasty donghua-ish base
    exposure=0.25,
    gamma=1.0,
    # sky (Sky Texture, multiple scattering): orange at the sun, blue-violet in the north
    sky_strength=0.18,
    sky_altitude=300.0,        # m
    sky_air=2.0,               # more Rayleigh -> redder low sun, bluer zenith
    sky_aerosol=2.5,           # golden-hour dust
    sky_ozone=4.0,             # Chappuis absorption -> violet twilight tint
    sky_knee=1.0,              # sky values above this are softly compressed (keeps hue)
    sky_knee_width=1.5,        # ... toward knee + width
    sun_disc_size_deg=0.9,     # visible disc (slightly larger than real for readability)
    sun_disc_strength=24.0,    # radiance of the painted disc (EEVEE has no sky disc)
    sun_halo_strength=1.2,     # soft forward glow around the sun in the sky
    below_horizon_color=(0.42, 0.40, 0.44),   # linear; hazy colour where the floor fades out
    below_horizon_blend=0.06,  # dir.z range over which the sky fades into the floor
    # preview cloud floor (world shader, below the horizon)
    cloud_floor_depth=160.0,   # m below the camera the cloud tops appear to be
    cloud_scale=0.0035,        # noise scale (1/m)
    cloud_lit_color=(1.3, 0.9, 0.62),
    cloud_shadow_color=(0.16, 0.16, 0.28),
    cloud_sheen=0.6,
    cloud_emboss_offset=30.0,  # m toward the sun for the emboss sample
    cloud_emboss_gain=7.0,
    cloud_fade_distance=2500.0,
    # sun lamp
    sun_strength=8.0,          # W/m^2 (about 10x the sky's horizontal irradiance)
    sun_color=(1.0, 0.52, 0.23),
    sun_angle_deg=1.2,         # soft but crisp shadows
    sun_volume_factor=1.8,     # extra sun in-scatter in the haze -> golden air
    # haze (large volume box with height falloff)
    haze_density=0.00045,      # extinction per metre at base_z
    haze_base_z=0.0,
    haze_falloff=120.0,        # m: density halves every ~83 m of height
    haze_color=(1.0, 0.92, 0.84),
    haze_anisotropy=0.2,
    haze_extent=7000.0,        # half-size of the haze box in XY
    haze_floor_z=-140.0,       # bottom of the preview haze box (the cloud tops)
    # compositor
    # Glare threshold is on LUMINANCE (scene linear, before exposure). Sun-facing white marble
    # peaks at ~1.3-1.5; the shared materials' glows sit at 1.7-3.5 (orange lanterns ~1.7-2.6,
    # runes ~2.9, jade/molten ~3.5), so 2.0 blooms the glows and keeps sunlit stone out.
    bloom_threshold=2.0,
    bloom_smoothness=0.35,
    bloom_strength=0.6,
    bloom_size=0.55,
    bloom_saturation=1.0,
    bloom_max=60.0,
    vignette_strength=0.22,
    vignette_start=0.55,       # normalised radius (1 = frame edge midpoint)
    vignette_end=1.45,
    grade_slope=(1.02, 1.0, 0.975),
    grade_offset=(-0.0015, 0.0, 0.0025),
    grade_power=(1.0, 1.0, 1.0),
    grade_saturation=1.10,
    grade_highlight_saturation=1.25,  # undo some AgX bleaching of warm highlights
    grade_shadow_saturation=1.05,
)

VOLUMETRIC_END = 4000.0      # m, covers the ~3 km scene plus backdrop
CAMERA_CLIP_END = 9000.0

QUALITY = {
    "preview": dict(samples=32, rt_resolution="2", trace_quality=0.25, fast_gi_resolution="2",
                    fast_gi_steps=8, shadow_rays=1, shadow_steps=6, shadow_pool="1024",
                    vol_tile="8", vol_samples=64, vol_shadow_samples=16, motion_blur=False,
                    glare_quality="Medium", sun_jitter=False, overscan=True),
    "final": dict(samples=96, rt_resolution="1", trace_quality=0.5, fast_gi_resolution="1",
                  fast_gi_steps=12, shadow_rays=2, shadow_steps=12, shadow_pool="2048",
                  vol_tile="4", vol_samples=128, vol_shadow_samples=32, motion_blur=True,
                  glare_quality="High", sun_jitter=True, overscan=True),
}

LOOK_COLLECTION = "look"
AUTO_CAMERAS = ("front_34", "front", "aerial", "detail")


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------

def _log(*args):
    print("LOOK", *args, flush=True)


def _set(rna, attr, value):
    """Set an RNA property, warning (not crashing) if this Blender lacks it."""
    if not hasattr(rna, attr):
        _log("WARN missing property", type(rna).__name__ + "." + attr)
        return False
    try:
        setattr(rna, attr, value)
        return True
    except Exception as exc:  # wrong enum value etc.
        _log("WARN could not set", type(rna).__name__ + "." + attr, "=", repr(value), exc)
        return False


def _inp(node, *names):
    """First input socket of `node` whose name matches one of `names`."""
    for n in names:
        s = node.inputs.get(n)
        if s is not None:
            return s
    raise KeyError("%s has none of the inputs %s (has %s)" % (
        node.bl_idname, names, [i.name for i in node.inputs]))


def srgb_to_linear(c):
    """sRGB component (0-1) to linear."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_color(h, alpha=1.0):
    """'#rrggbb' to a linear RGBA tuple."""
    h = h.lstrip("#")
    rgb = [srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)]
    return (rgb[0], rgb[1], rgb[2], alpha)


def ensure_collection(name, parent=None):
    """Return collection `name`, creating it and linking it under `parent`
    (default: the scene collection)."""
    parent = parent or bpy.context.scene.collection
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in parent.children:
        parent.children.link(col)
    return col


def _link(obj, collection):
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    return obj


# --------------------------------------------------------------------------------------
# render settings
# --------------------------------------------------------------------------------------

def setup_render(scene, quality="preview", resolution=(1280, 720)):
    """EEVEE render settings: ray tracing, volumetrics + volumetric shadows over a
    `VOLUMETRIC_END` range, virtual shadow maps, AgX + cinematic look, film,
    TAA samples (preview 32 / final 96), motion blur only for 'final'."""
    q = QUALITY[quality]
    r = scene.render
    _set(r, "engine", "BLENDER_EEVEE")
    r.resolution_x, r.resolution_y = int(resolution[0]), int(resolution[1])
    r.resolution_percentage = 100
    _set(r, "fps", 24)
    _set(r, "fps_base", 1.0)
    _set(r, "filter_size", 1.5)
    _set(r, "film_transparent", False)
    _set(r, "dither_intensity", 1.0)
    _set(r, "use_compositing", True)
    _set(r, "use_motion_blur", bool(q["motion_blur"]))
    _set(r, "motion_blur_shutter", 0.5)
    _set(r, "motion_blur_position", "CENTER")
    _set(r, "compositor_device", "GPU")
    im = r.image_settings
    _set(im, "file_format", "PNG")
    _set(im, "color_mode", "RGB")
    _set(im, "color_depth", "8")
    _set(im, "compression", 15)

    ee = scene.eevee
    _set(ee, "taa_render_samples", int(q["samples"]))
    _set(ee, "taa_samples", 16)
    _set(ee, "use_taa_reprojection", True)
    # ray tracing
    _set(ee, "use_raytracing", True)
    _set(ee, "ray_tracing_method", "SCREEN")
    rto = ee.ray_tracing_options
    _set(rto, "resolution_scale", q["rt_resolution"])
    _set(rto, "trace_max_roughness", 0.5)
    _set(rto, "screen_trace_quality", q["trace_quality"])
    _set(rto, "screen_trace_thickness", 0.4)
    _set(rto, "use_denoise", True)
    _set(rto, "denoise_spatial", True)
    _set(rto, "denoise_temporal", True)
    _set(rto, "denoise_bilateral", True)
    # horizon scan / fast GI for rough surfaces
    _set(ee, "use_fast_gi", True)
    _set(ee, "fast_gi_method", "GLOBAL_ILLUMINATION")
    _set(ee, "fast_gi_resolution", q["fast_gi_resolution"])
    _set(ee, "fast_gi_step_count", q["fast_gi_steps"])
    _set(ee, "fast_gi_distance", 0.0)
    _set(ee, "fast_gi_thickness_near", 0.25)
    # shadows
    _set(ee, "use_shadows", True)
    _set(ee, "shadow_ray_count", q["shadow_rays"])
    _set(ee, "shadow_step_count", q["shadow_steps"])
    _set(ee, "shadow_pool_size", q["shadow_pool"])
    _set(ee, "shadow_resolution_scale", 1.0)
    # volumetrics
    _set(ee, "use_volume_custom_range", True)
    _set(ee, "volumetric_start", 0.5)
    _set(ee, "volumetric_end", VOLUMETRIC_END)
    _set(ee, "volumetric_tile_size", q["vol_tile"])
    _set(ee, "volumetric_samples", q["vol_samples"])
    _set(ee, "volumetric_sample_distribution", 0.9)
    _set(ee, "use_volumetric_shadows", True)
    _set(ee, "volumetric_shadow_samples", q["vol_shadow_samples"])
    _set(ee, "volumetric_ray_depth", 16)
    # clamps, film, motion blur
    _set(ee, "clamp_surface_indirect", 10.0)
    _set(ee, "light_threshold", 0.01)
    _set(ee, "use_overscan", bool(q["overscan"]))
    _set(ee, "overscan_size", 3.0)
    _set(ee, "motion_blur_steps", 1)
    _set(ee, "motion_blur_max", 32)
    _set(ee, "motion_blur_depth_scale", 100.0)

    # colour management
    _set(scene.display_settings, "display_device", "sRGB")
    vs = scene.view_settings
    _set(vs, "view_transform", LOOK["view_transform"])
    _set(vs, "look", LOOK["look"])
    _set(vs, "exposure", LOOK["exposure"])
    _set(vs, "gamma", LOOK["gamma"])
    _set(vs, "use_curve_mapping", False)
    scene["sect_look_quality"] = quality
    return scene


# --------------------------------------------------------------------------------------
# world: sky texture + painted sun disc
# --------------------------------------------------------------------------------------

def _sky_rotation(direction):
    """Sky Texture `sun_rotation` for a direction. Measured in 5.2: rotation is the
    compass azimuth (0 = sun toward +Y, +90 deg = toward +X)."""
    return math.atan2(direction.x, direction.y)


def _node(nodes, idname, loc, **inputs):
    n = nodes.new(idname)
    n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def _math(nodes, links, op, a, b=None, loc=(0, 0)):
    """Scalar Math node; a/b are sockets or numbers. Returns the output socket."""
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            links.new(v, n.inputs[i])
    return n.outputs[0]


def _vmath(nodes, links, op, a, b=None, scale=None, loc=(0, 0)):
    """Vector Math node; a/b are sockets or 3-tuples. Returns (vector, value) outputs."""
    n = nodes.new("ShaderNodeVectorMath")
    n.operation = op
    n.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (tuple, list, Vector)):
            n.inputs[i].default_value = tuple(v)
        else:
            links.new(v, n.inputs[i])
    if scale is not None:
        sock = _inp(n, "Scale")
        if isinstance(scale, (int, float)):
            sock.default_value = scale
        else:
            links.new(scale, sock)
    return n.outputs[0], n.outputs[1]


def _soft_knee(nodes, links, color, knee, width):
    """Hue-preserving highlight compression: the max channel m above `knee` becomes
    knee + e / (1 + e / width) (e = m - knee). Keeps the sunset glow saturated under
    AgX instead of bleaching to white. Returns the compressed colour socket."""
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(color, sep.inputs[0])
    m = _math(nodes, links, "MAXIMUM",
              _math(nodes, links, "MAXIMUM", sep.outputs[0], sep.outputs[1]), sep.outputs[2])
    e = _math(nodes, links, "MAXIMUM", _math(nodes, links, "SUBTRACT", m, knee), 0.0)
    comp = _math(nodes, links, "DIVIDE", e,
                 _math(nodes, links, "ADD", _math(nodes, links, "DIVIDE", e, width), 1.0))
    m2 = _math(nodes, links, "ADD", _math(nodes, links, "MINIMUM", m, knee), comp)
    scale = _math(nodes, links, "DIVIDE", m2, _math(nodes, links, "MAXIMUM", m, 1e-6))
    out, _ = _vmath(nodes, links, "SCALE", color, scale=scale)
    return out


def _cloud_floor(nodes, links, d, dz):
    """Procedural sea of cloud seen below the horizon (world shader, direction only):
    noise billows projected on a plane, embossed toward the sun so tops catch warm
    light and the lee sides fall into violet shadow. Returns an RGB socket."""
    negz = _math(nodes, links, "MAXIMUM", _math(nodes, links, "MULTIPLY", dz, -1.0), 0.015)
    t = _math(nodes, links, "DIVIDE", LOOK["cloud_floor_depth"], negz)
    p, _ = _vmath(nodes, links, "MULTIPLY", d, (1.0, 1.0, 0.0))
    p, _ = _vmath(nodes, links, "SCALE", p, scale=t)
    sun_h = Vector((SUN_DIR.x, SUN_DIR.y, 0.0)).normalized()
    p_sun, _ = _vmath(nodes, links, "ADD", p, tuple(sun_h * LOOK["cloud_emboss_offset"]))

    def billow(vec):
        n = nodes.new("ShaderNodeTexNoise")
        n.noise_dimensions = "3D"
        n.inputs["Scale"].default_value = LOOK["cloud_scale"]
        n.inputs["Detail"].default_value = 5.0
        n.inputs["Roughness"].default_value = 0.55
        links.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    h0, h1 = billow(p), billow(p_sun)
    puff = _node(nodes, "ShaderNodeMapRange", (0, 0))
    puff.interpolation_type = "SMOOTHSTEP"
    puff.inputs["From Min"].default_value = 0.36
    puff.inputs["From Max"].default_value = 0.66
    links.new(h0, puff.inputs["Value"])
    # sun-facing slopes: height falls toward the sun
    slope = _math(nodes, links, "MULTIPLY", _math(nodes, links, "SUBTRACT", h0, h1),
                  LOOK["cloud_emboss_gain"])
    shade = _math(nodes, links, "MAXIMUM",
                  _math(nodes, links, "MINIMUM", _math(nodes, links, "ADD", slope, 0.55), 1.0), 0.0)
    light = _math(nodes, links, "MULTIPLY", puff.outputs["Result"], shade)
    col = _node(nodes, "ShaderNodeMix", (0, 0))
    col.data_type = "RGBA"
    links.new(light, col.inputs["Factor"])
    col.inputs[6].default_value = tuple(LOOK["cloud_shadow_color"]) + (1.0,)
    col.inputs[7].default_value = tuple(LOOK["cloud_lit_color"]) + (1.0,)
    # warm sheen on the sun side of the floor
    dh, _ = _vmath(nodes, links, "NORMALIZE", p)
    _, sd = _vmath(nodes, links, "DOT_PRODUCT", dh, tuple(sun_h))
    sheen = _math(nodes, links, "POWER", _math(nodes, links, "MAXIMUM", sd, 0.0), 4.0)
    sheen_c, _ = _vmath(nodes, links, "SCALE", (1.0, 0.55, 0.28),
                        scale=_math(nodes, links, "MULTIPLY", sheen, LOOK["cloud_sheen"]))
    lit, _ = _vmath(nodes, links, "ADD", col.outputs[2], sheen_c)
    # fade to the horizon colour with distance along the floor
    fade = _math(nodes, links, "EXPONENT",
                 _math(nodes, links, "DIVIDE", t, -LOOK["cloud_fade_distance"]))
    out = _node(nodes, "ShaderNodeMix", (0, 0))
    out.data_type = "RGBA"
    links.new(fade, out.inputs["Factor"])
    out.inputs[6].default_value = tuple(LOOK["below_horizon_color"]) + (1.0,)
    links.new(lit, out.inputs[7])
    return out.outputs[2]


def setup_world(scene, name="look.world", cloud_floor=True):
    """World = multiple-scattering Sky Texture lit from SUN_DIR, a painted sun disc +
    halo (EEVEE does not draw the sky's own disc) and, below the horizon, either a
    procedural sea of cloud (`cloud_floor=True`, for previews) or a flat hazy horizon
    colour (world.py builds the real cloud sea). Returns the World."""
    world = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    scene.world = world
    nt = world.node_tree
    if nt is None:
        try:
            world.use_nodes = True
        except Exception:
            pass
        nt = world.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    tc = _node(nodes, "ShaderNodeTexCoord", (-1700, 0))
    d, _ = _vmath(nodes, links, "NORMALIZE", tc.outputs["Generated"], loc=(-1550, 0))
    sep = _node(nodes, "ShaderNodeSeparateXYZ", (-1400, 250))
    links.new(d, sep.inputs[0])

    sky = _node(nodes, "ShaderNodeTexSky", (-500, 200))
    _set(sky, "sky_type", "MULTIPLE_SCATTERING")
    _set(sky, "sun_disc", True)
    _set(sky, "sun_size", math.radians(LOOK["sun_disc_size_deg"]))
    _set(sky, "sun_intensity", 1.0)
    _set(sky, "sun_elevation", math.radians(SUN_ELEVATION))
    _set(sky, "sun_rotation", _sky_rotation(SUN_DIR))
    _set(sky, "sun_direction", SUN_DIR)
    _set(sky, "altitude", LOOK["sky_altitude"])
    _set(sky, "air_density", LOOK["sky_air"])
    _set(sky, "aerosol_density", LOOK["sky_aerosol"])
    _set(sky, "ozone_density", LOOK["sky_ozone"])
    sky_c, _ = _vmath(nodes, links, "SCALE", sky.outputs["Color"], scale=LOOK["sky_strength"],
                      loc=(-300, 200))
    sky_c = _soft_knee(nodes, links, sky_c, LOOK["sky_knee"], LOOK["sky_knee_width"])

    # painted sun disc + halo (camera sees it; its energy in the probe is negligible)
    _, cosang = _vmath(nodes, links, "DOT_PRODUCT", d, tuple(SUN_DIR), loc=(-1200, -200))
    r = math.radians(LOOK["sun_disc_size_deg"]) * 0.5
    disc = _node(nodes, "ShaderNodeMapRange", (-1000, -200))
    disc.interpolation_type = "SMOOTHSTEP"
    disc.inputs["From Min"].default_value = math.cos(r * 1.25)
    disc.inputs["From Max"].default_value = math.cos(r * 0.8)
    disc.inputs["To Max"].default_value = LOOK["sun_disc_strength"]
    links.new(cosang, disc.inputs["Value"])
    halo = _math(nodes, links, "MULTIPLY",
                 _math(nodes, links, "POWER",
                       _math(nodes, links, "MAXIMUM", cosang, 0.0, loc=(-1000, -400)),
                       900.0, loc=(-850, -400)),
                 LOOK["sun_halo_strength"], loc=(-700, -400))
    glow = _math(nodes, links, "ADD", disc.outputs["Result"], halo, loc=(-550, -250))
    sun_c, _ = _vmath(nodes, links, "SCALE", (1.0, 0.78, 0.52), scale=glow, loc=(-400, -250))

    # below the horizon: cloud sea (preview) or flat hazy colour
    below = _node(nodes, "ShaderNodeMapRange", (-500, 500))
    below.interpolation_type = "SMOOTHSTEP"
    below.inputs["From Min"].default_value = 0.0
    below.inputs["From Max"].default_value = -LOOK["below_horizon_blend"]
    links.new(sep.outputs["Z"], below.inputs["Value"])
    floor = _node(nodes, "ShaderNodeMix", (-200, 400))
    floor.data_type = "RGBA"
    links.new(below.outputs["Result"], floor.inputs["Factor"])
    links.new(sky_c, floor.inputs[6])
    if cloud_floor:
        links.new(_cloud_floor(nodes, links, d, sep.outputs["Z"]), floor.inputs[7])
    else:
        floor.inputs[7].default_value = tuple(LOOK["below_horizon_color"]) + (1.0,)

    col, _ = _vmath(nodes, links, "ADD", floor.outputs[2], sun_c, loc=(0, 0))
    bg = _node(nodes, "ShaderNodeBackground", (150, 0), Strength=1.0)
    links.new(col, bg.inputs["Color"])
    out = _node(nodes, "ShaderNodeOutputWorld", (350, 0))
    links.new(bg.outputs[0], out.inputs["Surface"])

    # EEVEE: the sun lamp does the direct light; do not extract a second sun
    _set(world, "sun_threshold", 0.0)
    _set(world, "use_sun_shadow", False)
    _set(world, "probe_resolution", "1024")
    return world


# --------------------------------------------------------------------------------------
# sun lamp
# --------------------------------------------------------------------------------------

def add_sun(scene, collection=None, name="look.sun", quality="preview"):
    """Warm golden-hour Sun lamp pointing along -SUN_DIR. Returns the object."""
    collection = collection or ensure_collection(LOOK_COLLECTION, scene.collection)
    light = bpy.data.lights.get(name)
    if light is None or light.type != "SUN":
        light = bpy.data.lights.new(name, "SUN")
    light.energy = LOOK["sun_strength"]
    light.color = LOOK["sun_color"]
    _set(light, "angle", math.radians(LOOK["sun_angle_deg"]))
    _set(light, "use_shadow", True)
    _set(light, "use_shadow_jitter", bool(QUALITY[quality]["sun_jitter"]))
    _set(light, "shadow_jitter_overblur", 10.0)
    _set(light, "shadow_filter_radius", 1.0)
    _set(light, "shadow_maximum_resolution", 0.001)
    _set(light, "volume_factor", LOOK["sun_volume_factor"])
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, light)
    obj.data = light
    _link(obj, collection)
    obj.location = SUN_DIR * 500.0
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = SUN_DIR.to_track_quat("Z", "Y")
    return obj


# --------------------------------------------------------------------------------------
# haze
# --------------------------------------------------------------------------------------

def _haze_material(name, density, base_z, falloff, color, anisotropy):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-900, 0)
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-720, 0)
    links.new(geo.outputs["Position"], sep.inputs[0])
    # density(z) = d0 * exp(-(z - base_z) / falloff), capped at 4 * d0
    sub = nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = base_z
    sub.location = (-560, 0)
    links.new(sep.outputs["Z"], sub.inputs[0])
    div = nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = -float(falloff)
    div.location = (-400, 0)
    links.new(sub.outputs[0], div.inputs[0])
    ex = nodes.new("ShaderNodeMath")
    ex.operation = "EXPONENT"
    ex.location = (-240, 0)
    links.new(div.outputs[0], ex.inputs[0])
    cap = nodes.new("ShaderNodeMath")
    cap.operation = "MINIMUM"
    cap.inputs[1].default_value = 4.0
    cap.location = (-80, 0)
    links.new(ex.outputs[0], cap.inputs[0])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = density
    mul.location = (80, 0)
    mul.label = "haze density"
    mul.name = "haze_density"
    links.new(cap.outputs[0], mul.inputs[0])

    sc = nodes.new("ShaderNodeVolumeScatter")
    sc.location = (280, 80)
    _inp(sc, "Color").default_value = tuple(color) + (1.0,)
    _inp(sc, "Anisotropy").default_value = anisotropy
    links.new(mul.outputs[0], _inp(sc, "Density"))
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (480, 0)
    links.new(sc.outputs[0], out.inputs["Volume"])
    _set(mat, "volume_intersection_method", "FAST")
    return mat


def add_haze(scene, collection=None, name="look.haze", density=None, base_z=None,
             falloff=None, extent=None, z_min=None, z_max=3500.0):
    """Atmospheric-perspective haze: a large box volume whose scattering density falls
    off exponentially with height. Defaults come from LOOK. Returns the object."""
    collection = collection or ensure_collection(LOOK_COLLECTION, scene.collection)
    density = LOOK["haze_density"] if density is None else density
    base_z = LOOK["haze_base_z"] if base_z is None else base_z
    falloff = LOOK["haze_falloff"] if falloff is None else falloff
    extent = LOOK["haze_extent"] if extent is None else extent
    z_min = LOOK["haze_floor_z"] if z_min is None else z_min
    mat = _haze_material(name + ".mat", density, base_z, falloff,
                         LOOK["haze_color"], LOOK["haze_anisotropy"])
    mesh = bpy.data.meshes.get(name)
    if mesh is None:
        mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 2.0 * extent
        v.co.y *= 2.0 * extent
        v.co.z = z_max if v.co.z > 0 else z_min
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.clear()
    mesh.materials.append(mat)
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, mesh)
    obj.data = mesh
    _link(obj, collection)
    obj.hide_select = True
    try:
        obj.visible_shadow = False
    except Exception:
        pass
    return obj


# --------------------------------------------------------------------------------------
# compositor (5.x: scene.compositing_node_group)
# --------------------------------------------------------------------------------------

def setup_compositor(scene, name="look.compositor", quality="preview"):
    """Glare bloom (only above `bloom_threshold` luminance, i.e. emissives) -> subtle ASC-CDL
    grade + saturation -> smooth elliptical vignette. Returns the node group."""
    ng = bpy.data.node_groups.get(name)
    if ng is None or ng.bl_idname != "CompositorNodeTree":
        ng = bpy.data.node_groups.new(name, "CompositorNodeTree")
    ng.nodes.clear()
    for item in list(ng.interface.items_tree):
        ng.interface.remove(item)
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes, links = ng.nodes, ng.links

    rl = nodes.new("CompositorNodeRLayers")
    rl.location = (-900, 0)
    rl.scene = scene

    glare = nodes.new("CompositorNodeGlare")
    glare.location = (-650, 0)
    _inp(glare, "Type").default_value = "Bloom"
    _inp(glare, "Quality").default_value = QUALITY[quality]["glare_quality"]
    _inp(glare, "Threshold").default_value = LOOK["bloom_threshold"]
    _inp(glare, "Smoothness").default_value = LOOK["bloom_smoothness"]
    _inp(glare, "Clamp").default_value = True
    _inp(glare, "Maximum").default_value = LOOK["bloom_max"]
    _inp(glare, "Strength").default_value = LOOK["bloom_strength"]
    _inp(glare, "Saturation").default_value = LOOK["bloom_saturation"]
    _inp(glare, "Size").default_value = LOOK["bloom_size"]
    links.new(rl.outputs["Image"], glare.inputs["Image"])

    grade = nodes.new("CompositorNodeColorBalance")
    grade.location = (-400, 0)
    _inp(grade, "Type").default_value = "Offset/Power/Slope (ASC-CDL)"
    grade.inputs["Factor"].default_value = 1.0
    sl, of, pw = LOOK["grade_slope"], LOOK["grade_offset"], LOOK["grade_power"]
    for sock in grade.inputs:
        if sock.identifier == "Color Slope":
            sock.default_value = (sl[0], sl[1], sl[2], 1.0)
        elif sock.identifier == "Color Offset":
            sock.default_value = (of[0], of[1], of[2], 1.0)
        elif sock.identifier == "Color Power":
            sock.default_value = (pw[0], pw[1], pw[2], 1.0)
    links.new(glare.outputs["Image"], grade.inputs["Image"])

    # tonal saturation: AgX bleaches bright warm light; give highlights a little back
    cc = nodes.new("CompositorNodeColorCorrection")
    cc.location = (-300, -150)
    for sock in cc.inputs:
        if sock.identifier == "Highlights Saturation":
            sock.default_value = LOOK["grade_highlight_saturation"]
        elif sock.identifier == "Shadows Saturation":
            sock.default_value = LOOK["grade_shadow_saturation"]
    links.new(grade.outputs["Image"], cc.inputs["Image"])

    sat = nodes.new("CompositorNodeHueSat")
    sat.location = (-200, 0)
    sat.inputs["Saturation"].default_value = LOOK["grade_saturation"]
    links.new(cc.outputs["Image"], sat.inputs["Image"])

    # vignette factor from normalised image coordinates
    coords = nodes.new("CompositorNodeImageCoordinates")
    coords.location = (-200, -300)
    links.new(sat.outputs["Image"], coords.inputs["Image"])
    centre = nodes.new("ShaderNodeVectorMath")
    centre.operation = "MULTIPLY_ADD"
    centre.location = (0, -300)
    centre.inputs[1].default_value = (2.0, 2.0, 0.0)
    centre.inputs[2].default_value = (-1.0, -1.0, 0.0)
    links.new(coords.outputs["Normalized"], centre.inputs[0])
    length = nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    length.location = (180, -300)
    links.new(centre.outputs["Vector"], length.inputs[0])
    vig = nodes.new("ShaderNodeMapRange")
    vig.interpolation_type = "SMOOTHSTEP"
    vig.location = (360, -300)
    vig.inputs["From Min"].default_value = LOOK["vignette_start"]
    vig.inputs["From Max"].default_value = LOOK["vignette_end"]
    vig.inputs["To Min"].default_value = 1.0
    vig.inputs["To Max"].default_value = 1.0 - LOOK["vignette_strength"]
    links.new(length.outputs["Value"], vig.inputs["Value"])

    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.location = (560, 0)
    mix.inputs["Factor"].default_value = 1.0
    links.new(sat.outputs["Image"], mix.inputs[6])          # A (colour)
    links.new(vig.outputs["Result"], mix.inputs[7])         # B (colour)

    gout = nodes.new("NodeGroupOutput")
    gout.location = (780, 0)
    links.new(mix.outputs[2], gout.inputs["Image"])

    scene.compositing_node_group = ng
    _set(scene.render, "use_compositing", True)
    return ng


# --------------------------------------------------------------------------------------
# lookdev entry point
# --------------------------------------------------------------------------------------

def setup_lookdev(scene, haze=True, compositor=True, quality=None, cloud_floor=True):
    """Sky world + sun lamp + optional haze volume + optional compositor on `scene`.
    Applies setup_render first if it was never run on this scene. `quality` defaults
    to the one setup_render used ('preview' otherwise). Objects go into a 'look'
    collection. Returns dict(world, sun, haze, compositor)."""
    if quality is None:
        quality = scene.get("sect_look_quality", "preview")
    if "sect_look_quality" not in scene:
        setup_render(scene, quality=quality, resolution=(scene.render.resolution_x,
                                                         scene.render.resolution_y))
    col = ensure_collection(LOOK_COLLECTION, scene.collection)
    world = setup_world(scene, cloud_floor=cloud_floor)
    sun = add_sun(scene, col, quality=quality)
    hz = add_haze(scene, col) if haze else None
    comp = setup_compositor(scene, quality=quality) if compositor else None
    return dict(world=world, sun=sun, haze=hz, compositor=comp)


# --------------------------------------------------------------------------------------
# cameras
# --------------------------------------------------------------------------------------

def camera_look_at(name, location, target, lens=35.0, collection=None):
    """Create or update camera `name` at `location` aimed at `target` (Z up).
    Returns the camera object."""
    collection = collection or bpy.context.scene.collection
    cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 36.0
    cam.sensor_fit = "AUTO"
    cam.clip_start = 0.1
    cam.clip_end = CAMERA_CLIP_END
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, cam)
    obj.data = cam
    _link(obj, collection)
    loc, tgt = Vector(location), Vector(target)
    obj.location = loc
    d = tgt - loc
    if d.length < 1e-6:
        d = Vector((0.0, 1.0, 0.0))
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return obj


def _fits(cam_loc, target, corners, lens, aspect, margin):
    fwd = (target - cam_loc)
    if fwd.length < 1e-6:
        return False
    fwd.normalize()
    right = fwd.cross(Vector((0, 0, 1)))
    if right.length < 1e-6:
        right = Vector((1, 0, 0))
    right.normalize()
    up = right.cross(fwd)
    tan_h = 18.0 / lens * margin if aspect >= 1 else 18.0 / lens / aspect * margin
    tan_v = tan_h / aspect
    for p in corners:
        v = p - cam_loc
        z = v.dot(fwd)
        if z <= 0.5:
            return False
        if abs(v.dot(right)) / z > tan_h or abs(v.dot(up)) / z > tan_v:
            return False
    return True


def _solve_distance(place, corners, lens, aspect, margin, hi):
    """Smallest t so the camera from `place(t) -> (loc, target)` sees all corners."""
    lo = 0.5
    loc, tgt = place(hi)
    if not _fits(loc, tgt, corners, lens, aspect, margin):
        return hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        loc, tgt = place(mid)
        if _fits(loc, tgt, corners, lens, aspect, margin):
            hi = mid
        else:
            lo = mid
    return hi


def auto_cameras(bbox, resolution=(1280, 720), margin=0.9):
    """Four framing cameras for a bbox (min Vector, max Vector):
    front_34, front (-Y axis, eye height ~10 m), aerial (~55 deg) and detail (lens 50).
    Returns a list of (name, location, target, lens)."""
    bmin, bmax = bbox
    c = (bmin + bmax) * 0.5
    corners = [Vector((x, y, z)) for x in (bmin.x, bmax.x) for y in (bmin.y, bmax.y)
               for z in (bmin.z, bmax.z)]
    size = (bmax - bmin).length
    hi = max(size * 20.0, 50.0)
    aspect = resolution[0] / float(resolution[1])
    cams = []

    def orbit(az, el, tgt):
        d = dir_from_az_el(az, el)
        return lambda t: (tgt + d * t, tgt)

    tgt = Vector((c.x, c.y, bmin.z + (bmax.z - bmin.z) * 0.42))
    t = _solve_distance(orbit(225.0, 25.0, tgt), corners, 35.0, aspect, margin, hi)
    cams.append(("front_34", tgt + dir_from_az_el(225.0, 25.0) * t, tgt, 35.0))

    eye = 10.0
    tgt_f = Vector((c.x, c.y, max(bmin.z + (bmax.z - bmin.z) * 0.45, 2.0)))

    def front(t):
        return Vector((c.x, bmin.y - t, eye)), tgt_f
    t = _solve_distance(front, corners, 35.0, aspect, margin, hi)
    loc, _ = front(t)
    cams.append(("front", loc, tgt_f, 35.0))

    tgt_a = Vector((c.x, c.y, bmin.z + (bmax.z - bmin.z) * 0.3))
    t = _solve_distance(orbit(200.0, 55.0, tgt_a), corners, 35.0, aspect, margin, hi)
    cams.append(("aerial", tgt_a + dir_from_az_el(200.0, 55.0) * t, tgt_a, 35.0))

    tgt_d = Vector((c.x, c.y, bmin.z + (bmax.z - bmin.z) * 0.4))
    t = _solve_distance(orbit(150.0, 14.0, tgt_d), corners, 50.0, aspect, margin, hi)
    cams.append(("detail", tgt_d + dir_from_az_el(150.0, 14.0) * (t * 0.45), tgt_d, 50.0))
    return cams


# --------------------------------------------------------------------------------------
# plinth (neutral karst pillar top under previews)
# --------------------------------------------------------------------------------------

PLINTH_MATERIAL = "rock_cliff"   # materials.py name used by add_plinth (same rock as world.py pillars)


def _rock_material():
    """The shared materials.get('rock_cliff'); a local rock only if materials.py fails to
    import or build (a warning is printed, so a broken materials.py is visible)."""
    try:
        from sect.lib import materials as M
        return M.get(PLINTH_MATERIAL)
    except Exception as exc:
        _log("WARN plinth: materials.get(%r) failed (%s: %s), using local rock"
             % (PLINTH_MATERIAL, exc.__class__.__name__, exc))
    return _local_rock_material()


def _local_rock_material(name="look.rock"):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-1300, 0)
    # vertical striations: squash Z so features stretch vertically
    squash = nodes.new("ShaderNodeVectorMath")
    squash.operation = "MULTIPLY"
    squash.inputs[1].default_value = (0.55, 0.55, 0.08)
    squash.location = (-1100, 100)
    links.new(tc.outputs["Object"], squash.inputs[0])
    n1 = nodes.new("ShaderNodeTexNoise")
    n1.location = (-900, 100)
    n1.inputs["Scale"].default_value = 1.0
    n1.inputs["Detail"].default_value = 8.0
    n1.inputs["Roughness"].default_value = 0.6
    links.new(squash.outputs[0], n1.inputs["Vector"])
    n2 = nodes.new("ShaderNodeTexNoise")
    n2.location = (-900, -150)
    n2.inputs["Scale"].default_value = 0.12
    n2.inputs["Detail"].default_value = 4.0
    links.new(tc.outputs["Object"], n2.inputs["Vector"])
    mixf = nodes.new("ShaderNodeMath")
    mixf.operation = "MULTIPLY_ADD"
    mixf.location = (-700, 0)
    mixf.inputs[1].default_value = 0.6
    links.new(n1.outputs["Fac"], mixf.inputs[0])
    links.new(n2.outputs["Fac"], mixf.inputs[2])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-520, 0)
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = hex_color("#57534b")
    ramp.color_ramp.elements[1].position = 0.95
    ramp.color_ramp.elements[1].color = hex_color("#8f8676")
    links.new(mixf.outputs[0], ramp.inputs["Fac"])
    # moss on up-facing surfaces
    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-900, -400)
    sepn = nodes.new("ShaderNodeSeparateXYZ")
    sepn.location = (-720, -400)
    links.new(geo.outputs["Normal"], sepn.inputs[0])
    mossmask = nodes.new("ShaderNodeMapRange")
    mossmask.location = (-540, -400)
    mossmask.interpolation_type = "SMOOTHSTEP"
    mossmask.inputs["From Min"].default_value = 0.55
    mossmask.inputs["From Max"].default_value = 0.9
    links.new(sepn.outputs["Z"], mossmask.inputs["Value"])
    mossn = nodes.new("ShaderNodeMath")
    mossn.operation = "MULTIPLY"
    mossn.location = (-360, -400)
    links.new(mossmask.outputs["Result"], mossn.inputs[0])
    links.new(n2.outputs["Fac"], mossn.inputs[1])
    mossk = nodes.new("ShaderNodeMapRange")
    mossk.location = (-200, -400)
    mossk.inputs["From Min"].default_value = 0.50
    mossk.inputs["From Max"].default_value = 0.66
    links.new(mossn.outputs[0], mossk.inputs["Value"])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.location = (-150, 0)
    links.new(mossk.outputs["Result"], mix.inputs["Factor"])
    links.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = hex_color("#55693f")
    bump = nodes.new("ShaderNodeBump")
    bump.location = (-150, -250)
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.3
    links.new(n1.outputs["Fac"], bump.inputs["Height"])
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    bsdf.inputs["Roughness"].default_value = 0.88
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (380, 0)
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def add_plinth(collection, footprint=40.0, top_z=-0.4, depth=30.0, seed=11, name="look.plinth"):
    """Neutral karst-pillar top: flat top at `top_z`, radius footprint + 6 m, fluted
    sides reaching `depth` metres down. Deterministic. Returns the object."""
    R = footprint + 6.0
    segs = max(96, min(256, int(R * 4.0)))
    off = Vector((seed * 17.31, seed * 3.77, seed * 9.13))
    # rings: (depth below top, radius offset in m, flute weight 0..1). The top lip is
    # rounded over the first 0.5 m; flutes and ledges grow below it.
    profile = [(0.0, -0.5, 0.0), (0.1, -0.15, 0.0), (0.4, 0.0, 0.15), (1.0, 0.2, 0.4),
               (2.0, 0.1, 0.7)]
    k = 3.0
    while k < depth:
        ledge = 0.6 * max(0.0, noise.noise(Vector((k * 0.21, 0.0, 0.0)) + off))
        profile.append((k, 0.15 + 1.2 * (k / depth) + ledge, 1.0))
        k += 2.0 if k < 12 else 3.5
    profile.append((depth, 1.6, 1.0))
    bm = bmesh.new()
    rings = []
    for dz, dr, fw in profile:
        z = top_z - dz
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            lobes = noise.noise(Vector((ca * 1.6, sa * 1.6, 0.0)) + off) * 2.2
            flute = noise.noise(Vector((ca * 14.0, sa * 14.0, z * 0.03)) + off) * 1.6
            pits = noise.noise(Vector((ca * 5.0, sa * 5.0, z * 0.12)) + off * 1.7) * 0.9
            r = R + 0.8 + dr + lobes + fw * (flute + pits)
            ring.append(bm.verts.new((ca * r, sa * r, z)))
        rings.append(ring)
    centre = bm.verts.new((0.0, 0.0, top_z))
    top_faces = []
    for i in range(segs):
        top_faces.append(bm.faces.new((centre, rings[0][i], rings[0][(i + 1) % segs])))
    side_faces = []
    for j in range(len(rings) - 1):
        a, b = rings[j], rings[j + 1]
        for i in range(segs):
            i2 = (i + 1) % segs
            side_faces.append(bm.faces.new((a[i], b[i], b[i2], a[i2])))
    bottom = bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in top_faces:
        f.smooth = False
    for f in side_faces:
        f.smooth = True
    bottom.smooth = False
    mesh = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.clear()
    mesh.materials.append(_rock_material())
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, mesh)
    obj.data = mesh
    _link(obj, collection)
    return obj


# --------------------------------------------------------------------------------------
# preview harness
# --------------------------------------------------------------------------------------

_WIPE = ("objects", "meshes", "materials", "node_groups", "worlds", "lights", "cameras",
         "collections", "curves", "textures", "actions", "particles", "grease_pencils",
         "volumes", "pointclouds", "hair_curves", "lattices", "metaballs", "armatures",
         "lightprobes", "speakers")


def reset_scene():
    """Empty the current file in place (all objects and data blocks except scenes,
    fonts and images), leaving one empty scene. Returns that scene.
    Note: lib caches holding datablock references must re-validate after this."""
    scene = bpy.context.scene
    for sc in list(bpy.data.scenes):
        if sc != scene:
            bpy.data.scenes.remove(sc)
    ids = []
    for attr in _WIPE:
        coll = getattr(bpy.data, attr, None)
        if coll is not None:
            ids.extend(coll)
    ids.extend(im for im in bpy.data.images if im.type not in {"RENDER_RESULT", "COMPOSITING"})
    if ids:
        bpy.data.batch_remove(ids)
    scene.world = None
    scene.camera = None
    try:
        scene.compositing_node_group = None
    except Exception:
        pass
    return scene


def _names(objects):
    """Object-name set from a Collection, an iterable of objects or of names."""
    if objects is None:
        return None
    if isinstance(objects, bpy.types.Collection):
        return set(o.name for o in objects.all_objects)
    return set(o if isinstance(o, str) else o.name for o in objects)


def build_bbox(scene, objects):
    """World-space bbox (min, max) of everything evaluated from `objects` (a Collection
    or an iterable of objects / names), including geometry-node and collection
    instances. Returns None if nothing renderable was found."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = _names(objects)
    lo = Vector((1e18, 1e18, 1e18))
    hi = Vector((-1e18, -1e18, -1e18))
    found = False
    for inst in dg.object_instances:
        src = inst.parent if inst.is_instance and inst.parent is not None else inst.object
        if src is None or src.original.name not in names:
            continue
        ob = inst.object
        if ob.type not in {"MESH", "CURVE", "FONT", "SURFACE", "META", "CURVES",
                           "POINTCLOUD", "VOLUME", "GREASEPENCIL"}:
            continue
        mw = inst.matrix_world
        for c in ob.bound_box:
            p = mw @ Vector(c)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
            found = True
    return (lo, hi) if found else None


def count_triangles(scene, objects=None):
    """Evaluated triangle count, instances included. `objects` (a Collection or an
    iterable of objects / names) limits the count to geometry coming from them."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = _names(objects)
    cache = {}
    total = 0
    for inst in dg.object_instances:
        src = inst.parent if inst.is_instance and inst.parent is not None else inst.object
        if names is not None and (src is None or src.original.name not in names):
            continue
        ob = inst.object
        if ob.type == "MESH":
            me = ob.data
            key = me.as_pointer()
            if key not in cache:
                cache[key] = len(me.loops) - 2 * len(me.polygons)
            total += cache[key]
        elif ob.type in {"CURVE", "FONT", "SURFACE", "META"}:
            key = ("obj", ob.as_pointer())
            if key not in cache:
                try:
                    me = ob.to_mesh()
                    cache[key] = len(me.loops) - 2 * len(me.polygons) if me else 0
                    ob.to_mesh_clear()
                except Exception:
                    cache[key] = 0
            total += cache[key]
    return total


def _clamp_bbox(bbox, footprint):
    """Keep auto-framing on the area: clamp to 1.6 x footprint in XY and a sane Z."""
    lo, hi = bbox
    lim = footprint * 1.6
    lo = Vector((max(lo.x, -lim), max(lo.y, -lim), max(lo.z, -footprint)))
    hi = Vector((min(hi.x, lim), min(hi.y, lim), min(hi.z, footprint * 2.0)))
    for i in range(3):
        if hi[i] <= lo[i]:
            hi[i] = lo[i] + 1.0
    return lo, hi


def preview(build_fn, out_dir, name="preview", cameras="auto", resolution=(1280, 720),
            footprint=40.0, samples=32, save_blend=None, quality="preview",
            haze=True, compositor=True):
    """Fresh scene + look-dev + rock plinth (top z=-0.4, radius footprint+6) +
    build_fn(collection), then render each camera to out_dir/<name>_<cam>.png and print
    'PREVIEW_STATS {json}'. `cameras` is 'auto', a list/comma string of auto names
    (front_34, front, aerial, detail), or a list of (name, location, target, lens).
    If build_fn has a `preview_cameras` attribute it replaces 'auto'. Returns stats."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    scene = reset_scene()
    scene.name = "preview"
    setup_render(scene, quality=quality, resolution=resolution)
    scene.eevee.taa_render_samples = int(samples)
    setup_lookdev(scene, haze=haze, compositor=compositor, quality=quality)
    look_col = ensure_collection(LOOK_COLLECTION, scene.collection)
    add_plinth(look_col, footprint=footprint)
    build_col = ensure_collection("build." + name, scene.collection)
    before = set(bpy.data.objects.keys())

    t0 = time.perf_counter()
    build_fn(build_col)
    bpy.context.view_layer.update()
    build_s = time.perf_counter() - t0
    # everything the build created counts, even if it was linked somewhere else
    built = (set(bpy.data.objects.keys()) - before) | _names(build_col)

    bbox = build_bbox(scene, built)
    if bbox is None:
        bbox = (Vector((-footprint, -footprint, 0.0)), Vector((footprint, footprint, 10.0)))
    fbox = _clamp_bbox(bbox, footprint)

    custom = [tuple(c) for c in (getattr(build_fn, "preview_cameras", None) or [])]
    named = {c[0]: c for c in auto_cameras(fbox, resolution)}
    named.update({c[0]: c for c in custom})
    if cameras == "auto":
        cam_list = custom or [named[k] for k in AUTO_CAMERAS]
    else:
        if isinstance(cameras, str):
            cameras = [c.strip() for c in cameras.split(",") if c.strip()]
        cam_list = []
        for c in cameras:
            if isinstance(c, str):
                if c not in named:
                    raise KeyError("unknown camera %r (valid: %s)" % (c, sorted(named)))
                cam_list.append(named[c])
            else:
                cam_list.append(tuple(c))

    tris = count_triangles(scene, built)
    n_objects = len(built)

    render_s = {}
    files = []
    for cname, loc, tgt, lens in cam_list:
        cam = camera_look_at("look.cam." + cname, loc, tgt, lens=lens, collection=look_col)
        scene.camera = cam
        path = os.path.join(out_dir, "%s_%s.png" % (name, cname))
        scene.render.filepath = path
        t1 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        render_s[cname] = round(time.perf_counter() - t1, 2)
        if not os.path.isfile(path):
            _log("WARN render did not write", path)
        files.append(path.replace("\\", "/"))
        _log("rendered", path, render_s[cname], "s")

    if save_blend:
        os.makedirs(os.path.dirname(os.path.abspath(save_blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save_blend), compress=True)

    stats = dict(name=name, objects=n_objects, triangles=tris, build_s=round(build_s, 2),
                 render_s=render_s, bbox=[list(map(lambda v: round(v, 2), bbox[0])),
                                          list(map(lambda v: round(v, 2), bbox[1]))],
                 files=files)
    print("PREVIEW_STATS " + json.dumps(stats), flush=True)
    return stats


# --------------------------------------------------------------------------------------
# look-dev test targets
# --------------------------------------------------------------------------------------

def _test_mat(name, color, rough=0.5, metal=0.0, emit=None, emit_strength=0.0, coat=0.0):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = hex_color(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        _inp(b, "Coat Weight").default_value = coat
        _inp(b, "Coat Roughness").default_value = 0.15
    if emit:
        _inp(b, "Emission Color").default_value = hex_color(emit)
        _inp(b, "Emission Strength").default_value = emit_strength
    return mat


def _box(collection, name, size, loc, mat, bevel=0.04):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2, affect="EDGES",
                        profile=0.5)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    collection.objects.link(obj)
    for p in mesh.polygons:
        p.use_smooth = False
    return obj


def _cylinder(collection, name, radius, height, loc, mat, segs=24):
    mesh = bpy.data.meshes.get(name + ".mesh")
    if mesh is None:
        mesh = bpy.data.meshes.new(name + ".mesh")
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius,
                              radius2=radius, depth=height)
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, height * 0.5))
        bm.to_mesh(mesh)
        bm.free()
        for p in mesh.polygons:
            p.use_smooth = len(p.vertices) == 4
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    collection.objects.link(obj)
    return obj


def _sphere(collection, name, radius, loc, mat):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    collection.objects.link(obj)
    return obj


def _roof(collection, name, half_x, half_y, eave_z, ridge_z, ridge_half, mat, upturn=0.7):
    """Concave hip roof with up-swept corners (look-dev stand-in only)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    def ring(hx, hy, z, corner_lift):
        pts = []
        n = 8
        for side in range(4):
            for i in range(n):
                t = i / n
                if side == 0:
                    x, y = -hx + 2 * hx * t, -hy
                elif side == 1:
                    x, y = hx, -hy + 2 * hy * t
                elif side == 2:
                    x, y = hx - 2 * hx * t, hy
                else:
                    x, y = -hx, hy - 2 * hy * t
                # lift toward corners
                cx = abs(x) / hx
                cy = abs(y) / hy
                lift = corner_lift * (max(cx, cy) ** 6) * (min(cx, cy) ** 6) if hx > 0 and hy > 0 else 0
                pts.append(bm.verts.new((x, y, z + lift)))
        return pts

    hx0, hy0 = half_x, half_y
    r0 = ring(hx0, hy0, eave_z, upturn)
    r1 = ring(hx0 * 0.78, hy0 * 0.62, eave_z + (ridge_z - eave_z) * 0.30, upturn * 0.25)
    r2 = ring(ridge_half + (hx0 - ridge_half) * 0.35, hy0 * 0.28,
              eave_z + (ridge_z - eave_z) * 0.68, 0.0)
    r3 = ring(ridge_half, 0.05, ridge_z, 0.0)
    rings = [r0, r1, r2, r3]
    for a, b in zip(rings[:-1], rings[1:]):
        m = len(a)
        for i in range(m):
            bm.faces.new((a[i], a[(i + 1) % m], b[(i + 1) % m], b[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.06)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    sol = obj.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.45
    sol.offset = -1.0
    return obj


def showcase(collection):
    """Look-dev test target: paved terrace, stepped marble platform, red columns,
    teal-green bracket band, concave hip roof, gold finials, hanging lanterns and a
    bright jade orb (bloom test)."""
    marble = _test_mat("look.test.marble", "#e8e4da", rough=0.38)
    paving = _test_mat("look.test.paving", "#a9a397", rough=0.7)
    lacquer = _test_mat("look.test.lacquer", "#a3221c", rough=0.35, coat=0.3)
    roof = _test_mat("look.test.roof", "#1f4f4b", rough=0.22, coat=0.6)
    band = _test_mat("look.test.dougong", "#2f6f73", rough=0.55)
    gold = _test_mat("look.test.gold", "#d4af37", rough=0.28, metal=1.0)
    jade = _test_mat("look.test.jade", "#2a8f78", rough=0.3, emit="#6fffd8", emit_strength=20.0)
    lamp = _test_mat("look.test.lantern", "#d0662e", rough=0.6, emit="#ffb46b", emit_strength=8.0)
    wood = _test_mat("look.test.wood", "#3a2418", rough=0.6)

    # paving disc and stepped platform (xumizuo stand-in)
    _cylinder(collection, "look.test.paving", 30.0, 0.4, (0, 0, -0.4), paving, segs=96)
    tiers = [(24.0, 16.0, 0.0, 0.7), (23.0, 15.0, 0.7, 0.5), (22.0, 14.0, 1.2, 0.6)]
    for i, (sx, sy, z0, h) in enumerate(tiers):
        _box(collection, "look.test.tier%d" % i, (sx, sy, h), (0, 0, z0 + h * 0.5), marble, 0.05)
    top = 1.8
    # front stairs
    for s in range(11):
        h = top / 11.0
        depth = 0.32
        _box(collection, "look.test.step%02d" % s, (7.0, depth * (11 - s), h),
             (0, -7.0 - depth * (11 - s) * 0.5, h * (s + 0.5)), marble, 0.02)
    # columns
    for ix, x in enumerate((-7.5, -2.5, 2.5, 7.5)):
        for iy, y in enumerate((-4.0, 4.0)):
            _cylinder(collection, "look.test.base%d%d" % (ix, iy), 0.55, 0.35, (x, y, top), marble)
            _cylinder(collection, "look.test.col%d%d" % (ix, iy), 0.32, 6.0, (x, y, top + 0.35),
                      lacquer, segs=20)
    # wall / door panel at the back of the bay (lattice stand-in)
    _box(collection, "look.test.wall", (14.5, 0.3, 5.6), (0, 3.6, top + 2.8), wood, 0.02)
    # bracket band and beams
    _box(collection, "look.test.beam", (17.0, 9.0, 0.5), (0, 0, top + 6.6), lacquer, 0.03)
    _box(collection, "look.test.band", (19.0, 11.0, 0.8), (0, 0, top + 7.25), band, 0.03)
    # roof
    _roof(collection, "look.test.roof", 13.5, 9.0, top + 7.7, top + 12.6, 6.0, roof)
    for x in (-6.0, 6.0):
        _sphere(collection, "look.test.finial%+d" % x, 0.45, (x, 0, top + 12.9), gold)
    # lanterns hanging at the front eave corners
    for x in (-11.0, 11.0):
        _cylinder(collection, "look.test.cord%+d" % x, 0.03, 1.4, (x, -7.6, top + 5.2), wood, 6)
        _sphere(collection, "look.test.lantern%+d" % x, 0.45, (x, -7.6, top + 4.9), lamp)
    # jade orb (bloom) floating over the stair head
    _sphere(collection, "look.test.orb", 0.9, (0, -15.0, top + 3.5), jade)
    # a few loose stone blocks / grey cards for value reading
    _box(collection, "look.test.block1", (2.0, 2.0, 2.0), (-17.0, -12.0, 1.0), paving, 0.08)
    _box(collection, "look.test.block2", (1.4, 3.0, 1.2), (16.0, -10.0, 0.6), marble, 0.08)
    return collection


def haze_showcase(collection):
    """Haze test: marble boxes on rock pillars 50 m, 200 m, 600 m and 1500 m north of
    the origin, each scaled with distance so they look about the same size. Cameras:
    `wide_n` (looking north at them) and `wide_sun` (looking into the sun)."""
    rock = _local_rock_material()
    marble = _test_mat("look.test.marble", "#e8e4da", rough=0.38)
    for i, (d, az) in enumerate(((50.0, -14.0), (200.0, -5.0), (600.0, 5.0), (1500.0, 14.0))):
        s = d * 0.09
        p = dir_from_az_el(az, 0.0) * d
        _box(collection, "look.haze.box%d" % i, (s, s, s), (p.x, p.y, 8.0 + s * 0.5), marble, s * 0.02)
        _cylinder(collection, "look.haze.pillar%d" % i, s * 0.45, 260.0 + s,
                  (p.x, p.y, 8.0 - 260.0 - s), rock, segs=32)
    return collection


haze_showcase.preview_cameras = [
    ("wide_n", (0.0, -40.0, 14.0), (0.0, 400.0, 34.0), 35.0),
    ("wide_sun", (0.0, -40.0, 14.0),
     tuple(Vector((0.0, -40.0, 14.0)) + dir_from_az_el(SUN_AZIMUTH + 12.0, 3.0) * 500.0), 35.0),
]


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def _parse_args(argv):
    import argparse
    p = argparse.ArgumentParser(prog="look.py", description="Moonlit Sect preview harness")
    p.add_argument("--target", default="sect.lib.look:showcase",
                   help="module:function; the function receives the build collection")
    p.add_argument("--out", default=None, help="output folder for PNGs")
    p.add_argument("--name", default=None, help="file prefix (default: module/area key)")
    p.add_argument("--footprint", type=float, default=None)
    p.add_argument("--cams", default="auto", help="auto, or a comma list of front_34,front,aerial,detail and any "
                        "names in the target's preview_cameras")
    p.add_argument("--res", default="1280x720")
    p.add_argument("--samples", type=int, default=None)
    p.add_argument("--quality", default="preview", choices=sorted(QUALITY))
    p.add_argument("--blend", default=None, help="also save the preview scene here")
    p.add_argument("--no-haze", action="store_true")
    p.add_argument("--no-comp", action="store_true")
    p.add_argument("--look-json", default=None,
                   help='JSON dict of LOOK overrides for tuning, e.g. {"sun_strength": 7}')
    return p.parse_args(argv)


def main(argv=None):
    """CLI entry point (argv = the arguments after Blender's '--')."""
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = _parse_args(argv)
    if args.look_json:
        LOOK.update(json.loads(args.look_json))
    import importlib
    mod_name, _, fn_name = args.target.partition(":")
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name or "build")
    area = getattr(mod, "AREA", None) if fn_name in ("", "build") else None
    footprint = args.footprint
    if footprint is None:
        footprint = float(area["footprint"]) if area else 40.0
    key = area["key"] if area else mod_name.rsplit(".", 1)[-1]
    name = args.name or key
    out = args.out or os.path.join(ROOT, "out", "previews", key)
    w, h = (int(v) for v in args.res.lower().split("x"))
    samples = args.samples or QUALITY[args.quality]["samples"]
    preview(fn, out, name=name, cameras=args.cams, resolution=(w, h), footprint=footprint,
            samples=samples, save_blend=args.blend, quality=args.quality,
            haze=not args.no_haze, compositor=not args.no_comp)


if __name__ == "__main__":
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from sect.lib import look as _look   # one module instance for target + harness
        _look.main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        print("PREVIEW_ERROR", flush=True)
        sys.exit(1)
