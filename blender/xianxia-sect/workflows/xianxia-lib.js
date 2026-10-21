export const meta = {
  name: 'xianxia-lib',
  description: 'Build and critique the shared Blender library (materials, look-dev, architecture, props, nature) for the xianxia sect scene',
  phases: [
    { title: 'Foundation', detail: 'util + materials, look-dev + preview harness' },
    { title: 'Build', detail: 'architecture, props, nature modules with showcase renders' },
    { title: 'Critique', detail: 'art-direction and technical critics look at renders' },
    { title: 'Revise', detail: 'module authors fix critic findings' },
    { title: 'Integrate', detail: 'combined showcase, API reference, integration fixes' },
  ],
}

const ROOT = 'E:/Github/PortfolioV5/blender/xianxia-sect'
const BLENDER = '"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"'

const COMMON = `
You are part of a team building a production-quality xianxia (Chinese cultivation fantasy) sect scene in Blender 5.2, procedurally, with Python.
FIRST read ${ROOT}/spec.md completely. It is the contract: paths, world conventions, art direction, palette, architecture rules, module contracts. Follow it exactly.
Hard rules:
- Run Blender ONLY in background mode: ${BLENDER} --background --factory-startup --python <script> -- <args>. Never touch the user's open Blender (never call mcp__blender__execute_blender_code). Never use Higgsfield or any paid generation service.
- Only edit the files you own (named below). Read others freely. Write previews only into your own out/previews/<your-folder>/ and scratch into out/tmp/<your-folder>/.
- Other team members run Blender at the same time on the same GPU. Keep preview renders <= 1280x720, EEVEE, modest samples.
- Blender 5.x APIs differ from older versions. Introspect at runtime (bl_rna.properties, node input/output names) or use the mcp__blender__search_api_docs tool (works without the live Blender) instead of guessing.
- Judge your work by LOOKING at your renders with the Read tool (it displays PNGs). Iterate until it genuinely looks good, not just until the script runs. Be your own harshest critic about silhouette, proportions, materials, and whether it reads as Chinese xianxia rather than generic fantasy.
- Python must be deterministic (seeded), idempotent, and well organised; add short docstrings for public functions.
`

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    files_written: { type: 'array', items: { type: 'string' } },
    public_api: { type: 'array', items: { type: 'string' }, description: 'one line per public function: signature - what it builds' },
    preview_images: { type: 'array', items: { type: 'string' }, description: 'absolute paths of the best showcase PNGs' },
    how_to_preview: { type: 'string', description: 'exact command to re-render the showcase' },
    stats: { type: 'string', description: 'triangle counts, build/render times' },
    known_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['files_written', 'public_api', 'preview_images', 'how_to_preview', 'known_issues'],
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    overall_grade: { type: 'string', description: 'A-F with one sentence why' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          where: { type: 'string', description: 'function / file:line / image' },
          problem: { type: 'string' },
          fix: { type: 'string', description: 'concrete, actionable fix' },
        },
        required: ['severity', 'where', 'problem', 'fix'],
      },
    },
    strengths: { type: 'array', items: { type: 'string' } },
    images_reviewed: { type: 'array', items: { type: 'string' } },
  },
  required: ['overall_grade', 'issues', 'images_reviewed'],
}

// ---------------- Phase 1: foundation ----------------
phase('Foundation')

const UTIL_MAT_PROMPT = `${COMMON}
YOUR JOB: write ${ROOT}/sect/__init__.py, ${ROOT}/sect/lib/__init__.py (both empty), ${ROOT}/sect/lib/util.py and ${ROOT}/sect/lib/materials.py, plus ${ROOT}/docs/api_util.md and ${ROOT}/docs/api_materials.md. Preview folder: out/previews/materials/.

util.py must provide (names can be refined, document them):
- get_collection(name, parent=None); link(obj, collection); empty(name, collection, location=(0,0,0), parent=None, display_size=1)
- mesh_from_pydata(name, verts, faces, collection, materials=None, smooth=False) and mesh_from_bmesh(name, bm, collection, materials=None)
- instance(src_obj, name, collection, location=(0,0,0), rotation=(0,0,0), scale=(1,1,1), parent=None, matrix=None) -> linked duplicate sharing mesh data
- proto_collection(name) -> a collection that is excluded from the view layer (so prototype objects never render) for use as instancing sources; collection_instance(src_collection, name, collection, matrix/location/rotation/scale, parent)
- parent(child, parent_obj, keep_transform=True); bevel(obj, width, segments=2, angle_limit); auto_smooth(obj, angle) that works in Blender 5.2 (mesh.set_sharp_from_angle or the Smooth by Angle modifier - verify); apply_modifiers if needed
- rng(seed) returning random.Random; noise helpers using mathutils.noise
- curve_tube(name, points, radius, collection, material, resolution) for ropes, cords, chains' guide curves, roots
- evaluated_triangle_count(objects or collection)
- name helper that guarantees unique, prefixed names
- Anything else you judge every module will need. Keep it small and solid.

materials.py: get(name) returns a shared procedural material (created once, cached by name), NAMES lists all, register(name, builder_fn) lets other modules add module-specific materials without editing this file, and unknown names raise KeyError listing valid ones. Use the palette in spec.md section 3. Use Object or Generated texture coordinates scaled sensibly for meter-scale objects so instanced/scaled objects still look right. Bump, not displacement. Make each material genuinely good under a low warm golden-hour sun in EEVEE (Principled BSDF, roughness variation, subtle colour variation from noise, edge wear where it fits). Required names at minimum:
lacquer_red, lacquer_red_worn, wood_dark, wood_light, wood_soot, roof_tile_teal, roof_tile_black, roof_tile_moon, bracket_paint, gold, silver, bronze, bronze_verdigris, jade, jade_glow, marble_white, marble_paving, stone_grey, stone_dark, rock_cliff, moss, grass, soil, paper_lantern, paper_screen, paper_screen_lit, plaque_board, cloth_red, cloth_gold, cloth_white, cloth_teal, cloth_black, rune_cyan, rune_gold, rune_silver, light_beam, water_pond, water_fall, molten, ember, smoke_volume, mist_volume, cloud_volume, glass_shield, foliage_pine, foliage_blossom, foliage_willow, foliage_bamboo, bark_pine, bark_dark, bamboo_stalk, lotus_leaf, lotus_flower, koi, ink, moon_surface.
Also provide banner_cloth(i) returning one of ~8 harmonious banner colour materials by index.
Glow materials: emission strength <= 30; light_beam and glass_shield should be transparent/additive-looking in EEVEE 5.2 (check blend/transparency settings that exist in 5.2). Volume materials use Principled Volume with noise-modulated density.

Test: write a temporary background script that lays out a swatch board (a sphere + a beveled cube + a small wall panel per material, labelled by name with text objects) under a low warm sun + sky (MULTIPLE_SCATTERING, sun elevation ~7 deg from the west, see spec) and renders it at 1280x720 with EEVEE to out/previews/materials/. Another teammate is writing sect/lib/look.py concurrently; if it exists and works when you test, you may use look.setup_lookdev, otherwise light your own test scene. Look at the renders and iterate until every material is convincing. Render a second, closer board for the architectural materials (lacquer, tiles, marble, gold, bracket paint, rock).`

const LOOK_PROMPT = `${COMMON}
YOUR JOB: write ${ROOT}/sect/lib/look.py and ${ROOT}/docs/api_look.md. Preview folder: out/previews/look/. A teammate is concurrently writing sect/lib/util.py and sect/lib/materials.py; do not edit them. look.py must work even if materials.py is not finished yet (import it lazily and fall back to a simple local material for the plinth).

look.py must provide:
- Constants SUN_AZIMUTH/SUN_ELEVATION, SUN_DIR (unit vector pointing from scene toward the sun), MOON_DIR, MOON_ANGULAR_SIZE, matching spec.md section 2 (sun low in the west ~7 deg; moon NNE ~16 deg elevation, ~14 deg wide). world.py will import these, so the preview look and the final look agree.
- setup_render(scene, quality='preview'|'final', resolution=(1280,720)): EEVEE ('BLENDER_EEVEE') with ray tracing, volumetrics + volumetric shadows (volumetric_end large enough for a 3 km scene but sensible tile size), shadows, AgX view transform with a look chosen for a cinematic golden-hour result, film settings, TAA samples (preview ~32, final ~96), motion blur only for final. Verify every property name exists in 5.2.
- setup_lookdev(scene, haze=True, compositor=True): World with Sky Texture (MULTIPLE_SCATTERING, sun direction from the constants, sun disc on), strength tuned so a sun lamp + sky give a rich golden-hour look; a Sun lamp aligned with SUN_DIR (warm colour, small angle for crisp but soft shadows, strength tuned); optional world-volume or large-volume haze that gives atmospheric perspective over hundreds of meters without washing out near objects; compositor: Glare node bloom (find the 5.2 API for the scene compositor node group; it changed in 5.0) + gentle vignette (e.g. ellipse mask or lens distortion) + very subtle colour grading. Must work in background renders.
- camera_look_at(name, location, target, lens=35, collection=None) helper.
- preview(build_fn, out_dir, name='preview', cameras='auto', resolution=(1280,720), footprint=40.0, samples=32, save_blend=None): resets to an empty scene, applies setup_render+setup_lookdev, creates a neutral rock plinth whose top sits at z=-0.4 with radius footprint+6 extending down ~30 m (looks like a karst pillar top), calls build_fn(collection), then frames cameras from the built objects' bounding box. 'auto' cameras: front_34 (from -Y and -X, elevated ~25 deg), front (on the -Y axis, eye height ~10 m, the hero approach), aerial (high oblique ~55 deg), detail (closer, lens 50, on the most detailed region = bbox centre). cameras may also be a list of (name, location, target, lens). Renders each to out_dir/<name>_<cam>.png, prints one line 'PREVIEW_STATS {json}' with object count, evaluated triangles, build seconds, render seconds per camera.
- A CLI so anyone can run: ${BLENDER} --background --factory-startup --python ${ROOT}/sect/lib/look.py -- --target sect.lib.arch:showcase --out ${ROOT}/out/previews/arch --name arch --footprint 40 [--cams front_34,aerial] [--res 1280x720] [--blend path]. --target is module:function; the function receives the collection. For area modules (--target sect.areas.forge:build) the footprint should default to the module's AREA['footprint']. The CLI must put ${ROOT} on sys.path itself.

Test: build a small test target inside look.py's own test (e.g. a few red-lacquer columns, a stepped stone platform and a simple roof-like wedge, a bright emissive orb to test bloom) and render via the CLI. Look at the images. Tune sky strength, sun strength, exposure, haze density and bloom until it looks like a cinematic golden-hour still: warm key light, readable shadows, cool sky fill, no blown-out whites, bloom only on emissive. Also render one wide shot with test boxes placed 50 m, 200 m, 600 m and 1500 m away to tune haze so distance reads but near objects stay crisp. Report the final tuned values.`

const foundation = await parallel([
  () => agent(UTIL_MAT_PROMPT, { label: 'util+materials', phase: 'Foundation', schema: RESULT_SCHEMA }),
  () => agent(LOOK_PROMPT, { label: 'look-dev+harness', phase: 'Foundation', schema: RESULT_SCHEMA }),
])
log('Foundation done: ' + foundation.filter(Boolean).length + '/2 agents returned')

// Integration check of foundation before building on it
const foundationCheck = await agent(`${COMMON}
YOUR JOB: make sure the foundation works together before three teammates build on it. Files: ${ROOT}/sect/lib/util.py, materials.py, look.py and docs/api_util.md, api_materials.md, api_look.md. You may edit these four python files and three docs ONLY to fix integration bugs (look.py's plinth must use materials.get('rock_cliff') now that materials exists; imports; API mismatches; anything broken in 5.2). Do not redesign them.
Run the look.py CLI on a tiny target that uses util + materials (write the target in out/tmp/foundation_check/check_target.py and put that folder on sys.path, or add a small public function look.selftest(collection) in look.py). Render front_34 and aerial into out/previews/foundation_check/ and look at them. Confirm: imports work from the CLI, materials render correctly under the look-dev lighting, bloom works, haze works, PREVIEW_STATS prints.
Foundation authors reported: ${JSON.stringify(foundation)}`,
  { label: 'foundation-check', phase: 'Foundation', schema: RESULT_SCHEMA })

// ---------------- Phase 2-4: build, critique, revise (pipelined per module) ----------------
const MODULES = [
  {
    key: 'arch',
    folder: 'arch',
    file: 'sect/lib/arch.py',
    brief: `Chinese architecture primitives. This is the most important module: roofs make or break the whole scene.
Build in this order and render after each step:
1) roof(name, collection, width, depth, kind, ...) where kind in 'xieshan' (hip-and-gable, the formal hall roof), 'wudian' (hip), 'xuanshan'/'yingshan' (gable), 'pyramid' (square/hex/oct pavilion, any n sides), 'round' (conical for round pavilions). Requirements: concave curved slopes (steeper at ridge, flatter at eave), generous overhang, eave corners that sweep up AND out (qiao jiao) smoothly, real thickness with a visible underside (painted rafters suggested by a ribbed underside or rafter-end row), tile courses as ridged geometry (alternating convex rows) or a convincing corrugation, a row of round tile end-caps along the eaves (instanced), main ridge with chiwen ornaments at both ends, hip ridges with a row of small beast figures ending in an upturned tip, gable triangle for xieshan. Parameters for rise, overhang, curve strength, corner lift, tile material. Double-eave option (chong yan) via a helper that stacks a lower skirt roof.
2) column(...) with marble base (guzheng-like drum) and red lacquer shaft; bracket_band(...) dougong band (stacked blocks/arms in bracket_paint with gold edges) that sits on the column tops under the eaves; beams.
3) lattice_panel(w, h, pattern) for doors/windows (grid, diamond, 'ice-crack' or cloud patterns) as real geometry or instanced bars, backed by paper_screen / paper_screen_lit.
4) platform(w, d, h, style='xumizuo') stepped mouldings in marble; stairs(width, height, run_per_step, ramp=True/False, balustrade=True) with a central carved ramp option; balustrade(points, height) white marble posts with cloud/lotus caps and carved panels, instanced.
5) Composite buildings, all facing -Y: hall(name, collection, bays_w, bays_d, bay=5, column_h=6, roof='xieshan', double_eave=False, platform_h=1.5, stairs=True, lit=False, roof_mat='roof_tile_teal') -> returns root and exposes plaque_anchor (a matrix/empty where a plaque should hang under the upper eave); pagoda(tiers=7, sides=8, radius=9, tier_h=5.5, taper, lit_floors=[], ...) with balconies and a finial spire; pavilion(sides=6, radius, height, roof='pyramid'|'round', double=False); paifang(bays=5, width, height, roofs=True) the ceremonial gate (stepped roofs over bays, centre bay tallest, plaque slot); corridor(points, width) covered walkway (lang); wall(points, height) courtyard wall with tiled cap; moon_gate(radius, wall_width); tower(kind='bell'|'drum').
6) showcase(collection): a hall with double eaves, a pagoda, a hexagonal pavilion, a 5-bay paifang, a corridor, stairs with balustrades, arranged like a small courtyard for previews.
Proportions must follow spec.md section 3 rule 2 (roof 40-55% of building height, deep eaves). Use materials.get names. Use instancing for tiles, end caps, brackets, posts, beasts.`,
  },
  {
    key: 'props',
    folder: 'props',
    file: 'sect/lib/props.py',
    brief: `Props and the magic layer. Required functions (refine signatures, document them):
lantern_hanging(style='palace'|'round', size), lantern_stone(height) (Japanese-style toro is WRONG; use Chinese stone lantern forms), plaque(text_zh, width, vertical=False) using KaiTi C:/Windows/Fonts/simkai.ttf, gold characters on plaque_board with a carved gold frame, readable at distance (test with 明教 and 藏经阁);
banner(height, width, material, pole=True, seed) cloth with natural wind curvature (displace/wave so it is not a flat card; gentle animated wave via modifier/texture offset keyed over frames is a bonus), with pole finial;
cauldron_ding(size, lit=True) bronze three/four-legged ding with handles, relief bands, molten glowing interior + ember sparks; incense_burner(size, smoke=True); bell(size) bronze; drum(size);
guardian_lion(size, mirror=False) or qilin: stylised but recognisable Chinese guardian on a plinth (build from shaped primitives + subdivision; stylised low-poly is fine if elegant);
sword(length, style), and artifact(kind, size) for 15 distinct kinds: sword, bell, mirror, orb, fan, seal, gourd, pagoda_treasure, ruyi, bead_string, flag, spear, lotus_lamp, compass, jade_disc. Each must be clearly distinct in silhouette with jade-glow accents;
chain(p0, p1, link_size, sag) instanced links along a catenary; rope(p0, p1, sag, radius);
jade_tablet(height, glow=True) with tassel and cord; stele(height, glyph_mat, turtle_base=True) tall stone stele with a carved top (dragon-ish arch), glowing glyph columns, on a bixi turtle base;
bamboo_slip_scroll(width, height, curve, glow=True) many jade slips tied with cords, glowing script columns; floating_scroll(width, open=True); book_stack(n);
stone_table, tea_set, cushion, wind_chime, weapon_rack, anvil, ore_pile;
crane(pose='standing'|'flying') elegant red-crowned crane, stylised; koi(seed);
rune_ring(radius, width, kind='trigram'|'sigil'|'script', material) glowing engraved ring geometry (actual glyph-like segment geometry, bagua trigram bars for 'trigram'); light_beam(p0, p1, radius); light_pillar(height, radius); spirit_motes(count, bounds, seed) tiny emissive instanced points; shield_dome(radius).
showcase(collection): lay them out readably (artifacts in a ring, a lit cauldron, banners in a row, stele, lion, plaques, rune rings on the ground, chain between two posts, crane).
Everything stylised-but-elegant, consistent with the palette. Instancing for repeated parts.`,
  },
  {
    key: 'nature',
    folder: 'nature',
    file: 'sect/lib/nature.py',
    brief: `Nature and terrain pieces. Required functions (refine signatures, document them):
pine(height, seed, style='huangshan'): the iconic Huangshan pine - twisted trunk, horizontal layered flat foliage pads (cloud-like tiers) on sweeping branches, possibly leaning; must be instantly recognisable and beautiful in silhouette. Provide several seeded variants cheaply (instancing).
blossom_tree(height, seed, kind='peach'|'plum'), willow(height, seed) with hanging strands, bamboo_clump(count, height, seed), shrubs/grass tufts.
rock(size, seed, kind='boulder'|'scholar'|'ledge') - scholar rocks (taihu stones) with holes and vertical flow; rock_pillar(height, top_radius, bottom_radius, seed, top_flat=True, top_z=0): Zhangjiajie-style sandstone karst pillar with vertical erosion grooves, horizontal strata ledges, moss/grass on ledges and top rim, a few clinging pines (optional flag), the flat top at top_z. world.py will use this for every plateau (top radius footprint+6) and for 100+ backdrop pillars, so provide a cheap LOD mode (lod='hero'|'far').
floating_rock(size, seed) flat-topped with inverted craggy cone; pond(radius or points, depth) water surface + rim stones; waterfall(height, width, seed) layered falling sheets with animated flowing noise (texture offset keyed over frames) + splash mist volume at base; lotus_patch(radius, count, seed); cloud_puff(size, seed) volumetric cumulus puff for EEVEE (soft, not cubic; density shaped by a falloff); cloud_bank(size, seed) a wide flat bank of puffs; scatter_on(surface_obj, prototypes, density, seed, max_slope, scale_range) geometry-nodes scattering helper (verify 5.2 node names).
showcase(collection): a rock pillar with pines, a pond with lotus and a scholar rock, a blossom tree, a willow, bamboo, a waterfall off a ledge, a few cloud puffs, a floating rock.
Quality: foliage must look lush and stylised (dense pads, not sparse sticks), cliffs must look massive and eroded, not blobby. Watch triangle budgets (spec section 3) and use instancing.`,
  },
]

const results = await pipeline(
  MODULES,
  // stage 1: build
  (m) => agent(`${COMMON}
YOUR JOB: write ${ROOT}/${m.file} and ${ROOT}/docs/api_${m.key}.md. Preview folder: out/previews/${m.folder}/. Other teammates are concurrently writing the other lib modules; the foundation (util.py, materials.py, look.py) is done - read docs/api_util.md, api_materials.md, api_look.md first and USE them. Do not edit foundation files: if you need a material that does not exist, use materials.register(...) inside your own module (prefix the name with '${m.key}_'). If you find a real foundation bug, work around it and report it in known_issues.
Preview with the look.py CLI (see docs/api_look.md), target sect.lib.${m.key}:showcase, plus any extra close-ups you need.
${m.brief}
Foundation check report: ${JSON.stringify(foundationCheck)}`,
    { label: `build:${m.key}`, phase: 'Build', schema: RESULT_SCHEMA }),
  // stage 2: critique with two lenses in parallel
  (built, m) => parallel([
    () => agent(`${COMMON}
YOU ARE A CRITIC, lens = ART DIRECTION + CHINESE ARCHITECTURAL/CULTURAL AUTHENTICITY. Do NOT edit ${m.file}. You may render extra views into out/previews/${m.folder}-critic-art/ using the look.py CLI (target sect.lib.${m.key}:showcase or a small script of your own in out/tmp/${m.folder}-critic-art/).
Review module ${ROOT}/${m.file}. Look at every image the author produced and render more angles yourself (including a close-up and a far view). Compare against spec.md sections 3 and 4: does it read as Chinese xianxia (proportions, roof curves, eave sweep, materials, ornament, plaque calligraphy) or as generic fantasy / Japanese / low-effort procedural? Is it beautiful? Would it hold up in a cinematic fly-through? Be specific and harsh; give concrete fixes (numbers, functions).
Author's report: ${JSON.stringify(built)}`,
      { label: `critic-art:${m.key}`, phase: 'Critique', schema: CRITIQUE_SCHEMA }),
    () => agent(`${COMMON}
YOU ARE A CRITIC, lens = TECHNICAL QUALITY. Do NOT edit ${m.file}. You may run scripts into out/previews/${m.folder}-critic-tech/ and out/tmp/${m.folder}-critic-tech/.
Review module ${ROOT}/${m.file} and docs/api_${m.key}.md: Blender 5.2 API correctness (run things, do not guess), determinism (build twice, compare), idempotence (call each public function several times in one scene: unique names, no material/mesh duplication explosions), instancing actually used for repeated parts, triangle counts vs the spec budget, normals/shading artifacts, z-fighting, gaps, floating parts, bevels on visible hard edges, parameters that break at extreme but plausible values (very wide halls, 3-tier vs 9-tier pagodas, tiny/huge sizes), docs matching code. Render renders to verify visual artifacts and LOOK at them. Report concrete, reproducible issues with fixes.
Author's report: ${JSON.stringify(built)}`,
      { label: `critic-tech:${m.key}`, phase: 'Critique', schema: CRITIQUE_SCHEMA }),
  ]).then((crits) => ({ built, crits: crits.filter(Boolean) })),
  // stage 3: revise
  (r, m) => agent(`${COMMON}
YOUR JOB: revise ${ROOT}/${m.file} and docs/api_${m.key}.md (you own them now). Preview folder: out/previews/${m.folder}/ (overwrite the showcase images with the improved versions; add _v2 suffix to keep before/after for key shots).
Two critics reviewed the module. Fix every high and medium issue; fix low ones when cheap. If you disagree with a finding, verify by rendering, and explain in known_issues. Then re-render the showcase and close-ups and LOOK at them; keep iterating until the module is genuinely production quality for a cinematic fly-through.
Original brief: ${m.brief}
Author's earlier report: ${JSON.stringify(r.built)}
Critiques: ${JSON.stringify(r.crits)}`,
    { label: `revise:${m.key}`, phase: 'Revise', schema: RESULT_SCHEMA }),
)

// ---------------- Phase 5: integration ----------------
phase('Integrate')
const integration = await agent(`${COMMON}
YOUR JOB: integration pass over the whole library before eleven area builders start using it. Files: ${ROOT}/sect/lib/*.py and ${ROOT}/docs/*.md. You may fix integration bugs anywhere in sect/lib (imports, name collisions between modules' registered materials, inconsistent signatures, broken docs) but do not redesign modules.
1) Write ${ROOT}/sect/lib/showcase_all.py with build(collection): a small sect courtyard using all modules together (a double-eave hall on a platform with stairs and balustrades, a plaque 任务殿 under its eave, lanterns, banners, a pagoda, a pavilion by a pond with lotus, pines on a rock pillar, a blossom tree, a lit cauldron with a few floating artifacts, a stele, a rune ring, a chain, a waterfall, cloud puffs). Render it with the look.py CLI (footprint 45) into out/previews/integration/ from front_34, front, aerial, detail and LOOK at the images.
2) Write ${ROOT}/docs/LIB_API.md: the single reference the area builders will read. For every public function in util, materials, look, arch, props, nature: signature, what it builds, real-world size it produces with default args, which way it faces, what it returns (root object, plaque_anchor, etc.), and a one-line example. Include the list of material names, the preview CLI command, and a 'gotchas' section (Blender 5.2 API quirks the team discovered, instancing patterns, how to avoid z-fighting with plinth/paving, emission limits).
3) Report remaining weaknesses honestly.
Module reports: ${JSON.stringify(results)}`,
  { label: 'integrate', phase: 'Integrate', schema: RESULT_SCHEMA })

return { foundation, foundationCheck, modules: results, integration }
