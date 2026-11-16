# Round 58: near broadleaf keep their leaf sprays

Status on 2026-11-12: built on a box, packed and on the page (not committed yet). See "How it ran".
(The older "round 58" in that file's `write_instances` is other work: page-grown trees.)

## Why

Reviewers called near trees "smooth blobs". The near broadleaf was the `.hero` crown with its ~190 leaf
sprays stripped and the rest collapsed to 0.8: 9 to 13 round blobs, unlike the far sprites, which show
the sprays. Near peaches were `.far` cut to 25 %: hard facets.

## What changes

- **Broadleaf** (`pine.broadleaf.v0`-`v7`, about 980 near trees). The near mesh is the `.hero` crown
  kept whole (trunk, limbs, blobs, no collapse) plus its leaf sprays as cut-out cards. It goes through
  the leafy bush's code (`shrub_near_mesh`): the same leaf material per area (`trees.needle.leaf.<area>`),
  `leaf_alpha.png` and bake material. Sprays keep their size (`BROADLEAF_LEAF_GROW` 1.0), so they match
  the far sprites. Crown normals now cover blobs and sprays (`canopy` materials count as foliage). The
  slot stays 384 px (`BROADLEAF_SLOT_PX`).
- **Peach stop-gap** (`blossom.peach.v0`-`v3`, about 10 near trees). The near mesh is the `.mid`
  prototype whole with crown normals, the card sprites' source too. Flower cards wait for a later round.
- Pines, bushes and their caches do not change. Only broadleaf have `canopy` materials and only peaches
  have `M.nature_blossom_peach` (checked in round 57's `plan.json`).

| Option on `bake_trees.py` | Default | Use |
|---|---|---|
| `--broadleaf-mesh leafy\|blob` | leafy | `blob` brings back the old near broadleaf exactly |
| `--broadleaf-leaf-grow k` | 1.0 | grow sprays if they look buried in the blobs |
| `--broadleaf-crown field\|none` | field | A/B of crown normals on broadleaf only |
| `--blossom-mesh mid\|far` | mid | `far` brings back the old near peach exactly |

Expected size, from round 57's `plan.json`: a near broadleaf goes from about 850-1,080 triangles to
1,825-2,108 (760 of them leaf cards). A near peach goes from about 2,900-3,500 to about 12-15k (`.far`
has 11.4-13.9k before its cut, `.mid` adds thin twigs). Each broadleaf instance group gets one more draw
call (its leaf cards). Atlas slots keep their size, so texture bytes should barely move.

## Run sheet

`BT` below means
`python E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/rblender.py --background E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/bake_trees.py`.
Run it from the worktree so the box gets this branch's script. Files come back under the worktree's
`blender/xianxia-sect/out/`. `RB` means the same `python .../tools/rblender.py`. Never run Blender on the PC.

1. **PC, before renting.** `python -m py_compile blender/xianxia-sect/sect/bake_trees.py` prints
   nothing. Copy round 57's `out/web/full/bake/trees/plan.json`, `trees_stats.json` and `verify_*.png`
   to `out/r58/trees_before/`: the build's files overwrite them when they come back.
2. **Box.** As round 57 (`light-r57.md`): one RTX 5090, the scene as `out/sect_chase.blend` with its md5
   checked, the audit cache and chunk plan, the small files in `out/web/full`, `out/section_timeline.json`.
   The run sheet needs `PIPELINE_CHANGED_OK=1` (`spec.md`). Run the trees after any scene patch and
   `chunks,meta` of this round.
3. **Look test, optional, about 25 minutes.** Two areas at dev quality, new and old, sharing one cache
   so the ray casts and sprites run once:
   - `BT -- plan,build --quality dev --out out/r58/trees_a --cache-dir out/r58/trees_cache --only gate,abode --only-recs`
   - the same with `--out out/r58/trees_b --broadleaf-mesh blob --blossom-mesh far`
   - `BT -- verify --out out/r58/trees_a --frames 93,1380`, then the same for `trees_b`.
   Compare the two `bake/trees/verify_*.png`. Warnings about the other areas' missing files are
   expected. Add a `--broadleaf-crown none` run if the crowns look lumpy.
4. **Plan, 1-2 minutes.** `BT -- plan --quality production`. In `out/web/full/bake/trees/plan.json`
   every `protos["pine.broadleaf.vN"].mesh` has object `...vN.hero`, ratio 1.0 and no
   `M.nature_shrub_leaf` in `removed`; every `protos["blossom.peach.vN"].mesh` has object `...vN.mid`
   and ratio 1.0; `options` has `broadleaf_mesh: leafy` and `blossom_mesh: mid`.
5. **Build, about 75 minutes cold.** `BT -- plan,build,instances --quality production`. Round 57 took
   70: 48 of CPU ray casts, 7 of mesh bakes, 13 of sprites, 2 of export. The log must show:
   - `TREES quality production mesh 512 ...`
   - per broadleaf `broadleaf proto pine.broadleaf.vN {... "leaf_tris": 760, "ratio": 1.0, ...}` and
     `broadleaf pine.broadleaf.vN tris <old> -> <new> texels per m <old> -> <new> (leaves ...) slot 384 -> 384`
   - per peach `blossom proto blossom.peach.vN {"source": "nature.proto.blossom.peach.vN.mid", ...}`
   - no `WARN no '.mid' prototype` and no `WARN needle bake material` lines.
   When the `baked pine.broadleaf...` lines start, check the GPU once with `RB --sh "nvidia-smi"`.
6. **Verify, about 2 minutes.** `BT -- verify` (all 11 hold frames). Compare each `verify_<frame>.png`
   with `out/r58/trees_before/`, hardest at 93 (gate), 772 (library), 974 (steles) and 1380 (abode):
   leafy crown outlines, no square cards, no dark leaf patches, near and far broadleaf alike. Dark or
   empty leaf islands in `preview_<area>_mesh.png` mean the leaf bake material was not applied.
7. **Tuning, only if step 6 says so, about 12 minutes.** `BT -- build,instances --quality production
   --broadleaf-leaf-grow 1.2` (or `--broadleaf-crown none`), then step 6 again. Ray casts and sprites
   come from the cache. Never pass `--fresh`: it re-casts 48 minutes of rays.
8. **md5.** `RB --sh "md5sum out/web/full/raw/*_trees.glb out/web/full/veg/instances.json"` against the
   PC's copies. Then destroy the box.

## Caches

Nothing to reset on a new box: `bakecache/trees_full` starts empty. On a reused box the broadleaf and
peach mesh bakes get new names by themselves (new triangle counts, plus the `bl1.g<grow>.c<crown>` and
`bm1.c<crown>` tags). Sprites and `sunvis.npz` stay valid, since card sources did not change. If plants
moved since `sunvis.npz` was cast, delete it (`RB --sh "rm bakecache/trees_full/sunvis.npz"`): it is
keyed by names.

## Before and after

`trees_stats.json`, per file (`files.<area>`): `tris_broadleaf` against `tris_broadleaf_old` (the old
mesh on the same trees) and `broadleaf_meshes`. `tris_leaf` rises by about 760 per near broadleaf;
click-target leaf cards now count there too (they were in `tris_needle`). `glb.triangles`, `glb.bytes`
and `glb.draw_calls` against `out/r58/trees_before/trees_stats.json`.

Per family (`broadleaf.<fam>`): `texels_per_m` against `old.texels_per_m` (texels per prototype metre
on the crown) and `leaf_texels_per_m`. If the crown loses more than about 10 %, set `BROADLEAF_SLOT_PX`
to 448 and rebuild. `blossom.<fam>`: `tris` against `old_tris_est`, and `texels_per_m`.

## On the PC afterwards

1. At below-normal priority: `python blender/xianxia-sect/tools/sect_pack.py --profile full --workers 2
   --only gate_trees,mirror_trees,forge_trees,arena_trees,mission_trees,library_trees,steles_trees,scroll_trees,formation_trees,abode_trees,summit_trees,backdrop_trees`.
   It must report 0 problems, with `trees.needle.leaf.*` OPAQUE and their occlusion texture.
2. `python blender/xianxia-sect/tools/sect_veg.py`. Its input should not change (same records).
3. Client tests, then screenshots on High and Low at the gate, mirror, library, abode and summit. Watch
   frame time on Low at the gate: Low keeps every leaf card. If it drops, rebuild with
   `--broadleaf-mesh blob`.

**Budget.** The last pack was 122.6 MB against `sect_pack.py`'s 125 MB, the opening 22.3 MB against
15 MB, and 8 of 11 chunks were already over 10 MB or 1.5M triangles. The gate should now pass 1.5M
triangles. Going over only adds an `over_budget` line. Write the real numbers and the decision in the
decisions log.

## How it ran (2026-11-12)

One box, instance 60406897: an RTX 5090 with an EPYC 9734, 0.81 US dollars an hour, up from 13:22 to
15:39 Pacific. The whole session cost 2.16 dollars, three short failed rentals included. 10.77 dollars
of credit are left.

| Step | Time | Note |
|---|---|---|
| Set up, upload the scene | 4 min | md5 of the scene matched |
| `plan` | 2 min | broadleaf `.hero` kept whole, peach `.mid`, options as planned |
| `plan,build,instances`, first try | 74 min | 71 minutes of sun ray casts, then Cycles found no GPU and the build stopped |
| Fix the box, same command again | 29 min | ray casts came from the cache; mesh bakes 6 min, sprites 15 min, export 4 min |
| `verify`, md5, destroy | 15 min | 13 files matched |

**Two faults of the box image, both now known.** Vast's base image starts with an SSH key file the
SSH server refuses, and it loads a CUDA library newer than the host's driver, which a consumer GPU
rejects (`cuInit` returns 804). `nvidia-smi` looks fine through both. The second one cost the first
build: the tree build casts its sun rays on the CPU for over an hour before it first starts Cycles.
The fix is one line on the box (`mv /etc/ld.so.conf.d/00-compat-*.conf /root/ld_off/ && ldconfig`),
and from now on a box is not used until
`python3 -c "import ctypes; print(ctypes.CDLL('libcuda.so.1').cuInit(0))"` prints 0.
`bakecache/trees_full/sunvis.npz` was copied to the PC (the folder is ignored by git), so a later tree
build on a new box can skip the ray casts: upload it to the same path first.

**What changed in numbers.** Triangles in the twelve tree files went from 5.83 to 6.94 million (up
19 %). A near broadleaf went from about 900 to about 1,900 triangles, 760 of them leaves; its crown
keeps about 10 texels a metre (it had 11) and the leaves get about 7. A peach went from about 3,000 to
about 15,500 triangles. The pack grew from 122.6 to 127.2 MB (low tier: 102.9 MB), so it is now 2.2 MB
over the packer's 125 MB line. That line only reports. The opening download is 22.9 MB (it was 22.3).

**What it looks like.** Before and after crops of the page are in
`.playwright-mcp/survey/r58_s2/trees_a.jpg` and `trees_b.jpg`. The smooth turtle-shell blobs at the
mirror and behind the forge's gate are leafy masses with a broken outline now, a little darker than
before. The abode's peach trees have full round blossom clusters. Low and Medium draw them without
errors. `--broadleaf-leaf-grow` stayed at 1.0.

## Known limits

- The sprays are procedural 8-leaf fans (`nature_shrub_leaf`): expect a leafy game tree.
- Cut-out cards cast no live shadow on the page. The baked soft shade under the trees stays.
- Near broadleaf get crown normals and the far sprites do not; step 6 checks they still match.
- Peach clumps are still 20-triangle icosahedra. A flower-card peach needs its own item.
