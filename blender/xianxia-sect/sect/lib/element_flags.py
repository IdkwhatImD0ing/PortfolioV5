"""Colours of the Ming Sect's Five Element Banners 五行旗 (areas/formation.py ELEMENT_FLAGS): the classical Wu Xing
colours, each flag on a cloth material of its own, so nothing else in the sect changes with them.

    木 wood   青 jade green       gold flame teeth, gold character
    火 fire   赤 vermilion        gold flame teeth, gold character
    土 earth  黄 imperial yellow  ink flame teeth, ink character
    金 metal  白 moon white       ink flame teeth, ink character
    水 water  黑 ink black        indigo flame teeth, gold character

Round 30 (owner, 2026-10-23: "The element flags in the formation should have colors corresponding to the element").
The cloth indices were right (wood jade, fire vermilion, earth gold, metal moon white, water ink black, from the shared
banner palette materials.BANNER_COLOURS), but at the formation's hold (frame 1208) on the site three of them read wrong:
- wood read slate blue. The site's grade (client/src/lib/sect/look.ts SECT_LOOK.grade.greenTame 1.0) takes all of green's
  lead over red and blue out of every baked texel, so the bake's jade (#288848 in the atlas) is drawn as #334e5e. No
  albedo survives that as green; the cloth only reads green where the client leaves the flags out of the tame (the
  round-30 client diff). The jade here is a little greener than the palette's (#2f7a5f, a blue-green), and keeps
  enough blue that with the tame it stays a dark teal, never black: the leaf greens tried (#1f7a3a, #2a7f3f, #3a8c2c)
  went near-black under the tame.
- earth read as a tan copy of the gold trim: the palette's imperial gold (#c9962e) is the trim's own colour (cloth_gold
  #c99a2e). A lemon-side yellow, #dcc800, with less translucency and sheen than the other cloths (0.25 and 0.3: both
  bleach a bright cloth toward cream under the bake's AgX) bakes to a yellow the site draws about #ffe183, well apart
  from the trim (about #ffb96c) and from the moon white (about #fffce7). Darker or more orange yellows (#c9a000,
  #d4c000 at 0.2) came out as the trim's peach again; the palette's translucency 0.38 left it pale straw.
- water read gold/tan: its big gold flame teeth (a fifth of the cloth) outshone the black. They are indigo now (banner_4,
  waves); the character and its ring stay gold.
Fire and metal read right; they get their own cloths too (fire the palette's vermilion, metal a cooler white so the
warm light leaves it white rather than cream).

Chosen with Cycles renders of the cloths from the side the bake lights (AgX Punchy, the bake's exposure 1.2) passed
through a copy of the site's grade (look.ts gradeLinear), checked against the bake's own atlas texels and the site's
screenshot of the hold (preview_r30_flags.py; round-30 report).

Data only (no bpy): lib/materials.py registers CLOTH (builder _cloth), areas/formation.py dresses each flag with TRIM,
and sect/patch_r30_flags.py recolours an existing file the same way.
"""

# element: (registered material name, colour (sRGB hex), translucency, sheen) for materials._cloth
CLOTH = {
    "wood": ("flag_wood", "#2e8b57", 0.38, 0.5),
    "fire": ("flag_fire", "#a8231c", 0.38, 0.5),
    "earth": ("flag_earth", "#dcc800", 0.25, 0.3),
    "metal": ("flag_metal", "#ecebe6", 0.38, 0.5),
    "water": ("flag_water", "#10141c", 0.15, 0.5),
}

# element: (flame teeth material (cloth slot 1), character and ring material (slot 2)): registered names. Gold on the
# dark cloths and ink (banner_7) on the light ones, as props.banner's trim='auto' does; the water flag's teeth indigo.
TRIM = {
    "wood": ("cloth_gold", "cloth_gold"),
    "fire": ("cloth_gold", "cloth_gold"),
    "earth": ("banner_7", "banner_7"),
    "metal": ("banner_7", "banner_7"),
    "water": ("banner_4", "cloth_gold"),
}

ORDER = ("wood", "fire", "earth", "metal", "water")      # the generating order, front to back on the rim


def register(M):
    """Register the five cloths with lib/materials ``M`` (idempotent: a name already registered must carry the same
    builder and parameters, or this raises). Returns the material names in ORDER."""
    for key in ORDER:
        name, colour, tr, sheen = CLOTH[key]
        want = dict(colour=colour, translucency=tr, sheen=sheen)
        if M.has(name):
            builder, params = M._REGISTRY[name]
            if builder is not M._cloth or params != want:
                raise RuntimeError("materials registers %s as %s %s, element_flags as _cloth %s" % (
                    name, getattr(builder, "__name__", builder), params, want))
            continue
        M.register(name, M._cloth, **want)
    return [CLOTH[k][0] for k in ORDER]
