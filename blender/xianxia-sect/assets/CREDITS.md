# Third-party assets

The downloaded files in this folder are git-ignored (see `.gitignore`); this list is kept. Details and links are in `../docs/asset-research.md`. Each Sketchfab folder also has an `info.json` with the author and licence as the API reported them.

## CC0 (no credit required)

- Poly Haven (https://polyhaven.com): rock_face_01, rock_face_02, mountainside, boulder_01, fern_02, moss_01 (models); marble_cliff_06, sparse_grass, leafy_grass, grass_ground (textures).
- Poly Haven "Pine Tree 01" (https://polyhaven.com/a/pine_tree_01) by Rob Tuytel (photography) and Rico Cilliers (modeling), CC0: its 2K twig colour and alpha maps (`polyhaven/pine_tree_01/textures/`) are composed into `web/twig_card.png` (tools/prep_textures.mjs), the needle-card texture shipped in the site's `*_trees.glb.gz` files. Credit is optional; suggested line: "Pine twig texture: Pine Tree 01 by Rob Tuytel and Rico Cilliers, Poly Haven (CC0)."
- ambientCG (https://ambientcg.com): Rock063, Moss001, Foliage008.
- ffish.asia / floraZia.com on Sketchfab: black pine twig, Japanese red pine, sakura branch, Indian lotus, Chinese silver grass.
- Brackeys VFX Bundle v1 (https://brackeysgames.itch.io/brackeys-vfx-bundle; its `LICENSE & CREDITS.txt`: "Creative Commons Zero (CC0)"), downloaded to `brackeys/vfx-bundle/`. Its flipbooks are by Thomas Iché (Unity Labs, https://unity.com/blog/engine-platform/free-vfx-image-sequences-flipbooks): the alpha of `cloud_01_8x8`, `wispy_smoke_01_8x8` and `cloud_02_8x8` (every 4th frame) is packed into the site's `client/public/sect/fx/mist_flipbook.webp` (tools/prep_textures.mjs --mist-flipbook), the mist puffs at the waterfall feet. Credit is optional; suggested line: "Mist flipbooks by Thomas Iché (Unity Labs), via the Brackeys VFX Bundle (CC0)."
- LibreShot "Waterfall Texture" by Martin Vorel (https://libreshot.com/waterfall-texture/, public domain / CC0: "without attribution"; the site forbids hotlinking, so we host our own derivative), downloaded to `libreshot/waterfall-texture/waterfall.jpg` (3500 x 2333). Its curtain is made into the tiling strand mask `client/public/sect/fx/strands.webp` (tools/prep_textures.mjs --fx) that runs down every waterfall sheet. Credit is optional; suggested line: "Waterfall Texture by Martin Vorel (LibreShot), CC0."
- ambientCG Foam002 (https://ambientcg.com/view?id=Foam002, CC0), downloaded to `ambientcg/Foam002/` (1K-JPG zip; the Color, Opacity and Displacement maps extracted). Its Opacity map becomes `client/public/sect/fx/foam.webp` (tools/prep_textures.mjs --fx), the pool foam at the waterfall feet. Credit is optional; suggested line: "Foam002 from ambientCG.com, CC0."

## Credit required

- Copernicus GLO-30 elevation tiles N30 E118 (Huangshan) and N24 E110 (Guilin):
  "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"
- CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/), Sketchfab:
  - "Japanese Black Pine" by matt z chan: https://sketchfab.com/3d-models/f0cb4705f1c446c7bc393fdbfcdf024a
  - "Free Bamboo Set" by JonhGillessen: https://sketchfab.com/3d-models/e9f9fa5397814f81bf85ad06acf5bf30
  - "Water lily" by Mariia Melnik: https://sketchfab.com/3d-models/04dd636204cd4b0db45a4fc82efa4385
  - "Reed Plants Pack" by Nicholas-3D: https://sketchfab.com/3d-models/bc77ea5218e44f2dbc23b2a4aef0c898
  - "Dark Vulture – Scarred Bald-Headed Horror Bird" by Pigcraft (https://sketchfab.com/s8819296): https://sketchfab.com/3d-models/09cb4ac72a7c4eab95355eef28808310. It is the summit's Divine Condor (on the site). The raw glTF is in `dl_condor/dark_vulture/`. sect/lib/condor_props.py makes a reduced copy of it (24k triangles, re-baked colour and normal maps) in `web/condor_mesh.npz`, `web/condor_diff.jpg` and `web/condor_nrm.png`. Its mesh names (`tripo_*`) show it was generated with Tripo AI. Suggested line: "Divine Condor model: Dark Vulture by Pigcraft (Sketchfab), CC-BY 4.0, reduced and re-textured."

Only the credit lines of assets that end up on the site need to appear there.
