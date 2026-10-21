<!-- Research of 2026-10-19: ready-made assets that could replace the procedural mountains, trees and grass. Nothing bought or downloaded. -->

# Asset recommendation for the /sect fly-through

There are better-looking assets for every item on your list. Most are free and safely licensed.

- **Rocks, peaks and grass:** free public-domain scans (CC0) are enough. CC0 means any use and no credit needed.
- **Trees:** the best-looking pines are paid Fab packs, and Fab's licence is a grey area for a public website. There is a free fallback, but it looks less good.

I recommend a small test first, called a pilot below. It changes one area and costs $0, or $30 if you approve one paid pine pack.

One thing to expect: each area shares a single 4096 px baked texture. So the 8K detail in these scans mostly disappears. The real improvements are better tree shapes and natural rock colour and banding. That is still the part that looks bad now.

## Which style

Use photoreal scans with your own shapes. Your buildings and lighting are baked in Cycles, so painted stylised assets would clash with them. AI-generated 3D is only good for rock pillars, and it's an optional test. It turns needles, leaves and grass into solid lumps.

## What I recommend for each item

### (a) Background peaks and pillars

**Far mountain ranges.** Use real elevation data: maps that store the ground height for every 30 m square. Import it into Blender with the free BlenderGIS add-on.
- NASADEM or SRTM (public domain): https://data.usgs.gov/datacatalog/data/USGS:EROS5e83a3ee1af480c5
- Copernicus GLO-30 (free, but needs a copyright line): https://registry.opendata.aws/copernicus-dem/
  - The line is: "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved".
- Tiles for Huangshan (N30 E118) and Guilin (N24 E110) give real ridges and tower karst.
- Zhangjiajie pillars are too thin to show at 30 m. The data only gives you the valleys there.
- BlenderGIS: https://blendergis.com/

**Pillars.** Keep your procedural pillar shapes. Replace their rock shader with scanned rock textures, projected from all sides (triplanar):
- Poly Haven rock_face_02 (banded sandstone): https://polyhaven.com/a/rock_face_02
- Poly Haven marble_cliff_06 (grey-buff layers, 8.1 m tile, so it repeats less): https://polyhaven.com/a/marble_cliff_06
- ambientCG Rock063 (layered mossy cliff): https://ambientcg.com/view?id=Rock063
- Blend moss in by slope: https://ambientcg.com/view?id=Moss001

All are CC0 and free. This is the cheapest big improvement.

**Optional hero pillar shape:** Sand Hollow Spire (CC-BY, 560K faces): https://sketchfab.com/3d-models/sand-hollow-spire-11351b04aa0e445d9bd8cf9602b631ee. Decimate it, retexture it, and add a green cap with pines.

**Optional stylised far layer:** Shahriar Shahrabi's "The Vast Land" (CC-BY): https://sketchfab.com/3d-models/the-vast-land-733b802f5a4743ef99ad574279d49920. It is painterly. Only try it as the farthest misty layer.

### (b) Close cliffs and rocks

All Poly Haven, CC0, free, with glTF or .blend downloads:
- rock_face_01 (20K triangles): https://polyhaven.com/a/rock_face_01
- rock_face_02 (30K): https://polyhaven.com/a/rock_face_02
- mountainside (288K): https://polyhaven.com/a/mountainside
- All cliffs: https://polyhaven.com/models/nature/rocks-stone/cliffs-rock-faces
- Floating-island undersides: flip boulders such as https://polyhaven.com/a/boulder_01 upside down.

### (c) Pines and other trees

Your tree system already uses a few prototype trees per species. It bakes each one into a light near mesh and far cards (flat pictures of the tree). So swapping a species means replacing one prototype, not every tree.

**Free and safe:**
- Japanese Black Pine by matt z chan (CC-BY, 158.8k triangles): https://sketchfab.com/models/f0cb4705f1c446c7bc393fdbfcdf024a. Good windswept shape, but only one model.
- ffish.asia CC0 black pine twig scan: https://sketchfab.com/models/78a7f47b3e7d4cad9d3316af821e6845
  - Use it to make real needle cards for your existing pine skeletons. This alone may fix much of the "bad" look.
  - Red pine scan: https://sketchfab.com/3d-models/cc0-japanese-red-pine-pinus-densiflora-a21a0843495a4235882873c121512a94

**Best looking, paid, grey licence:**
- Pinus taiwanensis 01 by 3DGardenPlants, $29.99 for 9 trees. Taiwan red pine is close kin to the Huangshan pine. https://www.fab.com/listings/af669a49-a880-434c-897f-afb419c47d7c
- Single Pinus taiwanensis trees by 3DTree, $8.99 each, for variety: https://www.fab.com/listings/b7d2379d-c978-4d16-b18b-a00c1746f29c

**Willow:**
- Salix babylonica 05, $29.99 on Fab (grey licence): https://www.fab.com/listings/7d7f49cf-aa42-4d6e-8965-fdc3a910ad89
- The free route is to keep your procedural willow and give it photo leaf cards.

### (d) Bamboo and blossom

- **Bamboo:** Free Bamboo Set by JonhGillessen (CC-BY, 37.8k triangles, ready for games): https://sketchfab.com/models/e9f9fa5397814f81bf85ad06acf5bf30
- **Blossom:** ffish.asia CC0 sakura branch scan, used to make blossom cards for your existing peach and blossom trees: https://sketchfab.com/models/f5e6f5a985ea4fc2a14ee0b4b37572b5
- **Paid option:** 3DTree Prunus persica, $9.99 (grey licence): https://www.fab.com/listings/f0657559-e0ea-461d-bf4a-2ad166ed9135

### (e) Grass and ground

**Lawns:** use a photo texture instead of modelled blades. It costs zero triangles. All Poly Haven CC0:
- sparse_grass (includes a grass/soil mask): https://polyhaven.com/a/sparse_grass
- leafy_grass: https://polyhaven.com/a/leafy_grass
- grass_ground: https://polyhaven.com/a/grass_ground

**Grass tufts:** make a few cross-shaped clumps of flat cards from the ambientCG grass textures, then scatter copies of them (CC0):
- https://ambientcg.com/view?id=Foliage008
- https://ambientcg.com/list?category=Foliage

**Lotus:**
- Light option: Lotus Flower by Valery.Li (CC-BY, 77.5k triangles): https://sketchfab.com/models/ebb4ed6bd8c442be88f9cdf7f0ebcf27
- Best botanical match: ffish.asia CC0 Indian lotus (1.5M triangles, bake it to cards): https://sketchfab.com/models/d69e1be5895f40e484f0db472a721c2f
- Cheap lily pads: Water lily by Mariia Melnik (CC-BY, 360 triangles): https://sketchfab.com/3d-models/water-lily-04dd636204cd4b0db45a4fc82efa4385

**Reeds:**
- Reed Plants Pack by Nicholas-3D (CC-BY, 1,619 triangles): https://sketchfab.com/models/bc77ea5218e44f2dbc23b2a4aef0c898
- Ridge grass: CC0 Chinese silver grass scan: https://sketchfab.com/models/99f88f1b9a6b4313bc2380addee29791

**Shaded cliff ledges:** fern_02 (https://polyhaven.com/a/fern_02) and moss_01 (https://polyhaven.com/a/moss_01).

## Licence risks

**Safe**
- CC0 (Poly Haven, ambientCG, ffish.asia, NASADEM).
- CC-BY, as long as you add a credits line.

**Grey area**
- Fab Standard, which includes Megascans and the paid pines above.
- What it allows: any engine, no credit needed, and the Personal tier is fine under $100k revenue.
- The problem: it says you must stop visitors from pulling the asset out. Anyone can open a public GLB file.
- What lowers the risk: your pipeline ships only decimated, re-baked meshes merged into area files, never the original files. Add a "no extraction or reuse" line to the site terms.
- This lowers the risk but does not remove it. It is not legal advice.
- The same applies to Superhive (Maxtree Vol 24 at $175, Per's scans). Get the creator's written OK first.

**What would change this: ship the scene in a scrambled format**
- Today the site serves plain .glb files. Anyone can save one from the browser's Network tab and open it in Blender.
- If the packer encrypts each file and the browser decrypts it before loading, no standard 3D program can open what is downloaded.
- TurboSquid's licence asks for exactly this: models "must be contained in proprietary formats so that they cannot be opened or imported in a publicly available software application or framework, or extracted without reverse engineering. WebGL exports from Unity, Unreal, and Lumberyard are permitted." (https://www.turbosquid.com/licensing)
- Fab: "you must restrict end users from extracting or otherwise using Content outside of the Project." (https://www.fab.com/eula)
- CGTrader Royalty Free: allowed "as long as the 3rd party cannot retrieve it on its own." (https://help.cgtrader.com/hc/en-us/articles/360015124437-Royalty-Free-License)
- With the scrambled format, Fab moves from grey to fine, and TurboSquid, CGTrader and (probably) BlenderKit Royalty Free come back into play. A determined person can still capture meshes from the graphics card; the licences accept that, as the Unity/Unreal clause shows.

**Do not use**

| Asset or source | Why |
|---|---|
| TurboSquid | Bans open formats on the web |
| Blendkit Royalty Free items | Bans open-format models in web apps |
| botaniq | Can't share the assets in any form |
| CGTrader Royalty Free | Requires blocking extraction |
| The Grove | Requires that trees can't be extracted |
| Synty | Needs written permission |
| SpeedTree | Subscription, and no redistribution |
| Any CC BY-NC, CC BY-ND or Editorial model (for example Old Man of Hoy) | Non-commercial, no-changes or news-only licences |
| Megascans "UE-only" content | Unreal Engine only |
| YF Cliff Pine, So Stylized Asia, Magicvalley Guilin | Unreal-only packs |
| "Sagano Bamboo Forest" | Ripped from a Gran Turismo 4 map |
| Galaxy Abundant lotus | Unclear origin |
| WonderFuel packs | AI-generated |
| Self-hosted Hunyuan3D 2.1 | Its licence excludes the EU, UK and South Korea |
| Lijiang River texture | Probably satellite imagery the uploader can't licence. The shape alone is fine. |

## Cost and effort

**Cost**
- The free path costs $0.
- The best-looking paid upgrade is about $30 to $50 (one Taiwan pine pack, plus a few $8.99 singles).

**Effort, roughly**

| Job | Time | What it involves |
|---|---|---|
| Retexture rocks | About 1 day plus bake time | Swap the rock shader for scan textures, then rebake. No new geometry. |
| Far ranges from elevation data | About 1 day | Import, crop, reduce to roughly 50 to 100k triangles per range, bake. |
| Each new tree species | About 1 to 2 days | Import, scale to real height, cut the trunk down to a few thousand triangles, make needle cards from the twig scan, register it as the species prototype. Your existing tree bake then makes the near meshes and far cards. |
| Grass | About 1 day | Lawn textures and card clumps. Lotus and reeds are about half a day each. |
| Credits page | Small | Lines for the CC-BY models. |

## Pilot

Do one area first. Compare it with the current look before changing anything else.

1. **Peak.** Retexture one pillar with rock_face_02 or marble_cliff_06 and moss blended in by slope. Add one far Huangshan ridge from the elevation data.
2. **Pines.** Make three versions of the Huangshan pine prototype:
   - your current skeleton with CC0 twig needle cards;
   - the matt z chan pine;
   - optionally, the $29.99 Taiwan pine, if you approve.
3. **Ground.** Poly Haven lawn texture plus ambientCG grass clumps.
4. **Compare.** Render the same hold frames before and after with `bake_trees.py verify`. Check that the area file stays near its 8 MB budget.

## Credits lines (if used)

- "Japanese Black Pine by matt z chan, CC BY 4.0, modified."
- "Free Bamboo Set by JonhGillessen, CC BY 4.0, modified."
- "Lotus Flower by Valery.Li, CC BY 4.0, modified."
- "Reed Plants Pack by Nicholas-3D, CC BY 4.0, modified."
- "Water lily by Mariia Melnik, CC BY 4.0, modified."
- "Sand Hollow Spire by GoochFauxRock, CC BY 4.0, modified."
- Add the Copernicus line above if you use GLO-30 instead of NASADEM.

## What's left for you

- Decide whether to pay $30 and accept the Fab grey area for the pine pack. Saying no still leaves a free pilot.
- Log in to Sketchfab and Fab when downloads start.

Nothing has been bought or downloaded.

## Full candidate table

"Web OK?" means whether you can ship the asset inside a public GLB file. Polygon counts are triangles unless marked "faces".

### Peaks and pillars

| Asset | Creator | Link | Licence | Web OK? | Price | Formats | Polys / textures | Fit | Status |
|---|---|---|---|---|---|---|---|---|---|
| NASADEM / SRTM elevation data | NASA / USGS | https://data.usgs.gov/datacatalog/data/USGS:EROS5e83a3ee1af480c5 | Public domain | Yes | Free | GeoTIFF | 30 m per pixel | Huangshan and Guilin ridges | Recommend |
| Copernicus GLO-30 elevation data | ESA / Airbus | https://registry.opendata.aws/copernicus-dem/ | Free, copyright line required | Yes | Free | GeoTIFF | 30 m per pixel, about 48 MB per tile | Same as above | Alternative |
| Sand Hollow Spire | GoochFauxRock | https://sketchfab.com/3d-models/sand-hollow-spire-11351b04aa0e445d9bd8cf9602b631ee | CC-BY | Yes, with credit | Free | glTF | 560K faces, one 8K texture | Pillar shape | Optional |
| Aphrodite's Rock | juanbrualla | https://sketchfab.com/3d-models/aphrodites-rock-cyprus-e90f78604b14454299ad390c84e8707c | CC-BY | Yes, with credit | Free | glTF | 1.5M faces, 8K | Sea stack | Optional |
| Rock Tower | Blender3D | https://sketchfab.com/3d-models/rock-tower-9021389231044fe6a289c9e2f3e82282 | CC-BY | Yes, with credit | Free | glTF | 21K faces, 4K | Stylised | Low fit |
| The Lijiang River in Guilin | bluepaint0218 | https://sketchfab.com/3d-models/the-lijiang-river-in-guilin-ae9e3aedb1cd4ddd873d5d7665fb1f98 | CC-BY | Shape only | Free | GLB | 20K faces, 8K | Real karst | Shape only, texture rights unclear |
| The Vast Land | Shahriar Shahrabi | https://sketchfab.com/3d-models/the-vast-land-733b802f5a4743ef99ad574279d49920 | CC-BY | Yes, with credit | Free | glTF | 124K faces, 8K | Painterly far layer | Optional |
| Mountain And River Scroll | Shahriar Shahrabi | https://sketchfab.com/3d-models/mountain-and-river-scroll-dd37769bdc0148a988535f893d01c551 | CC-BY | Yes, with credit | Free | glTF | 240K faces, 8K | Painterly | Optional |
| Three Peaks Mountain Terrain | Per's Scans | https://superhivemarket.com/products/three-peaks-mountain-terrain | Superhive Royalty Free | Ask creator | $15 | blend, FBX, OBJ, GLB | 500K, 16K | Icelandic rock | Grey |
| Large Cliff Peak Scan 02 | Per's Scans | https://superhivemarket.com/products/large-cliff-peak-scan-02 | Superhive Royalty Free | Ask creator | $10 | blend, FBX | 40K, 8K | Icelandic rock | Grey |
| Megascans cliffs | Quixel | https://www.fab.com/category/3d-model/nature-plants--rocks-stones--cliffs | Fab Standard | Grey | From $2.99 | FBX, glTF | Varies | No karst scans found | Grey |
| BlenderKit terrains | various | https://www.blendkit.com/asset-gallery-detail/924eaed7-a06b-41ca-976d-498f4353e06b/ | Royalty Free | No | Free | blend | 4K to 500K | Generic | Excluded, unless an item is CC0 |
| Floating Island With Roots And Rocks | dennis.hafemann | https://sketchfab.com/3d-models/floating-island-with-roots-and-rocks-4c05ffef4d1c45ab847ac565b8184a5b | CC-BY | Yes, with credit | Free | glTF | 131K faces, 2K | Stylised island | Optional |
| Pixal3D or TRELLIS.2 (AI generators) | Tencent ARC / Microsoft | https://huggingface.co/TencentARC/Pixal3D | MIT (use ComfyUI's native nodes) | Yes | Free, runs locally | GLB | Up to 1M, 4K | Pillars and boulders only | Optional test |
| Rodin Gen-2.5 / Meshy 7.1 (AI) | Deemos / Meshy | https://hyper3d.ai/pricing, https://www.meshy.ai/pricing | Paid plan: you own the output | Yes | About $20 to $30 a month | GLB, FBX | You choose | Pillars only | Optional |
| Hunyuan3D 2.1, self-hosted (AI) | Tencent | https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 | Excludes EU, UK, South Korea | No | Free | GLB | | | Excluded |
| Magicvalley Guilin Karst | Magicvalley | Fab | Unreal only | No | | | | | Excluded |

### Close rock and textures

| Asset | Creator | Link | Licence | Web OK? | Price | Formats | Polys / textures | Fit | Status |
|---|---|---|---|---|---|---|---|---|---|
| rock_face_02 | Poly Haven | https://polyhaven.com/a/rock_face_02 | CC0 | Yes | Free | blend, glTF, FBX | 30K, up to 8K | Banded sandstone | Recommend |
| rock_face_01 | Poly Haven | https://polyhaven.com/a/rock_face_01 | CC0 | Yes | Free | same | 20K | Cliff | Recommend |
| mountainside | Poly Haven | https://polyhaven.com/a/mountainside | CC0 | Yes | Free | same | 288K, 8K | Cliff | Recommend |
| namaqualand_cliff_02 | Poly Haven | https://polyhaven.com/models/nature/rocks-stone/cliffs-rock-faces | CC0 | Yes | Free | same | 364K | Cliff | Optional |
| coastal_cliff_04 | Poly Haven | same page | CC0 | Yes | Free | same | 2.9M | Too heavy | Low |
| marble_cliff_06 (texture) | Poly Haven | https://polyhaven.com/a/marble_cliff_06 | CC0 | Yes | Free | texture maps | 8K over 8.1 m | Zhangjiajie layers | Recommend |
| rock_face_03 / cliff_side (textures) | Poly Haven | https://polyhaven.com/a/rock_face_03, https://polyhaven.com/a/cliff_side | CC0 | Yes | Free | texture maps | 16K | cliff_side needs desaturating | Optional |
| Rock063 / Rock051 (textures) | ambientCG | https://ambientcg.com/view?id=Rock063 | CC0 | Yes | Free | JPG, PNG | Up to 8K | Mossy layered cliff | Recommend |
| Moss001 to Moss004 (textures) | ambientCG | https://ambientcg.com/view?id=Moss001 | CC0 | Yes | Free | JPG, PNG | 8K | Moss blend | Recommend |
| boulder_01 | Poly Haven | https://polyhaven.com/a/boulder_01 | CC0 | Yes | Free | glTF | | Island undersides | Recommend |

### Pines and trees

| Asset | Creator | Link | Licence | Web OK? | Price | Formats | Polys / textures | Fit | Status |
|---|---|---|---|---|---|---|---|---|---|
| Pinus taiwanensis 01 (9 trees) | 3DGardenPlants | https://www.fab.com/listings/af669a49-a880-434c-897f-afb419c47d7c | Fab Standard | Grey | $29.99 (Personal) | Blender, FBX, GLB | 100k to 1.5M each | Best Huangshan match | Pilot, if approved |
| Pinus taiwanensis 02 | 3DGardenPlants | https://www.fab.com/listings/934ffc43-29b8-488b-975d-458e89700683 | Fab Standard | Grey | $29.99 | same | same | Excellent | Optional |
| Pinus taiwanensis 01 to 07 | 3DTree | https://www.fab.com/listings/b7d2379d-c978-4d16-b18b-a00c1746f29c | Fab Standard | Grey | $8.99 each | FBX, 3ds Max | Not stated | Excellent | Optional |
| Pinus thunbergii (7 trees) | 3DGardenPlants | https://www.fab.com/listings/37ba2a8b-f6a7-48b8-b6d5-94428d2ea1d5 | Fab Standard | Grey | $29.99 | Blender, FBX, GLB | 100k to 1.5M | Courtyard pines | Optional |
| YF-Env Cliff Pine Tree (12 trees) | YF Habitat | https://www.fab.com/listings/1ac5366b-a151-4c65-8121-01605a920e1c | Fab Standard | Grey, Unreal-only format | $16.99 | Unreal only | Nanite | Best mood | Excluded unless you export through Unreal |
| Japanese Black Pine | matt z chan | https://sketchfab.com/models/f0cb4705f1c446c7bc393fdbfcdf024a | CC-BY 4.0 | Yes, with credit | Free | glTF | 158.8k, 5 textures | Good windswept shape | Recommend |
| Black pine twig scan | ffish.asia | https://sketchfab.com/models/78a7f47b3e7d4cad9d3316af821e6845 | CC0 | Yes | Free | glTF | 382.6k, 2 textures | Needle cards | Recommend |
| Japanese red pine scan | ffish.asia | https://sketchfab.com/3d-models/cc0-japanese-red-pine-pinus-densiflora-a21a0843495a4235882873c121512a94 | CC0 | Yes | Free | glTF | 1.4M | Needle cards | Recommend |
| Plant Models Vol 24 (72 pines, 8 species) | Maxtree | https://superhivemarket.com/products/plant-models-vol-24-blender | Superhive Royalty Free | Needs written OK | $175 | blend, FBX | Not stated | Best species range | Grey |
| Japanese Black Pine Tree Pack | hkhalif | https://superhivemarket.com/products/japanese-black-pine-tree-pack | Superhive Royalty Free | Needs written OK | $7.99 | Not stated | 82k / 328k | Garden pines | Grey |
| Pine Tree 01 | Poly Haven | https://polyhaven.com/a/pine_tree_01 | CC0 | Yes | Free | blend, glTF | 17.4M, 8K | Western pine | Textures only |
| Salix babylonica 05 (weeping willow) | 3DGardenPlants | https://www.fab.com/listings/7d7f49cf-aa42-4d6e-8965-fdc3a910ad89 | Fab Standard | Grey | $29.99 | Blender, FBX, GLB | 100k to 1.5M | Weeping willow | Optional |
| botaniq Full | polygoniq | https://superhivemarket.com/products/botaniq-trees | Royalty Free, no sharing | No | $129 | blend | | Willow, cherry, no pines | Excluded |
| Quaternius Stylized Nature MegaKit | Quaternius | https://quaternius.com/packs/stylizednaturemegakit.html | CC0 | Yes | Free | glTF, FBX | Low poly | Western, cartoon | Low fit |
| Stylized Trees, Asia Nature | So Stylized | https://www.fab.com/listings/7a400781-3a27-4121-a8dc-0bc62c4e2949 | Fab Standard | Grey | $34.99 | Unreal only | | Genshin-like | Excluded |
| Fantasy Sakura | Sonkiam | https://sketchfab.com/models/43f5b135e5af438cb706bbcb5bdf3cf1 | CC-BY | Yes, with credit | Free | glTF | 5.3k | Stylised spirit tree | Optional |
| SpeedTree, The Grove, Synty, TurboSquid | | | Licence limits | No | | | | | Excluded |

### Bamboo and blossom

| Asset | Creator | Link | Licence | Web OK? | Price | Formats | Polys / textures | Fit | Status |
|---|---|---|---|---|---|---|---|---|---|
| Free Bamboo Set | JonhGillessen | https://sketchfab.com/models/e9f9fa5397814f81bf85ad06acf5bf30 | CC-BY 4.0 | Yes, with credit | Free | glTF | 37.8k, 16 textures | Bamboo groves | Recommend |
| Sakura branch scan | ffish.asia | https://sketchfab.com/models/f5e6f5a985ea4fc2a14ee0b4b37572b5 | CC0 | Yes | Free | glTF | 1.1M, 5 textures | Blossom cards | Recommend |
| Prunus persica (peach) | 3DTree | https://www.fab.com/listings/f0657559-e0ea-461d-bf4a-2ad166ed9135 | Fab Standard | Grey | $9.99 | FBX | Not stated | Pink blossom | Optional |
| Megaplants Yoshino Cherry | Quixel | https://www.fab.com/listings/97f6cdb0-810d-470d-9e3a-3c9f059e6763 | Fab Standard | Grey | Free | Unreal .uasset, USD | Nanite, very heavy | Photoreal | Not recommended |
| Megaplants Giant Bamboo | Quixel | https://www.fab.com/listings/73f94dc9-9642-4c44-9f8e-c37eebe3205c | Fab Standard | Grey | Free | Unreal .uasset, USD | Nanite, very heavy | Photoreal | Not recommended |
| Sagano Bamboo Forest | Sketchfab uploader | | Ripped game asset | No | | | | | Excluded |
| WonderFuel bamboo and cherry packs | WonderFuel | Fab | AI-generated | | | | | | Excluded |

### Grass, ground, lotus and reeds

| Asset | Creator | Link | Licence | Web OK? | Price | Formats | Polys / textures | Fit | Status |
|---|---|---|---|---|---|---|---|---|---|
| sparse_grass / leafy_grass (textures) | Poly Haven | https://polyhaven.com/a/sparse_grass, https://polyhaven.com/a/leafy_grass | CC0 | Yes | Free | texture maps | 8K, with a grass/soil mask | Lawns | Recommend |
| grass_ground (texture) | Poly Haven | https://polyhaven.com/a/grass_ground | CC0 | Yes | Free | texture maps | 16K | Lawns | Recommend |
| forest_floor (texture) | Poly Haven | https://polyhaven.com/a/forest_floor | CC0 | Yes | Free | texture maps | | Under trees | Optional |
| Foliage001 to 008 (grass card textures) | ambientCG | https://ambientcg.com/view?id=Foliage008 | CC0 | Yes | Free | JPG, PNG | 2K to 8K | Card clumps | Recommend |
| grass_medium_01 / 02 | Poly Haven | https://polyhaven.com/a/grass_medium_01 | CC0 | Yes | Free | blend, glTF | 1.6M / 1.04M | Use textures only | Optional |
| fern_02 / moss_01 | Poly Haven | https://polyhaven.com/a/fern_02, https://polyhaven.com/a/moss_01 | CC0 | Yes | Free | glTF | 6.2k / 246k | Shaded ledges | Optional |
| Indian Lotus scan | ffish.asia | https://sketchfab.com/models/d69e1be5895f40e484f0db472a721c2f | CC0 | Yes | Free | glTF | 1.5M, 4K | Right species | Recommend, as cards |
| Lotus Flower | Valery.Li | https://sketchfab.com/models/ebb4ed6bd8c442be88f9cdf7f0ebcf27 | CC-BY | Yes, with credit | Free | glTF | 77.5k, 2K | Realistic lotus | Recommend |
| Hand Painted Lotus Plant | Sarath K | https://sketchfab.com/models/aeceb2d45fb84a69a394363d437c20d7 | CC-BY | Yes, with credit | Free | glTF | 1k | Stylised | Low fit |
| Water lily | Mariia Melnik | https://sketchfab.com/3d-models/water-lily-04dd636204cd4b0db45a4fc82efa4385 | CC-BY | Yes, with credit | Free | glTF | 360, 1K | Lily pads | Recommend |
| Reed Plants Pack | Nicholas-3D | https://sketchfab.com/models/bc77ea5218e44f2dbc23b2a4aef0c898 | CC-BY | Yes, with credit | Free | glTF | 1,619, up to 4K | Pond reeds | Recommend |
| Chinese Silver Grass scan | ffish.asia | https://sketchfab.com/models/99f88f1b9a6b4313bc2380addee29791 | CC0 | Yes | Free | glTF | 286k, 4K | Ridge grass | Optional, as cards |
| Common and Japanese reed scans | ffish.asia | https://sketchfab.com/models/91f546fb238149ff9e99a8594a3a2b58, https://sketchfab.com/models/365c33ce6b5a4a68898b97c69cfe0b2f | CC0 | Yes | Free | glTF | 163k / 301k | Reeds | Optional |
| GA Free lotus clusters | Galaxy Abundant | https://sketchfab.com/models/c17ba909e1014b7ba38b858bcb107a4f | Unclear origin | | Free | | 470k to 1.25M | | Excluded |
| Megascans grass | Quixel | Fab | Fab Standard | Grey | Free to $0.99 | FBX, glTF | | Generic | Fallback only |

I didn't open the Megascans and Megaplants listings myself. Their prices come from search snippets.

The research browser left preview screenshots in `E:\Github\PortfolioV5\.playwright-mcp\`. They are untracked and can be deleted.
