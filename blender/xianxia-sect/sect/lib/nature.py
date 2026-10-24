"""Nature and terrain pieces for the Moonlit Sect.

Huangshan pines, blossom trees, willows, bamboo, shrubs and grass, boulders / scholar rocks /
ledges, Zhangjiajie karst pillars, floating rocks, ponds, waterfalls, lotus, volumetric cloud
puffs and banks, and a geometry-nodes scatter helper.

    from sect.lib import nature as N
    N.pine(coll, height=9, seed=3, location=(4, 2, 0), name="summit.pine")
    N.rock_pillar(coll, height=160, top_radius=46, bottom_radius=38, seed=7, top_z=-0.4)

Conventions (spec.md): meters, Z up, front faces -Y, objects sit on z = 0 at their origin.
Every builder takes ``collection`` first and accepts ``name`` (object-name prefix, e.g.
"mirror.willow"), ``location``, ``rotation`` (a Z angle in radians or an XYZ Euler) and
``parent``. It returns the root object it created. Repeated things (pine variants, shrubs,
grass, lotus, rim stones, bamboo culms) are prototypes in excluded ``_protos`` collections,
built once per session and placed as collection instances / linked duplicates / GN instances.
All randomness is seeded; the same call gives the same result.
"""

import math
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as _mnoise

from . import materials as M
from . import util as U

__all__ = [
    "pine", "blossom_tree", "willow", "bamboo_clump", "shrub", "grass_tuft",
    "rock", "rock_pillar", "floating_rock", "ground_patch",
    "pond", "waterfall", "lotus_patch", "cloud_puff", "cloud_bank", "scatter_on",
    "showcase", "board_trees", "board_rocks", "board_clouds", "plant_prototypes", "BAMBOO_HEIGHT",
    "PINE_VARIANTS", "PINE_HEIGHT",
]

PREFIX = "nature"
PINE_HEIGHT = 10.0          # canonical prototype height; instances are scaled to the asked height
PINE_VARIANTS = {"huangshan": 6, "cliff": 4, "ancient": 3, "masson": 4}   # masson: round 48's slim spire
_PROTO_TAG = "nature_proto"
_Z = Vector((0.0, 0.0, 1.0))


# =====================================================================================
# materials (module-specific, registered through materials.register; names start nature_)
# =====================================================================================

def _mat_pine_pad(g, dark="#10241a", mid="#173326", light="#244a35", sun="#76884a", under="#1a3324",
                  tuft=4.0, transl=0.22, sun_mix=0.2, crevice="#0a1812", under_k=0.5, cells=3.6):
    """Stylised pine needle mass (blue-green), drawn the way Chinese painting draws pine
    foliage: many small rounded needle tufts (voronoi cells of 1/``cells`` m, each lighter and
    domed in the middle, darker in the gaps between), fibrous needle streaks, warmer sunlit
    tops, dark-green (never black) undersides, mild translucency (also on the undersides)."""
    v = g.coord("object")
    up = g.sep(g.geometry("Normal"))[2]
    clump = g.noise(v, tuft, detail=3.0, roughness=0.55, distortion=0.9)
    n1 = g.noise(v, 0.9, detail=3.0, roughness=0.5)
    fib = g.noise(g.mapping(v, scale=(1.0, 1.0, 2.5)), 34.0, detail=6.0, roughness=0.75, distortion=1.2)
    fine = g.noise(v, 11.0, detail=4.0, roughness=0.65)
    col = g.ramp(g.add(g.mul(n1, 0.5), g.mul(fine, 0.5)), [(0.25, dark), (0.55, mid), (0.85, light)])
    lump = g.smooth(clump, 0.48, 0.72)
    if cells:
        vc = g.vmath('ADD', v, g.vmath('SCALE', g.noise(v, 1.3, detail=2.0, color=True), scale=0.3))
        dist = g.voronoi(vc, cells, randomness=0.95)
        cid = g.voronoi(vc, cells, randomness=0.95, out="Color")
        tm = g.smooth(g.add(dist, g.mul(g.math('SUBTRACT', fib, 0.5), 0.25)), 0.66, 0.08)  # 1 tuft centre, 0 gap
        cr, cg, _cb = g.sep(cid)
        col = g.hsv(col, g.maprange(cr, 0, 1, 0.485, 0.515), 1.0, g.maprange(cg, 0, 1, 0.82, 1.15))
        col = g.mix(g.mix(col, crevice, 0.6), g.hsv(col, 0.5, 1.05, 1.3), tm)
        lump = g.add(g.mul(lump, 0.4), g.mul(tm, 0.6))
    else:
        col = g.mix(col, g.hsv(col, 0.5, 1.05, 1.3), g.mul(lump, 0.4))
        col = g.mix(col, crevice, g.mul(g.smooth(clump, 0.42, 0.28), 0.4))
    col = g.mix(col, g.hsv(col, 0.48, 1.0, 1.5), g.mul(g.smooth(fib, 0.6, 0.78), 0.45))
    col = g.mix(col, sun, g.mul(g.smooth(up, 0.35, 0.95), sun_mix))
    tup = g.sep(g.geometry("True Normal"))[2]
    col = g.mix(col, under, g.mul(g.smooth(up, -0.2, -0.75), 0.6))
    col = g.mix(col, under, g.mul(g.smooth(tup, 0.1, -0.5), under_k))
    col = g.tint_per_object(col, hue=0.015, sat=0.1, val=0.12)
    nrm = g.bump(lump, 0.6, 0.12)
    nrm = g.bump(fib, 0.45, 0.008, nrm)
    lit = g.smooth(tup, -0.3, 0.4)            # undersides: no sheen, almost no specular (no sky glints)
    bsdf = g.principled(base_color=col, roughness=g.maprange(fine, 0.2, 0.8, 0.7, 0.9),
                        sheen_weight=g.mul(lit, 0.12), sheen_roughness=0.6, sheen_tint="#9fb87a",
                        specular_ior_level=g.mixf(0.04, 0.25, lit), normal=nrm)
    if transl:
        tk = g.mul(transl, g.add(0.45, g.mul(g.smooth(up, -0.6, 0.2), 0.55)))   # undersides glow a little too
        bsdf = g.mix_shader(tk, bsdf, g.translucent(g.mix(col, "#7d9a3a", 0.5), nrm))
    g.mat.use_backface_culling = False
    g.viewport(mid, 0.7)
    g.output(bsdf)


def _mat_needle(g, base="#0b1a14", mid="#15392d", tip="#3d6f58", sun="#8d9a54", under="#0c1d15", transl=0.3,
                needles=34.0, spread=1.5, width=0.014):
    """Pine needle fan cards. UV: the fan's root at (0.5, 0); x = (u - 0.5) * 2 and y = v are in
    units of the card's length, so radius rho = |(x, y)| and angle phi = atan2(x, y). The alpha
    cuts out ``needles`` straight tapered needles spread over ``spread`` radians (each with a
    jittered angle and its own length), like an ink-painting pine-needle stroke. Colour runs
    dark at the root to lighter blue-green tips; warm sunlit tops, dark undersides, translucent.
    Dithered (hashed) transparency with transparent shadows."""
    m = g.mat
    m.surface_render_method = 'DITHERED'
    m.use_transparent_shadow = True
    m.use_backface_culling = False
    uv = g.coord("uv")
    u, y, _ = g.sep(uv)
    x = g.mul(g.math('SUBTRACT', u, 0.5), 2.0)
    rho = g.math('SQRT', g.add(g.mul(x, x), g.mul(y, y)))
    phi = g.math('ARCTAN2', x, y)
    f = g.mul(g.add(g.math('DIVIDE', phi, spread), 0.5), needles)
    cell = g.math('FLOOR', f)
    fr = g.math('FRACT', f)
    wn = g.node("ShaderNodeTexWhiteNoise", {"W": cell}, noise_dimensions='1D')
    jit = g.mul(g.math('SUBTRACT', wn.outputs["Value"], 0.5), 0.5)
    ln = g.maprange(g.sep(wn.outputs["Color"])[0], 0.0, 1.0, 0.62, 1.0)
    arc = g.mul(g.mul(g.math('ABSOLUTE', g.math('SUBTRACT', g.math('SUBTRACT', fr, 0.5), jit)), spread / needles), rho)
    # needles are hair-thin at the root (so the fan never shows a solid wedge), widest at ~30 %
    taper = g.mul(g.mul(width, g.math('SUBTRACT', 1.0, g.math('DIVIDE', rho, ln), clamp=True)), g.smooth(rho, 0.02, 0.3))
    a_needle = g.smooth(g.math('SUBTRACT', arc, taper), 0.004, -0.004)
    a_len = g.mul(g.smooth(rho, ln, g.mul(ln, 0.94)), g.smooth(rho, 0.0, 0.04))
    alpha = g.mul(a_needle, a_len)
    t = g.math('DIVIDE', rho, ln, clamp=True)
    up = g.sep(g.geometry("Normal"))[2]
    n = g.noise(g.coord("object"), 1.4, detail=2.0)
    col = g.ramp(t, [(0.0, base), (0.4, mid), (1.0, tip)])
    col = g.mix(col, g.hsv(col, 0.49, 1.05, 1.35), g.mul(g.smooth(n, 0.5, 0.72), 0.6))
    col = g.mix(col, sun, g.mul(g.mul(g.smooth(up, 0.35, 0.95), t), 0.28))
    col = g.mix(col, under, g.mul(g.smooth(up, -0.05, -0.7), 0.7))
    col = g.tint_per_object(col, hue=0.012, sat=0.1, val=0.12)
    bsdf = g.principled(base_color=col, roughness=0.6, sheen_weight=0.2, sheen_tint="#b8d0a0",
                        specular_ior_level=0.3, alpha=alpha)
    tr = g.translucent(g.mix(col, "#7d9a3a", 0.45))
    tr = g.mix_shader(alpha, g.transparent(), tr)
    bsdf = g.mix_shader(g.mul(transl, g.smooth(up, -0.5, 0.3)), bsdf, tr)
    g.viewport(mid, 0.6)
    g.output(bsdf)


def _mat_pine_bark(g, low=("#3a332f", "#5a5048"), high=("#4e3a30", "#6a4c3a"), crack="#241b16",
                   lichen="#8e9180", warm_z=(4.0, 7.0), scale=6.0):
    """Huangshan pine bark in prototype space (trees are built 10 m tall): deep vertical
    furrows breaking the grey-brown lower trunk into small, irregular, vertically stretched
    scales with thin brown (not black) fissures; thinner, flaky, warmer red-brown bark from
    about half height up and on the limbs; grey lichen patches near the foot."""
    v = g.coord("object_raw")
    z = g.sep(v)[2]
    warp = g.noise(v, 3.0, detail=2.0, color=True)
    vp = g.vmath('ADD', g.mapping(v, scale=(scale * 1.7, scale * 1.7, scale * 0.55)), g.vmath('SCALE', warp, scale=0.7))
    cell = g.voronoi(vp, 1.0, randomness=1.0, out="Color")
    edge = g.voronoi(vp, 1.0, feature='DISTANCE_TO_EDGE', randomness=1.0)
    fur = g.noise(g.mapping(v, scale=(scale * 1.1, scale * 1.1, scale * 0.12)), 1.0, detail=4.0, roughness=0.6,
                  distortion=0.3)
    hi = g.smooth(g.add(z, g.mul(g.noise(v, 0.6, detail=2.0), 1.6)), warm_z[0], warm_z[1])
    lo_k = g.math('SUBTRACT', 1.0, g.mul(hi, 0.75))
    furrow = g.mul(g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', fur, 0.5)), 0.06, 0.0), lo_k)
    crack_m = g.mul(g.smooth(edge, 0.03, 0.006), g.mul(lo_k, 0.6))
    tone = g.sep(cell)[0]
    fine = g.noise(v, 30.0, detail=5.0, roughness=0.65)
    flake = g.noise(g.mapping(v, scale=(12.0, 12.0, 3.0)), 1.0, detail=4.0, roughness=0.6)
    t = g.add(g.mul(tone, 0.45), g.mul(fine, 0.55))
    c_lo = g.ramp(t, [(0.25, low[0]), (0.8, low[1])])
    c_hi = g.ramp(g.add(g.mul(flake, 0.6), g.mul(fine, 0.4)), [(0.3, high[0]), (0.75, high[1])])
    col = g.mix(c_lo, c_hi, hi)
    col = g.mix(col, crack, g.math('MAXIMUM', crack_m, furrow))
    lich = g.mul(g.smooth(g.noise(v, 1.6, detail=4.0, distortion=0.4), 0.55, 0.66), g.smooth(z, 2.6, 0.4))
    col = g.mix(col, lichen, g.mul(lich, 0.5))
    col = g.tint_per_object(col, hue=0.01, sat=0.08, val=0.1)
    nrm = g.bump(g.math('MAXIMUM', crack_m, furrow), 0.8, 0.02, invert=True)
    nrm = g.bump(g.add(fine, g.mul(flake, hi)), 0.3, 0.006, nrm)
    g.viewport(low[1], 0.9)
    g.output(g.principled(base_color=col, roughness=g.maprange(fine, 0, 1, 0.78, 0.95), normal=nrm,
                          specular_ior_level=0.3))


def _mat_blossom(g, colours=(("#d9668a", 0.0), ("#f3a9c0", 0.45), ("#fde2ea", 0.8), ("#fff7f8", 1.0)),
                 centre="#b8325a", petal=9.0, transl=0.32, sun="#fff1e6"):
    """Blossom mass: petal-sized cells, darker flower centres, pale sunlit tops, translucent."""
    v = g.coord("object")
    up = g.sep(g.geometry("Normal"))[2]
    cells = g.voronoi(v, petal, randomness=1.0)
    gaps = g.voronoi(v, petal, feature='DISTANCE_TO_EDGE', randomness=1.0)
    n1 = g.noise(v, 1.1, detail=3.0)
    clump = g.noise(v, 3.5, detail=3.0, distortion=0.8)
    fine = g.noise(v, 30.0, detail=3.0)
    col = g.ramp(g.add(g.add(g.mul(n1, 0.45), g.mul(clump, 0.35)), g.mul(fine, 0.2)), [(p, c) for c, p in colours])
    col = g.mix(col, centre, g.mul(g.smooth(cells, 0.12, 0.02), 0.55))
    col = g.mix(col, g.hsv(col, 0.5, 1.15, 0.72), g.mul(g.smooth(gaps, 0.06, 0.0), 0.45))
    col = g.mix(col, g.hsv(col, 0.5, 1.2, 0.6), g.mul(g.smooth(clump, 0.42, 0.25), 0.5))
    col = g.mix(col, sun, g.mul(g.smooth(up, 0.4, 1.0), 0.3))
    col = g.mix(col, g.hsv(col, 0.5, 1.2, 0.55), g.mul(g.smooth(up, -0.1, -0.8), 0.6))
    col = g.tint_per_object(col, hue=0.012, sat=0.1, val=0.08)
    nrm = g.bump(g.smooth(clump, 0.35, 0.7), 0.4, 0.08)
    nrm = g.bump(g.smooth(gaps, 0.0, 0.08), 0.25, 0.01, nrm)
    bsdf = g.principled(base_color=col, roughness=0.55, sheen_weight=0.4, sheen_tint="#ffffff",
                        sheen_roughness=0.4, specular_ior_level=0.3, normal=nrm)
    bsdf = g.mix_shader(transl, bsdf, g.translucent(g.hsv(col, 0.5, 1.1, 1.3), nrm))
    g.mat.use_backface_culling = False
    g.viewport(colours[1][0], 0.55)
    g.output(bsdf)


def _mat_willow(g, dark="#4d6a26", mid="#7f9e3c", light="#b9c76a", transl=0.38):
    """Willow strands (UV: u across, v = arc length in leaf periods): alpha-cut slender leaves
    alternating left and right of a thin central twig, slanting down and out; per-strand tone
    variation, translucent. Dithered transparency, transparent shadows."""
    m = g.mat
    m.surface_render_method = 'DITHERED'
    m.use_transparent_shadow = True
    m.use_backface_culling = False
    uv = g.coord("uv")
    u, v, _ = g.sep(uv)

    def leaf(f, sign):
        uc = g.add(0.5, g.mul(sign, g.add(0.04, g.mul(f, 0.36))))
        w = g.mul(0.15, g.math('POWER', g.math('SINE', g.mul(f, math.pi)), 0.8))
        d = g.math('ABSOLUTE', g.math('SUBTRACT', u, uc))
        return g.smooth(g.math('SUBTRACT', d, w), 0.012, -0.012)
    f1 = g.math('FRACT', v)
    f2 = g.math('FRACT', g.add(v, 0.5))
    twig = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', u, 0.5)), 0.05, 0.025)
    alpha = g.math('MAXIMUM', g.math('MAXIMUM', leaf(f1, 1.0), leaf(f2, -1.0)), twig)
    n1 = g.noise(g.coord("object"), 0.8, detail=2.0)
    n2 = g.noise(g.coord("object"), 3.5, detail=2.0)
    col = g.ramp(g.add(g.mul(n1, 0.6), g.mul(n2, 0.4)), [(0.25, dark), (0.55, mid), (0.85, light)])
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 0.65), g.mul(twig, 0.6))
    col = g.tint_per_object(col, hue=0.012, sat=0.1, val=0.1)
    bsdf = g.principled(base_color=col, roughness=0.55, sheen_weight=0.25, specular_ior_level=0.35, alpha=alpha)
    tr = g.mix_shader(alpha, g.transparent(), g.translucent(g.mix(col, "#d8e070", 0.5)))
    bsdf = g.mix_shader(transl, bsdf, tr)
    g.viewport(mid, 0.55)
    g.output(bsdf)


def _mat_leaf_card(g, base="#3e6a2c", tip="#8bab4c", vein="#26401c", transl=0.3):
    """Leaf blades (bamboo, grass, reeds, stems): UV v runs base (0) to tip (1), u across the
    blade (0..1): base-to-tip gradient, a pale midrib, translucency."""
    uv = g.coord("uv")
    u, t, _ = g.sep(uv)
    col = g.ramp(t, [(0.0, vein), (0.25, base), (1.0, tip)])
    rib = g.smooth(g.math('ABSOLUTE', g.math('SUBTRACT', u, 0.5)), 0.06, 0.0)
    col = g.mix(col, g.hsv(col, 0.5, 0.8, 1.35), g.mul(rib, 0.4))
    n = g.noise(g.coord("object"), 6.0, detail=2.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.0, 1.2), g.mul(g.smooth(n, 0.5, 0.75), 0.5))
    col = g.tint_per_object(col, hue=0.02, sat=0.12, val=0.12)
    bsdf = g.principled(base_color=col, roughness=0.5, sheen_weight=0.2, specular_ior_level=0.4,
                        normal=g.bump(n, 0.1, 0.005))
    bsdf = g.mix_shader(transl, bsdf, g.translucent(g.hsv(col, 0.5, 1.2, 1.4)))
    g.mat.use_backface_culling = False
    g.viewport(base, 0.5)
    g.output(bsdf)


def _mat_cloud_puff(g, colour="#fbf8f4", density=1.6, anisotropy=0.35, lumps=2.3, soft=0.16, base_cut=0.55):
    """Cumulus puff volume. Density = ellipsoid falloff of the domain's bounding box (generated
    coords) pushed in and out by billowy noise, a flat-ish base, and obj['density']. Each object
    gets its own billows from Object Info > Random."""
    gen = g.coord("generated")
    q = g.vmath('SUBTRACT', g.vmath('SCALE', gen, scale=2.0), (1.0, 1.0, 1.0))      # -1..1 in the box
    qx, qy, qz = g.sep(q)
    ell = g.vmath('LENGTH', q)
    rnd = g.vmath('SCALE', g.obj_rand3(), scale=50.0)
    p = g.vmath('ADD', q, rnd)
    big = g.noise(p, lumps, detail=2.0, roughness=0.5)
    small = g.noise(p, lumps * 3.0, detail=3.0, roughness=0.55)
    cells = g.voronoi(p, lumps * 0.9, randomness=0.9)                 # round cauliflower lobes
    bill = g.add(g.add(g.mul(big, 0.5), g.mul(small, 0.2)), g.mul(g.math('SUBTRACT', 1.0, cells), 0.3))
    # upper half more billowy than the base
    upw = g.maprange(qz, -0.4, 0.6, 0.45, 0.95)
    shape = g.add(g.math('SUBTRACT', 0.92, ell), g.mul(g.math('SUBTRACT', bill, 0.5), upw))
    base = g.smooth(qz, -base_cut - 0.25, -base_cut + 0.1)
    d = g.mul(g.smooth(shape, 0.0, soft), base)
    k = g.obj_prop("density", 1.0)
    g.viewport(colour, 0.5)
    g.output(volume=g.volume(color=colour, density=g.mul(g.mul(d, density), k), anisotropy=anisotropy,
                             absorption_color="#000000"))


def _mat_waterfall(g, water="#7aa7ab", foam="#f4f8f8", deep="#3d6c72", speed=0.22, alpha=(0.5, 1.0)):
    """Falling water sheet: foam streaks stretched along local Z that flow downward
    (frame driven, ``speed`` m/frame times obj['flow']), fades at the strip's top and bottom
    (generated Z) and toward its side edges (generated X)."""
    g.blended(shadows=True)
    t = g.node("ShaderNodeValue")
    g.frame_driven(t.outputs[0], "frame")
    k = g.obj_prop("flow", 1.0)
    off = g.mul(g.mul(t.outputs[0], speed), k)
    v = g.coord("object")
    vx, vy, vz = g.sep(v)
    rnd = g.mul(g.obj_random(), 37.0)
    vv = g.comb(g.add(vx, rnd), vy, g.add(vz, off))
    st = g.noise(g.mapping(vv, scale=(5.0, 5.0, 0.18)), 1.0, detail=5.0, roughness=0.62, distortion=0.5)
    st2 = g.noise(g.mapping(vv, scale=(16.0, 16.0, 0.45)), 1.0, detail=3.0)
    st3 = g.noise(g.mapping(vv, scale=(2.0, 2.0, 0.06)), 1.0, detail=2.0)
    foam_m = g.smooth(g.add(g.add(g.mul(st, 0.6), g.mul(st2, 0.25)), g.mul(st3, 0.15)), 0.34, 0.6)
    col = g.mix(g.mix(deep, water, st3), foam, foam_m)
    gen = g.coord("generated")
    gx, _gy, gz = g.sep(gen)
    fade = g.mul(g.smooth(gz, 0.0, 0.07), g.smooth(gz, 1.0, 0.97))
    side = g.math('ABSOLUTE', g.math('SUBTRACT', gx, 0.5))
    fade = g.mul(fade, g.smooth(side, 0.5, 0.36))
    a = g.mul(g.maprange(foam_m, 0.0, 1.0, alpha[0], alpha[1]), fade)
    gk = g.obj_prop("glow", 1.0)
    bsdf = g.principled(base_color=col, roughness=g.mixf(0.06, 0.45, foam_m), alpha=a, ior=1.33,
                        sheen_weight=0.5, sheen_tint="#ffffff",
                        emission_color=col, emission_strength=g.mul(g.mul(foam_m, 0.35), gk),
                        normal=g.bump(st, 0.4, 0.03))
    g.viewport(foam, 0.3)
    g.output(bsdf)


def _mat_foam(g, foam="#f2f6f6", water="#5d8c90", speed=0.02):
    """Churning white foam on the pool surface below a waterfall (radial generated coords,
    frame-driven swirl), transparent toward its rim."""
    g.blended(shadows=False)
    t = g.node("ShaderNodeValue")
    g.frame_driven(t.outputs[0], "frame*%r" % speed)
    gen = g.coord("generated")
    gx, gy, _ = g.sep(gen)
    cx = g.math('SUBTRACT', gx, 0.5)
    cy = g.math('SUBTRACT', gy, 0.5)
    r = g.mul(g.math('SQRT', g.add(g.mul(cx, cx), g.mul(cy, cy))), 2.0)
    v = g.coord("object")
    n = g.noise(v, 1.6, detail=5.0, roughness=0.6, distortion=0.6, dims='4D', w=t.outputs[0])
    n2 = g.noise(v, 5.0, detail=3.0, dims='4D', w=g.mul(t.outputs[0], 2.0))
    m = g.smooth(g.add(g.mul(n, 0.65), g.mul(n2, 0.35)), 0.3, 0.62)
    edge = g.smooth(r, 1.0, 0.45)
    a = g.mul(g.maprange(m, 0, 1, 0.25, 1.0), edge)
    col = g.mix(water, foam, m)
    g.viewport(foam, 0.4)
    g.output(g.principled(base_color=col, roughness=0.5, alpha=a, sheen_weight=0.4,
                          emission_color=col, emission_strength=g.mul(m, 0.25)))


def _mat_flower(g, stamen="#f2cf6a", centre="#a81c3a", petal="#fff4f4", edge="#f2b6c6", transl=0.35):
    """Five-petal flower cards (plum, peach, azalea): UV centre (0.5, 0.5) is the flower centre.
    Alpha cuts five rounded petals with notched tips; colour runs stamens -> dark centre ring ->
    petal -> tinted rim. Dithered transparency, transparent shadows."""
    m = g.mat
    m.surface_render_method = 'DITHERED'
    m.use_transparent_shadow = True
    m.use_backface_culling = False
    uv = g.coord("uv")
    u, v, _ = g.sep(uv)
    du = g.math('SUBTRACT', u, 0.5)
    dv = g.math('SUBTRACT', v, 0.5)
    rr = g.mul(g.math('SQRT', g.add(g.mul(du, du), g.mul(dv, dv))), 2.0)
    phi = g.math('ARCTAN2', dv, du)
    lobe = g.math('ABSOLUTE', g.math('COSINE', g.mul(phi, 2.5)))
    edge_r = g.add(0.42, g.mul(0.56, g.math('POWER', lobe, 0.45)))
    notch = g.mul(0.08, g.smooth(lobe, 0.97, 1.0))
    edge_r = g.math('SUBTRACT', edge_r, notch)
    alpha = g.smooth(g.math('SUBTRACT', rr, edge_r), 0.03, -0.03)
    t = g.math('DIVIDE', rr, edge_r)
    col = g.ramp(t, [(0.0, stamen), (0.14, stamen), (0.24, centre), (0.42, petal), (0.82, petal), (1.0, edge)])
    vein = g.smooth(g.math('ABSOLUTE', g.math('SINE', g.mul(phi, 15.0))), 0.15, 0.0)
    col = g.mix(col, g.hsv(col, 0.5, 1.15, 0.9), g.mul(vein, g.mul(g.smooth(t, 0.3, 0.6), 0.3)))
    col = g.tint_per_object(col, hue=0.01, sat=0.12, val=0.06)
    bsdf = g.principled(base_color=col, roughness=0.5, sheen_weight=0.3, specular_ior_level=0.3, alpha=alpha)
    tr = g.mix_shader(alpha, g.transparent(), g.translucent(g.hsv(col, 0.5, 1.1, 1.2)))
    bsdf = g.mix_shader(transl, bsdf, tr)
    g.viewport(petal, 0.5)
    g.output(bsdf)


def _mat_splash(g, foam="#f6fafa", water="#9cc4c6", speed=0.03):
    """Churning splash lumps: frame-driven white foam with translucent gaps."""
    g.blended(shadows=False)
    t = g.node("ShaderNodeValue")
    g.frame_driven(t.outputs[0], "frame*%r" % speed)
    v = g.coord("object")
    n = g.noise(v, 3.0, detail=5.0, roughness=0.6, distortion=0.8, dims='4D', w=t.outputs[0])
    m = g.smooth(n, 0.32, 0.6)
    fres = g.layer_weight(0.3, "Facing")
    a = g.mul(g.maprange(m, 0, 1, 0.35, 0.95), g.maprange(fres, 0.0, 1.0, 1.0, 0.45))
    col = g.mix(water, foam, m)
    g.viewport(foam, 0.4)
    g.output(g.principled(base_color=col, roughness=0.45, alpha=a, sheen_weight=0.5,
                          emission_color=col, emission_strength=g.mul(m, 0.3), normal=g.bump(n, 0.4, 0.05)))


def _register_materials():
    R = M.register
    R("nature_pine_pad", _mat_pine_pad)
    R("nature_pine_pad_far", _mat_pine_pad, tuft=1.6, transl=0.1, dark="#1d3a2a", mid="#26482f", light="#365c3a",
      sun="#7d8a4a", under="#183224", crevice="#16301f", sun_mix=0.25, under_k=0.3, cells=1.8)
    R("nature_pine_needle", _mat_needle)
    R("nature_bark_pine", _mat_pine_bark)
    R("nature_blossom_peach", _mat_blossom, petal=45.0,
      colours=(("#d65f86", 0.0), ("#ee9ab4", 0.45), ("#f9cfdc", 0.8), ("#fff0f4", 1.0)), centre="#c83a6a")
    R("nature_flower_peach", _mat_flower, stamen="#f4d27a", centre="#c83a6a", petal="#f8b9cb", edge="#f4a6bd",
      transl=0.35)
    R("nature_flower_azalea", _mat_flower, stamen="#f2c86a", centre="#8a1030", petal="#e0587a", edge="#c8385c",
      transl=0.3)
    R("nature_blossom_plum", _mat_blossom,
      colours=(("#e9b9c8", 0.0), ("#f8dde6", 0.45), ("#fff3f5", 0.8), ("#ffffff", 1.0)),
      centre="#a8203f", petal=26.0, transl=0.3)
    R("nature_flower_plum", _mat_flower)
    R("nature_willow", _mat_willow, dark="#30521a", mid="#5f8a26", light="#9cbc45", transl=0.32)
    R("nature_shrub", _mat_pine_pad, dark="#1d3317", mid="#335226", light="#557a35", sun="#8c9a45",
      under="#14220f", tuft=5.0, transl=0.2, sun_mix=0.3)
    R("nature_shrub_leaf", _mat_needle, base="#22391a", mid="#41672a", tip="#76984a", sun="#a3a852",
      under="#16260f", needles=8.0, spread=2.3, width=0.12)
    R("nature_bamboo_leaf", _mat_leaf_card, base="#3f6d2a", tip="#86a948", vein="#2a4a1d")
    R("nature_grass_blade", _mat_leaf_card, base="#5f7d34", tip="#bdb86a", vein="#40562a", transl=0.3)
    R("nature_peach_leaf", _mat_leaf_card, base="#4f7a2e", tip="#86ad4c", vein="#36552a", transl=0.3)
    R("nature_lotus_stem", _mat_leaf_card, base="#4f7a34", tip="#6e9444", vein="#3a5a26", transl=0.1)
    V = M.variant
    V("nature_lotus_pod", "moss", colours=[(0.2, "#a9a83c"), (0.6, "#c8c25a"), (1.0, "#e2d77a")],
      rough=(0.45, 0.6), scale=6.0, bump=0.4, sheen=0.1)
    V("nature_bark_blossom", "bark_dark", c1="#2e2420", c2="#4e3e36", crack="#100b09", scale=1.4)
    # boulders are 1-5 m: rock_cliff's marble_cliff_06 scan at a finer tile (M.ROCK_SMALL_SCAN_SCALE, 0.5)
    V("nature_rock_small", "rock_cliff", strata=0.45, joints=0.25, stain=0.4, moss_amt=0.8,
      scan_scale="ROCK_SMALL_SCAN_SCALE")
    V("nature_taihu", "stone_grey", c1="#7b7f80", c2="#4f5456", speck="#25292b", rough=(0.5, 0.78),
      bump=0.6, scale=2.2, light="#a7aba8", light_amt=0.3)
    V("nature_pond_water", "water_pond", deep="#0f2e2c", shallow="#2a564e")
    V("nature_rim_stone", "stone_grey", c1="#7d7a73", c2="#5b5852", light="#a29e94", light_amt=0.25, moss=0.8)
    V("nature_soil_moss", "soil", colours=[(0.15, "#3a3222"), (0.45, "#4b5a2e"), (0.8, "#5f7236")],
      rough=(0.85, 0.98), scale=1.2, bump=0.35, speckle=None, scan="ground")
    R("nature_cloud_puff", _mat_cloud_puff)
    R("nature_waterfall", _mat_waterfall)
    R("nature_foam", _mat_foam)
    R("nature_splash", _mat_splash)


_register_materials()


# =====================================================================================
# small helpers
# =====================================================================================

def _rot(rotation):
    """Z angle (float) or XYZ Euler -> Euler tuple."""
    if rotation is None:
        return (0.0, 0.0, 0.0)
    if isinstance(rotation, (int, float)):
        return (0.0, 0.0, float(rotation))
    return tuple(rotation)


def _name(name, default):
    """Unique object name: ``name`` if given (e.g. 'mirror.willow'), else 'nature.<default>'."""
    return U.unique_name(name or (PREFIX + "." + default))


def _root(name, collection, location, rotation, parent, scale=(1, 1, 1), size=1.0):
    return U.empty(name, collection, location=location, rotation=_rot(rotation), scale=scale,
                   parent=parent, display_size=size)


def _proto(key, build):
    """Prototype collection 'nature.proto.<key>' under _protos, filled once by build(col).
    Survives look.reset_scene() (re-validated by a tag) and repeated calls."""
    cname = "nature.proto." + key
    col = bpy.data.collections.get(cname)
    if col is not None and col.get(_PROTO_TAG) == key and len(col.all_objects):
        return col
    col = U.proto_collection(cname)
    U.clear_collection(col)
    col[_PROTO_TAG] = key
    build(col)
    return col


def _smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


def _n(p, s=0):
    """Perlin noise [-1, 1] at a Vector (no seed offset cost)."""
    return _mnoise.noise(p if s == 0 else p + Vector((s * 13.17, s * 7.31, s * 3.93)), noise_basis='PERLIN_NEW')


def _fbm(p, octaves=3, s=0, lac=2.03, gain=0.5):
    q = p + Vector((s * 13.17, s * 7.31, s * 3.93))
    amp, tot, nrm, f = 1.0, 0.0, 0.0, 1.0
    for _ in range(octaves):
        tot += amp * _mnoise.noise(q * f, noise_basis='PERLIN_NEW')
        nrm += amp
        amp *= gain
        f *= lac
    return tot / nrm


# ------------------------------------------------------------------ bmesh kernels

def _frames(cs, closed=False):
    """Parallel-transport frames along a polyline: list of (tangent, normal, binormal)."""
    m = len(cs)
    tans = []
    for i in range(m):
        a = cs[i - 1] if i > 0 else cs[i]
        b = cs[i + 1] if i < m - 1 else cs[i]
        t = b - a
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(ref).normalized()
    out = []
    for i in range(m):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                ang = tans[i - 1].angle(tans[i], 0.0)
                nrm = (Matrix.Rotation(ang, 3, ax.normalized()) @ nrm).normalized()
        out.append((tans[i], nrm.copy(), tans[i].cross(nrm).normalized()))
    return out


def _bm_tube(bm, points, radius, sides=8, sps=4, cap_start=False, cap_end=True, bumpy=0.0, seed=0,
             mat=0, flatten=1.0):
    """Tube along a Catmull-Rom spline through ``points`` ((x, y, z) or (x, y, z, radius factor))
    into ``bm``. ``bumpy`` adds gnarly radius noise. Returns the list of rings (lists of BMVerts)."""
    path = U.catmull_rom(points, sps)
    cs = [Vector(p[:3]) for p in path]
    ws = [p[3] for p in path]
    fr = _frames(cs)
    rings = []
    for i, (c, w) in enumerate(zip(cs, ws)):
        _t, nn, bb = fr[i]
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            d = nn * math.cos(a) + bb * math.sin(a) * flatten
            r = radius * w
            if bumpy:
                r *= 1.0 + bumpy * _n((c + d * r) * 1.7, seed)
            ring.append(bm.verts.new(c + d * r))
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((a[k], a[k2], b[k2], b[k]))
            f.material_index = mat
            f.smooth = True
    if cap_end:
        f = bm.faces.new(rings[-1])
        f.material_index = mat
        f.smooth = True
    if cap_start:
        f = bm.faces.new(list(reversed(rings[0])))
        f.material_index = mat
    return rings


_NRM = "nature_nrm"     # BMesh vertex layer: target custom normal (zero = automatic)


def _nrm_layer(bm):
    """The custom-normal vertex layer (create it before making the verts that use it)."""
    return bm.verts.layers.float_vector.get(_NRM) or bm.verts.layers.float_vector.new(_NRM)


def _env_normal(p, env):
    """Normal of an envelope ellipsoid env = (centre, (a, b, c), R3x3) at point p."""
    c, (a, b, cz), R = env
    l = R.transposed() @ (p - c)
    return (R @ Vector((l.x / (a * a), l.y / (b * b), l.z / (cz * cz)))).normalized()


def _bm_blob(bm, center, size, subdiv=2, seed=0, lump=0.18, freq=1.6, flatten=0.55, rot=None, mat=0,
             dome=0.0, env=None, env_w=0.72):
    """Lumpy ellipsoid (icosphere pushed by noise): foliage pads, bushes, blossom clumps, pebbles.
    ``size`` = (rx, ry, rz); ``flatten`` squashes the underside; ``dome`` lifts the top centre.
    ``env`` = (centre, radii, R) of an enclosing soft shape: vertex normals are bent toward that
    shape's normals (weight ``env_w``) so a cluster of blobs shades as one soft cloud."""
    lay = _nrm_layer(bm) if env else None      # before creating verts: a new layer invalidates BMVerts
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    vs = res["verts"]
    rx, ry, rz = size
    off = Vector((seed * 3.71, seed * 1.93, seed * 5.17))
    R = rot if rot is not None else Matrix.Identity(3)
    c = Vector(center)
    for v in vs:
        d = v.co.normalized()
        n = _fbm(d * freq + off, 3)
        n2 = _n(d * freq * 3.1 + off * 1.3)
        k = 1.0 + lump * n + lump * 0.35 * n2
        p = Vector((d.x * rx * k, d.y * ry * k, d.z * rz * k))
        if p.z < 0:
            p.z *= flatten
        elif dome:
            p.z += dome * rz * (1.0 - min(1.0, (d.x * d.x + d.y * d.y)))
        v.co = c + R @ p
        if env:
            own = (R @ Vector((d.x / rx, d.y / ry, d.z / rz))).normalized()
            v[lay] = (_env_normal(v.co, env) * env_w + own * (1.0 - env_w)).normalized()
    for f in {f for v in vs for f in v.link_faces}:
        f.smooth = True
        f.material_index = mat
    return vs


def _mesh_obj(name, bm, collection, materials, parent=None, location=(0, 0, 0), rotation=(0, 0, 0),
              scale=(1, 1, 1)):
    """BMesh -> object, keeping per-face smooth flags and material indices. Target normals stored
    in the ``_NRM`` vertex layer become custom normals (zero vectors stay automatic)."""
    ob = U.mesh_from_bmesh(name, bm, collection, materials=materials, smooth=None, parent=parent,
                           location=location, rotation=_rot(rotation), scale=scale)
    me = ob.data
    at = me.attributes.get(_NRM)
    if at is not None:
        n = len(me.vertices)
        flat = [0.0] * (3 * n)
        at.data.foreach_get("vector", flat)
        me.attributes.remove(at)
        me.normals_split_custom_set_from_vertices([flat[3 * i:3 * i + 3] for i in range(n)])
    return ob


# =====================================================================================
# trees: skeletons
# =====================================================================================

class _Skel:
    """Tree skeleton: branches (point lists with radius factor, base radius, level) and
    foliage pads (centre, radii, yaw, kind)."""

    def __init__(self):
        self.branches = []     # (points[(x,y,z,w)], radius, level)
        self.pads = []         # (centre Vector, (rx, ry, rz), yaw)

    def branch(self, pts, radius, level):
        self.branches.append(([tuple(p) for p in pts], radius, level))

    def pad(self, centre, radii, yaw=0.0):
        self.pads.append((Vector(centre), radii, yaw))


def _trunk_point(pts, t):
    """Point and radius factor at parameter t (0..1) along a sampled polyline of (x,y,z,w)."""
    path = U.catmull_rom(pts, 6)
    n = len(path) - 1
    f = max(0.0, min(1.0, t)) * n
    i = min(int(f), n - 1)
    u = f - i
    a, b = path[i], path[i + 1]
    return Vector([_lerp(a[j], b[j], u) for j in range(3)]), _lerp(a[3], b[3], u)


def _branch_path(start, direction, length, rise, r, segs=5, zig=0.12, droop=0.0, upturn=0.0):
    """Sweeping, slightly zig-zag branch from ``start`` along horizontal ``direction``."""
    d = Vector((direction.x, direction.y, 0.0)).normalized()
    side = _Z.cross(d)
    pts = []
    for j in range(segs + 1):
        s = j / segs
        h = length * s
        z = length * (rise * s - (rise * 0.75 + droop) * s * s + upturn * max(0.0, s - 0.7) ** 2 * 3.0)
        lat = 0.0 if j == 0 else length * zig * r.uniform(-1, 1) * (0.4 + s)
        zz = 0.0 if j == 0 else length * zig * 0.4 * r.uniform(-1, 1)
        p = start + d * h + side * lat + Vector((0, 0, z + zz))
        pts.append((p.x, p.y, p.z, 1.0 - 0.82 * s))
    return pts


_SINK = 0.4     # trunks and culms start this far below z = 0, so sloped ground never shows a gap


def _curve_trunk(r, height, lean, lean_d, bend, wobble, n=9, w_top=0.32, kink=None, sink=_SINK):
    """Trunk centreline: leans out by ``lean`` (radians) toward ``lean_d`` through the middle and
    curves back up near the top (``bend`` 0..1), with a sideways S-wobble. Base flare included.
    ``kink`` = (t, angle): an extra twisting elbow at trunk parameter t (old, wind-bent trees).
    The first point sits ``sink`` m below z = 0 (buried foot)."""
    side = _Z.cross(lean_d)
    phase = r.uniform(0, 6.28)
    p = Vector((0.0, 0.0, 0.0))
    step = height / (n - 1)
    pts = [(0.0, 0.0, 0.0, 1.45)]
    for i in range(1, n):
        t = i / (n - 1)
        th = lean * (0.35 + 1.1 * math.sin(math.pi * min(1.0, t * 0.95))) * (1.0 - bend * max(0.0, t - 0.6) * 2.2)
        d = lean_d * math.sin(th) + _Z * math.cos(th)
        d += side * (math.sin(t * math.pi * 1.7 + phase) * wobble)
        if kink is not None:
            kt, ka = kink
            g = math.exp(-((t - kt) / 0.12) ** 2)
            d += (side * math.cos(phase) + lean_d * 0.5) * (ka * g)
        p = p + d.normalized() * step
        w = (1.0 - (1.0 - w_top) * t) * (1.12 if i == 1 else 1.0)
        pts.append((p.x, p.y, p.z, w))
    # rescale so the top sits exactly at ``height``
    k = height / max(1e-6, pts[-1][2])
    pts = [(x, y, z * k, w) for x, y, z, w in pts]
    if sink:
        pts.insert(0, (0.0, 0.0, -sink, 1.5))
    return pts


def _tier_ts(r, tiers, t_lo, t_hi):
    """Tier heights (trunk parameter t) with uneven spacing (gaps 0.6-1.4x the mean)."""
    if tiers <= 1:
        return [t_lo]
    gaps = [r.uniform(0.6, 1.4) for _ in range(tiers - 1)]
    tot = sum(gaps)
    ts, acc = [t_lo], 0.0
    for gp in gaps:
        acc += gp
        ts.append(t_lo + (t_hi - t_lo) * acc / tot)
    return ts


def _limb_plates(sk, r, pts, L, az, br, rz_k=1.0, arm=False):
    """Foliage plates for one limb: a main plate over the outer limb and 0-2 side twigs, each
    with its own smaller plate, kept apart (0.3-0.8 m gaps) so sky and wood show between them.
    ``arm``: a long welcoming arm carries a row of plates along its outer half instead."""
    path = U.catmull_rom(pts, 4)

    def at(s):
        q = path[min(len(path) - 1, int(s * (len(path) - 1)))]
        return Vector(q[:3]), q[3]
    d = Vector((math.cos(az), math.sin(az), 0.0))
    placed = []                                   # (centre, radius) in XY for gap checks

    def free(c, rad):
        return all((Vector((c.x - q.x, c.y - q.y, 0)).length > rad + qr + 0.3) for q, qr in placed)
    rz = (0.42 + 0.055 * L) * rz_k
    if arm:
        # a cascade: each plate further out sits lower and is 10-20 % smaller
        a_ = min(2.3, 0.18 * L + 0.8)
        for s, kk in ((0.98, 0.7), (0.72, 0.84), (0.46, 1.0)):
            c, _ = at(s)
            aa = a_ * kk * r.uniform(0.95, 1.05)
            if s < 0.9:                           # side twig off the arm, alternating sides
                sgn = 1 if s > 0.6 else -1
                dd = Matrix.Rotation(sgn * r.uniform(0.9, 1.2), 3, 'Z') @ d
                Ls = aa * 1.35
                sp = _branch_path(c, dd, Ls, r.uniform(0.04, 0.14), r, segs=3, zig=0.07)
                sk.branch(sp, br * 0.42, 2)
                c = Vector(sp[-1][:3])
            if free(c, aa * 0.85):
                sk.pad(c + Vector((0, 0, rz * 0.3)), (aa, aa * 0.74, rz * (0.75 + 0.25 * kk)), az + r.uniform(-0.3, 0.3))
                placed.append((c, aa * 0.85))
        return
    c, _ = at(0.8)
    a_ = min(3.2, 0.36 * L + 0.95)
    sk.pad(c + Vector((0, 0, rz * 0.3)), (a_, a_ * 0.74, rz), az + r.uniform(-0.15, 0.15))
    placed.append((c, a_ * 0.85))
    n_sub = 0 if L < 1.8 else (1 if L < 3.2 else 2)
    for j in range(n_sub):
        s = r.uniform(0.3, 0.5)
        q0, qw = at(s)
        sgn = 1 if j % 2 == 0 else -1
        for _try in range(3):
            ang = sgn * r.uniform(0.9, 1.35)
            dd = Matrix.Rotation(ang, 3, 'Z') @ d
            Ls = L * r.uniform(0.38, 0.5)
            sp = _branch_path(q0, dd, Ls, r.uniform(0.1, 0.24), r, segs=4, zig=0.07)
            st = Vector(sp[-1][:3]) - dd * 0.25
            pa = min(2.3, 0.5 * Ls + 0.75)
            dz = r.uniform(-0.35, 0.3)
            if free(st, pa * 0.8):
                sk.branch(sp, br * qw * 0.8, 2)
                sk.pad(st + Vector((0, 0, rz * 0.25 + dz)), (pa, pa * 0.78, rz * 0.9), az + ang)
                placed.append((st, pa * 0.8))
                break
            sgn = -sgn


def _pine_skeleton(style, variant):
    """Huangshan-pine skeleton at canonical height PINE_HEIGHT (10 m): a curving leaning trunk,
    unevenly spaced tiers of long near-horizontal limbs that mostly reach toward the lean side
    (flag form), each carrying thin flat foliage plates with gaps between them, a flat umbrella
    crown. 'ancient' adds one very long welcoming arm low on the trunk. ``sk.lean_az`` is the
    yaw the tree leans and reaches toward (prototype space)."""
    if style == "masson":
        return _masson_skeleton(variant)
    r = U.rng("nature.pine", style, variant)
    H = PINE_HEIGHT
    sk = _Skel()
    lean_az = r.uniform(0, 2 * math.pi)
    lean_d = Vector((math.cos(lean_az), math.sin(lean_az), 0.0))
    if style == "cliff":
        # grows out of a wall facing -Y: nearly horizontal first, then sweeping up; its foot is
        # buried 0.5 m inside the wall (+Y)
        lean_d = Vector((r.uniform(-0.3, 0.3), -1.0, 0.0)).normalized()
        lean_az = math.atan2(lean_d.y, lean_d.x)
        base_r = r.uniform(0.26, 0.32)
        top = H * r.uniform(0.5, 0.6)
        ctrl = _curve_trunk(r, top, r.uniform(1.15, 1.35), lean_d, 0.75, 0.12, n=8, w_top=0.38, sink=0.0)
        ctrl[0] = (ctrl[0][0], ctrl[0][1], ctrl[0][2], 1.25)
        ctrl.insert(0, (0.0, 0.55, -0.12, 1.3))
        tiers, len_k, t_lo = r.randint(2, 3), 0.8, 0.5
    elif style == "ancient":
        base_r = r.uniform(0.5, 0.58)
        top = H * r.uniform(0.64, 0.7)
        ctrl = _curve_trunk(r, top, r.uniform(0.5, 0.62), lean_d, 0.6, 0.35, n=11, w_top=0.36,
                            kink=(0.55, r.uniform(0.45, 0.65)))
        tiers, len_k, t_lo = 4, 1.1, 0.3
    else:
        base_r = r.uniform(0.36, 0.43)
        top = H * r.uniform(0.76, 0.84)
        ctrl = _curve_trunk(r, top, r.uniform(0.26, 0.5), lean_d, r.uniform(0.3, 0.8), 0.22, n=9)
        tiers, len_k, t_lo = r.randint(4, 5), 1.0, r.uniform(0.34, 0.42)
    sk.branch(ctrl, base_r, 0)
    ctrl = [p for p in ctrl if p[2] >= -1e-6]         # sample tiers on the part above ground
    sk.trunk, sk.base_r, sk.lean_az = ctrl, base_r, lean_az
    # buttress roots gripping the rock (level 3: dropped from the far LOD)
    if style != "cliff":
        for k in range(5):
            a = lean_az + k * 2 * math.pi / 5 + r.uniform(-0.35, 0.35)
            d = Vector((math.cos(a), math.sin(a), 0))
            L = base_r * r.uniform(1.6, 2.6)
            pts = [(0.0, 0.0, base_r * 1.6, 1.0)]
            for j in (1, 2, 3):
                s = j / 3
                p = d * (L * (0.25 + 0.75 * s)) + Vector((0, 0, base_r * 1.6 * (1 - s) ** 1.5 - 0.3 * s))
                pts.append((p.x, p.y, p.z, 1.0 - 0.7 * s))
            sk.branch(pts, base_r * 0.55, 3)
    side_lean = lean_d if style != "cliff" else Vector((0, -1, 0))
    lean_az2 = math.atan2(side_lean.y, side_lean.x)
    flip = 1 if r.random() < 0.5 else -1
    arm_az = lean_az2 + r.uniform(-0.3, 0.3)
    arm_done = style == "cliff"
    for k, t in enumerate(_tier_ts(r, tiers, t_lo, 0.86)):
        tf = k / max(1, tiers - 1)
        is_arm = not arm_done and k == 0
        if is_arm or k == tiers - 1 or style == "ancient":
            nb = 1
        else:
            nb = 1 if r.random() < 0.55 else 2
        for b in range(nb):
            if is_arm:
                az = arm_az
            elif style == "ancient":
                az = arm_az + flip * (-1) ** k * r.uniform(0.25, 1.0)      # stays on the arm side
            elif b == 0:
                az = lean_az2 + flip * (-1) ** k * r.uniform(0.1, 1.2)     # within ~70 deg of the lean
            else:
                az = lean_az2 + math.pi + r.uniform(-0.6, 0.6)            # short counter-limb
            d = Vector((math.cos(az), math.sin(az), 0.0))
            if style == "cliff" and d.y > 0.25:
                d = (d + Vector((0, -1.3, 0))).normalized()                # keep off the wall
                az = math.atan2(d.y, d.x)
            toward = max(0.0, d.dot(side_lean))
            p0, w = _trunk_point(ctrl, t + r.uniform(-0.02, 0.02))
            L = H * r.uniform(0.27, 0.36) * (0.72 + 0.7 * toward) * (1.12 - 0.45 * tf) * len_k
            if b == 1:
                L *= 0.62
            rise, droop, upturn = r.uniform(0.16, 0.3), r.uniform(0.02, 0.1), 0.06
            if is_arm:
                L = H * (0.8 if style == "ancient" else 0.5) * r.uniform(0.92, 1.03)
                if style == "ancient":       # rises off the trunk, then reaches down over the void
                    rise, droop, upturn = r.uniform(0.2, 0.26), r.uniform(0.2, 0.26), 0.04
                else:
                    rise, droop, upturn = r.uniform(0.06, 0.12), r.uniform(0.0, 0.04), 0.1
                arm_done = True
            pts = _branch_path(p0, d, L, rise, r, segs=7 if is_arm else 6, zig=0.05, droop=droop, upturn=upturn)
            br = base_r * w * (0.72 if is_arm else 0.6)
            sk.branch(pts, br, 1)
            _limb_plates(sk, r, pts, L, az, br, arm=is_arm and style == "ancient")
    # crown: flat umbrella plate over the leader, with two short limbs widening it
    top_p, _w = _trunk_point(ctrl, 1.0)
    cr = r.uniform(1.7, 2.2) * (1.1 if style == "ancient" else (0.8 if style == "cliff" else 1.0))
    yaw = lean_az2 + r.uniform(-0.4, 0.4)
    crz = 0.3 + 0.05 * cr
    sk.pad(top_p + side_lean * cr * 0.3 + Vector((0, 0, crz * 0.5)), (cr * 1.2, cr * 0.9, crz), yaw)
    for j in range(2):
        a = yaw + (j * 2 - 1) * r.uniform(1.6, 2.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = _branch_path(top_p - Vector((0, 0, 0.45)), d, cr * 1.25, 0.18, r, segs=3, zig=0.05)
        sk.branch(pts, base_r * 0.22, 2)
        q = Vector(pts[-1][:3])
        sk.pad(q + Vector((0, 0, -0.05)), (cr * 0.62, cr * 0.5, crz * 0.85), a)
    if style == "ancient":       # a bare broken snag for character
        p0, w = _trunk_point(ctrl, r.uniform(0.5, 0.62))
        a = lean_az + math.pi + r.uniform(-0.7, 0.7)
        pts = _branch_path(p0, Vector((math.cos(a), math.sin(a), 0)), H * 0.17, 0.5, r, segs=3, zig=0.15)
        sk.branch(pts, base_r * w * 0.38, 1)
    return sk


def _masson_skeleton(variant):
    """Round 48: a Masson pine (Pinus massoniana) spire at PINE_HEIGHT: a nearly straight trunk, 6-8 irregular tiers
    of short limbs all round (shorter toward the top), each carrying one small rounded plate, and a pointed leader
    plate. The crown is 3.5-5 times taller than wide, so it pokes up through a broadleaf canopy as a slim spire
    (critique P4: caps of round blobs alone read as broccoli). No buttress roots (it stands in the canopy)."""
    r = U.rng("nature.pine", "masson", variant)
    H = PINE_HEIGHT
    sk = _Skel()
    lean_az = r.uniform(0, 2 * math.pi)
    lean_d = Vector((math.cos(lean_az), math.sin(lean_az), 0.0))
    base_r = r.uniform(0.2, 0.26)
    top = H * r.uniform(0.9, 0.96)
    ctrl = _curve_trunk(r, top, r.uniform(0.03, 0.1), lean_d, 0.3, 0.06, n=10, w_top=0.22)
    sk.branch(ctrl, base_r, 0)
    ctrl = [p for p in ctrl if p[2] >= -1e-6]
    sk.trunk, sk.base_r, sk.lean_az = ctrl, base_r, lean_az
    tiers = r.randint(6, 8)
    az0 = r.uniform(0, 2 * math.pi)
    golden = math.radians(137.5)
    k = 0
    for i, t in enumerate(_tier_ts(r, tiers, r.uniform(0.3, 0.38), 0.9)):
        tf = i / max(1, tiers - 1)
        for b in range(r.randint(2, 3)):
            az = az0 + golden * k + r.uniform(-0.3, 0.3)
            k += 1
            d = Vector((math.cos(az), math.sin(az), 0.0))
            p0, w = _trunk_point(ctrl, t + r.uniform(-0.015, 0.015))
            L = H * r.uniform(0.09, 0.14) * (1.15 - 0.62 * tf)
            pts = _branch_path(p0, d, L, r.uniform(0.18, 0.32), r, segs=3, zig=0.05, droop=r.uniform(0.0, 0.06))
            sk.branch(pts, base_r * w * 0.45, 1)
            a_ = max(0.45, min(0.95, 0.42 * L + 0.4))
            q = Vector(pts[-1][:3])
            sk.pad(q + Vector((0, 0, 0.12)), (a_, a_ * 0.8, 0.3 + 0.04 * a_), az + r.uniform(-0.3, 0.3))
    top_p, _w = _trunk_point(ctrl, 1.0)
    sk.pad(top_p + Vector((0, 0, 0.1)), (0.55, 0.45, 0.42), lean_az)
    sk.pad(top_p - Vector((0, 0, 0.75)), (0.8, 0.65, 0.34), lean_az + 1.2)
    return sk


def _needle_fan(bm, base, direction, length, mat, env=None, spread=1.5, lift=0.4, droop=0.12, up_w=0.35,
                roll=0.0, segs=4):
    """Pine-needle fan card (material ``nature_pine_needle``): a shallow fan polygon of ``segs``
    triangles rooted at ``base``, opening over ``spread`` radians around ``direction`` (match the
    material's spread), the centre raised by ``lift`` (radians) and the sides drooping, so a fan
    has some volume. The shader cuts ~34 needles out of it. ``roll`` tilts the fan about its
    axis. With ``env`` the card takes the plate envelope's normal bent toward +Z (soft,
    volume-like shading)."""
    d = Vector(direction)
    d = Vector((d.x, d.y, 0.0)).normalized() if Vector((d.x, d.y, 0)).length > 1e-6 else Vector((1, 0, 0))
    side = _Z.cross(d)
    up = _Z.copy()
    if roll:
        Rr = Matrix.Rotation(roll, 3, d)
        side, up = Rr @ side, Rr @ up
    lay = _nrm_layer(bm) if env is not None else None
    uvl = _uv_layer(bm)
    c = bm.verts.new(base)
    rim = []
    for i in range(segs + 1):
        f = i / segs - 0.5
        ang = f * spread * 1.08
        el = lift * (1.0 - 1.3 * abs(f)) - droop * abs(f) * 2.0
        dv = (d * math.cos(ang) + side * math.sin(ang)) * math.cos(el) + up * math.sin(el)
        rim.append((bm.verts.new(base + dv * (length * 1.06)), (0.5 + 0.5 * math.sin(ang) * 1.06,
                                                                 math.cos(ang) * 1.06)))
    if lay is not None:
        for v in [c] + [v for v, _ in rim]:
            v[lay] = (_env_normal(v.co, env) * (1.0 - up_w) + _Z * up_w).normalized()
    for i in range(segs):
        (v1, uv1), (v2, uv2) = rim[i], rim[i + 1]
        fc = bm.faces.new((c, v1, v2))
        fc.material_index = mat
        fc.smooth = True
        for lp, uv in zip(fc.loops, ((0.5, 0.0), uv1, uv2)):
            lp[uvl].uv = uv


def _bm_lens(bm, centre, a, b, rz, R, mat, env, seed, n=12, wav=0.16, under=0.35):
    """Cheap soft cushion (far-LOD foliage plate): a scalloped elliptical rim, a shoulder ring
    and a flat-ish domed top (not a cone), a flatter underside; 4n triangles, envelope normals.
    No alpha cards, so it never vanishes at distance."""
    lay = _nrm_layer(bm)
    o = Vector((seed * 0.37, seed * 0.11, 0.0))
    top = bm.verts.new(centre + Vector((0, 0, rz)))
    bot = bm.verts.new(centre - Vector((0, 0, rz * under)))
    rim, sh = [], []
    for i in range(n):
        t = 2 * math.pi * i / n
        k = 1.0 + wav * _n(Vector((math.cos(t) * 1.7, math.sin(t) * 1.7, 0)) + o) + 0.06 * (i % 2)
        rim.append(bm.verts.new(centre + R @ Vector((math.cos(t) * a * k, math.sin(t) * b * k, rz * 0.12 * (i % 2)))))
        sh.append(bm.verts.new(centre + R @ Vector((math.cos(t) * a * k * 0.68, math.sin(t) * b * k * 0.68, rz * 0.82))))
    for v in [top, bot] + rim + sh:
        v[lay] = _env_normal(v.co, env)
    for i in range(n):
        j = (i + 1) % n
        for f in (bm.faces.new((top, sh[i], sh[j])), bm.faces.new((sh[i], rim[i], rim[j], sh[j])),
                  bm.faces.new((bot, rim[j], rim[i]))):
            f.material_index = mat
            f.smooth = True


def _pad_core_z(rr, rz):
    """Height (relative to the plate centre) of the hero/mid core's top surface at radius ``rr``
    (0 centre .. 1 core rim, relative to the core ellipse), matching the blob in _pad_cluster."""
    q = min(1.0, rr * rr)
    return rz * (0.25 + 0.9 * math.sqrt(max(0.0, 1.0 - q)) * (1.0 + 0.1 * (1.0 - q)))


def _pad_cluster(bm, centre, radii, yaw, seed, lod, mat, needle_mat=2):
    """One cloud-like pine foliage plate (``radii`` = half length, half width, half thickness):
    a dense scalloped dark-green slab (a lumpy core plus rim lobes), flatter underneath, gently
    domed on top. 'hero': brush-stroke needle fans root inside the core and overlap its top and
    rim, so the outline is a ~0.3 m needle fringe (needles have a real size: the fringe width is
    absolute, the core is the plate minus the fringe); 'mid': a coarser core and two longer fan
    rings; 'far': one or two soft scalloped cushions, no alpha cards (they vanish at range).
    Normals follow the plate's envelope (each plate shades as one soft cloud)."""
    a, b, rz = radii
    r = U.rng("pad", seed)
    R = Matrix.Rotation(yaw, 3, 'Z')
    env = (centre + Vector((0, 0, rz * 0.25)), (a * 1.05, b * 1.05, rz * 1.7), R)
    if lod == "far":
        _bm_lens(bm, centre + Vector((0, 0, rz * 0.15)), a, b, rz * 1.4, R, mat, env, seed)
        if a > 1.3:                               # a second, smaller lens on top: cloud-like profile
            ang = r.uniform(0, 6.28)
            p = R @ Vector((math.cos(ang) * a * 0.25, math.sin(ang) * b * 0.25, rz * 0.9))
            _bm_lens(bm, centre + p, a * 0.55, b * 0.55, rz * 0.9, R, mat, env, seed + 7, n=8)
        return
    hero = lod == "hero"
    fringe = 0.3 if hero else 0.45
    ac, bc = max(a * 0.45, a - fringe), max(b * 0.45, b - fringe)
    # core: the plate's dense body (dark green, never black), lumpy so its outline is scalloped
    _bm_blob(bm, centre + Vector((0, 0, rz * 0.25)), (ac, bc, rz * 0.9),
             subdiv=2 if hero else 1, seed=seed, lump=0.1, freq=1.4, flatten=0.3, rot=R, mat=mat, dome=0.1,
             env=env, env_w=0.85)
    nl = 4 if hero else 2
    for i in range(nl):                           # rim lobes break the ellipse into cloud scallops
        ang = 2 * math.pi * (i + r.uniform(0.0, 0.6)) / nl
        p = Vector((math.cos(ang) * ac * 0.6, math.sin(ang) * bc * 0.6, rz * 0.2))
        k = r.uniform(0.42, 0.5)
        _bm_blob(bm, centre + R @ p, (ac * k, bc * k, rz * 0.72), subdiv=1, seed=seed + 5 + i, lump=0.1,
                 flatten=0.3, rot=R, mat=mat, dome=0.1, env=env, env_w=0.9)
    perim = math.pi * (ac + bc)
    # rings of needle fans spreading outward over the core's edge: (z lo, z hi, position on the
    # core ellipse, spacing, lift). Every fan's root (where its needles converge into a dark V) is
    # buried ~0.15 m inside the core, and nothing hangs below the core's rim: drooping underside
    # fans read as palm fronds, and roots left outside the core as a flock of little birds.
    rows = ((0.4, 0.75, 0.72, 0.2, 0.55), (0.15, 0.45, 0.97, 0.15, 0.3), (-0.02, 0.15, 1.0, 0.13, 0.06)) if hero \
        else ((0.15, 0.4, 0.92, 0.42, 0.35), (0.0, 0.15, 1.0, 0.42, 0.05))
    for zlo, zhi, ke, step, lift in rows:
        nf = max(8, int(perim * ke / step))
        for i in range(nf):
            ang = 2 * math.pi * (i + r.uniform(-0.35, 0.35)) / nf
            kk = ke * r.uniform(0.97, 1.02)
            p = Vector((math.cos(ang) * ac * kk, math.sin(ang) * bc * kk, rz * r.uniform(zlo, zhi)))
            out = R @ Vector((math.cos(ang) / ac, math.sin(ang) / bc, 0.0)).normalized()
            L = r.uniform(0.32, 0.46) if hero else r.uniform(0.55, 0.75)
            _needle_fan(bm, centre + R @ p - out * 0.16, out, L, needle_mat, env=env,
                        lift=lift + r.uniform(-0.05, 0.1), roll=r.uniform(-0.2, 0.2), segs=4 if hero else 3,
                        droop=0.12 if lift > 0.2 else 0.0)
    # top: fans lying over the dome, rooted in the core surface, pointing outward and up, so the
    # top reads as a dense needle mass
    n_top = int(math.pi * a * b * (18.0 if hero else 1.5)) + 2
    for i in range(n_top):
        ang = r.uniform(0, 6.28)
        rr = math.sqrt(r.uniform(0.0, 0.8))
        p = Vector((math.cos(ang) * ac * rr, math.sin(ang) * bc * rr, _pad_core_z(rr, rz) - 0.06))
        out = R @ Vector((math.cos(ang), math.sin(ang), 0.0))
        L = r.uniform(0.3, 0.45) if hero else r.uniform(0.5, 0.7)
        _needle_fan(bm, centre + R @ p - out * (L * 0.3), out, L, needle_mat, env=env,
                    lift=r.uniform(0.2, 0.55) + 0.3 * (1.0 - rr), roll=r.uniform(-0.5, 0.5), up_w=0.5,
                    segs=4 if hero else 3)


def _tree_bm(sk, lod, seed, sides=(12, 7, 5), pad_fn=None, bumpy=0.1, pad_mat=1, cap_start=True):
    """Wood (material 0) + foliage (material ``pad_mat``) BMesh from a skeleton. Branch levels:
    0 trunk, 1 limbs, 2 twigs, 3 buttress roots. ``cap_start`` closes the trunk's (buried or
    walled-in) base. The far LOD keeps a thinner trunk and the limbs only (foliage lenses hide
    them; at range the wood must not dominate)."""
    bm = bmesh.new()
    for i, (pts, rad, lvl) in enumerate(sk.branches):
        if lod in ("far", "mid"):
            if lod == "far":
                if lvl >= 2:
                    continue
                sd, sps, rad = (4, 3)[lvl], 1, rad * (0.8 if lvl == 0 else 0.7)
            else:
                if lvl == 2 and rad < 0.06:
                    continue
                sd, sps = (6, 4, 3, 3)[lvl], 2
        else:
            sd = sides[min(lvl, 2)]
            sps = 5 if lvl == 0 else 3
        _bm_tube(bm, pts, rad, sides=sd, sps=sps, cap_end=True, cap_start=cap_start and i == 0,
                 bumpy=bumpy if lvl == 0 else bumpy * 0.6, seed=seed + i, mat=0)
    for j, (c, radii, yaw) in enumerate(sk.pads):
        (pad_fn or _pad_cluster)(bm, c, radii, yaw, U.seed_from(seed, j) % 100000, lod, pad_mat)
    return bm


# =====================================================================================
# trees: public builders
# =====================================================================================

_LODS = ("hero", "mid", "far")


def _check(value, valid, what):
    """Raise ValueError unless ``value`` is one of ``valid``."""
    if value not in valid:
        raise ValueError("%s must be one of %s (got %r)" % (what, ", ".join(repr(v) for v in valid), value))


def _pine_proto(style, variant, lod):
    _check(lod, _LODS, "pine lod")
    key = "pine.%s.v%d.%s" % (style, variant, lod)

    def build(col):
        sk = _pine_skeleton(style, variant)
        bm = _tree_bm(sk, lod, U.seed_from("pine", style, variant), bumpy=0.14)
        foliage = "nature_pine_pad" if lod == "hero" else "nature_pine_pad_far"
        _mesh_obj("nature.proto." + key, bm, col, ["nature_bark_pine", foliage, "nature_pine_needle"])
        col["lean_az"] = sk.lean_az
    return _proto(key, build)


def pine(collection, height=9.0, seed=0, style="huangshan", lod="hero", name=None, location=(0, 0, 0),
         rotation=None, parent=None, spread=None, lean_toward=None):
    """Huangshan pine: twisted leaning trunk, long near-horizontal limbs reaching mostly to the
    lean side (flag form), thin flat cloud-like foliage plates fringed with brush-stroke needle
    fans, gaps between plates, a flat umbrella crown, roots gripping the rock.

    style: 'huangshan' (6 variants), 'cliff' (4 variants: grows out of a wall toward -Y, then up;
    place its origin on a cliff face), 'ancient' (3 variants: thick, leaning, one very long
    welcoming arm low on the trunk with plates along it; the summit's lone pine).
    ``seed`` picks the variant and the yaw. ``rotation`` sets the yaw directly;
    ``lean_toward`` (a world yaw in radians, e.g. the direction of the cliff edge) instead turns
    the tree so its lean and long limbs point that way. lod='hero' ~35-45k tris (camera within
    ~60 m), 'mid' ~4k (60-250 m), 'far' ~0.8k (forests on backdrop pillars).
    ``spread`` scales the crown horizontally (default seeded 0.92-1.08).
    Returns a collection-instance Empty (origin at the trunk base)."""
    nv = PINE_VARIANTS.get(style)
    if nv is None:
        raise ValueError("pine style must be one of %s" % sorted(PINE_VARIANTS))
    _check(lod, _LODS, "pine lod")
    r = U.rng("nature.pine.inst", seed)
    variant = seed % nv
    proto = _pine_proto(style, variant, lod)
    s = height / PINE_HEIGHT
    sp = spread if spread is not None else r.uniform(0.92, 1.08)
    yaw = r.uniform(0, 2 * math.pi)
    if lean_toward is not None:
        rot = (0.0, 0.0, float(lean_toward) - float(proto.get("lean_az", 0.0)))
    else:
        rot = _rot(rotation) if rotation is not None else (0.0, 0.0, yaw)
    ob = U.collection_instance(proto, _name(name, "pine"), collection, location=location, rotation=rot,
                               scale=(s * sp, s * sp, s), parent=parent, display_size=height * 0.2)
    return ob


# ------------------------------------------------------------------ strips, leaves, blades

def _uv_layer(bm):
    return bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")


def _bm_strip(bm, centres, sides, widths, mat, nrm=None, uv_len=None):
    """Ribbon through ``centres`` (Vectors); ``sides`` = unit across-vectors, ``widths`` per row
    (0 makes a pointed row). UV: u across (0..1), v along (0..1, or arc length / ``uv_len`` when
    given, so a pattern keeps its size on long and short strips). ``nrm`` = one normal per row
    (written to the custom-normal layer) or None."""
    lay = _nrm_layer(bm) if nrm is not None else None
    uvl = _uv_layer(bm)
    rows = []
    n = len(centres)
    if uv_len:
        acc, vs = 0.0, [0.0]
        for i in range(1, n):
            acc += (centres[i] - centres[i - 1]).length
            vs.append(acc / uv_len)
    else:
        vs = [i / (n - 1) for i in range(n)]
    for i, (c, sd, w) in enumerate(zip(centres, sides, widths)):
        if w <= 1e-6:
            row = [bm.verts.new(c)]
        else:
            row = [bm.verts.new(c - sd * (w * 0.5)), bm.verts.new(c + sd * (w * 0.5))]
        if lay is not None:
            for v in row:
                v[lay] = nrm[i]
        rows.append(row)
    for i in range(n - 1):
        a, b = rows[i], rows[i + 1]
        v0, v1 = vs[i], vs[i + 1]
        if len(a) == 2 and len(b) == 2:
            f = bm.faces.new((a[0], a[1], b[1], b[0]))
            uvs = ((0, v0), (1, v0), (1, v1), (0, v1))
        elif len(a) == 2:
            f = bm.faces.new((a[0], a[1], b[0]))
            uvs = ((0, v0), (1, v0), (0.5, v1))
        elif len(b) == 2:
            f = bm.faces.new((a[0], b[1], b[0]))
            uvs = ((0.5, v0), (1, v1), (0, v1))
        else:
            continue
        f.material_index = mat
        f.smooth = True
        for lp, uv in zip(f.loops, uvs):
            lp[uvl].uv = uv
    return rows


def _bm_leaf(bm, base, direction, length, width, droop, mat, segs=4, twist_up=None, nrm_up=0.0):
    """Lanceolate leaf / grass blade from ``base`` along ``direction``, bending down by ``droop``
    (radians over its length). Widest at about 35 %, pointed tip. ``nrm_up`` bends its shading
    normals toward +Z (tufts and sprays then shade as soft masses)."""
    d = direction.normalized()
    up = twist_up if twist_up is not None else _Z
    side = d.cross(up)
    if side.length < 1e-6:
        side = Vector((1, 0, 0))
    side.normalize()
    cs, sds, ws, ns = [], [], [], []
    p = Vector(base)
    step = length / segs
    for i in range(segs + 1):
        s = i / segs
        cs.append(p.copy())
        sds.append(side)
        ws.append(0.0 if i == segs else width * (math.sin(math.pi * min(1.0, 0.25 + s * 0.9)) ** 0.8))
        fn = side.cross(d).normalized()
        if fn.z < 0:
            fn = -fn
        ns.append((fn * (1 - nrm_up) + _Z * nrm_up).normalized())
        d = (Matrix.Rotation(-droop / segs, 3, side) @ d).normalized()
        p = p + d * step
    return _bm_strip(bm, cs, sds, ws, mat, nrm=ns if nrm_up else None)


def _bm_flower(bm, centre, normal, radius, mat, cup=0.25, spin=0.0):
    """Five-petal flower card facing ``normal``: a square of half-size ``radius`` whose corners
    lift by ``cup`` x radius around a centre vertex (4 triangles). The flower material cuts the
    petals out with alpha (UV centre = flower centre). ``spin`` turns it in its plane."""
    uvl = _uv_layer(bm)
    n = normal.normalized()
    ref = _Z if abs(n.z) < 0.9 else Vector((1, 0, 0))
    a = n.cross(ref).normalized()
    b = n.cross(a)
    if spin:
        Rs = Matrix.Rotation(spin, 3, n)
        a, b = Rs @ a, Rs @ b
    c = bm.verts.new(centre - n * (radius * cup * 0.3))
    corners = []
    for (x, y) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        corners.append((bm.verts.new(centre + (a * x + b * y) * radius + n * (radius * cup)),
                        (0.5 + 0.5 * x, 0.5 + 0.5 * y)))
    for k in range(4):
        (v1, uv1), (v2, uv2) = corners[k], corners[(k + 1) % 4]
        f = bm.faces.new((c, v1, v2))
        f.material_index = mat
        f.smooth = True
        for lp, uv in zip(f.loops, ((0.5, 0.5), uv1, uv2)):
            lp[uvl].uv = uv


# =====================================================================================
# blossom trees
# =====================================================================================

_BLOSSOM = {
    # canonical height H, trunk (length, radius), kids per level, spread per level (rad),
    # first limb length, length ratios, zig / upward bias per level, blossom blob radius range,
    # 'along' = spacing of clusters along terminal twigs (0: clumps at the tips only)
    "peach": dict(H=6.0, trunk=(1.2, 0.24), kids=((4, 5), (3, 3), (2, 3), (2, 3)), spread=(0.98, 0.72, 0.66),
                  first=2.1, ratio=(0.64, 0.62), zig=(0.12, 0.18, 0.24, 0.28), up=(0.0, 0.03, 0.05, 0.05),
                  blob=(0.06, 0.1), along=0.075, tip=1.3, levels=4, fill=0, twigs=True),
    "plum": dict(H=5.0, trunk=(1.3, 0.22), kids=((3, 3), (3, 3), (2, 3)), spread=(0.8, 0.75, 0.7),
                 first=2.0, ratio=(0.66, 0.62), zig=(0.25, 0.42, 0.48, 0.5), up=(0.05, 0.14, 0.18, 0.2),
                 blob=(0.14, 0.24), along=0.075, tip=1.3, levels=3, fill=0, twigs=False),
}


def _grow(sk, r, start, d, length, radius, level, P, tips):
    """Recursive branch growth into skeleton ``sk``; terminal branches are collected in ``tips``."""
    segs = 4 if level < 2 else 3
    pts, p, dd = [], Vector(start), d.normalized()
    for j in range(segs + 1):
        s = j / segs
        pts.append((p.x, p.y, p.z, 1.0 - 0.55 * s))
        if j < segs:
            dd = (dd + U.jitter(r, P["zig"][min(level, 3)]) + Vector((0, 0, P["up"][min(level, 3)]))).normalized()
            p = p + dd * (length / segs)
    sk.branch(pts, radius, min(level, 2))
    if level >= P["levels"] or (P.get("twigs") and level >= 2):
        tips.append((pts, length))
    if level >= P["levels"]:
        return
    lo, hi = P["kids"][min(level, len(P["kids"]) - 1)]
    nk = r.randint(lo, hi)
    path = U.catmull_rom(pts, 3)
    for k in range(nk):
        s = 1.0 if k == 0 else r.uniform(0.5, 0.92)
        q = path[min(len(path) - 1, int(round(s * (len(path) - 1))))]
        qv, w = Vector(q[:3]), q[3]
        ang = P["spread"][min(level, 2)] * r.uniform(0.7, 1.15)
        ref = _Z if abs(dd.z) < 0.95 else Vector((1, 0, 0))
        ax = Matrix.Rotation(r.uniform(0, 6.28), 3, dd) @ dd.cross(ref).normalized()
        nd = Matrix.Rotation(ang * (0.55 if k == 0 else 1.0), 3, ax) @ dd
        out = Vector((qv.x, qv.y, 0.0))
        if out.length > 1e-4:
            nd = (nd + out.normalized() * 0.35).normalized()
        L = length * P["ratio"][min(level - 1, 1)] * r.uniform(0.82, 1.15)
        _grow(sk, r, qv, nd, L, radius * w * 0.62, level + 1, P, tips)


def _blossom_skeleton(kind, variant):
    P = _BLOSSOM[kind]
    r = U.rng("nature.blossom", kind, variant)
    sk = _Skel()
    tl, tr = P["trunk"]
    lean = Vector((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), 1.0)).normalized()
    tips = []
    # trunk (level 0) with a little bend, then limbs fanned around it
    pts = []
    p = Vector((0, 0, 0))
    for j in range(4):
        pts.append((p.x, p.y, p.z, 1.3 if j == 0 else 1.0 - 0.25 * j / 3))
        p = p + (lean + U.jitter(r, 0.12, (1, 1, 0))).normalized() * (tl / 3)
    sk.branch(pts, tr, 0)
    top = Vector(pts[-1][:3])
    lo, hi = P["kids"][0]
    nk = r.randint(lo, hi)
    ph = r.uniform(0, 6.28)
    for k in range(nk):
        ang = P["spread"][0] * r.uniform(0.75, 1.2)
        az = ph + 2 * math.pi * k / nk + r.uniform(-0.4, 0.4)
        nd = Vector((math.sin(ang) * math.cos(az), math.sin(ang) * math.sin(az), math.cos(ang)))
        _grow(sk, r, top - Vector((0, 0, 0.1)), nd, P["first"] * r.uniform(0.85, 1.15), tr * 0.68, 1, P, tips)
    # blossom clumps
    blobs = []
    b0, b1 = P["blob"]
    for pts_, L in tips:
        path = U.catmull_rom(pts_, 3)
        n = max(2, int(L / P["along"]))
        s0 = 0.35 if P.get("twigs") else 0.2
        for i in range(n):
            q = Vector(path[min(len(path) - 1, int((s0 + (1 - s0) * i / max(1, n - 1)) * (len(path) - 1)))][:3])
            blobs.append((q + U.jitter(r, b1 * 0.35), r.uniform(b0, b1)))
        q = Vector(path[-1][:3])
        blobs.append((q + Vector((0, 0, b1 * 0.3)), r.uniform(b0, b1) * P["tip"]))
    if P["fill"]:
        # cover the crown's outer shell (upper three quarters) so it reads as one blossoming cloud
        lo_v = Vector([min(b[0][i] for b in blobs) for i in range(3)])
        hi_v = Vector([max(b[0][i] for b in blobs) for i in range(3)])
        c = (lo_v + hi_v) * 0.5
        rad = (hi_v - lo_v) * 0.5
        n = P["fill"]
        for i in range(n):
            zz = 1.0 - 1.55 * (i + 0.5) / n               # Fibonacci sphere, z from top to -0.55
            ring = math.sqrt(max(0.0, 1.0 - zz * zz))
            a = i * 2.39996 + r.uniform(-0.2, 0.2)
            q = Vector((c.x + math.cos(a) * ring * rad.x * 0.92, c.y + math.sin(a) * ring * rad.y * 0.92,
                        c.z + zz * rad.z * 0.75 + 0.25))
            blobs.append((q, r.uniform(b0, b1) * 1.25))
    sk.blobs = blobs
    sk.tips = tips
    return sk


def _blossom_proto(kind, variant, lod):
    key = "blossom.%s.v%d.%s" % (kind, variant, lod)

    def build(col):
        sk = _blossom_skeleton(kind, variant)
        bm = bmesh.new()
        for i, (pts, rad, lvl) in enumerate(sk.branches):
            if lod == "far" and lvl >= 2 and rad < 0.03:
                continue
            sides = (10, 6, 4)[lvl] if lod == "hero" else (6, 4, 3)[lvl]
            _bm_tube(bm, pts, rad, sides=sides, sps=3 if lvl == 0 else 2, bumpy=0.12 if lvl == 0 else 0.05,
                     seed=i, mat=0)
        cs = [b[0] for b in sk.blobs]
        lo_v = Vector([min(c[i] for c in cs) for i in range(3)])
        hi_v = Vector([max(c[i] for c in cs) for i in range(3)])
        env = ((lo_v + hi_v) * 0.5, tuple(max(0.6, (hi_v[i] - lo_v[i]) * 0.5 + 0.5) for i in range(3)),
               Matrix.Identity(3))
        r = U.rng("nature.blossom.flowers", kind, variant)
        hero = lod == "hero"
        for j, (c, rad) in enumerate(sk.blobs):
            if kind == "plum" and hero:
                # discrete five-petal flowers in little clusters along the twigs
                for f_ in range(r.randint(2, 4)):
                    nrm = (c - env[0]).normalized() + U.jitter(r, 0.9)
                    _bm_flower(bm, c + U.jitter(r, rad * 0.45), nrm, r.uniform(0.065, 0.095), 1,
                               spin=r.uniform(0, 6.28))
                continue
            if kind == "peach" and hero:
                # a cluster of open five-petal flowers hugging the twig
                for f_ in range(r.randint(6, 9)):
                    d = (c - env[0]).normalized() * 0.7 + U.jitter(r, 1.0)
                    d = d.normalized() if d.length > 1e-6 else _Z
                    _bm_flower(bm, c + d * (rad * r.uniform(0.3, 1.0)), d, r.uniform(0.045, 0.06), 2, cup=0.3,
                               spin=r.uniform(0, 6.28))
                continue
            if not hero and j % 2:          # far: half the clumps, larger, cheap
                continue
            k = 1.0 if hero else 1.45
            _bm_blob(bm, c, (rad * 1.1 * k, rad * k, rad * 0.85 * k), subdiv=2 if hero else 1, seed=j,
                     lump=0.2 if kind == "peach" else 0.25, freq=2.0, flatten=0.7, mat=1, env=env,
                     env_w=0.45 if kind == "peach" else 0.4)
        if kind == "peach" and hero:
            # young leaves at about 15 % of the twig tips
            for pts_, L in sk.tips:
                if r.random() > 0.15 * 2.0:
                    continue
                q = Vector(pts_[-1][:3])
                d0 = (Vector(pts_[-1][:3]) - Vector(pts_[-2][:3])).normalized()
                for k in range(r.randint(2, 4)):
                    d = (d0 + U.jitter(r, 0.7)).normalized()
                    _bm_leaf(bm, q, d, r.uniform(0.09, 0.13), 0.028, r.uniform(0.3, 0.7), 3, segs=2, nrm_up=0.4)
        if kind == "peach":
            mats = ["nature_bark_blossom", "nature_blossom_peach", "nature_flower_peach", "nature_peach_leaf"]
        else:
            mats = ["nature_bark_blossom", "nature_flower_plum" if hero else "nature_blossom_plum"]
        _mesh_obj("nature.proto." + key, bm, col, mats)
    return _proto(key, build)


def blossom_tree(collection, height=6.0, seed=0, kind="peach", lod="hero", name=None, location=(0, 0, 0),
                 rotation=None, parent=None):
    """Blossoming tree. kind='peach': short trunk, spreading limbs and a soft pink cloud of
    blossom clumps. kind='plum': angular zig-zag dark branches studded with small pale clusters
    (ink-painting plum). 4 seeded variants each, instanced. Returns a collection-instance Empty
    (origin at the trunk base)."""
    if kind not in _BLOSSOM:
        raise ValueError("kind must be 'peach' or 'plum'")
    r = U.rng("nature.blossom.inst", seed)
    proto = _blossom_proto(kind, seed % 4, lod)
    s = height / _BLOSSOM[kind]["H"]
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    return U.collection_instance(proto, _name(name, kind + "_tree"), collection, location=location, rotation=rot,
                                 scale=(s, s, s), parent=parent, display_size=height * 0.2)


# =====================================================================================
# willow
# =====================================================================================

def _willow_limb(sk, r, start, d, length, radius, level, rise, arch, segs=5):
    """Arching willow limb: leaves ``start`` along ``d`` (unit), rises by ``rise`` (fraction of
    its length) and arches over and down by ``arch`` toward its tip. Returns its points."""
    h = Vector((d.x, d.y, 0.0))
    h = h.normalized() if h.length > 1e-6 else Vector((1, 0, 0))
    hz = math.sqrt(max(0.0, 1.0 - d.z * d.z))
    pts = []
    for j in range(segs + 1):
        s_ = j / segs
        p = start + h * (length * s_ * hz) + _Z * (length * (d.z * s_ + rise * s_ - (rise + arch) * s_ * s_))
        if j:
            p += U.jitter(r, length * 0.03 * s_)
        pts.append((p.x, p.y, p.z, 1.0 - 0.6 * s_))
    sk.branch(pts, radius, level)
    return pts


def _willow_proto(variant, lod):
    key = "willow.v%d.%s" % (variant, lod)

    def build(col):
        r = U.rng("nature.willow", variant)
        H = 8.0
        hero = lod == "hero"
        sk = _Skel()
        lean_az = r.uniform(0, 6.28)
        lean_d = Vector((math.cos(lean_az), math.sin(lean_az), 0))
        ctrl = _curve_trunk(r, H * r.uniform(0.27, 0.33), r.uniform(0.2, 0.38), lean_d, 0.3, 0.12, n=5, w_top=0.78)
        tr = r.uniform(0.3, 0.36)
        sk.branch(ctrl, tr, 0)
        top = Vector(ctrl[-1][:3])
        hang = []                     # (points, from_s): wood that drips strands
        nl = r.randint(3, 4)
        ph = lean_az + r.uniform(-0.5, 0.5)
        for k in range(nl):
            az = ph + 2 * math.pi * k / nl + r.uniform(-0.35, 0.35)
            el = math.radians(r.uniform(56, 68))
            d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
            L = r.uniform(4.4, 5.4) * (1.1 if math.cos(az - lean_az) > 0.7 else 1.0)
            pts = _willow_limb(sk, r, top - Vector((0, 0, 0.25)), d, L, tr * 0.6, 1, 0.08, 0.2)
            hang.append((pts, 0.5))
            path = U.catmull_rom(pts, 3)
            for m in range(r.randint(4, 6)):                  # whips off the limb's outer half and tip
                sm = 1.0 if m < 2 else r.uniform(0.5, 0.95)
                q = Vector(path[int(sm * (len(path) - 1))][:3])
                a3 = az + r.uniform(-1.3, 1.3)
                d3 = Vector((math.cos(a3), math.sin(a3), r.uniform(0.1, 0.5))).normalized()
                wp = _willow_limb(sk, r, q, d3, r.uniform(1.0, 1.8), tr * 0.09, 2, 0.35, 1.2, segs=3)
                hang.append((wp, 0.0))
            for j in range(r.randint(2, 3)):                  # sub-limbs reaching out, then arching down
                q = Vector(path[int(r.uniform(0.45, 0.85) * (len(path) - 1))][:3])
                a2 = az + (1 if j % 2 else -1) * r.uniform(0.35, 0.9)
                d2 = Vector((math.cos(a2) * 0.85, math.sin(a2) * 0.85, r.uniform(0.15, 0.4))).normalized()
                L2 = L * r.uniform(0.55, 0.75)
                sp = _willow_limb(sk, r, q, d2, L2, tr * 0.24, 2, 0.25, 0.8, segs=4)
                hang.append((sp, 0.15))
                spath = U.catmull_rom(sp, 3)
                for m in range(r.randint(3, 5)):              # whips
                    q2 = Vector(spath[int(r.uniform(0.35, 0.9) * (len(spath) - 1))][:3])
                    a3 = a2 + r.uniform(-1.0, 1.0)
                    d3 = Vector((math.cos(a3), math.sin(a3), r.uniform(0.0, 0.35))).normalized()
                    wp = _willow_limb(sk, r, q2, d3, r.uniform(0.9, 1.7), tr * 0.08, 2, 0.3, 1.1, segs=3)
                    hang.append((wp, 0.0))
        bm = _tree_bm(sk, lod, U.seed_from("willow", variant), sides=(14, 8, 4), bumpy=0.14)
        # curtains of leafy strands hanging from the wood: every sample point (0.25 m apart) drops
        # 6-12 strands from a shared start; 40 % reach 0.3-2.5 m above the ground, the rest are
        # 30-60 % as long. Each first arcs a little up and out, so the crown top is leafy too.
        wind = Vector((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), 0))
        step = 0.25 if hero else 0.55
        per = (5, 10) if hero else (3, 5)
        segs = 7 if hero else 4
        cx, cy = top.x, top.y
        for pts, s0 in hang:
            path = U.catmull_rom(pts, 6)
            acc = 0.0
            for i in range(1, len(path)):
                p_prev, p = Vector(path[i - 1][:3]), Vector(path[i][:3])
                acc += (p - p_prev).length
                if acc < step or i / (len(path) - 1) < s0:
                    continue
                acc = 0.0
                out = Vector((p.x - cx, p.y - cy, 0.0))
                out = out.normalized() if out.length > 1e-3 else Vector((1, 0, 0))
                for k in range(r.randint(*per)):
                    st = p + U.jitter(r, r.uniform(0.04, 0.1), (1, 1, 0.3))
                    drop = st.z - r.uniform(0.3, 2.5)
                    if r.random() > 0.4:
                        drop *= r.uniform(0.3, 0.6)
                    if drop < 0.4:
                        continue
                    yaw = math.atan2(out.y, out.x) + r.uniform(-1.0, 1.0)
                    o = Vector((math.cos(yaw), math.sin(yaw), 0.0))
                    side = _Z.cross(o).normalized()
                    reach = r.uniform(0.15, 0.45)
                    up = r.uniform(0.05, 0.3)
                    cs, ws, ns = [], [], []
                    for j in range(segs + 1):
                        t = j / segs
                        arc = min(1.0, t / 0.18)
                        q = st + out * (reach * (1 - (1 - arc) ** 2)) + wind * (t * t * drop * 0.3)
                        lift = up * math.sin(math.pi * arc) if t < 0.18 else 0.0
                        q.z = st.z + lift - drop * max(0.0, (t - 0.1) / 0.9) ** 1.2
                        q += side * (0.05 * drop * math.sin(t * 3.0 + k)) * t
                        cs.append(q)
                        ws.append(r.uniform(0.075, 0.095) * (1.0 - 0.35 * t) if hero else 0.16 * (1.0 - 0.3 * t))
                        ns.append((o * 0.75 + _Z * 0.45).normalized())
                    _bm_strip(bm, cs, [side] * len(cs), ws, 1, nrm=ns, uv_len=0.075 if hero else 0.13)
        k = H / max(v.co.z for v in bm.verts)          # exactly H tall (the hang lengths stay in place)
        bmesh.ops.scale(bm, vec=(k, k, k), verts=bm.verts[:])
        _mesh_obj("nature.proto." + key, bm, col, ["nature_bark_blossom", "nature_willow"])
    return _proto(key, build)


def willow(collection, height=8.0, seed=0, lod="hero", name=None, location=(0, 0, 0), rotation=None,
           parent=None):
    """Weeping willow: short thick leaning trunk, arching limbs, a soft crown and curtains of
    long hanging leafy strands ending 0.5-2.6 m (at 8 m height) above the ground. 4 seeded
    variants, instanced. Returns a collection-instance Empty."""
    r = U.rng("nature.willow.inst", seed)
    proto = _willow_proto(seed % 4, lod)
    s = height / 8.0
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    return U.collection_instance(proto, _name(name, "willow"), collection, location=location, rotation=rot,
                                 scale=(s, s, s), parent=parent, display_size=height * 0.2)


# =====================================================================================
# bamboo
# =====================================================================================

BAMBOO_HEIGHT = 8.0


def _bamboo_spray(bm, base, direction, r, n, size, mat):
    """A drooping fan of bamboo leaves."""
    d0 = direction.normalized()
    for i in range(n):
        ang = (i - (n - 1) / 2) * r.uniform(0.32, 0.45)
        d = Matrix.Rotation(ang, 3, _Z) @ d0
        d = (d + Vector((0, 0, r.uniform(-0.25, 0.15)))).normalized()
        _bm_leaf(bm, base + d * 0.02, d, size * r.uniform(0.8, 1.15), size * 0.17, r.uniform(0.7, 1.3), mat,
                 segs=3, nrm_up=0.5)


def _culm_proto(variant):
    key = "bamboo.culm.v%d" % variant

    def build(col):
        r = U.rng("nature.bamboo", variant)
        H = BAMBOO_HEIGHT
        bm = bmesh.new()
        lean = r.uniform(0.35, 1.0)
        wob = r.uniform(-0.25, 0.25)
        pts = []
        for i in range(11):
            t = i / 10
            pts.append((lean * t * t, wob * math.sin(t * math.pi), H * t, 1.0 - 0.5 * t))
        _bm_tube(bm, pts, 0.062, sides=8, sps=2, cap_end=True, mat=0)
        path = U.catmull_rom(pts, 2)
        node = 0.42
        z = H * 0.34
        k = 0
        while z < H * 0.97:
            t = z / H
            q = Vector((lean * t * t, wob * math.sin(t * math.pi), z))
            for side in (0, 1) if (r.random() < 0.85 or t > 0.6) else (0,):
                az = k * math.pi + side * r.uniform(1.6, 2.6) + r.uniform(-0.6, 0.6)
                out = Vector((math.cos(az), math.sin(az), 0))
                L = r.uniform(0.6, 1.3) * (1.2 - 0.6 * t)
                bd = (out + Vector((0, 0, r.uniform(0.5, 0.9)))).normalized()
                e = q + bd * L
                _bm_tube(bm, [(q.x, q.y, q.z, 1.0), (e.x, e.y, e.z, 0.6)], 0.011, sides=3, sps=1, cap_end=False,
                         mat=0)
                _bamboo_spray(bm, e, out + Vector((0, 0, 0.15)), r, r.randint(7, 9), 0.5, 1)
                for f_ in (0.35, 0.68):
                    mid = q + bd * (L * f_)
                    _bamboo_spray(bm, mid, Matrix.Rotation(r.uniform(-1.2, 1.2), 3, _Z) @ out, r, r.randint(4, 6),
                                  0.44, 1)
            z += node * (1 if r.random() < 0.8 else 2)
            k += 1
        tip = Vector(path[-1][:3])
        _bamboo_spray(bm, tip, Vector((lean, 0.0, -0.3)) + U.jitter(r, 0.3), r, 8, 0.46, 1)
        _bamboo_spray(bm, tip - Vector((0, 0, 0.3)), Vector((-lean, 0.4, -0.2)), r, 6, 0.44, 1)
        _mesh_obj("nature.proto." + key, bm, col, ["bamboo_stalk", "nature_bamboo_leaf"])
    return _proto(key, build)


def bamboo_clump(collection, count=12, height=8.0, seed=0, radius=None, name=None, location=(0, 0, 0),
                 rotation=None, parent=None):
    """Clump of ``count`` bamboo culms (6 culm prototypes: waxy culm with node rings, side
    branches with drooping leaf fans) leaning outward from the clump centre, plus short young
    culms filling the base. ``radius`` defaults to 0.35 * sqrt(count) m. Returns the clump root Empty."""
    r = U.rng("nature.bamboo.clump", seed)
    root = _root(_name(name, "bamboo"), collection, location, rotation, parent, size=1.0)
    rad = radius if radius is not None else 0.35 * math.sqrt(count)
    total = count + max(2, count // 3)
    for i in range(total):
        young = i >= count
        a = r.uniform(0, 2 * math.pi)
        rr = rad * math.sqrt(r.uniform(0.0, 1.0)) * (1.15 if young else 1.0)
        pos = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.0))
        out = math.atan2(pos.y, pos.x) if rr > 0.05 else r.uniform(0, 6.28)
        h = height * (r.uniform(0.28, 0.5) if young else r.uniform(0.72, 1.05))
        s = h / BAMBOO_HEIGHT
        proto = _culm_proto(r.randint(0, 5))
        U.collection_instance(proto, U.name(root.name, "culm", i), collection, location=pos,
                              rotation=(0.0, 0.0, out + r.uniform(-0.5, 0.5)), scale=(s, s, s), parent=root,
                              display_size=0.3)
    return root


# =====================================================================================
# shrubs and grass
# =====================================================================================

def _shrub_proto(kind, variant, lod="hero"):
    """Shrub prototype: 5-7 (low: 3-4) soft leafy clumps shaded as one mass, a fringe of leaf
    sprays (alpha cards) breaking the outline, and for 'azalea' open flowers scattered over the
    top. The lowest point sits 4 cm below z = 0, so it never floats."""
    key = "shrub.%s.v%d%s" % (kind, variant, "" if lod == "hero" else "." + lod)

    def build(col):
        r = U.rng("nature.shrub", kind, variant)
        hero = lod == "hero"
        bm = bmesh.new()
        env = (Vector((0, 0, 0.35)), (0.95, 0.85, 0.75), Matrix.Identity(3))
        blobs = []
        if kind == "scrub":
            # round 48: mountain scrub for 37-60 deg slopes and rock shelves: taller than wide (about 1.1 m wide,
            # 1.5 m tall at scale 1), a stack of clumps leaning a little, darker in the bake (more self-shadow)
            env = (Vector((0, 0, 0.7)), (0.6, 0.55, 0.85), Matrix.Identity(3))
            lean = Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), 0.0))
            for i in range(r.randint(5, 6) if hero else r.randint(3, 4)):
                h = (i + 0.5) / 5.5
                a = r.uniform(0, 6.28)
                rr = r.uniform(0.0, 0.22) * (1.0 - 0.5 * h)
                c = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.25 + 1.05 * h)) + lean * h
                sz = r.uniform(0.28, 0.4) * (1.15 - 0.45 * h) * (1.0 if hero else 1.2)
                radii = (sz, sz * 0.95, sz * 0.9)
                _bm_blob(bm, c, radii, subdiv=3 if hero else 2, seed=i + variant * 23 + 5, lump=0.16, freq=2.4,
                         flatten=0.6, mat=0, env=env, env_w=0.7)
                blobs.append((c, radii))
        for i in range(0 if kind == "scrub" else (r.randint(5, 7) if hero else r.randint(3, 4))):
            a = r.uniform(0, 6.28)
            rr = math.sqrt(r.uniform(0, 1)) * 0.45
            c = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.32 + (0.45 - rr) * 0.6 + r.uniform(-0.05, 0.1)))
            sz = r.uniform(0.32, 0.48) * (1.0 if hero else 1.2)
            radii = (sz * 1.1, sz, sz * 0.8)
            _bm_blob(bm, c, radii, subdiv=3 if hero else 2, seed=i + variant * 17, lump=0.14, freq=2.2,
                     flatten=0.5, mat=0, env=env, env_w=0.7)
            blobs.append((c, radii))

        def surface(zlo, zhi):
            c, (sx, sy, sz) = blobs[r.randrange(len(blobs))]
            ang = r.uniform(0, 6.28)
            dz = r.uniform(zlo, zhi)
            h = math.sqrt(max(0.0, 1.0 - dz * dz))
            d = Vector((math.cos(ang) * h, math.sin(ang) * h, dz))
            return c + Vector((d.x * sx, d.y * sy, d.z * sz)), d
        for i in range(170 if hero else 50):             # leaf sprays covering the clumps
            p, d = surface(-0.3, 0.95)
            out = Vector((d.x, d.y, 0.0))
            _needle_fan(bm, p - d * 0.04, out if out.length > 1e-3 else Vector((1, 0, 0)), r.uniform(0.11, 0.18), 1,
                        env=env, lift=0.2 + 1.0 * max(0.0, d.z), roll=r.uniform(-0.5, 0.5), up_w=0.4,
                        spread=r.uniform(1.8, 2.6))
        if kind == "azalea":
            for i in range(90 if hero else 30):
                p, d = surface(0.1, 1.0)
                nrm = ((p - env[0]).normalized() + U.jitter(r, 0.5)).normalized()
                _bm_flower(bm, p + nrm * 0.01, nrm, r.uniform(0.045, 0.062), 2, cup=0.35, spin=r.uniform(0, 6.28))
        zmin = min(v.co.z for v in bm.verts)
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0.0, 0.0, -zmin - 0.04))
        _mesh_obj("nature.proto." + key, bm, col, ["nature_shrub", "nature_shrub_leaf", "nature_flower_azalea"])
    return _proto(key, build)


def shrub(collection, size=1.6, seed=0, kind="green", name=None, location=(0, 0, 0), rotation=None, parent=None):
    """Rounded garden shrub (``size`` = width in m; height about 0.65 x width). kind 'green' or
    'azalea' (pink-red flowering). 6 variants each, instanced. Returns the instance Empty."""
    r = U.rng("nature.shrub.inst", seed)
    proto = _shrub_proto(kind, seed % 6)
    s = size / 1.6
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    return U.collection_instance(proto, _name(name, "shrub"), collection, location=location, rotation=rot,
                                 scale=(s, s, s * r.uniform(0.85, 1.1)), parent=parent, display_size=size * 0.3)


def _grass_proto(variant):
    key = "grass.v%d" % variant

    def build(col):
        r = U.rng("nature.grass", variant)
        bm = bmesh.new()
        n = r.randint(28, 36)
        for i in range(n):
            a = r.uniform(0, 6.28)
            rr = r.uniform(0.0, 0.09)
            base = Vector((math.cos(a) * rr, math.sin(a) * rr, -0.02))
            tilt = r.uniform(0.2, 0.85)
            d = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
            _bm_leaf(bm, base, d, r.uniform(0.25, 0.5), r.uniform(0.035, 0.05), r.uniform(0.5, 1.3), 0,
                     segs=3, nrm_up=0.85)
        _mesh_obj("nature.proto." + key, bm, col, ["nature_grass_blade"])
    return _proto(key, build)


def grass_tuft(collection, size=0.5, seed=0, name=None, location=(0, 0, 0), rotation=None, parent=None):
    """Tuft of 28-36 curved grass blades, ``size`` m tall. 4 variants, instanced.
    For many tufts use scatter_on(surface, plant_prototypes("grass"), ...)."""
    r = U.rng("nature.grass.inst", seed)
    proto = _grass_proto(seed % 4)
    s = size / 0.5
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    return U.collection_instance(proto, _name(name, "grass"), collection, location=location, rotation=rot,
                                 scale=(s, s, s), parent=parent, display_size=size)


# =====================================================================================
# rocks
# =====================================================================================

def _boulder_bm(seed, squash=0.7, subdiv=3, facets=(5, 8)):
    """Faceted boulder at unit size (radius ~1), base slightly sunk below z=0."""
    r = U.rng("nature.boulder", seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((r.uniform(-50, 50), r.uniform(-50, 50), r.uniform(-50, 50)))
    sy, sz = r.uniform(0.72, 0.95), squash * r.uniform(0.85, 1.1)
    planes = []
    for i in range(r.randint(*facets)):
        a = r.uniform(0, 6.28)
        el = r.uniform(-0.2, 1.0)
        n = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))).normalized()
        planes.append((n, r.uniform(0.62, 0.82)))
    for v in bm.verts:
        d = v.co.normalized()
        k = 1.0 + 0.2 * _fbm(d * 1.2 + off, 3) + 0.05 * _fbm(d * 4.5 + off, 2)
        p = d * k
        for n, c in planes:
            h = p.dot(n)
            if h > c:
                p -= n * ((h - c) * 0.88)
        p = Vector((p.x, p.y * sy, p.z * sz))
        lim = -0.42 * sz
        if p.z < lim:
            p.z = lim + (p.z - lim) * 0.15
        v.co = p
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + 0.12 * sz
    for f in bm.faces:
        f.smooth = True
    return bm


def _keep_largest_island(bm):
    """Delete every connected piece of ``bm`` except the one with the most vertices. Returns the
    number of pieces found."""
    bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        stack, part = [v0], []
        seen.add(v0.index)
        while stack:
            a = stack.pop()
            part.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        islands.append(part)
    if len(islands) > 1:
        islands.sort(key=len, reverse=True)
        bmesh.ops.delete(bm, geom=[v for part in islands[1:] for v in part], context='VERTS')
    return len(islands)


def _taihu_mesh(name, seed, voxel=0.015):
    """Scholar rock (taihu stone), exactly 1.0 tall with a flat base 4 cm below z = 0: a slender,
    sinuous, slightly top-heavy metaball column flattened front to back, with 2-3 strands that loop
    out and rejoin it (see-through holes by construction, so it can never fall apart), a few
    front-to-back tunnels capped at 0.4 x the local width, and side hollows, cut with a Boolean;
    voxel-remeshed and lightly smoothed (soft water-worn lips), then grooved with vertical ridged
    noise. Only the largest connected piece is kept. Returns a Mesh."""
    r = U.rng("nature.taihu", seed)
    sc = bpy.context.scene
    mb = bpy.data.metaballs.new("natureMB%d" % seed)
    mb.resolution = mb.render_resolution = 0.025
    mb.threshold = 0.6
    mob = bpy.data.objects.new("natureMB%d" % seed, mb)      # no dot: its own metaball family
    sc.collection.objects.link(mob)
    n = r.randint(8, 10)
    ph = r.uniform(0, 6.28)
    body = []

    def path(t):
        return Vector((0.12 * math.sin(t * 4.0 + ph) + 0.03 * math.sin(t * 11.0 + ph * 2.0),
                       0.035 * math.sin(t * 3.0 + ph * 0.7), 0.06 + 0.86 * t))
    for i in range(n):
        t = i / (n - 1)
        c = path(t)
        w = 0.12 * (0.9 + 0.3 * t) * (0.8 + 0.35 * math.sin(t * 7.0 + ph * 1.3)) * r.uniform(0.9, 1.1)
        if i == 0:
            w = max(w, 0.15)                                  # a real foot: contact patch ~0.25 x 0.15
        e = mb.elements.new(type='ELLIPSOID')
        e.co = c
        e.radius = w * 1.45
        e.size_x, e.size_y, e.size_z = 1.0, r.uniform(0.55, 0.65), r.uniform(1.0, 1.2)
        e.stiffness = 2.5
        body.append((c, w))
    # strands looping out of the column and back into it: holes you can see through
    loops = []
    for k in range(r.randint(2, 3)):
        t0 = r.uniform(0.12, 0.55)
        t1 = min(0.95, t0 + r.uniform(0.18, 0.32))
        a, b = path(t0), path(t1)
        side = r.choice((-1.0, 1.0))
        bulge = r.uniform(0.17, 0.26)
        rad = r.uniform(0.042, 0.06)
        m = 9
        for j in range(m + 1):
            u = j / m
            p = a.lerp(b, u) + Vector((side * bulge * math.sin(math.pi * u), r.uniform(-0.015, 0.015),
                                       0.04 * math.sin(math.pi * u)))
            e = mb.elements.new(type='BALL')
            e.co = p
            e.radius = rad * (1.25 - 0.35 * math.sin(math.pi * u))
            e.stiffness = 2.2
        loops.append((a, b, side, bulge))
    # a top-heavy crown lobe
    c, w = body[-2]
    e = mb.elements.new(type='ELLIPSOID')
    e.co = c + Vector((r.uniform(-0.06, 0.06), 0.0, 0.03))
    e.radius = w * r.uniform(1.5, 1.8)
    e.size_x, e.size_y, e.size_z = 1.0, 0.55, 0.75
    e.stiffness = 2.2
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me0 = bpy.data.meshes.new_from_object(mob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(mob, do_unlink=True)
    bpy.data.metaballs.remove(mb)
    # cutters: a few front-to-back tunnels (capped so they never sever the column) and hollows
    cb = bmesh.new()
    for i in range(r.randint(3, 5)):
        c, w = body[r.randint(1, n - 2)]
        if w < 0.12:
            continue
        d = Vector((r.uniform(-0.35, 0.35), 1.0, r.uniform(-0.3, 0.3)))
        cen = c + Vector((r.uniform(-0.3, 0.3) * w, 0.0, r.uniform(-0.03, 0.03)))
        rad = min(0.4 * w, w * r.uniform(0.22, 0.42))
        U.bm_cylinder(cb, radius=rad, depth=1.2, segments=14,
                      matrix=Matrix.Translation(cen) @ U.align_z(d).to_4x4() @
                      Matrix.Diagonal((1.0, r.uniform(1.0, 1.5), 1.0, 1.0)))
    for i in range(r.randint(5, 8)):
        c, w = body[r.randint(1, n - 1)]
        side = Vector((r.uniform(-1, 1), r.choice((-1, 1)) * 0.6, r.uniform(-0.3, 0.3))).normalized()
        bmesh.ops.create_icosphere(cb, subdivisions=2, radius=w * r.uniform(0.28, 0.48),
                                   matrix=Matrix.Translation(c + side * w * 0.85))
    cme = bpy.data.meshes.new("natureTaihuCut%d" % seed)
    cb.to_mesh(cme)
    cb.free()
    cob = bpy.data.objects.new("natureTaihuCut%d" % seed, cme)
    bob = bpy.data.objects.new("natureTaihuBody%d" % seed, me0)
    sc.collection.objects.link(cob)
    sc.collection.objects.link(bob)
    cob.hide_render = True
    bo = bob.modifiers.new("cut", 'BOOLEAN')
    bo.operation, bo.solver, bo.object = 'DIFFERENCE', 'FLOAT', cob   # EXACT returns empty on metaball meshes in 5.2
    rm = bob.modifiers.new("remesh", 'REMESH')
    rm.mode, rm.voxel_size = 'VOXEL', voxel
    sm = bob.modifiers.new("smooth", 'SMOOTH')
    sm.factor, sm.iterations = 0.7, 4
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(bob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(bob, do_unlink=True)
    bpy.data.objects.remove(cob, do_unlink=True)
    bpy.data.meshes.remove(me0)
    bpy.data.meshes.remove(cme)
    me.name = name
    bm = bmesh.new()
    bm.from_mesh(me)
    me["nature_islands"] = _keep_largest_island(bm)          # pieces before cleanup (1 = clean)
    # wrinkles: vertical ridged grooves (water flow) along the normals
    bm.normal_update()
    off = Vector((seed * 1.7, seed * 2.3, seed * 0.9))
    for v in bm.verts:
        p = v.co
        rid = 1.0 - abs(_n(Vector((p.x * 10.0, p.y * 10.0, p.z * 3.0)) + off))
        v.co = p + v.normal * (0.02 * (rid ** 3) - 0.009 + 0.008 * _fbm(p * 18.0 + off, 2))
    # exactly 1.0 tall above a flat contact patch sunk 4 cm: scale so the height above the cut
    # plane (5 cm over the lowest point) is 1.04, flatten everything below it, then sink
    zmin = min(v.co.z for v in bm.verts)
    zmax = max(v.co.z for v in bm.verts)
    k = 1.09 / max(1e-6, zmax - zmin)
    for v in bm.verts:
        v.co = Vector((v.co.x * k, v.co.y * k, (v.co.z - zmin) * k))
        if v.co.z < 0.05:
            v.co.z = 0.05
        v.co.z -= 0.09
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    return me


def _ledge_bm(seed, width, mat_top=0, mat_side=0):
    """Layered sandstone outcrop: 3-5 slabs with their own irregular outlines, crisp edges,
    vertical cracks and uneven tops; upper slabs reach further toward -Y (overhanging lip).
    Width along X; returns (bm, lip, top_z)."""
    r = U.rng("nature.ledge", seed)
    bm = bmesh.new()
    depth = width * 0.62
    nl = r.randint(3, 5)
    H = width * r.uniform(0.45, 0.6)
    ts = [r.uniform(0.6, 1.4) for _ in range(nl)]
    ts = [t * H / sum(ts) for t in ts]
    z0 = -0.15
    seg = 64
    lip = None
    for li, t in enumerate(ts):
        off = Vector((seed * 3.1 + li * 17.3, seed * 1.3 - li * 5.1, li * 2.9))
        grow = 1.0 + 0.04 * li + r.uniform(-0.04, 0.04)
        shift = -0.1 * width * li / max(1, nl - 1)
        rings = ((0.0, 0.95), (0.08, 1.0), (0.9, 1.0), (1.0, 0.965))
        made = []
        prev = None
        for ri, (fz, k) in enumerate(rings):
            z = z0 + t * fz
            ring = []
            for i in range(seg):
                a = 2 * math.pi * i / seg
                ca, sa = math.cos(a), math.sin(a)
                n = _fbm(Vector((ca * 1.3, sa * 1.3, 0)) + off, 4)
                crack = (1.0 - abs(_n(Vector((ca * 7.0, sa * 7.0, z * 0.3)) + off))) ** 8
                rr = (1.0 + 0.22 * n - 0.07 * crack) * k * grow
                x = ca * width * 0.5 * rr
                y = sa * depth * 0.5 * rr + shift
                dz = 0.0
                if ri == len(rings) - 1:
                    dz = 0.05 * width * _fbm(Vector((ca * 2.5, sa * 2.5, 3)) + off, 2)
                ring.append(bm.verts.new((x, y, z + dz)))
            if prev:
                for i in range(seg):
                    f = bm.faces.new((prev[i], prev[(i + 1) % seg], ring[(i + 1) % seg], ring[i]))
                    f.smooth = True
                    f.material_index = mat_side
            prev = ring
            made.append(ring)
        top = made[-1]
        c = bm.verts.new((sum(v.co.x for v in top) / seg, sum(v.co.y for v in top) / seg,
                          sum(v.co.z for v in top) / seg + 0.02 * width))
        for i in range(seg):
            f = bm.faces.new((top[i], top[(i + 1) % seg], c))
            f.smooth = True
            f.material_index = mat_top
        f = bm.faces.new(list(reversed(made[0])))
        f.material_index = mat_side
        if li == nl - 1:
            front = min(top, key=lambda v: v.co.y + 0.6 * abs(v.co.x))
            lip = (front.co.x, front.co.y, front.co.z)
        z0 += t * 0.98
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm, lip, z0


def rock(collection, size=1.5, seed=0, kind="boulder", name=None, location=(0, 0, 0), rotation=None,
         parent=None, material=None):
    """A rock. ``size`` is the overall width (m).

    kind='boulder': faceted, weathered boulder (8 shared variants, linked duplicates), sits on
    z=0, about 0.6 x size tall. Material nature_rock_small (cliff sandstone at boulder scale).
    kind='scholar': taihu scholar stone, ``size`` = HEIGHT, about 0.45 x size wide: sinuous,
    top-heavy, pierced with through-holes, wrinkled (6 variants, metaball-built once).
    kind='ledge': layered sandstone outcrop, size = width, 0.45-0.6 x size tall, upper slabs
    overhang toward -Y. obj['lip'] holds the local (x, y, z) of the front lip of its top slab
    (place a waterfall there). Unique mesh per seed.
    Returns the rock object."""
    r = U.rng("nature.rock.inst", seed)
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    if kind == "boulder":
        v = seed % 8
        me = U.shared_mesh("nature.boulder.v%d" % v, lambda: _boulder_bm(v + 100))
        if not me.materials:
            U.set_materials(me, ["nature_rock_small"])
            U.auto_smooth(me, math.radians(42))
        ob = U.object_from_mesh(_name(name, "boulder"), me, collection, location=location, rotation=rot,
                                scale=(size * 0.5,) * 3, parent=parent)
        if material:
            U.set_object_material(ob, material)
        return ob
    if kind == "scholar":
        v = seed % 6
        key = "nature.taihu.v%d" % v
        me = bpy.data.meshes.get(key)
        if me is None or me.get("sect_shared") != key:
            me = _taihu_mesh(key, v + 7)
            U.auto_smooth(me, math.radians(70))
            me["sect_shared"] = key
            U.set_materials(me, ["nature_taihu"])
        ob = U.object_from_mesh(_name(name, "scholar_rock"), me, collection, location=location, rotation=rot,
                                scale=(size,) * 3, parent=parent)
        if material:
            U.set_object_material(ob, material)
        return ob
    if kind == "ledge":
        bm, lip, top = _ledge_bm(seed, size)
        ob = _mesh_obj(_name(name, "ledge"), bm, collection, [material or "rock_cliff"], parent=parent,
                       location=location, rotation=_rot(rotation) if rotation is not None else (0, 0, 0))
        U.auto_smooth(ob, math.radians(50))
        ob["lip"] = lip
        ob["top_z"] = top
        return ob
    raise ValueError("kind must be 'boulder', 'scholar' or 'ledge'")


# =====================================================================================
# karst pillars and floating rocks
# =====================================================================================

class _PillarShape:
    """Radius field r(theta, z) of a Zhangjiajie sandstone pillar: taper, blocky strata (each
    bed sticks out or steps back, so beds that protrude past the one above form flat shelves),
    rounded bed shoulders and undercuts, a few deep major fissures that split the pillar into
    columns, fine vertical fluting, and slow buttress lobes."""

    def __init__(self, seed, height, top_r, bot_r, top_z, lod, preset=None):
        r = U.rng("nature.pillar", seed)
        self.r = r
        self.lod = lod
        self.h, self.tr, self.br, self.tz = height, top_r, bot_r, top_z
        self.off = Vector((r.uniform(-90, 90), r.uniform(-90, 90), r.uniform(-90, 90)))
        R = max(top_r, bot_r)
        self.R = R
        self.preset = preset
        self.dome_range = (0.12, 0.3)
        if preset is not None:          # round 48 (peak_pillar): every draw below comes after the ones above
            self._init_preset(r, R, preset)
            return
        self.n_major = r.randint(5, 9)
        self.major_a = min(7.0, 0.16 * R)
        self.minor_f = max(1.6, R / 2.6)
        self.minor_a = min(3.0, 0.07 * R) if lod == "hero" else 0.0
        self.lobe_a = 0.12
        self.bulge = r.uniform(-0.05, 0.08)
        self.shoulder = min(0.9, 0.012 * R + 0.12)
        self.layers = []
        z = top_z
        lo, hi = (0.25 * R ** 0.5 + 0.8, 1.1 * R ** 0.5 + 4.0)
        if lod != "hero":
            lo, hi = lo * 1.8, hi * 1.6
        i = 0
        base = 0.0
        while z > top_z - height - 1:
            t = (lo + (hi - lo) * r.random() ** 1.6) * (1.0 if i else 0.7)
            if r.random() < 0.3:             # a hard bed that sticks out: a real ledge
                amp = base + r.uniform(0.035, 0.07) * R
            else:
                base = r.uniform(-1.0, 1.0) * 0.02 * R
                amp = base
            self.layers.append((z, z - t, amp))
            z -= t
            i += 1

    def _init_preset(self, r, R, P):
        """Round 48: a PILLAR_PRESETS shape. Own bed sequence from this pillar's top down (no two pillars share bed
        heights), shelves (beds that stick out past the one above by shelf_amp x R) on shelf_p of the beds, fissures
        and crown per preset; 'mid' and 'far' keep hero bed thickness x bed_k (far x 1.1 more, not 1.6-1.8)."""
        lod = self.lod
        self.n_major = r.randint(*P["fissures"])
        self.major_a = min(P["fissure_cap"], P["fissure_k"] * R)
        self.minor_f = max(1.6, R / 2.6)
        self.minor_a = min(3.0, 0.07 * R) if lod == "hero" else 0.0
        self.lobe_a = P["lobe"]
        self.bulge = r.uniform(*P["bulge"])
        self.shoulder = min(1.2, (0.012 * R + 0.12) * P["shoulder_k"])
        self.dome_range = P["dome"]
        self.layers = []
        lo, hi = (0.25 * R ** 0.5 + 0.8) * P["bed_k"], (1.1 * R ** 0.5 + 4.0) * P["bed_k"]
        if lod == "far":
            lo, hi = lo * 1.1, hi * 1.1
        z = self.tz
        i = 0
        base = 0.0
        smin = P.get("shelf_min", 0.0) if lod == "hero" else 0.0
        mas = P.get("massive")
        while z > self.tz - self.h - 1:
            t = (lo + (hi - lo) * r.random() ** 1.6) * (1.0 if i else 0.7)
            if mas and i > 1 and r.random() < mas[0]:
                t *= r.uniform(mas[1], mas[2])
            if i > 1 and r.random() < P["shelf_p"]:
                amp = base + max(r.uniform(*P["shelf_amp"]) * R, smin)
            else:
                base = r.uniform(-1.0, 1.0) * P["bed_amp"] * R
                amp = base
            self.layers.append((z, z - t, amp))
            z -= t
            i += 1

    def fissure(self, th, z):
        """Strength (0 .. ~1.4) of the major fissure term of radius() at (th, z): 1 in the middle of a cleft."""
        c, s = math.cos(th), math.sin(th)
        o = self.off
        fm = self.n_major / (2 * math.pi) * 1.15
        w1 = 0.25 * _n(Vector((c * 1.5, s * 1.5, z * 0.03)) + o)
        g1 = 1.0 - abs(_n(Vector((c * fm + w1, s * fm - w1, z * 0.6 / self.R)) + o * 0.7))
        fade = 0.55 + 0.45 * _n(Vector((c * 0.7, s * 0.7, z * 0.04)) + o * 1.3)
        return (g1 ** 9) * max(0.0, fade) * 1.4

    def layer_at(self, z):
        for i, (zt, zb, a) in enumerate(self.layers):
            if z >= zb:
                return i, zt, zb, a
        i = len(self.layers) - 1
        return (i,) + self.layers[-1]

    def radius(self, th, z, detail=True):
        c, s = math.cos(th), math.sin(th)
        u = max(0.0, min(1.0, (self.tz - z) / self.h))
        R = _lerp(self.tr, self.br, u) * (1.0 + self.bulge * math.sin(math.pi * u))
        o = self.off
        lob = self.lobe_a * R * _fbm(Vector((c * 1.1, s * 1.1, z * 0.5 / self.R)) + o, 3)
        # major fissures: sharp narrow clefts, wandering a little and fading in and out with height
        fm = self.n_major / (2 * math.pi) * 1.15
        w1 = 0.25 * _n(Vector((c * 1.5, s * 1.5, z * 0.03)) + o)
        g1 = 1.0 - abs(_n(Vector((c * fm + w1, s * fm - w1, z * 0.6 / self.R)) + o * 0.7))
        fade = 0.55 + 0.45 * _n(Vector((c * 0.7, s * 0.7, z * 0.04)) + o * 1.3)
        major = self.major_a * (g1 ** 9) * max(0.0, fade) * 1.4
        # bed profile: protrusion of this bed, rounded shoulder at its top, undercut at its foot
        i, zt, zb, amp = self.layer_at(z)
        a = amp * (0.6 + 0.4 * _n(Vector((c * 1.8, s * 1.8, i * 1.7)) + o))
        dz = zt - z
        t = max(1e-3, zt - zb)
        sh = self.shoulder * (1.0 - _smoothstep(0.0, min(0.5, 0.25 * t), dz)) if i > 0 else 0.0
        uc = 0.3 * self.shoulder * _smoothstep(0.85, 1.0, dz / t)
        rr = R + lob + a - major - sh - uc
        if detail:
            w2 = 0.3 * _n(Vector((c * 3.0, s * 3.0, z * 0.05)) + o * 2.3)
            g2 = 1.0 - abs(_n(Vector((c * self.minor_f + w2, s * self.minor_f - w2, z * 0.035)) + o * 1.9))
            rr -= self.minor_a * (g2 ** 4)
            rr += 0.012 * R * _fbm(Vector((c * 9.0, s * 9.0, z * 0.25)) + o, 2)
        return rr


def _pillar_rings(shape, lod, top_flat):
    """Ring heights (top-down): a flat-shelf pair at every bed boundary, rounded shoulders below
    it, sparser rings inside tall beds and toward the (cloud-hidden) bottom."""
    zs = set()
    tz, h = shape.tz, shape.h
    step = 1.6 if lod == "hero" else (2.8 if lod == "mid" else 6.0)   # (round 48: 'mid', peak_pillar)
    deep = min(h * 0.4, max(25.0, 1.2 * shape.R))       # below this, detail is mostly lost in the cloud sea
    preset = getattr(shape, "preset", None) is not None
    for i, (zt, zb, _a) in enumerate(shape.layers):
        if zt < tz - h:
            break
        fine = lod == "hero" and (tz - zt) < deep
        if i > 0 and preset and not fine and abs(_a - shape.layers[i - 1][2]) < 0.03 * shape.R:
            zs.add(round(zt, 3))        # round 48: a bed boundary with no step needs no shelf pair
        elif i > 0:
            zs.add(round(zt + 0.04, 3))
            if fine:
                for d in (0.04, 0.2, 0.45, 0.9):
                    zs.add(round(zt - d, 3))
            else:
                zs.add(round(zt - 0.06, 3))
                zs.add(round(zt - 1.2, 3))
        z = zt - (1.6 if fine else 3.0)
        while z > zb + 0.3:
            depth = tz - z
            zs.add(round(z, 3))
            z -= step * (1.0 + depth / max(1.0, h) * 1.2) * (1.0 if fine or lod != "hero" else 2.2)
        zs.add(round(zb + 0.3, 3))
    zs = sorted((z for z in zs if tz - h < z < tz - (1.0 if top_flat else 0.3)), reverse=True)
    zs.append(tz - h)
    return zs


def _pillar_bm(shape, lod, top_flat, segs, seed):
    """Pillar side wall + top (flat cap or vegetated dome). Faces with material 1 are soil/grass
    (dome tops). Returns (bm, rim_radii)."""
    r = U.rng("nature.pillar.mesh", seed)
    bm = bmesh.new()
    tz = shape.tz
    ths = [2 * math.pi * i / segs for i in range(segs)]
    detail = lod == "hero"
    rim = [shape.radius(t, tz - 0.9, detail) for t in ths]
    if top_flat:
        rim = [max(shape.tr - 2.5, x) for x in rim]
    rings = []
    # rounded top lip
    if top_flat:
        prof = ((0.0, -0.75), (-0.22, -0.28), (-0.55, -0.05), (-0.95, 0.0))
    else:
        prof = ((0.0, -0.2), (-0.3, 0.0))
    for dz, dr in prof:
        rings.append([bm.verts.new((math.cos(t) * (rr + dr), math.sin(t) * (rr + dr), tz + dz))
                      for t, rr in zip(ths, rim)])
    for z in _pillar_rings(shape, lod, top_flat):
        rings.append([bm.verts.new((math.cos(t) * shape.radius(t, z, detail), math.sin(t) * shape.radius(t, z, detail), z))
                      for t in ths])
    for j in range(len(rings) - 1):
        a, b = rings[j], rings[j + 1]
        for i in range(segs):
            i2 = (i + 1) % segs
            f = bm.faces.new((a[i], b[i], b[i2], a[i2]))
            f.smooth = True
    bm.faces.new(rings[-1])
    if top_flat:
        c = bm.verts.new((0.0, 0.0, tz))
        for i in range(segs):
            f = bm.faces.new((c, rings[0][(i + 1) % segs], rings[0][i]))
            f.smooth = False
    else:
        # vegetated dome: concentric rings rising to an uneven crown
        dome = shape.tr * r.uniform(*getattr(shape, "dome_range", (0.12, 0.3)))
        prev = rings[0]
        o = shape.off
        for k, rho in enumerate((0.82, 0.62, 0.42, 0.22)):
            ring = []
            for t, rr in zip(ths, rim):
                h = dome * math.sqrt(1 - rho * rho) + 0.06 * shape.tr * _n(Vector((math.cos(t) * rho * 2, math.sin(t) * rho * 2, k)) + o)
                ring.append(bm.verts.new((math.cos(t) * rr * rho, math.sin(t) * rr * rho, tz + h)))
            for i in range(segs):
                i2 = (i + 1) % segs
                f = bm.faces.new((prev[i], prev[i2], ring[i2], ring[i]))
                f.smooth = True
                f.material_index = 1
            prev = ring
        c = bm.verts.new((0.0, 0.0, tz + dome * 1.02))
        for i in range(segs):
            f = bm.faces.new((prev[i], prev[(i + 1) % segs], c))
            f.smooth = True
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm, rim


def _veg_attribute(ob, top_z, top_r, top_flat, flip=False, min_nz=0.55):
    """FACE float 'nature_veg': 1 where plants may grow (up-facing ledges, the top rim band of a
    flat top, every up-facing face of a dome top), 0 elsewhere. ``flip``: the mesh is inside out
    (_top_down), so a face's true up-facing normal is its stored normal reversed. ``min_nz``: the
    lowest normal z that counts as up-facing."""
    me = ob.data
    at = me.attributes.get("nature_veg") or me.attributes.new("nature_veg", 'FLOAT', 'FACE')
    sz = -1.0 if flip else 1.0
    vals = []
    for p in me.polygons:
        c, n = p.center, p.normal
        v = 0.0
        if sz * n.z > min_nz:
            if c.z < top_z - 0.5:
                v = 1.0
            elif not top_flat:
                v = 1.0
            elif math.hypot(c.x, c.y) > top_r - 3.2:
                v = 1.0
        vals.append(v)
    at.data.foreach_set("value", vals)


def plant_prototypes(kind="ledge"):
    """Prototype collections for scatter_on: 'ledge' (low-poly shrubs + grass tufts), 'grass',
    'garden' (azalea + green shrubs + grass), 'forest' (far-LOD pines + low shrubs, for pillar
    tops), 'pines' (hero huangshan pines)."""
    if kind == "grass":
        return [_grass_proto(i) for i in range(4)]
    if kind == "ledge":
        return [_shrub_proto("green", i, "low") for i in range(4)] + [_grass_proto(i) for i in range(4)]
    if kind == "garden":
        return [_shrub_proto("green", i) for i in range(3)] + [_shrub_proto("azalea", i) for i in range(2)] + \
            [_grass_proto(i) for i in range(3)]
    if kind == "forest":
        return [_pine_proto("huangshan", i, "far") for i in range(6)] + [_shrub_proto("green", i, "low") for i in range(2)]
    if kind == "pines":
        return [_pine_proto("huangshan", i, "hero") for i in range(6)]
    raise ValueError("unknown plant set %r" % kind)


def rock_pillar(collection, height=120.0, top_radius=20.0, bottom_radius=None, seed=0, top_flat=True, top_z=0.0,
                lod="hero", pines=True, vegetation=True, name=None, location=(0, 0, 0), rotation=None,
                parent=None, segments=None):
    """Zhangjiajie sandstone karst pillar.

    The top is at ``top_z`` (flat cap of radius about ``top_radius`` if ``top_flat``, else a
    vegetated dome rising above top_z) and the pillar reaches down to ``top_z - height``.
    Deep vertical erosion grooves, buttress lobes, horizontal strata with ledges, bedding notches;
    material rock_cliff (moss on ledges). vegetation=True scatters shrubs and grass (GN
    instances) on ledges and on the outer 3 m of a flat top (the area inside stays clear);
    dome tops get a forest of far-LOD pines. pines=True adds 2-4 cliff pines on the upper walls
    (hero LOD only). lod='hero': ~1.25 m wall resolution with full detail in the top
    max(25 m, 1.2 x radius), coarser below (46 m radius x 200 m: ~91k rock + ~47k plant tris,
    1.4 s). lod='far': 4 m resolution, no fluting (~4-8k rock tris, ~19k with its forest).
    For world.py plateaus: rock_pillar(coll, height=200, top_radius=footprint+6, top_z=-0.4, ...)
    on the area anchor. Returns the rock object (vegetation and pines are its children)."""
    t0 = time.perf_counter()
    bottom_radius = top_radius * 0.85 if bottom_radius is None else bottom_radius
    shape = _PillarShape(seed, height, top_radius, bottom_radius, top_z, lod)
    if segments is None:
        segments = int(2 * math.pi * top_radius / (1.25 if lod == "hero" else 4.0))
        segments = max(96, min(320, segments)) if lod == "hero" else max(36, min(80, segments))
    bm, rim = _pillar_bm(shape, lod, top_flat, segments, seed)
    nm = _name(name, "pillar")
    ob = _mesh_obj(nm, bm, collection, ["rock_cliff", "nature_soil_moss"], parent=parent, location=location,
                   rotation=_rot(rotation) if rotation is not None else (0, 0, 0))
    ob["nature_top_z"] = top_z
    ob["nature_top_radius"] = top_radius
    if vegetation:
        _veg_attribute(ob, top_z, top_radius, top_flat)
        if lod == "hero":
            scatter_on(ob, plant_prototypes("ledge"), density=0.07, seed=seed, max_slope=math.radians(40),
                       scale_range=(0.7, 1.6), mask_attribute="nature_veg", align=0.35, collection=collection,
                       name=nm + ".plants")
        else:
            scatter_on(ob, plant_prototypes("ledge")[:4], density=0.004, seed=seed, max_slope=math.radians(40),
                       scale_range=(1.8, 3.5), mask_attribute="nature_veg", align=0.3, collection=collection,
                       name=nm + ".plants")
        if not top_flat:
            ks = max(0.6, min(1.8, top_radius / 12.0))
            scatter_on(ob, plant_prototypes("forest"), density=0.018 if lod == "far" else 0.04, seed=seed + 1,
                       max_slope=math.radians(32), scale_range=(0.55 * ks, 1.0 * ks), mask_attribute="nature_veg",
                       z_range=(top_z - 0.5, top_z + 1e4), align=0.1, collection=collection,
                       name=nm + ".forest")
    if pines and lod == "hero":
        r = U.rng("nature.pillar.pines", seed)
        n = r.randint(2, 4)
        for i in range(n):
            th = r.uniform(0, 2 * math.pi)
            depth = r.uniform(2.5, min(18.0, height * 0.25))
            z = top_z - depth
            rr = shape.radius(th, z) - 0.25
            ph = th + math.pi / 2
            pine(collection, height=r.uniform(5.5, 9.0) * max(0.8, min(1.4, top_radius / 15)), seed=seed * 5 + i,
                 style="cliff", name=nm + ".pine", location=(math.cos(th) * rr, math.sin(th) * rr, z),
                 rotation=(0.0, 0.0, ph), parent=ob)
    ob["nature_build_s"] = round(time.perf_counter() - t0, 3)
    return ob


def floating_rock(collection, size=12.0, seed=0, depth=None, vegetation=True, roots=True, pine_on_top=None,
                  name=None, location=(0, 0, 0), rotation=None, parent=None):
    """Floating island rock: a flat grassy top (z = 0, radius about size/2) over an inverted,
    craggy cone (``depth`` default 0.9-1.2 x size) with vertical grooves, strata steps,
    stalactite spurs and hanging roots. Small ones (size < 8) skip the pine.
    Returns the rock object (plants, roots, pine as children)."""
    r = U.rng("nature.float", seed)
    R = size * 0.5
    D = depth if depth is not None else size * r.uniform(0.9, 1.2)
    segs = max(40, min(160, int(2 * math.pi * R / 0.5)))
    shape = _PillarShape(seed + 991, D, R, R * 0.2, 0.0, "hero")
    shape.major_a = 0.14 * R
    shape.minor_a = 0.035 * R
    shape.shoulder = 0.04 * R + 0.1
    bm = bmesh.new()
    ths = [2 * math.pi * i / segs for i in range(segs)]
    rim = [shape.radius(t, -0.6) for t in ths]
    rings = []
    for dz, dr in ((0.12, -0.6), (0.0, -0.15), (-0.35, 0.05)):
        rings.append([bm.verts.new((math.cos(t) * (rr + dr), math.sin(t) * (rr + dr), dz)) for t, rr in zip(ths, rim)])
    nz = max(8, int(D / 0.7))
    o = shape.off
    for k in range(1, nz + 1):
        u = k / nz
        z = -0.35 - (D - 0.35) * u
        prof = (1.0 - u) ** 0.85
        ring = []
        for t, rr in zip(ths, rim):
            c, s = math.cos(t), math.sin(t)
            crag = 1.0 + 0.35 * u * _fbm(Vector((c * 2.2, s * 2.2, z * 0.15)) + o, 3)
            rad = max(0.05, shape.radius(t, z) * prof * crag) if u < 1.0 else 0.0
            ring.append(bm.verts.new((c * rad + R * 0.08 * u * _n(Vector((u * 3, 0, 0)) + o),
                                      s * rad, z - 0.15 * D * u * max(0.0, _n(Vector((c * 3, s * 3, 1)) + o)))))
        rings.append(ring)
    for j in range(len(rings) - 1):
        a, b = rings[j], rings[j + 1]
        for i in range(segs):
            i2 = (i + 1) % segs
            f = bm.faces.new((a[i], b[i], b[i2], a[i2]))
            f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=rings[-1], dist=0.02)
    # grassy top: slight dome
    prev = rings[0]
    for k, rho in enumerate((0.75, 0.45, 0.18)):
        ring = [bm.verts.new((math.cos(t) * (rr - 0.6) * rho, math.sin(t) * (rr - 0.6) * rho,
                              0.12 + 0.05 * R * math.sqrt(1 - rho * rho) * 0.5)) for t, rr in zip(ths, rim)]
        for i in range(segs):
            f = bm.faces.new((prev[i], prev[(i + 1) % segs], ring[(i + 1) % segs], ring[i]))
            f.smooth = True
            f.material_index = 1
        prev = ring
    c = bm.verts.new((0, 0, 0.12 + 0.025 * R))
    for i in range(segs):
        f = bm.faces.new((prev[i], prev[(i + 1) % segs], c))
        f.smooth = True
        f.material_index = 1
    # stalactite spurs under the cone
    for i in range(r.randint(3, 6)):
        a = r.uniform(0, 6.28)
        u0 = r.uniform(0.25, 0.65)
        z0 = -0.35 - (D - 0.35) * u0
        rad0 = shape.radius(a, z0) * (1 - u0) ** 0.85 * 0.8
        base = Vector((math.cos(a) * rad0, math.sin(a) * rad0, z0))
        L = D * r.uniform(0.25, 0.45)
        pts = [(base.x, base.y, base.z + 0.5, 1.0), (base.x * 0.95, base.y * 0.95, base.z - L * 0.5, 0.6),
               (base.x * 0.9, base.y * 0.9, base.z - L, 0.05)]
        _bm_tube(bm, pts, R * r.uniform(0.1, 0.16), sides=7, sps=3, bumpy=0.25, seed=i, mat=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    nm = _name(name, "floating_rock")
    ob = _mesh_obj(nm, bm, collection, ["rock_cliff", "nature_soil_moss"], parent=parent, location=location,
                   rotation=_rot(rotation) if rotation is not None else (0, 0, 0))
    if roots:
        rb = bmesh.new()
        for i in range(r.randint(5, 9)):
            a = r.uniform(0, 6.28)
            rr = shape.radius(a, -0.6) - 0.3
            L = D * r.uniform(0.3, 0.7)
            pts = [(math.cos(a) * rr, math.sin(a) * rr, -0.3, 1.0)]
            for j in range(1, 5):
                s_ = j / 4
                pts.append((math.cos(a) * (rr + 0.4 * s_) + r.uniform(-0.2, 0.2),
                            math.sin(a) * (rr + 0.4 * s_) + r.uniform(-0.2, 0.2), -0.3 - L * s_, 1.0 - 0.8 * s_))
            _bm_tube(rb, pts, max(0.04, R * 0.012), sides=5, sps=3, seed=i, mat=0)
        _mesh_obj(nm + ".roots", rb, collection, ["nature_bark_blossom"], parent=ob)
    if vegetation:
        # (recalc_face_normals turns some rocks inside out, world._top_faces_up: their top faces down and an
        # up-facing mask found nothing there. The mask reads the faces' true orientation and then carries the
        # slope rule itself; the scatter's own normal test, which sees the reversed normals, is switched off.)
        down = _top_down(ob)
        _veg_attribute(ob, 10.0, R, False, flip=down, min_nz=math.cos(_ROCK_PLANT_SLOPE) if down else 0.55)
        scatter_on(ob, plant_prototypes("ledge"), density=0.25, seed=seed,
                   max_slope=math.pi if down else _ROCK_PLANT_SLOPE, scale_range=(0.6, 1.4),
                   mask_attribute="nature_veg", align=0.0 if down else 0.2, collection=collection,
                   name=nm + ".plants")
    if pine_on_top or (pine_on_top is None and size >= 8):
        pine(collection, height=size * 0.55, seed=seed, style="huangshan", name=nm + ".pine",
             location=(r.uniform(-0.2, 0.2) * R, r.uniform(-0.2, 0.2) * R, 0.1), parent=ob)
    return ob


_ROCK_PLANT_SLOPE = math.radians(30)     # floating_rock's plant scatter: steepest face that gets plants


def _top_down(ob, top_index=1):
    """True when a floating_rock came out inside out: its grassy top (material ``top_index``)
    faces down (the test of world._top_faces_up; the mesh is left as it is)."""
    s = 0.0
    for p in ob.data.polygons:
        if p.material_index == top_index:
            s += p.normal.z * p.area
    return s < 0.0


def fix_inside_out_plants(ob):
    """For a finished floating_rock: when it is inside out (_top_down), rewrite its 'nature_veg'
    mask from the faces' true orientation and set its plant scatter (the child whose
    NatureScatter reads 'nature_veg') the way floating_rock builds it now: normal test off,
    instances upright. Mesh geometry, materials and normals are not touched. Idempotent.
    Returns True when the rock was inside out (sect/patch_density.py)."""
    if ob.type != 'MESH' or ob.data.attributes.get("nature_veg") is None or not _top_down(ob):
        return False
    _veg_attribute(ob, 10.0, 0.0, False, flip=True, min_nz=math.cos(_ROCK_PLANT_SLOPE))
    ob.data.update()
    for ch in ob.children:
        mod = ch.modifiers.get("NatureScatter")
        if mod is None or mod.node_group is None:
            continue
        ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree
               if getattr(s, "in_out", None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry'}
        if _get_mod_input(mod, ids["Mask"]) != "nature_veg":
            continue
        _set_mod_input(mod, ids["Min Normal Z"], math.cos(math.pi))
        _set_mod_input(mod, ids["Align"], 0.0)
    return True


def ground_patch(collection, radius=20.0, seed=0, height=0.5, holes=(), material="grass", edge_drop=0.6,
                 name=None, location=(0, 0, 0), rotation=None, parent=None):
    """Gently undulating grassy ground disc (garden lawns, mounds) at z ~ 0 with a soil rim that
    drops ``edge_drop`` m at its edge. ``holes`` = [(x, y, radius, depth), ...] are dug as smooth
    basins (put a pond() in them). Steep faces get soil. Returns the ground object."""
    r = U.rng("nature.ground", seed)
    bm = bmesh.new()
    o = Vector((r.uniform(-50, 50), r.uniform(-50, 50), 0))
    nr = max(6, int(radius / 0.8))
    segs = max(48, int(2 * math.pi * radius / 0.8))

    def height_at(x, y):
        rr = math.hypot(x, y) / radius
        z = height * _fbm(Vector((x * 0.07, y * 0.07, 0)) + o, 3)
        z -= edge_drop * _smoothstep(0.8, 1.0, rr)
        for hx, hy, hr, hd in holes:
            d = math.hypot(x - hx, y - hy)
            if d < hr * 1.4:
                z = _lerp(z, -hd, _smoothstep(hr * 1.4, hr * 0.75, d))
        return z
    centre = bm.verts.new((0.0, 0.0, height_at(0.0, 0.0)))
    rings = []
    for k in range(1, nr + 1):
        rho = (k / nr) ** 0.9
        ring = []
        for i in range(segs):
            t = 2 * math.pi * (i + 0.5 * (k % 2)) / segs
            x, y = math.cos(t) * radius * rho, math.sin(t) * radius * rho
            if k < nr:
                x += 0.22 * _n(Vector((x * 0.6, y * 0.6, 1.0)) + o)
                y += 0.22 * _n(Vector((x * 0.6, y * 0.6, 2.0)) + o)
            ring.append(bm.verts.new((x, y, height_at(x, y))))
        rings.append(ring)
    for i in range(segs):
        bm.faces.new((centre, rings[0][i], rings[0][(i + 1) % segs]))
    for k in range(nr - 1):
        a, b = rings[k], rings[k + 1]
        for i in range(segs):
            bm.faces.new((a[i], b[i], b[(i + 1) % segs], a[(i + 1) % segs]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = True
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
        f.material_index = 0 if f.normal.z > 0.8 else 1
    ob = _mesh_obj(_name(name, "ground"), bm, collection, [material, "soil"], parent=parent, location=location,
                   rotation=_rot(rotation) if rotation is not None else (0, 0, 0))
    return ob


# =====================================================================================
# scatter (geometry nodes)
# =====================================================================================

_SCATTER_VERSION = 3


_RSCATTER_VERSION = 1      # round 48: the range-only group 'nature.rscatter.<method>' (rscatter_on), its own version so
                           # the shared 'nature.scatter.*' groups (every area garden and grove) are never rebuilt


def _scatter_group(method="RANDOM", factor=False):
    """Shared GN group 'nature.scatter.<method>': distribute points on a surface object's faces
    (slope / height / attribute mask), instance random children of a collection on them.
    ``factor`` (round 48): the range-only group 'nature.rscatter.<method>' instead, with one more input "Factor":
    the name of a FACE / POINT float attribute that multiplies the density per face (groves and clearings,
    gullies and ridges); without that attribute on the surface the group places nothing."""
    name = ("nature.rscatter." if factor else "nature.scatter.") + method.lower()
    tag, version = ("nature_rscatter", _RSCATTER_VERSION) if factor else ("nature_scatter", _SCATTER_VERSION)
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get(tag) == version:
        return ng
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng[tag] = version
    it = ng.interface
    it.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    spec = [("Surface", 'NodeSocketObject', None), ("Prototypes", 'NodeSocketCollection', None),
            ("Density", 'NodeSocketFloat', 0.5), ("Seed", 'NodeSocketInt', 0),
            ("Min Normal Z", 'NodeSocketFloat', 0.8), ("Scale Min", 'NodeSocketFloat', 0.8),
            ("Scale Max", 'NodeSocketFloat', 1.2), ("Align", 'NodeSocketFloat', 0.0),
            ("Mask", 'NodeSocketString', ""), ("Z Min", 'NodeSocketFloat', -1e6),
            ("Z Max", 'NodeSocketFloat', 1e6), ("Min Distance", 'NodeSocketFloat', 0.0)]
    if factor:
        spec.append(("Factor", 'NodeSocketString', ""))
    for nm, st, dv in spec:
        s = it.new_socket(nm, in_out='INPUT', socket_type=st)
        if dv is not None:
            s.default_value = dv
    it.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")

    def node(idn, **props):
        n = N.new(idn)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def out(n, name):
        return n.outputs[name]
    oi = node("GeometryNodeObjectInfo", transform_space='RELATIVE')
    L.new(gi.outputs["Surface"], oi.inputs["Object"])
    # selection: slope, height band, optional mask attribute
    nrm = node("GeometryNodeInputNormal")
    sep_n = node("ShaderNodeSeparateXYZ")
    L.new(nrm.outputs["Normal"], sep_n.inputs[0])
    c_slope = node("FunctionNodeCompare", data_type='FLOAT', operation='GREATER_EQUAL')
    L.new(sep_n.outputs["Z"], c_slope.inputs["A"])
    L.new(gi.outputs["Min Normal Z"], c_slope.inputs["B"])
    pos = node("GeometryNodeInputPosition")
    sep_p = node("ShaderNodeSeparateXYZ")
    L.new(pos.outputs["Position"], sep_p.inputs[0])
    c_zlo = node("FunctionNodeCompare", data_type='FLOAT', operation='GREATER_EQUAL')
    L.new(sep_p.outputs["Z"], c_zlo.inputs["A"])
    L.new(gi.outputs["Z Min"], c_zlo.inputs["B"])
    c_zhi = node("FunctionNodeCompare", data_type='FLOAT', operation='LESS_EQUAL')
    L.new(sep_p.outputs["Z"], c_zhi.inputs["A"])
    L.new(gi.outputs["Z Max"], c_zhi.inputs["B"])
    na = node("GeometryNodeInputNamedAttribute", data_type='FLOAT')
    L.new(gi.outputs["Mask"], na.inputs["Name"])
    c_m = node("FunctionNodeCompare", data_type='FLOAT', operation='GREATER_THAN')
    L.new(na.outputs["Attribute"], c_m.inputs["A"])
    c_m.inputs["B"].default_value = 0.5
    no_attr = node("FunctionNodeBooleanMath", operation='NOT')
    L.new(na.outputs["Exists"], no_attr.inputs[0])
    m_ok = node("FunctionNodeBooleanMath", operation='OR')
    L.new(no_attr.outputs[0], m_ok.inputs[0])
    L.new(c_m.outputs[0], m_ok.inputs[1])
    a1 = node("FunctionNodeBooleanMath", operation='AND')
    L.new(c_slope.outputs[0], a1.inputs[0])
    L.new(c_zlo.outputs[0], a1.inputs[1])
    a2 = node("FunctionNodeBooleanMath", operation='AND')
    L.new(a1.outputs[0], a2.inputs[0])
    L.new(c_zhi.outputs[0], a2.inputs[1])
    a3 = node("FunctionNodeBooleanMath", operation='AND')
    L.new(a2.outputs[0], a3.inputs[0])
    L.new(m_ok.outputs[0], a3.inputs[1])
    dist = node("GeometryNodeDistributePointsOnFaces", distribute_method=method)
    L.new(oi.outputs["Geometry"], dist.inputs["Mesh"])
    L.new(a3.outputs[0], dist.inputs["Selection"])
    fac = None
    if factor:
        fa = node("GeometryNodeInputNamedAttribute", data_type='FLOAT')
        L.new(gi.outputs["Factor"], fa.inputs["Name"])
        fac = fa.outputs["Attribute"]
    if method == "POISSON":
        L.new(gi.outputs["Density"], dist.inputs["Density Max"])
        L.new(gi.outputs["Min Distance"], dist.inputs["Distance Min"])
        if fac is not None:
            L.new(fac, dist.inputs["Density Factor"])
    elif fac is not None:
        dm = node("ShaderNodeMath", operation='MULTIPLY')
        L.new(gi.outputs["Density"], dm.inputs[0])
        L.new(fac, dm.inputs[1])
        L.new(dm.outputs[0], dist.inputs["Density"])
    else:
        L.new(gi.outputs["Density"], dist.inputs["Density"])
    L.new(gi.outputs["Seed"], dist.inputs["Seed"])
    # instances
    ci = node("GeometryNodeCollectionInfo", transform_space='ORIGINAL')
    L.new(gi.outputs["Prototypes"], ci.inputs["Collection"])
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True

    def rnd(dtype, lo, hi, salt):
        n = node("FunctionNodeRandomValue", data_type=dtype)
        sd = node("ShaderNodeMath", operation='ADD')
        L.new(gi.outputs["Seed"], sd.inputs[0])
        sd.inputs[1].default_value = salt
        L.new(sd.outputs[0], n.inputs["Seed"])
        if isinstance(lo, (int, float)):
            n.inputs["Min"].default_value = lo
        else:
            L.new(lo, n.inputs["Min"])
        if isinstance(hi, (int, float)):
            n.inputs["Max"].default_value = hi
        else:
            L.new(hi, n.inputs["Max"])
        return n
    ri = node("FunctionNodeRandomValue", data_type='INT')
    ri.inputs["Min"].default_value = 0
    ri.inputs["Max"].default_value = 99991
    sdi = node("ShaderNodeMath", operation='ADD')
    L.new(gi.outputs["Seed"], sdi.inputs[0])
    sdi.inputs[1].default_value = 17
    L.new(sdi.outputs[0], ri.inputs["Seed"])
    rz = rnd('FLOAT', 0.0, 2 * math.pi, 29)
    cz = node("ShaderNodeCombineXYZ")
    L.new(rz.outputs[0], cz.inputs["Z"])
    e2r = node("FunctionNodeEulerToRotation")
    L.new(cz.outputs[0], e2r.inputs["Euler"])
    al = node("FunctionNodeAlignRotationToVector", axis='Z', pivot_axis='AUTO')
    L.new(e2r.outputs[0], al.inputs["Rotation"])
    L.new(gi.outputs["Align"], al.inputs["Factor"])
    L.new(dist.outputs["Normal"], al.inputs["Vector"])
    rs = rnd('FLOAT', gi.outputs["Scale Min"], gi.outputs["Scale Max"], 41)
    iop = node("GeometryNodeInstanceOnPoints")
    L.new(dist.outputs["Points"], iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    L.new(ri.outputs[0], iop.inputs["Instance Index"])
    L.new(al.outputs[0], iop.inputs["Rotation"])
    L.new(rs.outputs[0], iop.inputs["Scale"])
    L.new(iop.outputs[0], go.inputs[0])
    return ng


def _proto_set(prototypes):
    """Collection under _protos whose children are the given prototype collections / objects."""
    items = []
    for p in prototypes:
        if isinstance(p, str):
            p = bpy.data.collections.get(p) or bpy.data.objects[p]
        items.append(p)
    key = "nature.scatterset.%08x" % U.seed_from(*sorted(i.name for i in items))
    col = U.proto_collection(key)
    for it in items:
        if isinstance(it, bpy.types.Collection):
            if col.children.get(it.name) is None:
                col.children.link(it)
        elif col.objects.get(it.name) is None:
            col.objects.link(it)
    return col


def scatter_on(surface_obj, prototypes, density=0.5, seed=0, max_slope=math.radians(30), scale_range=(0.8, 1.2),
               collection=None, name=None, align=0.0, mask_attribute=None, z_range=None, min_distance=0.0):
    """Geometry-nodes scatter: instances of ``prototypes`` (Objects and/or Collections, built at
    the origin; e.g. plant_prototypes('ledge')) on the faces of ``surface_obj``.

    density: points per m^2 (in the surface's world scale). max_slope: radians from flat
    (faces steeper than this get nothing). scale_range: uniform random instance scale.
    align: 0 = instances stay upright, 1 = they follow the face normal. mask_attribute: a FACE or
    POINT float attribute on the surface; only where it is > 0.5 (ignored if missing).
    z_range: (zmin, zmax) in the surface's local space. min_distance > 0 switches to Poisson-disk
    distribution (density then acts as the maximum). Instances stay instances (cheap, counted
    per instance by the renderer). Returns the scatter object: a child of ``surface_obj`` with an
    identity transform (it follows the surface), modifier 'NatureScatter' (shared node group)."""
    method = "POISSON" if min_distance > 0 else "RANDOM"
    ng = _scatter_group(method)
    coll = collection or (surface_obj.users_collection[0] if surface_obj.users_collection else None)
    me = bpy.data.meshes.new(name or (surface_obj.name + ".scatter"))
    ob = U.object_from_mesh(U.unique_name(name or (surface_obj.name + ".scatter")), me, coll, parent=surface_obj)
    mod = ob.modifiers.new("NatureScatter", 'NODES')
    mod.node_group = ng
    ids = {s.name: s.identifier for s in ng.interface.items_tree
           if getattr(s, "in_out", None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry'}
    vals = {"Surface": surface_obj, "Prototypes": _proto_set(prototypes), "Density": float(density),
            "Seed": int(seed) % 100000, "Min Normal Z": math.cos(max_slope), "Scale Min": float(scale_range[0]),
            "Scale Max": float(scale_range[1]), "Align": float(align), "Mask": mask_attribute or "",
            "Z Min": float(z_range[0]) if z_range else -1e6, "Z Max": float(z_range[1]) if z_range else 1e6,
            "Min Distance": float(min_distance)}
    for k, v in vals.items():
        _set_mod_input(mod, ids[k], v)
    return ob


def rscatter_on(surface_obj, prototypes, density=0.5, seed=0, max_slope=math.radians(30), scale_range=(0.8, 1.2),
                collection=None, name=None, align=0.0, mask_attribute=None, factor_attribute="",
                z_range=None, min_distance=0.0):
    """Round 48: scatter_on through the range-only group 'nature.rscatter.<method>' (_scatter_group(factor=True)):
    the same inputs plus ``factor_attribute``, a FACE float attribute of the surface that multiplies ``density`` per
    face (0 = nothing, 1 = density, 2 = twice). The shared 'nature.scatter.*' groups are not touched, so no area
    garden or grove re-seeds. Returns the scatter object (modifier 'NatureScatter', a child of the surface)."""
    method = "POISSON" if min_distance > 0 else "RANDOM"
    ng = _scatter_group(method, factor=True)
    coll = collection or (surface_obj.users_collection[0] if surface_obj.users_collection else None)
    me = bpy.data.meshes.new(name or (surface_obj.name + ".rscatter"))
    ob = U.object_from_mesh(U.unique_name(name or (surface_obj.name + ".rscatter")), me, coll, parent=surface_obj)
    mod = ob.modifiers.new("NatureScatter", 'NODES')
    mod.node_group = ng
    ids = {s.name: s.identifier for s in ng.interface.items_tree
           if getattr(s, "in_out", None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry'}
    vals = {"Surface": surface_obj, "Prototypes": _proto_set(prototypes), "Density": float(density),
            "Seed": int(seed) % 100000, "Min Normal Z": math.cos(max_slope), "Scale Min": float(scale_range[0]),
            "Scale Max": float(scale_range[1]), "Align": float(align), "Mask": mask_attribute or "",
            "Z Min": float(z_range[0]) if z_range else -1e6, "Z Max": float(z_range[1]) if z_range else 1e6,
            "Min Distance": float(min_distance), "Factor": factor_attribute or ""}
    for k, v in vals.items():
        _set_mod_input(mod, ids[k], v)
    return ob


def _set_mod_input(mod, ident, value):
    """Set a Geometry Nodes modifier input. Blender 5.x: mod.properties.inputs.<Socket_N>.value
    (modifier ID-properties are gone); older versions: mod['Socket_N']."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        getattr(props.inputs, ident).value = value
    else:
        mod[ident] = value


def _get_mod_input(mod, ident):
    """Read a Geometry Nodes modifier input (the counterpart of _set_mod_input)."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        return getattr(props.inputs, ident).value
    return mod.get(ident)


# =====================================================================================
# water: ponds, waterfalls, lotus
# =====================================================================================

def _outline(radius, seed, points=None, n=56):
    if points:
        return [Vector((p[0], p[1], 0.0)) for p in points]
    r = U.rng("nature.outline", seed)
    o = Vector((r.uniform(-40, 40), r.uniform(-40, 40), 0))
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        k = 1.0 + 0.16 * _fbm(Vector((math.cos(t) * 1.2, math.sin(t) * 1.2, 0)) + o, 3)
        out.append(Vector((math.cos(t) * radius * k, math.sin(t) * radius * k * 0.82, 0.0)))
    return out


def pond(collection, radius=6.0, seed=0, points=None, depth=1.2, water_level=-0.18, rim_stones=True, reeds=True,
         name=None, location=(0, 0, 0), rotation=None, parent=None):
    """Garden pond: an organic outline (or ``points`` = [(x, y), ...] counter-clockwise), a still
    water surface at ``water_level`` (material nature_pond_water, slow ripples), a soil basin down
    to -``depth``, a ring of half-sunk rim stones (linked duplicates) and a few reed tufts.
    Ground or paving around it must leave the hole open (ground_patch(holes=...)).
    Returns the root Empty; root['outline'] holds the outline."""
    r = U.rng("nature.pond", seed)
    nm = _name(name, "pond")
    root = _root(nm, collection, location, rotation, parent)
    ol = _outline(radius, seed, points)
    n = len(ol)
    cen = sum(ol, Vector()) / n
    # water surface: centre fan + concentric rings (keeps the flat surface well shaped)
    bm = bmesh.new()
    c = bm.verts.new((cen.x, cen.y, water_level))
    rings = []
    for k in (0.35, 0.7, 1.02):
        rings.append([bm.verts.new((cen.x + (p.x - cen.x) * k, cen.y + (p.y - cen.y) * k, water_level)) for p in ol])
    for i in range(n):
        bm.faces.new((c, rings[0][i], rings[0][(i + 1) % n]))
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            bm.faces.new((a[i], b[i], b[(i + 1) % n], a[(i + 1) % n]))
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    _mesh_obj(nm + ".water", bm, collection, ["nature_pond_water"], parent=root)
    # basin (faces inward/up)
    bm = bmesh.new()
    prof = ((1.12, 0.05), (1.04, -0.1), (0.96, water_level - 0.25), (0.75, -depth * 0.8), (0.35, -depth))
    rings = [[bm.verts.new((cen.x + (p.x - cen.x) * k, cen.y + (p.y - cen.y) * k, z)) for p in ol] for k, z in prof]
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            f = bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            f.smooth = True
    f = bm.faces.new(rings[-1])
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    _mesh_obj(nm + ".basin", bm, collection, ["nature_soil_moss"], parent=root)
    if rim_stones:
        # walk the outline, dropping stones of varied size (spacing follows size), partly sunk
        s0 = max(0.45, min(1.2, radius * 0.14))
        seglen = [(ol[(j + 1) % n] - ol[j]).length for j in range(n)]
        per = sum(seglen)

        def at(d):
            d %= per
            for j in range(n):
                if d <= seglen[j]:
                    return ol[j] + (ol[(j + 1) % n] - ol[j]) * (d / max(1e-6, seglen[j]))
                d -= seglen[j]
            return ol[0]
        d, k = 0.0, 0
        while d < per - s0 * 0.4:
            sz = s0 * (r.uniform(1.1, 1.7) if r.random() < 0.22 else r.uniform(0.55, 1.05))
            p = at(d + sz * 0.4)
            out = (p - cen)
            out.z = 0
            out = out.normalized()
            loc = p + out * r.uniform(0.0, 0.3) * sz
            st = rock(collection, size=sz, seed=seed * 31 + k, kind="boulder", name=nm + ".stone", parent=root,
                      location=(loc.x, loc.y, -0.1 * sz))
            st.scale.z *= r.uniform(0.5, 0.8)
            U.set_object_material(st, "nature_rim_stone")
            if sz > s0 * 1.05 and r.random() < 0.6:
                q = loc + out * sz * 0.55 + U.jitter(r, 0.2 * sz, (1, 1, 0))
                st2 = rock(collection, size=sz * 0.5, seed=seed * 37 + k, kind="boulder", name=nm + ".stone",
                           parent=root, location=(q.x, q.y, -0.03))
                st2.scale.z *= 0.6
                U.set_object_material(st2, "nature_rim_stone")
            d += sz * r.uniform(0.62, 0.8)
            k += 1
    if reeds:
        for k in range(r.randint(3, 6)):
            j = r.randint(0, n - 1)
            p = cen + (ol[j] - cen) * r.uniform(0.82, 0.95)
            for m in range(r.randint(2, 4)):
                q = p + U.jitter(r, 0.3, (1, 1, 0))
                grass_tuft(collection, size=r.uniform(0.7, 1.2), seed=seed + k * 7 + m, name=nm + ".reed",
                           location=(q.x, q.y, water_level - 0.05), parent=root)
    root["outline"] = [tuple(p[:2]) for p in ol]
    root["water_level"] = water_level
    return root


# Waterfall layers (plan B1/B2). Every sheet carries obj['water_layer'] (its role) and obj['exit_speed'] (m/s over
# the lip); the web export (bake_web.py water) writes the role to COLOR_0.b (core 0, side 0.5, veil 1) and the
# speed into the fall time of its second UV set. The side curtain and the front veil hang SHEET_FRONT m in front of
# the core (toward the pour; they were 6 cm apart per sheet, so they read as one ribbon).
SHEET_ROLES = {1: ("core",), 2: ("core", "veil"), 3: ("core", "side", "veil")}
SHEET_FRONT = {"core": 0.0, "side": 0.15, "veil": 0.40}
SHEET_ROWS_MAX = 660           # rows of 0.5 m up to 330 m; taller sheets (the falls into the cloud sea) get longer
                               # rows (the web export thins every sheet to <= 3000 triangles anyway)
PLUNGE_SINK = 0.4              # plunge stones: base this x their size under the foot (boulders are ~0.6 x size tall)
# plunge stones around the landing line (x across, y back toward the cliff, in units of the core's lip width;
# size x that width): two at the ends of the line, two behind the curtain, a small one out to the left. None in
# front of the line (the pool and its koi) or in it (the web draws an animated foam ring there).
PLUNGE_SPOTS = ((-0.74, 0.12, 0.24), (0.78, 0.2, 0.28), (-0.32, 0.26, 0.2), (0.3, 0.3, 0.22), (-0.98, -0.08, 0.15))


def sheet_roles(n):
    """Layer role of each of ``n`` sheets of one fall, in build order: 'core', then the 'side' curtain and the front
    'veil' (SHEET_ROLES; more than three alternate side / veil)."""
    if n in SHEET_ROLES:
        return SHEET_ROLES[n]
    return ("core",) + tuple(("side", "veil")[(k - 1) % 2] for k in range(1, max(1, n)))


def plunge_stones(collection, root, foot, width, name):
    """Half-sunk boulders (nature_rim_stone) around the landing line of a fall, children of its ``root``: PLUNGE_SPOTS
    around ``foot`` (root-local) scaled by ``width`` (the core sheet's width at the lip), bases PLUNGE_SINK x size
    under the foot. Their own generator is keyed by ``name`` (the fall's root name), so sect/patch_water.py places
    the same stones in a finished scene. Each is tagged obj['sect_water'] = 'plunge'. Returns the objects."""
    r = U.rng("nature.plunge", name)
    fx, fy, fz = foot
    out = []
    for k, (ax, ay, s) in enumerate(PLUNGE_SPOTS):
        size = width * s * r.uniform(0.85, 1.15)
        x = fx + width * (ax + r.uniform(-0.05, 0.05))
        y = fy + width * (ay + r.uniform(-0.04, 0.04))
        ob = rock(collection, size=size, seed=r.randrange(1, 100000), kind="boulder", name=name + ".stone",
                  location=(x, y, fz - PLUNGE_SINK * size), parent=root, material="nature_rim_stone")
        ob["sect_water"] = "plunge"
        out.append(ob)
    return out


def _sheet_bm(width, height, seed, exit_speed, spread=0.25, behind=0.7):
    """One falling water sheet: slides over the lip (from +Y ``behind`` m back), leaves it with
    ``exit_speed`` m/s toward -Y and falls on a ballistic arc to z = -height. Rows every 0.5 m (at most
    SHEET_ROWS_MAX, then longer ones); each row has one z."""
    r = U.rng("nature.sheet", seed)
    bm = bmesh.new()
    cols = max(4, int(width / 0.35))
    rows = max(14, min(int(height / 0.5), SHEET_ROWS_MAX))
    o = Vector((r.uniform(-50, 50), r.uniform(-50, 50), 0))
    grid = []
    zs = [(behind, 0.04), (behind * 0.35, 0.03)]
    for j in range(rows + 1):
        t = j / rows
        d = height * (t ** 1.0)
        y = -exit_speed * math.sqrt(2.0 * d / 9.81) - 0.05
        zs.append((y, -d))
    for j, (y, z) in enumerate(zs):
        t = max(0.0, -z / height)
        row = []
        for i in range(cols + 1):
            u = i / cols - 0.5
            x = u * width * (1.0 + spread * t)
            x += 0.18 * width * t * _n(Vector((u * 2.0, t * 3.0, 0)) + o)
            yy = y + 0.25 * t * _n(Vector((u * 3.0, t * 4.0, 5.0)) + o)
            row.append(bm.verts.new((x, yy, z)))
        grid.append(row)
    for j in range(len(grid) - 1):
        for i in range(cols):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.smooth = True
    return bm


def waterfall(collection, height=20.0, width=4.0, seed=0, sheets=3, mist=True, foam=True, name=None,
              location=(0, 0, 0), rotation=None, parent=None, exit_speed=None, spread=None):
    """Waterfall pouring off a lip: origin = centre of the lip, water leaves toward -Y and falls
    ``height`` m. Layered transparent sheets (nature_waterfall: foam streaks flowing down, frame
    driven, a different speed per sheet via obj['flow']; roles sheet_roles(sheets) in obj['water_layer'],
    the side curtain / front veil SHEET_FRONT m in front of the core; obj['exit_speed'] in m/s) and a
    splash-mist volume (mist_volume) at the foot. ``foam``: plunge stones around the landing line
    (plunge_stones). The baked foam disc and splash blobs are gone: the web draws an animated foam ring
    and spray there, and a baked white lump froze under them. root['foot'] = local (x, y, z) where the
    water lands (the farthest sheet's arc, front offsets left out, so a pool placed from it stays put).
    Returns the root Empty."""
    r = U.rng("nature.waterfall", seed)
    nm = _name(name, "waterfall")
    root = _root(nm, collection, location, rotation, parent)
    roles = sheet_roles(sheets)
    foot_y = 0.0
    w0 = width
    for s in range(sheets):
        w = width * (1.0 - 0.16 * s) * r.uniform(0.95, 1.05)
        # (round 48: exit_speed / spread for falls that arc and widen: 2.5-4 m/s, 40-60 %; None = as before)
        v = (exit_speed * r.uniform(0.9, 1.1) if exit_speed else r.uniform(1.1, 1.6)) * (1.0 + 0.12 * s)
        bm = _sheet_bm(w, height, seed * 13 + s, v, spread=(0.2 if spread is None else spread) + 0.08 * s)
        ob = _mesh_obj(nm + ".sheet", bm, collection, ["nature_waterfall"], parent=root,
                       location=(r.uniform(-0.1, 0.1) * width, -SHEET_FRONT[roles[s]], 0.01 * s))
        ob["flow"] = (1.0, 1.22, 0.86, 1.1)[s % 4]
        ob["water_layer"] = roles[s]
        ob["exit_speed"] = v
        U.set_visibility(ob, shadow=False)
        foot_y = min(foot_y, -v * math.sqrt(2.0 * height / 9.81))
        if s == 0:
            w0 = w
    foot = Vector((0.0, foot_y, -height))
    if foam:
        plunge_stones(collection, root, tuple(foot), w0, nm)
    if mist:
        me = U.shared_mesh("nature.unit_cube", lambda: _unit_cube())
        sx, sy, sz = width * 2.8, width * 2.4 + 2.0, max(3.0, min(14.0, height * 0.35))
        ob = U.object_from_mesh(nm + ".mist", me, collection, location=(foot.x, foot.y + 0.3, foot.z + sz * 0.38),
                                scale=(sx, sy, sz), parent=root)
        if not me.materials:
            U.set_materials(me, ["mist_volume"])
        ob["density"] = 2.2
        U.set_visibility(ob, shadow=False)
    root["foot"] = tuple(foot)
    return root


def _unit_cube():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    return bm


def _pad_mesh(variant, cup=0.0):
    """Unit lotus leaf (radius 1) centred on its origin: wavy upturned rim, optional cup."""
    key = "nature.lotus.pad.v%d.c%d" % (variant, int(cup * 10))

    def build():
        r = U.rng("nature.lotus.pad", variant)
        bm = bmesh.new()
        segs, nr = 28, 4
        o = Vector((r.uniform(-30, 30), r.uniform(-30, 30), 0))
        c = bm.verts.new((0, 0, -0.04 if cup else 0.02))
        rings = []
        for k in range(1, nr + 1):
            rho = k / nr
            ring = []
            for i in range(segs):
                t = 2 * math.pi * i / segs
                wav = 0.06 * rho * rho * math.sin(t * r.randint(5, 7) + r.uniform(0, 6))
                rr = rho * (1.0 + 0.04 * _n(Vector((math.cos(t) * 2, math.sin(t) * 2, 0)) + o))
                z = cup * rho * rho + wav + (0.05 * rho ** 4 if not cup else 0.0)
                ring.append(bm.verts.new((math.cos(t) * rr, math.sin(t) * rr, z)))
            rings.append(ring)
        for i in range(segs):
            bm.faces.new((c, rings[0][i], rings[0][(i + 1) % segs]))
        for a, b in zip(rings[:-1], rings[1:]):
            for i in range(segs):
                bm.faces.new((a[i], b[i], b[(i + 1) % segs], a[(i + 1) % segs]))
        for f in bm.faces:
            f.smooth = True
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if bm.faces[0].normal.z < 0:
            for f in bm.faces:
                f.normal_flip()
        return bm
    me = U.shared_mesh(key, build)
    if not me.materials:
        U.set_materials(me, ["lotus_leaf"])
    return me


def _petal_bm(bm, base, yaw, tilt, length, width, cup=0.35):
    """Spoon-shaped petal: cupped across its width, curving up at the tip."""
    R = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(-tilt, 3, 'X')
    rows = []
    for j in range(6):
        s = j / 5
        w = width * math.sin(math.pi * min(1.0, 0.18 + s * 0.85)) ** 0.7
        row = []
        for i in range(4):
            u = i / 3 - 0.5
            p = Vector((u * w, cup * width * (u * u * 2.0) - 0.02 * s * s, s * length))
            p.y += -0.12 * length * s * s       # tip curls outward slightly
            row.append(bm.verts.new(base + R @ p))
        rows.append(row)
    for j in range(5):
        for i in range(3):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            f.smooth = True


def _lotus_flower_proto(variant, bud=False):
    key = "lotus.%s.v%d" % ("bud" if bud else "flower", variant)

    def build(col):
        r = U.rng("nature.lotus.flower", variant, bud)
        h = r.uniform(0.45, 0.85)
        lean = Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), 0))
        stem = [(0, 0, -0.6, 1.0), (lean.x * 0.5, lean.y * 0.5, h * 0.5, 1.0), (lean.x, lean.y, h, 0.9)]
        U.tube_mesh("nature.proto." + key + ".stem", stem, 0.012, col, material="nature_lotus_stem", sides=5)
        head = Vector((lean.x, lean.y, h))
        bm = bmesh.new()
        if bud:
            for k in range(6):
                _petal_bm(bm, Vector((0, 0, 0)), k * math.pi / 3 + r.uniform(-0.1, 0.1), 0.12, 0.17, 0.11, cup=0.5)
        else:
            for layer, (n, tilt, L, W) in enumerate(((8, 1.05, 0.16, 0.1), (8, 0.7, 0.16, 0.1), (6, 0.32, 0.14, 0.09))):
                ph = r.uniform(0, 1) + layer * 0.4
                for k in range(n):
                    _petal_bm(bm, Vector((0, 0, 0.005 * layer)), ph + 2 * math.pi * k / n,
                              tilt + r.uniform(-0.08, 0.08), L * r.uniform(0.9, 1.1), W, cup=0.4)
        _mesh_obj("nature.proto." + key + ".petals", bm, col, ["lotus_flower"], location=head)
        if not bud:
            pb = bmesh.new()
            U.bm_lathe(pb, [(0.0, 0.0), (0.022, 0.0), (0.045, 0.05), (0.04, 0.058), (0.0, 0.06)], segments=14)
            _mesh_obj("nature.proto." + key + ".pod", pb, col, ["nature_lotus_pod"], location=head)
    return _proto(key, build)


def _raised_leaf_proto(variant):
    key = "lotus.raised.v%d" % variant

    def build(col):
        r = U.rng("nature.lotus.raised", variant)
        h = r.uniform(0.3, 0.8)
        tilt = r.uniform(0.15, 0.4)
        U.tube_mesh("nature.proto." + key + ".stem", [(0, 0, -0.6, 1.0), (0.03, 0.0, h * 0.6, 1.0), (0.05, 0, h, 1.0)],
                    0.011, col, material="nature_lotus_stem", sides=5)
        me = _pad_mesh(variant + 10, cup=0.28)
        U.object_from_mesh("nature.proto." + key + ".leaf", me, col, location=(0.05, 0, h), rotation=(tilt, 0, 0),
                           scale=(0.36, 0.36, 0.36))
    return _proto(key, build)


def lotus_patch(collection, radius=3.0, count=24, seed=0, flowers=None, buds=None, name=None, location=(0, 0, 0),
                rotation=None, parent=None):
    """Lotus patch for a pond surface (place the root at water level): ``count`` round leaves
    (about 70 % floating with wavy upturned rims, 30 % cupped on stems above the water),
    ``flowers`` open pink lotus (3 petal rings, seed pod) and ``buds`` on stems.
    All are shared meshes / prototype instances. Returns the root Empty."""
    r = U.rng("nature.lotus", seed)
    nm = _name(name, "lotus")
    root = _root(nm, collection, location, rotation, parent)
    flowers = max(1, count // 5) if flowers is None else flowers
    buds = max(1, count // 7) if buds is None else buds
    placed = []

    def free_spot(min_d, tries=40):
        for _ in range(tries):
            a = r.uniform(0, 2 * math.pi)
            rr = radius * math.sqrt(r.uniform(0, 1))
            p = Vector((math.cos(a) * rr, math.sin(a) * rr, 0))
            if all((p - q).length > min_d + qs for q, qs in placed):
                return p
        return p
    for i in range(count):
        s = r.uniform(0.22, 0.48)
        p = free_spot(s * 0.9)
        placed.append((p, s * 0.9))
        if r.random() < 0.3:
            U.collection_instance(_raised_leaf_proto(r.randint(0, 3)), U.name(nm, "leaf"), collection,
                                  location=(p.x, p.y, 0.0), rotation=(0, 0, r.uniform(0, 6.28)),
                                  scale=(s / 0.36,) * 3, parent=root, display_size=0.2)
        else:
            me = _pad_mesh(r.randint(0, 3))
            U.object_from_mesh(U.name(nm, "pad"), me, collection, location=(p.x, p.y, 0.01),
                               rotation=(r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03), r.uniform(0, 6.28)),
                               scale=(s, s, s), parent=root)
    for i in range(flowers + buds):
        p = free_spot(0.2)
        bud = i >= flowers
        sc = r.uniform(1.3, 1.75)
        U.collection_instance(_lotus_flower_proto(r.randint(0, 2), bud), U.name(nm, "bud" if bud else "flower"),
                              collection, location=(p.x, p.y, 0.0), rotation=(0, 0, r.uniform(0, 6.28)),
                              scale=(sc, sc, sc), parent=root, display_size=0.2)
    return root


# =====================================================================================
# clouds
# =====================================================================================

def _cloud_domain():
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    return bm


def cloud_puff(collection, size=20.0, seed=0, density=1.0, flatten=0.62, name=None, location=(0, 0, 0),
               rotation=None, parent=None):
    """Volumetric cumulus puff for EEVEE: an icosphere domain (``size`` m wide, ``flatten`` x as
    tall) with nature_cloud_puff: ellipsoid falloff pushed by billowy noise (different per
    object), a flatter base, soft edges, never box-shaped. Density is normalised by size, so
    ``density`` = 1 gives a dense core and wispy rim at any size. Returns the domain object."""
    r = U.rng("nature.cloud", seed)
    me = U.shared_mesh("nature.cloud_domain", _cloud_domain)
    if not me.materials:
        U.set_materials(me, ["nature_cloud_puff"])
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    h = size * 0.5
    ob = U.object_from_mesh(_name(name, "cloud"), me, collection, location=location, rotation=rot,
                            scale=(h, h * r.uniform(0.75, 1.0), h * flatten), parent=parent)
    ob["density"] = density * 14.0 / max(1.0, size)
    return ob


def cloud_bank(collection, size=120.0, seed=0, density=1.0, depth=None, puffs=None, name=None,
               location=(0, 0, 0), rotation=None, parent=None):
    """A wide, flat bank of cloud: ``puffs`` (default size/10, 6-30) overlapping cumulus puffs
    along X (``size`` long, ``depth`` default 0.35 x size deep), biggest in the middle, over a
    thin flat base layer. Returns the root Empty."""
    r = U.rng("nature.cloudbank", seed)
    nm = _name(name, "cloud_bank")
    root = _root(nm, collection, location, rotation, parent, size=size * 0.1)
    depth = size * 0.35 if depth is None else depth
    n = puffs or max(6, min(30, int(size / 10)))
    for i in range(n):
        u = (i + r.uniform(0.2, 0.8)) / n - 0.5
        mid = 1.0 - abs(u) * 1.3
        ps = size * r.uniform(0.16, 0.26) * (0.55 + 0.45 * mid)
        loc = (u * size * 0.92, r.gauss(0, depth * 0.22), ps * r.uniform(0.05, 0.22) * mid)
        cloud_puff(collection, size=ps, seed=seed * 101 + i, density=density, flatten=r.uniform(0.45, 0.6),
                   name=nm + ".puff", location=loc, parent=root)
    base = cloud_puff(collection, size=size * 1.05, seed=seed * 101 + 99, density=density * 0.55, flatten=0.12,
                      name=nm + ".base", location=(0, 0, -size * 0.02), rotation=0.0, parent=root)
    base.scale.y = depth * 0.5
    return root


# =====================================================================================
# showcase and preview boards (sect.lib.look CLI targets)
# =====================================================================================

def showcase(collection):
    """Nature showcase for look.py previews (footprint 40): a lawn with a lotus pond, scholar rock,
    a waterfall pouring off a layered ledge crowned by a Huangshan pine, a weeping willow over
    the water, peach and plum trees, a bamboo clump, garden shrubs and grass (GN scatter), a
    vegetated karst pillar with cliff pines, a flat-topped pillar with an ancient pine, a floating
    rock, cloud puffs and a cloud bank. Returns the root Empty 'nature.showcase'."""
    root = U.empty(_name("nature.showcase", "showcase"), collection, display_size=2.0)
    pond_c = (-6.0, -6.0)
    ground = ground_patch(collection, radius=30.0, seed=4, height=0.3, holes=[(pond_c[0], pond_c[1], 6.6, 1.0)],
                          name="nature.lawn", parent=root)
    scatter_on(ground, plant_prototypes("grass"), density=0.22, seed=3, max_slope=math.radians(25),
               scale_range=(1.0, 2.0), z_range=(-0.25, 5.0), collection=collection, name="nature.lawn.grass")
    pond(collection, radius=6.2, seed=2, name="nature.pond", location=(pond_c[0], pond_c[1], 0.0), parent=root)
    lotus_patch(collection, radius=3.3, count=26, seed=3, name="nature.lotus", location=(pond_c[0] - 1.2, pond_c[1] - 1.5, -0.18),
                parent=root)
    rock(collection, size=3.6, seed=2, kind="scholar", name="nature.scholar", location=(1.2, -11.2, -0.05),
         rotation=0.35, parent=root)
    rock(collection, size=1.6, seed=5, kind="boulder", name="nature.boulder", location=(2.6, -10.2, 0.0), parent=root)
    # waterfall off a layered ledge into the back of the pond, a pine on the ledge
    led = rock(collection, size=11.0, seed=4, kind="ledge", name="nature.ledge", location=(-6.5, 5.6, 0.0),
               rotation=0.0, parent=root)
    lx, ly, lz = led["lip"]
    waterfall(collection, height=lz + 0.18, width=2.6, seed=1, name="nature.waterfall",
              location=(-6.5 + lx, 5.6 + ly + 0.25, lz), parent=root)
    pine(collection, height=8.5, seed=2, style="huangshan", name="nature.ledge_pine",
         location=(-9.5, 6.8, led["top_z"] - 0.15), rotation=2.6, parent=root)
    willow(collection, height=8.0, seed=1, name="nature.willow", location=(-16.5, -9.0, 0.0), rotation=0.4, parent=root)
    blossom_tree(collection, height=6.0, seed=1, kind="peach", name="nature.peach", location=(9.5, -7.5, 0.0),
                 rotation=0.3, parent=root)
    blossom_tree(collection, height=4.8, seed=2, kind="plum", name="nature.plum", location=(15.5, -2.0, 0.0),
                 rotation=1.2, parent=root)
    bamboo_clump(collection, count=14, height=9.0, seed=2, name="nature.bamboo", location=(19.0, 7.0, 0.0), parent=root)
    pine(collection, height=9.0, seed=4, style="huangshan", name="nature.pine", location=(6.0, 10.0, 0.0), parent=root)
    for i, (x, y, k) in enumerate(((3.5, -6.0, "azalea"), (-12.0, 2.5, "green"), (13.0, 2.5, "azalea"),
                                   (-1.0, 3.0, "green"), (8.0, -12.5, "green"), (-14.0, -14.0, "azalea"))):
        shrub(collection, size=1.7, seed=i, kind=k, name="nature.shrub", location=(x, y, 0.0), parent=root)
    # karst pillars: a vegetated dome pillar with cliff pines, and a flat-topped one with an ancient pine
    rock_pillar(collection, height=36.0, top_radius=6.5, bottom_radius=8.5, seed=3, top_flat=False, top_z=30.0,
                name="nature.pillar", location=(13.0, 23.0, 0.0), parent=root)
    rock_pillar(collection, height=24.0, top_radius=4.8, bottom_radius=6.0, seed=8, top_flat=True, top_z=21.0,
                pines=False, name="nature.pillar_b", location=(-18.0, 24.0, 0.0), parent=root)
    pine(collection, height=8.0, seed=0, style="ancient", name="nature.ancient_pine", location=(-18.5, 23.0, 21.0),
         rotation=-0.6, parent=root)
    floating_rock(collection, size=9.0, seed=5, name="nature.floating", location=(26.0, -6.0, 15.0), parent=root)
    cloud_puff(collection, size=14.0, seed=1, name="nature.cloud", location=(2.0, 30.0, 16.0), parent=root)
    cloud_puff(collection, size=9.0, seed=2, name="nature.cloud", location=(27.0, 16.0, 9.0), parent=root)
    cloud_bank(collection, size=80.0, seed=3, name="nature.cloud_bank", location=(0.0, 62.0, 5.0), parent=root)
    return root


showcase.preview_cameras = [
    ("hero", (-26.0, -44.0, 13.0), (2.0, 4.0, 7.0), 32.0),
    ("front", (-2.0, -38.0, 4.5), (0.0, 0.0, 5.0), 35.0),
    ("pond", (2.0, -21.0, 3.2), (-6.0, -4.0, 2.0), 35.0),
    ("pillar", (-6.0, -12.0, 22.0), (8.0, 22.0, 20.0), 35.0),
    ("aerial", (-30.0, -50.0, 46.0), (0.0, 6.0, 4.0), 35.0),
]


def board_trees(collection):
    """Preview board: the six huangshan pine variants, ancient and cliff pines, far-LOD pines,
    peach / plum trees, willows, bamboo, shrubs and grass."""
    root = U.empty(_name("nature.board_trees", "board_trees"), collection)
    for i in range(6):
        pine(collection, height=10, seed=i, location=(-30 + i * 12, 0, 0), rotation=0.0, parent=root)
    pine(collection, height=10, seed=0, style="ancient", location=(-26, 20, 0), rotation=0.0, parent=root)
    pine(collection, height=10, seed=1, style="cliff", location=(-12, 22, 3), rotation=0.0, parent=root)
    for i in range(3):
        pine(collection, height=10, seed=i, lod="far", location=(26 + i * 8, 20, 0), rotation=0.0, parent=root)
    for i in range(2):
        blossom_tree(collection, height=6, seed=i, kind="peach", location=(-28 + i * 9, -18, 0), rotation=0.0, parent=root)
        blossom_tree(collection, height=5, seed=i, kind="plum", location=(-8 + i * 8, -18, 0), rotation=0.0, parent=root)
    willow(collection, height=8, seed=0, location=(12, -18, 0), rotation=0.0, parent=root)
    bamboo_clump(collection, count=12, height=8, seed=0, location=(24, -18, 0), parent=root)
    for i in range(6):
        shrub(collection, size=1.6, seed=i, kind="green" if i < 4 else "azalea", location=(2 + i * 2.4, 14, 0),
              parent=root)
    return root


board_trees.preview_cameras = [("front", (0, -75, 12), (0, 2, 5), 35), ("close", (-14, -34, 4), (-14, -18, 4), 35)]


def board_rocks(collection):
    """Preview board: boulders, scholar rocks, ledges, hero and far karst pillars, a floating rock."""
    root = U.empty(_name("nature.board_rocks", "board_rocks"), collection)
    for i in range(4):
        rock(collection, size=1.6, seed=i, kind="boulder", location=(-12 + i * 2.4, -14, 0), parent=root)
    for i in range(3):
        rock(collection, size=3.2, seed=i, kind="scholar", location=(-2 + i * 2.6, -14, 0), rotation=0.0, parent=root)
    rock(collection, size=8, seed=1, kind="ledge", location=(9, -12, 0), rotation=0.0, parent=root)
    rock_pillar(collection, height=40, top_radius=8, bottom_radius=9.5, seed=3, top_flat=True, top_z=30,
                location=(-14, 10, 0), parent=root)
    rock_pillar(collection, height=36, top_radius=6, bottom_radius=7.5, seed=4, top_flat=False, top_z=28,
                location=(4, 16, 0), parent=root)
    rock_pillar(collection, height=40, top_radius=7, bottom_radius=9, seed=5, top_flat=False, top_z=32, lod="far",
                location=(20, 14, 0), parent=root)
    floating_rock(collection, size=12, seed=2, location=(24, -6, 20), parent=root)
    return root


board_rocks.preview_cameras = [("wide", (0, -75, 18), (2, 4, 16), 35), ("rocks", (-2, -26, 3.5), (-1, -13, 1.2), 35)]


def board_clouds(collection):
    """Preview board: cloud puffs of 8-40 m and a 120 m cloud bank (render with --no-haze; see
    docs/api_nature.md on EEVEE volume range)."""
    root = U.empty(_name("nature.board_clouds", "board_clouds"), collection)
    cloud_puff(collection, size=40, seed=1, location=(-30, 90, 25), parent=root)
    cloud_puff(collection, size=12, seed=2, location=(10, 10, 8), parent=root)
    cloud_puff(collection, size=8, seed=4, location=(-6, 4, 5), parent=root)
    cloud_bank(collection, size=120, seed=3, location=(40, 160, 15), parent=root)
    return root


board_clouds.preview_cameras = [("front", (0, -30, 8), (0, 40, 14), 35)]


# =====================================================================================
# round 48: the background with intent (scratchpad r45/plan_final.md P-1 .. P-4, r49/intent.md)
# =====================================================================================
#
# - peak_pillar: the range's tall peaks rebuilt as karst pillars on their own bed sequences (no shared contour
#   heights), with real shelves, fissures, a vegetated dome cap, and a hanging green fringe and drapes on every shelf
#   lip. Face attributes for the planting: 'nature_cap' (dome top), 'nature_shelf' (up-facing shelf tops, which also
#   turn moss-green), 'nature_crack' (steep faces in a fissure: fern and shrub strips).
# - canopy trees: a rounded broadleaf (6 variants in 3 greens + 2 spring-green accents), the Masson pine spire
#   (pine style 'masson') and mountain scrub (shrub kind 'scrub'). The broadleaf is named under the bake pipeline's
#   tree kind ('nature.proto.pine.broadleaf.v<N>.<lod>'): bake_trees treats it like any tree (near mesh within
#   --tree-near with its leaf cards stripped, crossed cards with sprites from the '.hero' leafy crown farther out), so
#   no export or bake script needs a new vegetation kind.
# - hull clumps (P-4): low-poly merged crown blobs for 70-250 m, baked like terrain.

PILLAR_PRESETS = dict(
    # Zhangjiajie sandstone column: thin uneven beds, a real shelf on about a quarter of them (2-5 m deep on a main
    # peak: shelf_amp x R past the bed above), 5-9 deep fissures, a low dome
    # (round 48 slice: a hero pillar's shelves stick out up to shelf_min m or more (0.2-1 x that round the pillar,
    # about 2 m on average), so they read as ledges with plants;
    # massive: a share of beds 2-3x thicker, so the beds are not stacked drums of one height)
    sandstone=dict(fissures=(5, 9), fissure_k=0.16, fissure_cap=7.0, lobe=0.12, bulge=(-0.04, 0.06), shoulder_k=1.0,
                   bed_k=1.4, shelf_p=0.26, shelf_amp=(0.08, 0.15), bed_amp=0.02, dome=(0.12, 0.28), dip=(1.0, 3.0),
                   shelf_min=3.0, massive=(0.15, 2.0, 3.0)),
    # Huangshan granite: thick beds with only small ledges, 8-12 fissures splitting it into columns, a rounded crown
    granite=dict(fissures=(8, 12), fissure_k=0.12, fissure_cap=5.5, lobe=0.16, bulge=(0.0, 0.1), shoulder_k=1.8,
                 bed_k=2.0, shelf_p=0.16, shelf_amp=(0.035, 0.07), bed_amp=0.02, dome=(0.26, 0.42), dip=(0.5, 2.0)),
    # far mesa (world.BACKDROP_R48): a wide table with a low dome, so its skyline reads level from 2 km
    mesa=dict(fissures=(10, 16), fissure_k=0.03, fissure_cap=8.0, lobe=0.05, bulge=(0.0, 0.04), shoulder_k=2.5,
              bed_k=2.2, shelf_p=0.2, shelf_amp=(0.01, 0.02), bed_amp=0.006, dome=(0.04, 0.08), dip=(0.2, 0.8)),
)
PILLAR_SEG = dict(hero=1.25, mid=2.5, far=4.0)             # m of wall per segment round the pillar
PILLAR_SEG_CLAMP = dict(hero=(96, 320), mid=(40, 160), far=(28, 80))
SHELF_NZ = 0.55            # an up-facing rock face this flat (normal z) under the dome is a shelf top
CRACK_MIN = 0.3            # fissure strength (_PillarShape.fissure) over which a steep face is a crack strip
CRACK_NZ = 0.5             # ... steep: |normal z| under this (60 deg and steeper)
FRINGE_MIN = 0.6           # m: a shelf this deep or deeper gets the hanging fringe along its lip
FRINGE_LEN = (1.0, 2.2)    # m the fringe hangs over the lip
DRAPE_P = 0.16             # share of a fringed lip's samples that also drop a long drape
DRAPE_LEN = (3.0, 8.0)     # m
DRAPE_W = (0.8, 1.6)       # m wide at the lip
FRINGE_LOW = 0.85          # no fringe on the lowest 15 % of a pillar (mist and the plinth's forest hide it)
# Round 48 slice: peak_pillar makes no fringe by default. The strips baked as flat green paper up close and black
# sticks on the web, and their few upward faces marked the client's "built" mask (range-look.ts RANGE_LOOK.built)
# over three quarters of a pillar, so the range rock grade never reached it (B0 b: sunlit rock saturation 0.50).
# The shelf shrubs (clumped, overhanging the lip) carry the green instead.
PILLAR_FRINGE = False


def _shear(co, k_x, k_y):
    return Vector((co.x, co.y, co.z + k_x * co.x + k_y * co.y))


def _pillar_fringe_bm(shape, seed, kx, ky, detail):
    """The green fringe pouring over every shelf lip of ``shape`` (a strip from just inside the lip to FRINGE_LEN
    below it, on 60-70 % of the lip) and long drapes on DRAPE_P of the fringed samples. Pillar-local coordinates,
    sheared like the pillar (kx, ky). Returns (bm, number of fringed shelves)."""
    r = U.rng("nature.fringe", seed)
    bm = bmesh.new()
    R = shape.R
    n = max(24, min(120, int(2 * math.pi * R / 2.5)))
    ths = [2 * math.pi * i / n for i in range(n)]
    o = shape.off
    z_low = shape.tz - shape.h * FRINGE_LOW
    shelves = 0
    for i, (zt, _zb, amp) in enumerate(shape.layers):
        if i < 2 or zt < z_low:
            continue
        if amp - shape.layers[i - 1][2] < 0.03 * R:
            continue
        rows = []
        for t in ths:
            c, s = math.cos(t), math.sin(t)
            depth = shape.radius(t, zt - 0.5, detail) - shape.radius(t, zt + 0.3, detail)
            cover = _n(Vector((c * 1.3, s * 1.3, i * 0.9)) + o) > -0.3
            if depth < FRINGE_MIN or not cover:
                rows.append(None)
                continue
            rl = shape.radius(t, zt - 0.15, detail)
            L = FRINGE_LEN[0] + (FRINGE_LEN[1] - FRINGE_LEN[0]) * (0.5 + 0.5 * _n(Vector((c * 3.1, s * 3.1, i * 1.7))
                                                                                  + o))
            top = bm.verts.new(_shear(Vector((c * (rl - 0.3), s * (rl - 0.3), zt + 0.12)), kx, ky))
            bot = bm.verts.new(_shear(Vector((c * (rl + 0.4), s * (rl + 0.4), zt - L)), kx, ky))
            rows.append((top, bot, t, rl))
        made = False
        for j in range(n):
            a, b = rows[j], rows[(j + 1) % n]
            if a is None or b is None:
                continue
            f = bm.faces.new((a[0], b[0], b[1], a[1]))
            f.smooth = True
            made = True
        shelves += 1 if made else 0
        for row in rows:
            if row is None or r.random() >= DRAPE_P:
                continue
            _top, _bot, t, _rl = row
            c, s = math.cos(t), math.sin(t)
            sx, sy = -s, c                                   # across the wall
            Ld = r.uniform(*DRAPE_LEN)
            w = r.uniform(*DRAPE_W)
            prev = None
            for k in range(5):
                q = k / 4.0
                z = zt - 0.2 - Ld * q
                rr = shape.radius(t, z, detail) + 0.3
                hw = 0.5 * w * (1.0 - 0.75 * q)
                p = Vector((c * rr, s * rr, z))
                cur = (bm.verts.new(_shear(p + Vector((sx * hw, sy * hw, 0.0)), kx, ky)),
                       bm.verts.new(_shear(p - Vector((sx * hw, sy * hw, 0.0)), kx, ky)))
                if prev is not None:
                    f = bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
                    f.smooth = True
                prev = cur
    # face the strips out of the rock (the web draws them double-sided; the bake lights the outer side)
    for f in bm.faces:
        f.normal_update()
        cc = f.calc_center_median()
        if f.normal.x * cc.x + f.normal.y * cc.y < 0.0:
            f.normal_flip()
    return bm, shelves


def peak_pillar(collection, height=150.0, top_radius=18.0, bottom_radius=None, seed=0, top_z=0.0, preset="sandstone",
                lod="mid", name=None, location=(0, 0, 0), parent=None, dip=None, dip_az=None, fringe=None,
                green_shelves=True):
    """Round 48 (P-1): one of the range's peaks as a karst pillar from ``top_z`` down ``height`` m (sink its foot
    8-10 m into the plinth), PILLAR_PRESETS[``preset``] shape at ``lod`` ('hero' 1.25 m, 'mid' 2.5 m, 'far' 4 m wall
    resolution), tilted ``dip`` degrees (seeded 1-3 sandstone / 0.5-2 granite) toward ``dip_az`` so its beds are not
    level lines. Vegetated dome cap (material 1). Face attributes 'nature_cap', 'nature_shelf' (shelf tops; material
    1 when ``green_shelves``) and 'nature_crack'. ``fringe`` (None: PILLAR_FRINGE): a child mesh '<name>.fringe'
    (material nature_vine) hanging over every shelf lip. No plants: patch_r48_green / scenery.build_canopy plant the
    attributes. Returns (object, info)."""
    t0 = time.perf_counter()
    fringe = PILLAR_FRINGE if fringe is None else fringe
    P = PILLAR_PRESETS[preset]
    bottom_radius = top_radius * 1.15 if bottom_radius is None else bottom_radius
    shape = _PillarShape(seed, height, top_radius, bottom_radius, top_z, lod, preset=P)
    lo_, hi_ = PILLAR_SEG_CLAMP[lod]
    segs = max(lo_, min(hi_, int(2 * math.pi * max(top_radius, bottom_radius) / PILLAR_SEG[lod])))
    bm, _rim = _pillar_bm(shape, lod, False, segs, seed)
    r = U.rng("nature.peak_pillar", seed)
    dip = r.uniform(*P["dip"]) if dip is None else float(dip)
    dip_az = r.uniform(0.0, 2 * math.pi) if dip_az is None else float(dip_az)
    k = math.tan(math.radians(dip))
    kx, ky = k * math.cos(dip_az), k * math.sin(dip_az)
    for v in bm.verts:
        v.co = _shear(v.co, kx, ky)
    bm.normal_update()
    cap_l = bm.faces.layers.float.new("nature_cap")
    shelf_l = bm.faces.layers.float.new("nature_shelf")
    crack_l = bm.faces.layers.float.new("nature_crack")
    detail = lod == "hero"
    n_shelf = n_crack = 0
    for f in bm.faces:
        if f.material_index == 1:
            f[cap_l] = 1.0
            continue
        c = f.calc_center_median()
        nz = f.normal.z
        z0 = c.z - kx * c.x - ky * c.y
        if nz > SHELF_NZ and top_z - height * 0.97 < z0 < top_z - 1.0:
            f[shelf_l] = 1.0
            n_shelf += 1
            if green_shelves:
                f.material_index = 1
        elif abs(nz) < CRACK_NZ and shape.fissure(math.atan2(c.y, c.x), z0) > CRACK_MIN:
            f[crack_l] = 1.0
            n_crack += 1
    nm = _name(name, "peak_pillar")
    ob = _mesh_obj(nm, bm, collection, ["rock_cliff", "nature_soil_moss"], parent=parent, location=location)
    ob["nature_top_z"] = top_z
    ob["nature_top_radius"] = top_radius
    ob["nature_bottom_radius"] = bottom_radius
    ob["nature_preset"] = preset
    ob["nature_lod"] = lod
    ob["nature_dip"] = (round(dip, 3), round(dip_az, 4))
    info = dict(segments=segs, layers=len(shape.layers), shelf_faces=n_shelf, crack_faces=n_crack,
                tris=sum(len(p.vertices) - 2 for p in ob.data.polygons), fringe_tris=0, fringe_shelves=0)
    if fringe:
        fb, nsh = _pillar_fringe_bm(shape, seed, kx, ky, detail)
        if len(fb.faces):
            fo = U.mesh_from_bmesh(nm + ".fringe", fb, collection, materials=["nature_vine"], smooth=None,
                                   parent=ob)
            fo["nature_fringe"] = True
            info["fringe_tris"] = sum(len(p.vertices) - 2 for p in fo.data.polygons)
            info["fringe_shelves"] = nsh
        else:
            fb.free()
    ob["nature_build_s"] = round(time.perf_counter() - t0, 3)
    return ob, info


def pillar_radius_profile(height, top_radius, bottom_radius, seed, top_z, preset="sandstone", lod="mid", n_th=48,
                          dz=4.0):
    """[(z, largest radius round the pillar at z)] of peak_pillar's shape before its dip (for the corridor check:
    the pillar must stay inside the old peak's cone at every height)."""
    shape = _PillarShape(seed, height, top_radius, bottom_radius, top_z, lod, preset=PILLAR_PRESETS[preset])
    out = []
    z = top_z - 0.5
    detail = lod == "hero"
    while z > top_z - height:
        out.append((z, max(shape.radius(2 * math.pi * i / n_th, z, detail) for i in range(n_th))))
        z -= dz
    return out


# ---- canopy trees ---------------------------------------------------------------------------------------------

CANOPY_VARIANTS = 6                         # broadleaf crowns in three greens (CANOPY_TONES by variant % 3)
CANOPY_ACCENTS = (6, 7)                     # two spring-green accent variants (cool, not warm: rule 15)
CANOPY_TONES = ("nature_canopy_a", "nature_canopy_b", "nature_canopy_c")
CANOPY_HEIGHT = PINE_HEIGHT                 # prototype height; instances scale to 6-12 m


def _broadleaf_proto(variant, lod="hero"):
    """Broadleaf canopy tree (round 48, P-3) at CANOPY_HEIGHT: a short trunk the crown hides (about 15 % shows), 3-4
    limbs, 9-13 lumpy crown blobs in a crown wider than tall (0.8-0.95 H wide, 0.6 H tall) shaded as one soft cloud,
    and ('hero') about 190 leaf sprays breaking the outline. Tri count: hero ~4.5k (the bake's near mesh strips the
    sprays and decimates to ~1.2k), far ~1k (no sprays). Materials: bark, a canopy green, nature_shrub_leaf."""
    _check(lod, ("hero", "far"), "broadleaf lod")
    key = "pine.broadleaf.v%d.%s" % (variant, lod)

    def build(col):
        r = U.rng("nature.broadleaf", variant)
        H = CANOPY_HEIGHT
        hero = lod == "hero"
        bm = bmesh.new()
        lean_az = r.uniform(0, 2 * math.pi)
        Rz = Matrix.Rotation(lean_az, 3, 'Z')
        cc = Vector((0.0, 0.0, H * r.uniform(0.58, 0.64)))
        rx = H * r.uniform(0.4, 0.48)
        ry = rx * r.uniform(0.84, 1.0)
        rz = H * r.uniform(0.29, 0.35)
        env = (cc, (rx, ry, rz), Rz)
        base = cc - Vector((0.0, 0.0, rz * 0.45))
        lean = Rz @ Vector((H * 0.04, 0.0, 0.0))
        trunk = [(0.0, 0.0, -0.4, 1.3), (0.0, 0.0, 0.0, 1.15), (lean.x * 0.5, lean.y * 0.5, base.z * 0.5, 0.9),
                 (lean.x, lean.y, base.z, 0.65)]
        _bm_tube(bm, trunk, H * 0.034, sides=7 if hero else 5, sps=3 if hero else 1, cap_start=True,
                 bumpy=0.12, seed=variant, mat=0)
        top = Vector(trunk[-1][:3])
        for k in range(r.randint(3, 4)):
            a = lean_az + 2 * math.pi * k / 4 + r.uniform(-0.4, 0.4)
            end = cc + Rz @ Vector((math.cos(a) * rx * 0.55, math.sin(a) * ry * 0.55, rz * r.uniform(0.0, 0.35)))
            mid = top.lerp(end, 0.5) + Vector((0.0, 0.0, H * 0.04))
            _bm_tube(bm, [tuple(top) + (1.0,), tuple(mid) + (0.7,), tuple(end) + (0.35,)], H * 0.018,
                     sides=5 if hero else 4, sps=2 if hero else 1, seed=variant * 7 + k, mat=0)
        blobs = []
        for i in range(r.randint(9, 13)):
            a = r.uniform(0, 2 * math.pi)
            u = r.uniform(-0.35, 1.0)
            rho = math.sqrt(max(0.0, 1.0 - u * u)) * r.uniform(0.5, 0.85)
            c = cc + Rz @ Vector((math.cos(a) * rho * rx, math.sin(a) * rho * ry, u * rz * 0.68))
            s = H * r.uniform(0.17, 0.26)
            size = (s, s * r.uniform(0.85, 1.0), s * 0.76)
            _bm_blob(bm, c, size, subdiv=2 if hero else 1, seed=variant * 31 + i, lump=0.16, freq=1.8,
                     flatten=0.55, mat=1, env=env, env_w=0.75)
            blobs.append((c, size))
        if hero:
            for i in range(190):
                c, (sx, sy, sz) = blobs[r.randrange(len(blobs))]
                ang = r.uniform(0, 6.28)
                dz = r.uniform(-0.25, 0.95)
                hh = math.sqrt(max(0.0, 1.0 - dz * dz))
                d = Vector((math.cos(ang) * hh, math.sin(ang) * hh, dz))
                p = c + Vector((d.x * sx, d.y * sy, d.z * sz))
                out = Vector((d.x, d.y, 0.0))
                _needle_fan(bm, p - d * 0.1, out if out.length > 1e-3 else Vector((1, 0, 0)), r.uniform(0.55, 0.85),
                            2, env=env, lift=0.2 + 0.9 * max(0.0, d.z), roll=r.uniform(-0.5, 0.5), up_w=0.4,
                            spread=r.uniform(1.8, 2.6))
        tone = CANOPY_TONES[variant % 3] if variant < CANOPY_VARIANTS else "nature_canopy_accent"
        _mesh_obj("nature.proto." + key, bm, col, ["nature_bark_blossom", tone, "nature_shrub_leaf"])
        col["lean_az"] = lean_az
    return _proto(key, build)


def canopy_tree(collection, height=8.0, seed=0, lod="hero", accent=False, name=None, location=(0, 0, 0),
                rotation=None, parent=None, spread=None):
    """Broadleaf canopy tree (round 48): ``seed`` picks the variant (accent: one of CANOPY_ACCENTS) and the yaw.
    Returns a collection-instance Empty (origin at the trunk base)."""
    r = U.rng("nature.broadleaf.inst", seed)
    variant = CANOPY_ACCENTS[seed % len(CANOPY_ACCENTS)] if accent else seed % CANOPY_VARIANTS
    proto = _broadleaf_proto(variant, lod)
    s = height / CANOPY_HEIGHT
    sp = spread if spread is not None else r.uniform(0.9, 1.12)
    rot = _rot(rotation) if rotation is not None else (0.0, 0.0, r.uniform(0, 2 * math.pi))
    return U.collection_instance(proto, _name(name, "canopy_tree"), collection, location=location, rotation=rot,
                                 scale=(s * sp, s * sp, s), parent=parent, display_size=height * 0.2)


def canopy_prototypes(kind="broadleaf"):
    """Prototype lists for the round-48 scatters: 'broadleaf' (6 hero crowns), 'accent' (2), 'spire' (4 Masson pines,
    hero: their sprites need the needle fans), 'scrub' (4 low scrub; the hero ones are built too, for the bake's
    leafy near bush), 'shelf' (2 green low shrubs + 2 low scrub), 'fern' (the 4 green low shrubs, small)."""
    if kind == "broadleaf":
        for v in range(CANOPY_VARIANTS):
            _broadleaf_proto(v, "far")
        return [_broadleaf_proto(v, "hero") for v in range(CANOPY_VARIANTS)]
    if kind == "accent":
        for v in CANOPY_ACCENTS:
            _broadleaf_proto(v, "far")
        return [_broadleaf_proto(v, "hero") for v in CANOPY_ACCENTS]
    if kind == "spire":
        for v in range(PINE_VARIANTS["masson"]):
            _pine_proto("masson", v, "far")
        return [_pine_proto("masson", v, "hero") for v in range(PINE_VARIANTS["masson"])]
    if kind == "scrub":
        for v in range(4):
            _shrub_proto("scrub", v)
        return [_shrub_proto("scrub", v, "low") for v in range(4)]
    if kind == "shelf":
        for v in range(2):
            _shrub_proto("scrub", v)
        return [_shrub_proto("green", v, "low") for v in range(2)] + [_shrub_proto("scrub", v, "low") for v in range(2)]
    if kind == "fern":
        return [_shrub_proto("green", v, "low") for v in range(4)]
    raise ValueError("unknown canopy set %r" % kind)


# ---- hull clumps (P-4) ------------------------------------------------------------------------------------------

def hull_clumps_bm(clumps, seed=0):
    """One BMesh of low-poly crown clumps for 70-250 m (round 48, P-4): per clump (x, y, z_ground, radius) 3-5 lumpy
    icosphere blobs (80 triangles each: a big centre crown and smaller ones round it at uneven heights) sitting on their
    own ground height, wider than tall, flat underneath. The blobs' normals bend toward the clump's envelope (the
    custom-normal layer _NRM: build the object with _mesh_obj), so a clump shades as one soft crown mass, not as
    faceted pyramids. One material (index 0, nature_canopy_mass). Coordinates as given (world, for an object at the
    origin)."""
    r = U.rng("nature.hulls", seed)
    bm = bmesh.new()
    _nrm_layer(bm)
    for i, (x, y, z, rad) in enumerate(clumps):
        n = 3 if rad < 6.0 else (4 if rad < 9.0 else 5)
        hk = r.uniform(0.62, 0.85)                       # this clump's height to width
        env = (Vector((x, y, z + rad * hk * 0.55)), (rad * 1.05, rad * 1.05, rad * hk * 0.75), Matrix.Identity(3))
        for k in range(n):
            a = r.uniform(0, 2 * math.pi)
            off = rad * (0.0 if k == 0 else r.uniform(0.4, 0.72))
            s = rad * (0.68 if k == 0 else r.uniform(0.32, 0.55))
            h = s * hk * r.uniform(0.95, 1.2)
            c = Vector((x + math.cos(a) * off, y + math.sin(a) * off,
                        z + h * 0.7 + (0.0 if k == 0 else r.uniform(-0.15, 0.25) * rad)))
            _bm_blob(bm, c, (s, s * r.uniform(0.85, 1.0), h), subdiv=1, seed=seed * 101 + i * 7 + k, lump=0.24,
                     freq=1.7, flatten=0.35, mat=0, env=env, env_w=0.7)
    return bm


def _register_r48_materials():
    R = M.register
    pad = dict(tuft=2.0, transl=0.18, sun_mix=0.32, under_k=0.4, cells=2.2)
    R("nature_canopy_a", _mat_pine_pad, dark="#1f3322", mid="#2f4a32", light="#4d6b35", sun="#8a9a4a",
      under="#1b2c1f", crevice="#152519", **pad)
    R("nature_canopy_b", _mat_pine_pad, dark="#253823", mid="#3a5530", light="#5c7639", sun="#9aa24e",
      under="#1e301d", crevice="#18281a", **pad)
    R("nature_canopy_c", _mat_pine_pad, dark="#1b3026", mid="#2b4637", light="#476548", sun="#82955a",
      under="#182b22", crevice="#132219", **pad)
    R("nature_canopy_accent", _mat_pine_pad, dark="#2c4426", mid="#4a6a32", light="#7a9a48", sun="#b0b860",
      under="#24381f", crevice="#1e301a", **pad)
    # shell and hull clumps: one mass at 70 m and farther, bigger tufts, no translucency (baked)
    R("nature_canopy_mass", _mat_pine_pad, dark="#1d3122", mid="#2c4630", light="#4a6634", sun="#86964a",
      under="#182a1d", crevice="#132218", tuft=0.45, transl=0.0, sun_mix=0.3, under_k=0.5, cells=0.32)
    # shelf fringes and drapes
    R("nature_vine", _mat_pine_pad, dark="#18291b", mid="#2a4329", light="#466338", sun="#7c8a48",
      under="#15241a", crevice="#101c14", tuft=3.0, transl=0.1, sun_mix=0.25, under_k=0.4, cells=2.6)


_register_r48_materials()
