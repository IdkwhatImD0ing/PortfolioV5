# Real-time web fly-through: pipeline recipe (first test)

Researched 2026-10-15. Scope of the first test: Mountain Gate to Heart-Mirror Terrace, chase camera
`chase.cam` frames 1-288 of `out/sect_chase.blend`, shown at `/sect` with three.js and lighting baked
in Blender Cycles on the rented RTX 5090. Items marked **later** are not needed for the first test.
Items marked **verify** are API details that could not be checked without Blender; check them once on
the box (one `print` is enough) before building on them.

## 0. Decisions at a glance

| Topic | Decision | Why |
|---|---|---|
| Baked lighting | Bake **Combined** (diffuse direct + indirect + emission; no glossy, no transmission) per area into atlases on a new UV layer `bake`. Denoise in the compositor, apply the scene grade + AgX Punchy + exposure there, save 8-bit sRGB PNG. The web draws these unlit. | Every sect material is procedural (`docs/api_materials.md`), so there are no albedo textures to keep. Baking the view transform into the texture makes the web match Blender exactly; three's AgX is not Blender's AgX Punchy + CDL. |
| Not `lightMap` | Do not ship linear lightmaps + `MeshStandardMaterial.lightMap` (uv1) in the first test. | It would need web tone mapping (mismatch above) and separate albedo maps we do not have. Kept as an option in section 6. |
| Renderer | R3F `<Canvas flat>` (NoToneMapping), output sRGB. Postprocessing: Bloom + Vignette only. Never a ToneMappingEffect. | Baked textures already contain the tone curve. |
| Loader | three's own `GLTFLoader` (r186) through R3F `useLoader`, with three's `MeshoptDecoder`. Not drei `useGLTF`. | drei's `useGLTF` uses three-stdlib's older loader copy. Keeping one three version for the loader and the KTX2 transcoder avoids mismatches. |
| Compression | Windows Node script with glTF Transform 4.5.1: dedup, instance, flatten, join (keeps hotspot and glow nodes), unlit, prune, WebP q90 (max 2048), meshopt (positions 16 bit, UVs 14 bit). | No extra tools needed. KTX2 is **later** and needs KTX-Software's `ktx` 4.4+ on PATH. |
| Texel density | Per object, from its nearest distance to the camera path (known in advance): about 2.5 screen px per texel at closest approach, cap 40 px/m, floor 2 px/m. Atlases 2048². | Spends texels where the camera actually goes. |
| Vegetation | Near the path (< ~80 m): realized, decimated, baked into the atlases. 80-300 m: GPU-instanced low-LOD meshes. 300 m-1.5 km: instanced crossed-quad cards. LOD chosen once from distance to the path. | 13k trees cannot be unique geometry; the camera is on rails, so static LOD is enough. |
| Sky | World-only equirect panorama rendered in Cycles, used as `scene.background`. Gradient from meta.json as fallback. | The world is at infinity, so the panorama is correct from any camera position. |
| Fog | Replace three's fog shader chunks once: exponential haze with height falloff plus a dense cloud layer below y ≈ 15. Constants from meta.json. | three's `FogExp2` (squared) and `Fog` (smoothstep) cannot match Blender's volume haze. |
| Camera | 288 samples. Catmull-Rom on position, slerp on rotation, lerp on fovY. Scroll maps to frames with extra dwell at holds; exponential damping; `?frame=N` jumps with no damping. | Smooth at any scroll speed, deterministic for screenshots. |

## 1. Packages (npm registry, checked 2026-10-15)

The client locks React 19.2.6 and Next 15.2.8 (`client/pnpm-lock.yaml`).

| Package | Pin | Notes |
|---|---|---|
| `three` | 0.186.1 | Latest (2026-09-24). Inside `postprocessing`'s peer range `>=0.168 <0.187`. Do not jump to 0.187 until `postprocessing` widens its range. |
| `@types/three` | 0.186.0 | Matches. |
| `@react-three/fiber` | 9.8.1 | Peer `react >=19 <19.4`, fine with 19.2.6. 9.8.2 came out 2026-10-14 and should also work; 9.8.1 has had three weeks of use. |
| `@react-three/postprocessing` | 3.1.3 | Needs fiber >= 9.7. Fixes the composer not resizing when the DPR changes (matters with adaptive DPR). 3.2.0 (2026-10-10) also fine. Its `EffectComposer` defaults: HalfFloat buffers, `multisampling` 4, and it forces `toneMapping = NoToneMapping` while mounted. |
| `postprocessing` | 6.39.5 | Peer of the above. |
| `@react-three/drei` | 10.7.9 | Optional. Use only `PerformanceMonitor` (and maybe `Stats`). Skip `useGLTF` and `useDetectGPU` (the latter downloads benchmark data from a CDN at runtime). |
| dev: `@gltf-transform/core`, `/functions`, `/extensions`, `/cli` | 4.5.1 | All four at the same version. |
| dev: `meshoptimizer` | 1.3.0 | Encoder for the pack script. |
| dev: `sharp` | 0.35.5 | WebP encoder. Ships prebuilt Windows binaries (`@img/sharp-win32-x64`). If pnpm 10 lists sharp under ignored build scripts, check `node -e "require('sharp')"`; the prebuilt binary normally loads anyway. |

```bash
# run in E:/Github/PortfolioV5/client
pnpm add three@0.186.1 @react-three/fiber@9.8.1 @react-three/postprocessing@3.1.3 postprocessing@6.39.5 @react-three/drei@10.7.9
pnpm add -D @types/three@0.186.0 @gltf-transform/core@4.5.1 @gltf-transform/functions@4.5.1 @gltf-transform/extensions@4.5.1 @gltf-transform/cli@4.5.1 meshoptimizer@1.3.0 sharp@0.35.5
```

Not needed: `lenis` (native scroll + our own damping), `maath`, `three-stdlib`, `transpilePackages`
(three ships ESM). WebGPU: R3F 9 + pmndrs `postprocessing` are WebGL-only, so stay on `WebGLRenderer`.

## 2. Next.js wiring (App Router, client-only canvas, code splitting)

- `src/app/sect/page.tsx`: a server component. `export const metadata: Metadata = { title: "Sect test", robots: { index: false, follow: false } }` (this overrides the root layout's `index: true`). Renders `<SectClient />`. Not linked anywhere; `src/app/sitemap.ts` only lists `/`, so leave it alone.
- `src/app/sect/sect-client.tsx`: `'use client'` + `const SectScene = dynamic(() => import('./sect-scene'), { ssr: false, loading: () => <Poster /> })`. Next 15 rejects `ssr: false` inside a server component, so this wrapper is required.
- `src/app/sect/sect-scene.tsx` (and children): the only modules that import `three` / R3F. Because they are only reachable through the dynamic import, three lands in a chunk loaded only on `/sect`. Check with `pnpm build`: the `/` route's first-load JS must not grow.
- `src/lib/sect/*.ts`: pure logic with vitest tests (node environment is already configured): manifest/meta/camera parsing, camera sampling, scroll-to-frame mapping, damping, FOV adaptation, fog constants, quality tier, budget math.

Canvas settings:

```tsx
<Canvas
  flat                                   // NoToneMapping; baked textures already carry the tone curve
  dpr={tier === 'low' ? 1 : [1, 1.5]}
  gl={{ antialias: tier === 'low', powerPreference: 'high-performance', stencil: false }}
  camera={{ near: 0.5, far: 9000, fov: 35 }}
  style={{ position: 'fixed', inset: 0 }}
>
```

The page is a fixed canvas plus a tall, empty scroll spacer (section 8). Load each GLB under its own
`<Suspense>` with the gate GLB first, so the opening view appears before the mirror area finishes.
Show a poster image while loading (a 1280×720 WebP of the start frame) and keep it as the fallback
when WebGL2 is unavailable.

## 3. Blender side (rented 5090 only, via `tools/rblender.py`)

Never save over `sect_chase.blend`. Each script opens it, works in memory, writes outputs under
`out/web/` (copied back to this PC), and keeps raw EXR bakes in a folder outside `out/` on the box
(for example `E:/Github/PortfolioV5/blender/xianxia-sect/bakecache/`), so regrading does not need
a re-bake and large EXRs are not copied back every run.

### 3.1 Decide what to export (visibility along the path)

1. Step through frames 1-288 (every 2nd frame is enough). For every mesh, and for every instance from
   `depsgraph.object_instances`, project the 8 world-bbox corners with
   `bpy_extras.object_utils.world_to_camera_view(scene, cam, co)`. Visible if any corner has
   `-0.1 <= x,y <= 1.1` and `z > 0`. Record `d_min`, the smallest camera-to-bbox distance over all frames.
2. Classes: HERO (visible, `d_min` < 80 m) gets a unique bake. MID (visible, 80 m-1.5 km) gets a
   low-density bake or instancing. FAR (> 1.5 km) goes into the low-poly backdrop or the panorama.
3. Never export: collection `flyer` (but keep `chase.cam`, which lives in it), the haze and cloud
   volumes, look-dev helpers. Everything else stays in the scene during the bake as a shadow and
   bounce source. The golden-hour sun is low, so far objects cast long shadows into the areas.

### 3.2 Prepare bake targets

- Collection instances: `bpy.ops.object.duplicates_make_real()`. Geometry-node scatters:
  `bpy.ops.object.convert(target='MESH')` (realizes instances and applies modifiers). Then
  `bpy.ops.object.make_single_user(object=True, obdata=True)`.
- Decimate (modifier `DECIMATE`, `COLLAPSE`) dense meshes **before** unwrapping. Rough target:
  one triangle per 20-50 screen px² at the object's closest approach. Never simplify after baking:
  the UVs would slide off the baked texels. That is why the pack script turns simplification off.
- Hotspots: join each hotspot's parts into one mesh object (e.g. `hotspot.gate`, `hotspot.mirror`,
  plus a few natural click targets such as the gate's name plaque or the pond) with custom
  properties `hotspot` and `label`. Objects with emission get a custom property `glow` (the value
  the spec already uses, e.g. 3). Both stay separate meshes through the pack step.

### 3.3 Texel density from the camera path

The chase lens is 32 mm on a 36 mm sensor (`sect/chase_plan.py`), so at 16:9 the horizontal FOV is
58.7° and the vertical FOV is about 35°. At 1920 px wide one pixel spans `α = 2·tan(29.35°)/1920 ≈ 5.9e-4` rad.

```
texel size  s = k · α · d_min        (k = 2.5 screen px per texel)
density     ρ = clamp(1/s, 2, 40) px/m
texels      T = Σ area_i · ρ_i² / 0.7      (0.7 = packing efficiency)
atlases     n = ceil(T / 2048²)
```

Examples: `d_min` 10 m gives 68 px/m (capped to 40); 20 m gives 34; 40 m gives 17; 80 m gives 8.5;
200 m gives 3.4. Group objects into atlases by area and distance. Stay at 2048² (works on every
phone; one 4096² RGBA texture is 89 MB of GPU memory). Expect roughly 6-12 atlases for the two areas;
measure with the formula before baking.

### 3.4 Lightmap UVs (layer `bake`)

Per object:

```python
uv = me.uv_layers.get("bake") or me.uv_layers.new(name="bake")
me.uv_layers.active = uv                     # UV operators act on the active layer
# edit mode, select all faces
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0,
                         area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
```

Then scale that object's UVs (numpy via `uv.data.foreach_get/foreach_set("uv", ...)`) by
`ρ_i · sqrt(world_area_i / uv_area_i)`, so UV area is proportional to world area × ρ². Join the
non-hotspot objects of one atlas group (same-named UV layers merge), then pack the joined mesh and the
group's hotspot meshes together in multi-object edit mode:

```python
bpy.ops.uv.pack_islands(rotate=True, scale=True, merge_overlap=False,
                        margin_method='FRACTION', margin=8 / 2048, shape_method='CONCAVE')
```

`pack_islands(scale=True)` scales everything uniformly, so the per-object density ratios survive.
8 px gaps at 2048 plus a 16 px bake margin keep bleeding away until mip level 3 (where the object is
tiny on screen). `uv.lightmap_pack` makes one island per face; avoid it for architecture (many seams,
wasted margin). Check: `bpy.ops.uv.select_overlap()` selects nothing.

### 3.5 Bake (Cycles 5.2, OptiX)

```python
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
for d in prefs.devices: d.use = (d.type == 'OPTIX')
sc.cycles.samples = 512                      # 256 for MID atlases; denoised afterwards
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 1
sc.cycles.transparent_max_bounces = 8; sc.cycles.sample_clamp_indirect = 10   # tame fireflies
atlas = bpy.data.images.new("atlas_00", 2048, 2048, alpha=False, float_buffer=True)  # scene linear
# every material on the group's objects: an unlinked Image Texture node with image=atlas, set as nodes.active
bpy.ops.object.bake(type='COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'EMIT'},
                    uv_layer='bake', margin=16, margin_type='EXTEND', use_clear=True,
                    target='IMAGE_TEXTURES')
# denoiser guide: same objects, type='DIFFUSE', pass_filter={'COLOR'}, 16 samples, into atlas_00_albedo
```

- Glossy is off on purpose. A bake must pick one view direction ("Above Surface" or "Active Camera"),
  which is wrong for a moving camera. Shiny things get small web-side effects (section 7).
- Materials are shared between atlases. Before each atlas bake, point the bake-target node in each
  involved material at that atlas. Only selected objects are baked.
- Render-disable during the bake: `world.haze`, the cloud fog layer, cloud banks, the flyer. Keep the
  world shader (sky and cloud floor light the scene from below) and the sun.
- The look was tuned in EEVEE. Cycles traces more bounce light, so shadows will come out lighter.
  Before baking everything, render one Cycles still at frame 93 with haze off and compare it with the
  EEVEE reference. Fix brightness with exposure in the post step, not by changing lights.
- Save the raw float bakes as OpenEXR half into `bakecache/`.
- Alternative for distant, low-poly meshes: `target='VERTEX_COLORS'` needs no UVs at all. **later**

### 3.6 Post step: denoise, grade, view transform

Blender 5.x still has no bake denoiser; use the compositor Denoise node (OpenImageDenoise) with the
albedo bake as a guide. Do it in a separate empty scene so the "render" costs nothing.

```python
post = bpy.data.scenes.new("bakepost")
post.render.engine = 'CYCLES'; post.cycles.samples = 1
post.render.resolution_x = post.render.resolution_y = 2048; post.render.resolution_percentage = 100
for k in ("view_transform", "look", "exposure", "gamma"):          # copy AgX, 'AgX - Punchy', +0.25
    setattr(post.view_settings, k, getattr(src.view_settings, k))
post.display_settings.display_device = src.display_settings.display_device
post.render.image_settings.file_format = 'PNG'
post.render.image_settings.color_mode = 'RGB'; post.render.image_settings.color_depth = '8'
ng = bpy.data.node_groups.new("bakepost", 'CompositorNodeTree')
post.compositing_node_group = ng           # Blender 5.x: scene.use_nodes / scene.node_tree are gone
ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
# Image(beauty EXR) -> Denoise(Image; Albedo = albedo EXR; HDR on; Prefilter Accurate)
#   -> the ASC-CDL ColorBalance + ColorCorrection + HueSat nodes exactly as sect/lib/look.py
#      setup_compositor builds them, but WITHOUT Glare and WITHOUT the vignette (both are screen-space;
#      the web does them) -> NodeGroupOutput
post.render.filepath = "E:/Github/PortfolioV5/blender/xianxia-sect/out/web/tex/atlas_00.png"
bpy.ops.render.render(write_still=True, scene=post.name)
```

**verify**: in 5.x several node options became input sockets (look.py already sets the ColorBalance
"Type" through a socket). Print `[s.name for s in denoise.inputs]` once and set HDR / Prefilter by
socket if they are there, else by the old properties. `sect/lib/look.py` around line 627
(`setup_compositor`) is a working 5.2 example of building this tree.

Without denoising (e.g. a 2048-sample MID atlas), `img.save_render(path, scene=post)` also applies the
scene view transform when it writes a float image to PNG ("Save as Render").

Check the result: pick 5 texels on sunlit marble, shade, red column, teal roof and grass, and
compare with the same surfaces in a Cycles camera render (haze off). They should agree within about
3/255. Grading iterations (to move toward `kf_gate.png` / `kf_mirror.png`: warmer highlights, more
saturation on reds and teals) only rerun this post step on the stored EXRs.

### 3.7 Export

- Per atlas, one material `baked.<atlas>`: Image Texture (the PNG, sRGB) on UV map `bake`, into the
  Base Color of a Principled BSDF. That is the simplest node setup the exporter understands; the pack
  script then marks every material `KHR_materials_unlit` (three makes `MeshBasicMaterial`). Delete
  every other UV layer first, so the bake UV is `TEXCOORD_0` and no `uv1` is needed.
- Exporter call (5.2 names; **verify** once with
  `print(sorted(bpy.ops.export_scene.gltf.get_rna_type().properties.keys()))`):

```python
bpy.ops.export_scene.gltf(filepath=".../out/web/raw/gate.glb", export_format='GLB',
    use_selection=True, export_apply=True, export_texcoords=True, export_normals=False,
    export_extras=True, export_materials='EXPORT', export_image_format='AUTO',
    export_cameras=False, export_lights=False, export_animations=False, export_yup=True,
    export_gpu_instances=False)
```

- `export_extras=True` writes custom properties to glTF `extras`; three puts them in `object.userData`.
- three renames nodes: `PropertyBinding.sanitizeNodeName` turns spaces into `_` and deletes
  `. : / [ ]` (so `gate.roof.001` becomes `gateroof001`). The original name is kept in
  `object.userData.name`. Look hotspots up by `userData.hotspot`, never by name.
- Blender 5.2's exporter can write meshopt itself (`export_meshopt_compression_enable`). Leave that
  off; the Windows step compresses everything the same way.
- One GLB per group: `gate.glb`, `mirror.glb`, `trees.glb`, `backdrop.glb`. The manifest lists them in
  load order, gate first.

### 3.8 Trees and other vegetation

The trees are collection instances and geometry-node scatters of a few prototypes (`sect/lib/nature.py`).

- NEAR (visible, `d_min` < ~80 m): realize, decimate to roughly 3-5k triangles per tree, bake into the
  area atlases like everything else. Their light and shadows then match the ground exactly.
  Cap the total near-tree triangles around 400k.
- MID (80-300 m): keep them as shared-mesh instances of a decimated prototype (~800 triangles). Bake
  the prototype once at the origin with sky light only (no sun), because instances have random yaw and
  a baked sun side would rotate with them. On the web add a cheap sun term from the normal
  (`baked × (ambient + sunColour × wrap(N·L))`). Export them as plain nodes sharing one mesh; the
  pack step's `instance()` turns them into `EXT_mesh_gpu_instancing`, which three loads as one
  `InstancedMesh` per prototype. Give each area its own copy of the prototype mesh so each area gets
  its own batch and can be frustum-culled (three culls an `InstancedMesh` by the sphere around all its
  instances).
- FAR (300 m-1.5 km): crossed-quad cards (2 quads, 4 triangles) with a sprite rendered from each
  prototype in Cycles (transparent film, same view transform), `alphaTest` 0.5. Plain
  `MeshBasicMaterial` works; no custom shader needed.
- LOD is static: each tree's class comes from its `d_min` along the known path, so there is no runtime
  LOD switching. drei `<Detailed>` (a `THREE.LOD` wrapper) only helps for a handful of single objects.
- **later**: a per-instance shadow tint. In Blender, ray-cast from each crown toward the sun
  (`scene.ray_cast`) and store 0.55-1.0 in `obj["shade"]`; write it as an `_COLOR_0` instance
  attribute (three maps that to `instanceColor`) with a 40-line variant of glTF Transform's `instance()`.

### 3.9 Sky panorama and far backdrop

- Sky: hide every object, camera `cam.data.type = 'PANO'`, `cam.data.panorama_type = 'EQUIRECTANGULAR'`,
  rotation (90°, 0, 0) at any position, Cycles 64-128 samples, 4096×2048, same colour management.
  Save `sky.webp` (about 1-2 MB). It contains only the world, so it is exact from every camera
  position. Include the high cirrus layer if you want clouds in it (it is far enough).
  If the world shader's painted sun disc is in it, still draw a small HDR sun sprite on the web at the
  same spot so bloom picks it up.
- Backdrop: karst pillars and peaks beyond ~1.5 km. Decimate to 2-5 %, bake at 1-2 px/m into one or
  two atlases (`backdrop.glb`). Objects beyond ~5 km can go into the panorama instead (a 250 m path
  shifts a 5 km object by under 3°).

### 3.10 camera.json and meta.json

Axis change: three = (bx, bz, −by), which is a −90° rotation about X. Cameras look down local −Z with
+Y up in both programs, so the camera needs no extra local correction.

```python
import math, json
from mathutils import Matrix
from bpy_extras.object_utils import world_to_camera_view
C = Matrix.Rotation(-math.pi / 2, 4, 'X')
sc = bpy.context.scene; cam = sc.objects['chase.cam']
W, H = sc.render.resolution_x, sc.render.resolution_y
frames, prev = [], None
for f in range(1, 289):
    sc.frame_set(f)
    loc, rot, _ = (C @ cam.matrix_world).decompose()
    if prev is not None and rot.dot(prev) < 0: rot.negate()   # keep quaternions on one hemisphere
    prev = rot.copy()
    d = cam.data                                  # assert d.shift_x == d.shift_y == 0
    horiz = d.sensor_fit == 'HORIZONTAL' or (d.sensor_fit == 'AUTO' and W >= H)
    if horiz:
        fov_x = 2 * math.atan(d.sensor_width / (2 * d.lens))
        fov_y = 2 * math.atan(math.tan(fov_x / 2) * H / W)
    else:
        size = d.sensor_height if d.sensor_fit == 'VERTICAL' else d.sensor_width
        fov_y = 2 * math.atan(size / (2 * d.lens))
    frames.append({"f": f, "p": [round(v, 4) for v in loc],
                   "q": [round(v, 6) for v in (rot.x, rot.y, rot.z, rot.w)],   # Blender is (w,x,y,z)
                   "fovY": round(math.degrees(fov_y), 4)})
```

- `startFrame`: the first frame where all 8 corners of the gate's world bbox project inside
  `[0.03, 0.97]` with `z > 0`, the camera is above the cloud layer (Blender z > `CLOUD_SEA_Z + 75`
  = 15 m) and outside the opening cloud bank (`OPENING_BANK` in `sect/world.py`).
- Optional extra key `refAspect` (render W/H, 16/9) helps the web adapt the FOV (section 8).
- meta.json, all positions and directions in three space, colours as sRGB hex picked from the Blender
  reference render (display values):
  - `sun`: `dir` = direction toward the sun = sun lamp `matrix_world.to_quaternion() @ (0,0,1)`, converted; `color`.
  - `sky`: `zenith`, `horizon`; optional `panorama: "sky.webp"` and `panoramaRotationY`.
  - `fog`: `color`, `range: [near, far]` for the plain fallback, plus `density` (0.0003 /m, from
    `world.HAZE`), `baseY` (100), `falloff` (220), `cloudTop` (15), `cloudDensity`, `sunColor`.
  - `moon`: `position`, `size` (from `look.moon_placement`). `cloudSea`: `y` = −60 (`CLOUD_SEA_Z`).
  - `waterfalls`: `[{name, position, size: [w, h], rotation: [x, y, z, w]}]` (a quaternion avoids Euler-order mistakes).
  - `hotspots`: `[{id, label, center, size}]`. Convert the bbox center as (cx, cz, −cy) and the size as (sx, sz, sy).

## 4. Compression on Windows (glTF Transform)

`client/scripts/sect-pack.mjs`, run as `node scripts/sect-pack.mjs <raw.glb> <public/sect/proto/x.glb>`:

```js
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, instance, flatten, join, weld, unlit, prune, textureCompress, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import sharp from 'sharp';

const [input, output, size = '2048'] = process.argv.slice(2);
await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(input);
const joinable = (node) => { const x = node.getExtras() ?? {}; return !('hotspot' in x) && !('glow' in x); };
await doc.transform(
  dedup(),
  instance({ min: 3 }),                       // shared meshes -> EXT_mesh_gpu_instancing (uses world TRS)
  flatten(),                                  // join only merges siblings
  join({ keepNamed: false, filter: joinable }),
  weld(),
  unlit(),                                    // all materials -> KHR_materials_unlit (skip for the flyer)
  prune(),                                    // also drops NORMAL on unlit meshes
  textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 90, resize: [+size, +size] }),
  meshopt({ encoder: MeshoptEncoder, quantizePosition: 16, quantizeTexcoord: 14 }),
);
await io.write(output, doc);
```

- Why not `gltf-transform optimize` as is: its defaults turn on `simplify` (breaks baked UVs),
  `palette`, joins named nodes (would swallow the hotspots), and quantize UVs to 12 bits
  (half a texel at 2048). The script above sets each step on purpose.
- Quantization volume stays per mesh (default); 16-bit positions give mm precision on a 100 m chunk.
- WebP lossy is always 4:2:0 chroma, so colours bleed about 1 px at island edges; the 16 px bake
  margin covers that.
- Report: `pnpm exec gltf-transform inspect public/sect/proto/gate.glb` lists triangles, draw calls
  and an estimated GPU memory figure.
- **later** KTX2 (lower GPU memory, needed for mobile at scale): install KTX-Software 4.4.2
  (`KTX-Software-4.4.2-Windows-x64.exe` from its GitHub releases; glTF Transform 4.5.1 calls
  `ktx create` and requires `ktx` >= 4.4.0 on PATH; the legacy `toktx` is not used). For baked colour,
  UASTC is the safe mode: `pnpm exec gltf-transform uastc in.glb out.glb --level 4 --rdo --rdo-lambda 4 --zstd 18`.
  ETC1S is 3-4× smaller but blocks up smooth lighting gradients. Web side: copy
  `node_modules/three/examples/jsm/libs/basis/basis_transcoder.{js,wasm}` to `public/sect/basis/` and
  `new KTX2Loader().setTranscoderPath('/sect/basis/').detectSupport(gl)`.

GPU memory per texture (with mipmaps, ×4/3): WebP/PNG decode to RGBA8, so 2048² = 22.4 MB and
1024² = 5.6 MB. KTX2 UASTC transcodes to BC7/ASTC at 1 byte/px (5.6 MB for 2048²); ETC1S to
BC1/ETC1 at 0.5 byte/px (2.8 MB).

## 5. Loading in the page

```ts
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
const gltf = useLoader(GLTFLoader, `/sect/proto/${file}`, (loader) => {
  loader.setMeshoptDecoder(MeshoptDecoder);
  // later: loader.setKTX2Loader(ktx2)
});
```

- three r186's loader supports `EXT_meshopt_compression` and `KHR_meshopt_compression`,
  `EXT_mesh_gpu_instancing` (including `_COLOR_0` to `instanceColor`), `EXT_texture_webp`,
  `KHR_texture_basisu` and `KHR_materials_unlit`. The meshopt decoder is embedded JS + WASM, no file to host.
- After load, traverse once: make sure baked meshes use `MeshBasicMaterial` with `fog: true`; set
  `map.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy())` (ground at grazing angles);
  `matrixAutoUpdate = false` on static nodes. For `userData.glow`: `material.color.setScalar(glow)` so the
  colour goes above 1.0 and only these surfaces bloom.
- Hotspot clicks: test the pointer ray against the `meta.hotspots` boxes (`Box3`). Do not attach
  R3F pointer handlers to the big merged meshes; R3F raycasts every object that has a handler.

## 6. Colour rules (no double tone mapping)

1. Baked atlases, card sprites and the sky panorama are display-referred sRGB (Blender's AgX Punchy,
   exposure and grade are inside). The loader sets `colorSpace = SRGBColorSpace` on base colour maps;
   for textures you load yourself, set it by hand.
2. The renderer never tone maps: `<Canvas flat>`. The `EffectComposer` also forces `NoToneMapping`.
   Never add `ToneMappingEffect`. With nothing in between, three decodes sRGB to linear and
   encodes it back on output: an exact round trip, so the screen shows Blender's pixels.
3. Web-only colours (fog, sky gradient, cloud sea, waterfalls, sun glow) are sRGB hex values picked
   from Blender reference renders and passed as `new Color('#rrggbb')`. ColorManagement converts them
   to linear and the output converts back, so they also round-trip.
4. Only bloom sources go above 1.0 (glow materials, the sun sprite, the mirror glint).
5. Lit materials (only the optional flyer) have no tone curve, so keep light intensities low enough
   that nothing clips, or give the flyer its own small bake.
6. If tiled albedo + separate lightmaps are ever needed: export the lightmap UV as `TEXCOORD_1`,
   load the lightmap separately, set `texture.channel = 1`, `material.lightMap = tex` and
   `lightMapIntensity = Math.PI` (three multiplies the lightmap by 1/π in both `MeshBasicMaterial` and
   `MeshStandardMaterial`). That path is linear and would then need a web tone curve, which is why it
   is not the first choice.

## 7. Atmosphere on the web

- **Fog** (the most important piece for matching Blender): before any material compiles (right after
  meta.json loads), replace `THREE.ShaderChunk.fog_pars_vertex`, `fog_vertex`, `fog_pars_fragment` and
  `fog_fragment`, writing meta values in as GLSL constants, and use `scene.fog = new FogExp2(color, density)`
  so three keeps `fogColor` and `fogDensity` updated. Vertex side: after `vFogDepth = -mvPosition.z;` add
  `vFogWorldPos = transpose(mat3(viewMatrix)) * (mvPosition.xyz - viewMatrix[3].xyz);` (works for
  instanced meshes too, because `mvPosition` already includes `instanceMatrix`). Fragment side:

```glsl
vec3 rd = vFogWorldPos - cameraPosition; float t = length(rd); rd /= max(t, 1e-4);
// haze: density fogDensity below FOG_BASE_Y, halving every ~0.69*FOG_FALLOFF metres above it
float b = 1.0 / FOG_FALLOFF; float k = rd.y * b;
float od = fogDensity * exp(-max(cameraPosition.y - FOG_BASE_Y, 0.0) * b)
         * (abs(k) > 1e-5 ? (1.0 - exp(-k * t)) / k : t);
// cloud layer: dense below CLOUD_TOP, thinning above with scale CLOUD_SCALE
float b2 = 1.0 / CLOUD_SCALE; float k2 = rd.y * b2;
od += CLOUD_DENSITY * exp(-(cameraPosition.y - CLOUD_TOP) * b2)
    * (abs(k2) > 1e-5 ? (1.0 - exp(-k2 * t)) / k2 : t);
float fogFactor = 1.0 - exp(-od);
vec3 fogCol = mix(fogColor, SUN_FOG_COLOR, pow(max(dot(rd, SUN_DIR), 0.0), 8.0));  // golden toward the sun
gl_FragColor.rgb = mix(gl_FragColor.rgb, fogCol, fogFactor);
```

  Clamp every `exp()` argument to [-80, 80]: a steep downward ray into the cloud layer otherwise
  overflows to infinity, and some mobile GPUs then return NaN (black pixels).
  The analytic height-fog form is from Íñigo Quílez's fog article. With density 0.0003 /m (`world.HAZE`),
  a horizontal view below 100 m is veiled about 16 % at 600 m and 36 % at 1.5 km. The fog colour must
  equal the panorama's horizon colour so distant rock melts into the sky. **later**: sample the panorama
  in the view direction at a blurry mip for the fog colour.
- **Sky**: `scene.background = skyTexture` with `mapping = EquirectangularReflectionMapping`,
  `colorSpace = SRGBColorSpace`; line it up once with `scene.backgroundRotation.y` so the sun in the
  image sits at `meta.sun.dir`. The background ignores fog. Fallback: a back-side sphere with a
  zenith-to-horizon gradient shader (`depthWrite: false`, `fog: false`).
- **Sun and moon**: additive sprites far away (inside the camera's far plane). The sun sprite colour is
  above 1.0 so it blooms. The moon is a textured disc at `meta.moon`.
- **Cloud sea**: a large plane (or a 6 km disc) at `y = -60` with a small shader: two scrolling samples of
  a 256² tiling noise texture (made at runtime in a `DataTexture`), lit by a fake Lambert from the noise
  gradient and the sun direction, warm tops and cool shadows picked from the reference render, faded to
  the fog colour with distance. The cloud fog term above hides where cliffs and stairs enter it.
  2-4 soft billboard cloud banks near the cliffs add depth. **later**: bake the Blender cloud-sea mesh
  at about 1 px/m and only add motion on top.
- **Waterfalls**: one plane each from `meta.waterfalls`, `MeshBasicMaterial` with a vertical streak
  texture, `wrapS/T = RepeatWrapping`, `texture.offset.y` advanced each frame, transparent, soft edges,
  fog on. An additive mist sprite at the base.
- **Bloom and vignette**:
  `<EffectComposer multisampling={4}><Bloom mipmapBlur luminanceThreshold={1} luminanceSmoothing={0.2} intensity={0.6} /><Vignette offset={0.3} darkness={0.5} /></EffectComposer>`.
  Threshold 1.0 means only HDR sources bloom, like look.py's scene-linear threshold 2.0. Tune the
  vignette to look.py's 22 % corner darkening.
- **Shiny surfaces**: the pond gets `envMap = sky panorama` (equirect) with `combine: MixOperation` and
  `reflectivity` about 0.5. **later**, desktop high tier only: a planar reflection (three's `Reflector`
  or drei `MeshReflectorMaterial`) at 512 px, active only around frames 166-287. The bronze mirror gets
  an HDR glint sprite whose strength follows `dot(view, reflect(-sunDir, mirrorNormal))`.
- **later**: falling petals as one instanced draw call (~400 quads, drift in the vertex shader).

## 8. Scroll-driven camera

All of this is pure logic in `src/lib/sect/` with tests.

- **Sampling at a fractional frame t**: `i = floor(t)`, `s = t - i`. Position: uniform Catmull-Rom on
  samples i-1..i+2 (clamped at the ends). Rotation: slerp from q[i] to q[i+1] (the export already keeps
  them on one hemisphere). fovY: lerp. 288 samples is about 20 KB of JSON.
- **Scroll to frame**: one scroll unit per frame from `startFrame` to `frameEnd`, plus `dwell` units (e.g.
  40) at each hold where the frame stays put. With about 12 px per unit the page is about 4-5 screens
  tall. Scroll 0 maps to `startFrame`, so the page opens on the gate in full view (frames before
  `startFrame` rise out of the clouds and are skipped). Optional: CSS `scroll-snap-type: y proximity`
  on invisible anchors at the holds.
- **Damping**: `x += (target - x) * (1 - Math.exp(-lambda * dt))`, `lambda` about 6 per second, `dt`
  clamped to 0.1 s. `prefers-reduced-motion`: large lambda, stop cloud/waterfall/petal motion.
- **`?frame=N`**: compute the scroll position for frame N (inverse mapping), scroll there, set the
  damped value straight to the target, then set `document.body.dataset.sectReady = "1"` after all GLBs
  loaded and two frames rendered. Screenshot agents wait for that attribute. Set
  `history.scrollRestoration = 'manual'` so reloads are deterministic.
- **FOV for other aspect ratios**: keep the reference horizontal FOV
  (`fovX = 2·atan(tan(fovY/2)·refAspect)`) and compute `fovY_web = clamp(2·atan(tan(fovX/2)/aspect), fovY, 70°)`.
  Portrait phones then see the centre bay instead of a narrow slit; the sides crop once fovY hits 70°.
- Camera `near` 0.5 m, `far` 9000 m. No logarithmic depth buffer (it disables early depth testing).

## 9. Budgets, quality tiers, debug HUD

My targets for this test (not from a standard): numbers count only what the scene draws, not the
5-10 extra full-screen passes from postprocessing.

| | desktop | mobile / low tier |
|---|---|---|
| Triangles drawn per frame | <= 1.5 M | <= 400 k |
| Draw calls | <= 120 | <= 60 |
| Texture GPU memory | <= 300 MB (about 12 atlases at 2048² WebP) | <= 120 MB (1024² variants or KTX2) |
| Download for frames 1-288 | <= 20 MB | <= 8 MB |
| Download before the first view | <= 8 MB | <= 4 MB |
| DPR | 1 to 1.5 | 1 |
| Postprocessing | Bloom + Vignette | off (sprites stay but do not glow) |

- Tier: `low` if the pointer is coarse and (`navigator.deviceMemory` <= 4 or `hardwareConcurrency` <= 4),
  or `MAX_TEXTURE_SIZE` < 4096. No WebGL2: show the poster only. At runtime drei `PerformanceMonitor`
  steps DPR down (1.5 to 1.25 to 1) and then turns bloom off.
- **later**: an optional manifest key `sceneLow` with 1024² variants (run the pack script with `1024`).
- HUD (`?debug=1`): set `gl.info.autoReset = false`; reset in a `useFrame` with priority -1 and read
  `gl.info.render.calls`, `.triangles`, `gl.info.memory.textures` in a `useFrame` with priority 2
  (after the composer, which renders at priority 1). Show fps, draw calls, triangles, textures and the
  current frame. Headless Playwright WebGL is software-rendered, so its fps means nothing; the counts
  are what to check.

## 10. Verification for the first test

1. Blender reference stills at frames 93 and 217, 1280×720 (EEVEE final as before, plus a Cycles
   still with haze off).
2. Web screenshots at `/sect?frame=93` and `/sect?frame=217`, viewport 1280×720 (16:9, so fovY is used
   unchanged). Composition must line up with the reference (this checks the axis and FOV math).
   Colours should match within a few levels on sunlit marble, shade, roofs and columns (this checks
   the colour rules).
3. Look for seams and light leaks at roof and wall junctions (UV margin or texel density too low).
4. `?debug=1` counts within the budget table; `gltf-transform inspect` sizes within the download budget.
5. `/sect` with no query: the first view is the gate in full view, not cloud.

## Sources

- glTF Transform 4.5.1 CLI and functions source (`optimize` defaults, `join` `filter`, `instance`,
  `prune` drops NORMAL on unlit, quantize defaults, `ktx` >= 4.4.0 check): https://gltf-transform.dev/cli,
  https://unpkg.com/@gltf-transform/cli@4.5.1/src/cli.ts, https://unpkg.com/@gltf-transform/cli@4.5.1/src/transforms/toktx.ts
- three r186 sources: `GLTFLoader.js` (extensions list, `_COLOR_0`, texCoord to `texture.channel`),
  `meshbasic.glsl.js` and `lights_fragment_maps.glsl.js` (lightMap × 1/π), `fog_fragment.glsl.js`,
  `PropertyBinding.sanitizeNodeName`, `Scene.backgroundRotation`: https://unpkg.com/three@0.186.1/
- drei 10.7.9 `useGLTF` uses three-stdlib: https://unpkg.com/@react-three/drei@10.7.9/core/Gltf.js
- @react-three/postprocessing 3.2.0 `EffectComposer` defaults (HalfFloat, multisampling 4, forces
  NoToneMapping): https://unpkg.com/@react-three/postprocessing@3.2.0/dist/index.js; release notes:
  https://github.com/pmndrs/react-postprocessing/releases
- pmndrs postprocessing README, "Tone Mapping" and "Output Color Space": https://github.com/pmndrs/postprocessing
- R3F releases (React 19.2/19.3 support, 9.8.x fixes): https://github.com/pmndrs/react-three-fiber/releases
- Next.js lazy loading, `ssr: false` only in client components: https://nextjs.org/docs/app/guides/lazy-loading
- Blender 5.2 manual: Render Baking (pass filters, margin types, "View From"), Denoise node,
  glTF 2.0 add-on (GPU instances limits, unlit, extras): https://docs.blender.org/manual/en/latest/render/cycles/baking.html,
  https://docs.blender.org/manual/en/latest/compositing/types/filter/denoise.html,
  https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html
- Blender Python API: `bpy.ops.object.bake` (`uv_layer`, `margin_type`), `bpy.ops.export_scene.gltf`
  (5.2 adds meshopt export): https://docs.blender.org/api/current/bpy.ops.object.html,
  https://docs.blender.org/api/current/bpy.ops.export_scene.html
- Blender 5.0 compositor API change (`scene.compositing_node_group`, Composite node replaced by Group
  Output): https://developer.blender.org/docs/release_notes/5.0/compositor
- KTX-Software releases (4.4.2 latest 4.x; 5.0 exists): https://github.com/KhronosGroup/KTX-Software/releases
- Analytic height fog: Íñigo Quílez, "fog" article, https://iquilezles.org/articles/fog/
