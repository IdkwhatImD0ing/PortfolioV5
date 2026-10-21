export const meta = {
  name: 'xianxia-blocking',
  description: 'Block out the 11 sect areas and the floating celestial mountain range, assemble them, plan the fly-through camera in <=12 s segments, review and fix',
  phases: [
    { title: 'Build', detail: 'one author per area + one for the floating range / sky' },
    { title: 'Assemble', detail: 'place areas, build the segmented camera path, render stills' },
    { title: 'Review', detail: 'check every segment for readability, clipping, mood' },
    { title: 'Fix', detail: 'apply review fixes, re-render stills' },
  ],
}

const ROOT = 'E:/Github/PortfolioV5/blender/xianxia-sect'
const BLENDER = 'python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py'

const COMMON = `
You are part of a team blocking out a xianxia (Chinese cultivation fantasy) sect in Blender 5.2 with Python: a celestial realm, a mountain range floating in the sky. The Blender render is the BLOCKING (layout + camera) for an AI video model that will generate the final look, so shape, outline, scale, colour coding and camera matter; fine detail does not.
FIRST read ${ROOT}/spec.md completely, especially section 0 (the blocking update, which overrides older text), section 4 (section-to-area map, anchors, area briefs, camera briefs) and section 5 (module contracts incl. CAMERA_HINTS). Then read the library docs ${ROOT}/docs/api_util.md, api_materials.md, api_look.md, api_arch.md, api_props.md, api_nature.md (skim the lib source where docs are thin). The library is finished and more detailed than needed: USE it, do not polish it.
Hard rules:
- Blender runs ONLY on a rented cloud GPU (the user is gaming on this PC: never start blender.exe locally). Use the wrapper exactly like the blender executable: ${BLENDER} --background --factory-startup --python <script> -- <args>. It uploads the project source (sect/, spec.md, docs/, small text files under out/tmp/) to the cloud box at the same path, runs Blender there with your arguments unchanged, streams the output back, and copies every file the run wrote under out/ back to this PC when it finishes. Use absolute forward-slash paths (E:/Github/PortfolioV5/blender/xianxia-sect/...). Paths Blender prints start with "/E:/..." (the mirror on the box): the same file is at "E:/..." on this PC once the run returns. Read the wrapper's docstring (tools/rblender.py) once. Never touch the user's open Blender (never call mcp__blender__* tools). Never use Higgsfield or any paid generation service.
- An earlier attempt was interrupted: if your file(s) already exist, read them and continue from them instead of starting over (keep what works, fix what does not).
- Only edit the files you own (named below). Do NOT edit sect/lib/* (work around gaps inside your own file; report real library bugs in known_issues).
- Write previews only into out/previews/<your-folder>/ and scratch files into out/tmp/<your-folder>/.
- About twelve teammates run Blender at the same time on one cloud RTX 5090. Keep previews <= 1280x720, EEVEE preview quality, no long renders. The first render of each run includes ~20 s of shader compilation; later frames take about a second.
- Blender 5.x APIs differ from older versions; introspect at runtime or use mcp__blender__search_api_docs (offline docs) instead of guessing.
- LOOK at your renders with the Read tool. Iterate on what matters for blocking: correct scale, readable silhouettes, the focal object, no clipping, a frame that reads instantly as Chinese xianxia. Then stop: time box about 20-30 minutes of work.
`

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    files_written: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    camera_hints: { type: 'array', items: { type: 'string' } },
    preview_images: { type: 'array', items: { type: 'string' }, description: 'absolute paths, best views first' },
    stats: { type: 'string' },
    known_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['files_written', 'summary', 'preview_images', 'known_issues'],
}

const ASSEMBLY_SCHEMA = {
  type: 'object',
  properties: {
    files_written: { type: 'array', items: { type: 'string' } },
    blend_file: { type: 'string' },
    timeline_json: { type: 'string' },
    segments: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          index: { type: 'number' },
          frame_start: { type: 'number' },
          frame_end: { type: 'number' },
          seconds: { type: 'number' },
          areas: { type: 'array', items: { type: 'string' } },
          start_still: { type: 'string' },
          end_still: { type: 'string' },
          description: { type: 'string', description: 'what the camera does and sees, second by second' },
        },
        required: ['index', 'frame_start', 'frame_end', 'areas', 'start_still', 'end_still', 'description'],
      },
    },
    contact_sheet: { type: 'string' },
    stills: { type: 'array', items: { type: 'string' } },
    render_command: { type: 'string', description: 'exact command to render the full blocking video frames' },
    seconds_per_frame: { type: 'number' },
    known_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['files_written', 'blend_file', 'timeline_json', 'segments', 'contact_sheet', 'render_command', 'known_issues'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    overall: { type: 'string' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          where: { type: 'string', description: 'segment / frame / area / file' },
          problem: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['severity', 'where', 'problem', 'fix'],
      },
    },
    images_reviewed: { type: 'array', items: { type: 'string' } },
  },
  required: ['overall', 'issues', 'images_reviewed'],
}

const AREAS = [
  { key: 'gate', section: 'hero', extra: 'The opening of the film: the camera pushes out of a cloud bank and rises up the stairway axis toward the gate, then flies through the centre bay. Gate silhouette against the sky and the stairway descending into the clouds below are the shot. Lantern pairs on landings, banners, guardian beasts, sword monoliths: blocky is fine.' },
  { key: 'mirror', section: 'about', extra: 'Pond, hexagonal pavilion, zig-zag bridge, giant round bronze mirror on a stand facing the approach, a blossom tree. Few, clear pieces.' },
  { key: 'forge', section: 'projects', extra: 'Forge hall with open front, colossal glowing ding cauldron, a ring of 15 floating artifacts (props.artifact kinds) around it, chimneys. A slow orbit of the ring (one rotating parent Empty, keyframed linear over frames 1-1500) is enough animation.' },
  { key: 'arena', section: 'hackathons', extra: 'Floating island: circular dueling platform with a bagua inlay, ~40 banner poles around the rim (materials.banner_cloth(i)), spectator tier on one side, giant stone sword piercing the island at the back, inverted craggy underside with hanging roots, chains running off to the sides.' },
  { key: 'mission', section: 'experience', extra: 'Grand double-eave hall on a platform, broad plaza, the mission wall with 7 large glowing jade tablets as the focal point on the axis, bell and drum towers.' },
  { key: 'library', section: 'education', extra: 'Tall 7-tier octagonal pagoda (arch.pagoda) with 3 lit floors, a lotus pool, glowing scrolls drifting in a spiral around the pagoda (one rotating parent Empty, linear keyframes over frames 1-1500).' },
  { key: 'steles', section: 'skills', extra: 'Rows of tall steles on turtle bases with glowing glyphs (4-6 glow colours = skill categories), a central aisle >= 12 m wide with nothing over it below 14 m, steles <= 8 m, covered corridors framing the courtyard, larger central stele under a small pavilion at the far end.' },
  { key: 'scroll', section: 'resume', extra: 'Two-storey pavilion on the cliff edge and, floating in front of it, the colossal unrolled jade bamboo-slip scroll (~22 m wide, 9 m tall, slightly curved, glowing script) that the camera passes in front of.' },
  { key: 'formation', section: 'architecture', extra: 'A huge circular plaza (~100 m) with concentric glowing rune rings, 8 array-flag pillar nodes and a central floating core, linked by light beams forming a NETWORK (hub, clusters, cross-links: like a system architecture diagram), a light pillar into the sky, a faint dome. Must read as a diagram from the high overhead camera.' },
  { key: 'abode', section: 'personal', extra: 'Your own cliff face (~60 m) behind the plateau with a round moon-gate cave entrance, a wooden balcony with a tea table, a waterfall beside it into a misty pool, a peach blossom tree, bamboo, a resting crane.' },
  { key: 'summit', section: 'footer', extra: 'Circular marble terrace on the highest peak, a round two-tier pavilion with moon-white tiles, a lone pine leaning over the edge, a crescent-moon arch. Last frames look up past the terrace to the colossal moon (world.py places it NNE, ~16 deg elevation), so the silhouette against the sky must be clean.' },
]

const WORLD_BRIEF = `YOUR JOB: write ${ROOT}/sect/world.py and ${ROOT}/docs/api_world.md. Preview folder out/previews/world/, scratch out/tmp/world/.
world.build(scene, anchors) per spec.md section 5; also expose ANCHORS (the table in spec.md section 4: key -> (x, y, z, footprint)). Build the CELESTIAL REALM from spec.md section 0:
1) Sky + sun via sect.lib.look (same constants the previews used). Heavenly mood: vast sky, a cloud sea far below (look.setup_world has a cheap procedural cloud floor; prefer cheap over volumetric where it reads the same), a few cloud banks at mid level drifting between peaks, high thin clouds if cheap.
2) The colossal moon: ~14 deg wide, NNE, ~16 deg elevation, several km away, simple crater shading, soft halo. The final shot of the film.
3) THE FLOATING MOUNTAIN RANGE: one continuous chain of steep, craggy Huangshan/Zhangjiajie-like peaks and ridges that rises from the gate (south, anchor z=40) to the summit (north, z=320), floating in the sky. Under every anchor except arena: a flat terrace at anchor z - 0.4 with radius footprint + 6, then steep slopes. Between consecutive anchors: ridges/saddles that stay at least 25 m below the straight line between them (the camera flies roughly along that line at anchor height + 10..30 m). Taller spires and side peaks OFF the corridor (|distance from the corridor| > 120 m) give the range-and-canyon feel. The range's underside is inverted craggy rock with hanging roots dissolving into cloud; the whole thing floats, no ground anywhere. The gate's stairway descends its south slope (gate builds the stairs; just leave a slope there). The abode builds its own cliff face; the arena floats over a gap in the range between the forge and mission areas. Build it at blocking resolution (a few hundred thousand triangles total is plenty): e.g. a heightfield top + an underside with a tapered rim, or a union of big rock masses; use nature.rock_pillar / floating_rock where they help.
4) 20-40 smaller floating islets around the range (some with a pine or a tiny pavilion), 3-5 waterfalls pouring off edges into the void, at least 5 connectors between consecutive areas (stairways along ridges, arched or chain bridges, floating stepping stones) that do not cross the camera corridor at camera height.
5) The film opens INSIDE a cloud bank around (0, -260, 15) that the camera pushes out of: put a soft cloud bank there.
Preview with simple stand-in blocks at each anchor sized to its footprint (the area modules are being written right now). Render: (a) from (0,-200,30) looking north up the range; (b) a high oblique overview of the whole range from the south-west; (c) mid-route near the formation anchor looking north-east; (d) from the summit (0,1500,330) toward the moon. LOOK at them; iterate on silhouette, the floating feel, depth, the moon. Report seconds per frame at 1280x720 preview quality.`

const ITEMS = [
  ...AREAS.map((a) => ({ ...a, kind: 'area', file: `sect/areas/${a.key}.py`, folder: a.key })),
  { key: 'world', kind: 'world', file: 'sect/world.py', folder: 'world' },
]

function buildPrompt(it) {
  if (it.kind === 'world') return `${COMMON}\n${WORLD_BRIEF}`
  return `${COMMON}
YOUR JOB: write ${ROOT}/${it.file} (create ${ROOT}/sect/areas/__init__.py as an empty file if it does not exist). Preview folder out/previews/${it.folder}/, scratch out/tmp/${it.folder}/.
Area '${it.key}' for site section '${it.section}'. Brief: spec.md section 4 (table row + numbered brief for '${it.key}'). Contract: spec.md section 5 (AREA dict, build(collection) returning '${it.key}.root', CAMERA_HINTS, front faces -Y, z=0 walkable top, footprint, '${it.key}.' name prefix, no world/render changes, plaque with title_zh).
Direction: ${it.extra}
Preview with the look.py CLI (--target sect.areas.${it.key}:build); render the auto cameras and every CAMERA_HINTS view. LOOK, fix the obvious, stop.`
}

phase('Build')
const built = await parallel(ITEMS.map((it) => () =>
  agent(buildPrompt(it), { label: `build:${it.key}`, phase: 'Build', schema: RESULT_SCHEMA })
    .then((r) => ({ key: it.key, result: r }))))
const ok = built.filter((b) => b && b.result)
log(`Built ${ok.length}/${ITEMS.length}: ${ok.map((b) => b.key).join(', ')}`)
const missing = ITEMS.map((i) => i.key).filter((k) => !ok.find((b) => b.key === k))
if (missing.length) log(`Missing (assembly must stub them): ${missing.join(', ')}`)

phase('Assemble')
const ASSEMBLY_BRIEF = `YOUR JOB: write ${ROOT}/sect/assemble.py and ${ROOT}/sect/camera.py (you own both), produce ${ROOT}/out/sect.blend, ${ROOT}/out/section_timeline.json, and stills. Folders: out/previews/assembly/, out/stills/, scratch out/tmp/assembly/.
1) assemble.py (runnable: blender --background --factory-startup --python sect/assemble.py -- [--quality blocking|preview] [--out out/sect.blend]): new scene, look.setup_render + look.setup_lookdev (blocking quality: fast; keep the golden-hour look), world.build(scene, anchors), then every area module's build() into its own collection named after its key, root moved to its anchor and rotated by a yaw so the area's front (local -Y) faces the direction the camera arrives from. If an area module fails to import or build, log it, place a labelled stand-in block, and continue. Report evaluated triangle count and build time.
2) camera.py: camera.build(scene, anchors, area_modules) creates ONE camera on ONE continuous smooth path through every area in section order (gate -> mirror -> forge -> arena -> mission -> library -> steles -> scroll -> formation -> abode -> summit), using each area's CAMERA_HINTS transformed to world space, honouring the camera briefs in spec.md section 4 (out of the cloud bank and up the gate stairs then through the centre bay; low over the arena; along the stele aisle at ~4 m; high overhead at the formation; ending tilted up at the moon past the summit). Smooth position AND smooth look-at (no snapping), gentle speed easing (slower at each area's hero view, faster in transit), slight banking on turns. Check clearance against the scene with BVH ray casts/nearest-point queries every frame: at least 5 m from geometry (except intentionally flying through the gate bay and the stele aisle). 24 fps, total about 50-70 s.
3) SEGMENTS for the AI video model: split the flight into consecutive segments of at most 12 s (288 frames) each, at calm moments (not mid-turn), each segment covering 1-3 whole areas. Write out/section_timeline.json: {"fps":24,"frame_start":1,"frame_end":N,"sections":[{"section_id","area","frame_start","frame_end","hero_frame"}...],"segments":[{"index","frame_start","frame_end","areas":[...]}...]}.
4) Render stills with EEVEE at 1280x720: the first and last frame of every segment (out/stills/seg<NN>_start.png / _end.png), each area's hero frame (out/stills/hero_<area>.png), and a contact sheet of one frame per second (montage via Blender compositing or Python PIL-free tiling; ffmpeg is on PATH and can tile: ffmpeg -i frames -vf tile=8x8). LOOK at them.
5) Choose blocking render settings that render a 1280x720 frame in about 1 s or less on the cloud RTX 5090 while keeping the look readable (low TAA samples, no motion blur, volumetrics off or minimal), store them as quality='blocking' in assemble.py, and report the exact wrapper command to render all frames to out/frames/####.png on the box (frames must stay on the box: render with a script that does not write under out/ until you want them copied back, or tell the wrapper user to expect a large copy). Do NOT render the full animation yourself.
6) Save out/sect.blend (everything built, camera active, frame range set) with the wrapper's --fetch-blend flag so the .blend is copied back to this PC.`

const assembled = await agent(`${COMMON}\n${ASSEMBLY_BRIEF}\nBuild reports: ${JSON.stringify(ok)}`,
  { label: 'assemble+camera', phase: 'Assemble', schema: ASSEMBLY_SCHEMA })

phase('Review')
const review = await agent(`${COMMON}
YOU ARE THE REVIEWER of the assembled fly-through. Do NOT edit files. Render extra frames into out/previews/review/ if needed (open out/sect.blend in background Blender and render specific frames at 960x540).
Look at the contact sheet, every segment start/end still and every hero still. For each segment judge: does each area read instantly (focal object visible, right scale, Chinese xianxia silhouette)? Any clipping through geometry, near misses, empty sky-only frames, ugly angles, jumps between consecutive frames, segment boundaries mid-turn? Does the whole thing feel like a celestial realm floating in the sky with a clear climb from gate to summit and the moon finale? Is each segment a good, self-contained 8-12 s shot for an AI video model? Also check spec.md compliance of placement (fronts facing the camera, nothing floating by accident, areas sitting on terraces, connectors not crossing the camera path).
Assembly report: ${JSON.stringify(assembled)}`,
  { label: 'review', phase: 'Review', schema: REVIEW_SCHEMA })

phase('Fix')
const fixed = await agent(`${COMMON}
${ASSEMBLY_BRIEF}
YOUR JOB NOW: you own sect/assemble.py, sect/camera.py and may make SMALL targeted fixes in sect/world.py and sect/areas/*.py when the reviewer found placement/scale/clipping problems there. Apply every high and medium review issue, then re-run assembly, re-render the segment stills, hero stills and contact sheet, LOOK at them, and re-save out/sect.blend and out/section_timeline.json.
Previous assembly report: ${JSON.stringify(assembled)}
Review: ${JSON.stringify(review)}`,
  { label: 'fix', phase: 'Fix', schema: ASSEMBLY_SCHEMA })

return { built: ok.map((b) => ({ key: b.key, summary: b.result.summary, known_issues: b.result.known_issues, previews: b.result.preview_images.slice(0, 3) })), missing, assembled, review, fixed }
