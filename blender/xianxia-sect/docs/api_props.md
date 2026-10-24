# sect.lib.props

Props and the magic layer: lanterns, plaques, banners, ding cauldrons, censers, bells, drums,
guardian lions, swords, artifacts, chains, ropes, jade tablets, steles on bixi turtles,
bamboo-slip and paper scrolls, books, garden furniture, forge props, cranes, koi, rune circles,
light beams and pillars, spirit motes and shield domes. Blender 5.2, EEVEE, all procedural
(the only external asset is the KaiTi font). Deterministic and idempotent.

```python
from sect.lib import props

root = U.empty("gate.root", coll)
props.guardian_lion(coll, 2.0, name="gate.lion_l", parent=root, location=(-9, -14, 0))
props.guardian_lion(coll, 2.0, mirror=True, name="gate.lion_r", parent=root, location=(9, -14, 0))
props.plaque(coll, "日月神教", 6.0, name="gate.plaque", parent=root, location=(0, -1.2, 17.5))
```

Preview (look.py CLI, run from the project root):

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python sect/lib/look.py -- --target sect.lib.props:showcase --out out/previews/props --name props --footprint 18
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python sect/lib/look.py -- --target sect.lib.props:closeups --out out/previews/props --name closeups --footprint 12
```

`showcase` has 9 cameras (overview, front, center, back, left, right, lions, corner, aerial):
317 objects, 686 k evaluated triangles, builds in about 4.5 s. `closeups` has 6 (artifacts,
arts_left, arts_right, plaques, stele_crown, lion_head). Renders are in `out/previews/props/`.

## Conventions (every public builder)

- First argument is the target `collection`. Then the prop's own dimensions, in meters.
- Shared keyword arguments: `name` (root object name, e.g. `"gate.lantern"`, made unique;
  default `"props.<kind>"`), `parent` (location/rotation are in the parent's space),
  `location`, `rotation` (XYZ Euler radians) and, for most, `scale`.
- The prop is built at the local origin, front facing **-Y**. The origin is the ground centre
  unless noted (hanging things: the suspension point; floating things: the centre).
- Returns the root object: an Empty, a collection-instance Empty, or a single object.
- Repeated props are **prototypes** in excluded collections under `_protos` (`props.<key>`), built
  once per parameter set and placed as collection instances. Size parameters snap to a sqrt(2)
  grid of prototype sizes and the remainder is applied as instance scale (at most 19 %), so
  `size=rng.uniform(0.8, 1.2)` does not create a new prototype per call. Unique props (plaque,
  banner, scrolls of slips, rune rings, beams, pillars, motes, domes, chains, ropes) build their
  own objects but share mesh data where possible.
- Glow: emissive parts carry `obj["glow"]` on the **prototype** objects. The shared materials read
  it with an OBJECT attribute, which instancers do not override, so glow is fixed per prototype.
- Names inside prototypes start with `props.`; objects you create directly start with your `name`.
- Everything is seeded (`seed=`); calling the same function twice in one scene gives unique
  names and shares the prototype; a rebuild after `look.reset_scene()` gives identical names
  (tested: two showcase builds in one session, 317 objects and 686,361 triangles both times).

## Functions

Sizes and triangle counts are measured at the default arguments.

### Lanterns and plaques

| Signature | What it builds | Size / tris |
|---|---|---|
| `lantern_hanging(collection, style='palace', size=1.0, cord=0.25, ...)` | `palace`: hexagonal rosewood palace lantern, glowing panels with gold borders, crown of six upswept gold dragon-head hooks with small tassels, big red tassel. `round`: red silk deng long with vertical pleats, black lacquer caps, gold bands, red tassel. **Origin = suspension point**, hangs in -Z; `cord` = cord length above the lantern. | palace 0.84 x 0.96 x 1.71 m below the origin, 5.6 k; round 0.61 x 1.39 m, 3.7 k |
| `lantern_stone(collection, height=2.4, material='stone_grey', lit=True, ...)` | Chinese square stone lantern (not a Japanese toro): xumizuo base with waist, downturned lotus, octagonal shaft with a band, upturned lotus capital, square chamber with round-arched openings and a glowing paper firebox, pyramidal pavilion roof with concave slopes, upturned corners and hip ridges, jewel finial. | 1.0 x 1.0 x 2.44 m, 8.9 k |
| `plaque(collection, text_zh, width=3.0, vertical=False, rtl=False, tilt=radians(8), board='plaque_board', frame='gold', text_material='gold', ...)` | Hanging plaque: dark blue board, carved gold frame (outer bead, key-fret band, ridge, row of pearls, inner lip, curved corner brackets), raised bevelled KaiTi characters fitted to the board. `vertical`: characters stacked, cloud crest on top. `rtl`: right-to-left (classical) for horizontal plaques. **Origin = board centre**, top leans forward by `tilt`. Unique (not instanced). | 3 chars, width 3: 3.0 x 1.17 m, 19 k. Vertical width 1.2: 3.2 m tall, 26 k |

```python
props.lantern_hanging(coll, "palace", 1.0, cord=0.4, name="mission.lantern", parent=root, location=(8, -6, 9.5))
props.plaque(coll, "藏经阁", 1.4, vertical=True, name="library.plaque", parent=root, location=(0, -4.1, 12))
```

### Banners

| Signature | What it builds | Size / tris |
|---|---|---|
| `banner(collection, height=6.0, width=1.0, material=0, pole=True, seed=0, length=None, trim='auto', wind=1.0, animate=True, pole_material='lacquer_red', ...)` | Vertical sect banner (fan) on a red pole with clamping stones and a gold spear finial; the cloth (`length` default 0.6 x height) hangs from a gold arm on the +X side, contrasting border (`trim`: gold, or ink black on gold/white cloth), toothed bottom edge, seeded static wind billow, and (`animate`) a Wave modifier sending ripples down the cloth over the frames (phase differs per seed). `material`: banner colour index (`materials.banner_cloth`), material name or Material. `pole=False`: cloth on a gold rod centred on the origin (for beams/eaves). | 1.73 x 6.52 m, 1.9 k |

```python
for i in range(40):   # arena: one per hackathon
    props.banner(coll, 7.0, 1.1, material=i, seed=i, name="arena.banner", parent=root, location=pos[i], rotation=(0, 0, yaw[i]))
```

### Bronzes, ritual objects

| Signature | What it builds | Size / tris |
|---|---|---|
| `cauldron_ding(collection, size=1.6, lit=True, legs=3, material='bronze_verdigris', sparks=True, light=False, smoke=False, ...)` | Bronze ding, `size` m to the top of the ears. `legs=3`: round ding, hoof legs, upright ears (openings face the front), neck band of six taotie masks between notched flanges, wave band. `legs=4`: square fang ding, column legs, nipple-boss bands, taotie, corner and centre flanges. `lit`: churning orange molten surface (`props_molten`), soft heat aura above the rim, ember sparks rising and fading (geometry nodes, scene time). `light`: a warm point light (counts toward an area's 8). `smoke`: a smoke column. `lit=False`: grey ash. | round: 1.57 m wide, ears at 1.6 m, sparks to 3.3 m; 45 k. Square 24 k |
| `incense_burner(collection, size=1.0, smoke=True, ...)` | Hexagonal stone pedestal, bronze tripod censer with elephant-trunk legs, crown ears, ridges, taotie masks, ash, three sticks with glowing tips, three thin curling smoke ribbons (to about 2.7 m). | 0.95 m wide, sticks at 1.1 m; 8.7 k |
| `bell(collection, size=1.6, material='bronze_verdigris', frame=False, ...)` | Chinese temple bell: eight-lobed scalloped lip, relief bands, four lotus striking seats, relief inscription, pu-lao dragon hanger. `frame=False`: **origin at the hanger top**. `frame=True`: on a red post-and-beam frame with a striking log on ropes in front; origin on the ground. | 1.28 x 1.75 m, 18 k; with frame 2.5 x 2.3 m, 20 k |
| `drum(collection, size=1.2, stand=True, ...)` | Red lacquer barrel drum, heads face -Y/+Y, gold bands, two rows of brass studs per head, ring pulls; rosewood stand with two sticks. `stand=False`: origin at the drum centre. | 1.68 x 1.08 x 1.70 m, 14 k |
| `guardian_lion(collection, size=1.0, mirror=False, material='marble_white', plinth_material=None, ...)` | Seated guardian lion on a xumizuo plinth with a brocade drape. Round 28 (`LION_SCAN`): a photogrammetry scan of a Qing white-marble lion ("Stone Big Lion 01", CC-BY 4.0; `sect/lib/lion_props.py`, its maps in `assets/web/lion_*`): carved curled mane, collar and bell, brocade lattice, clean weathered-marble colour, baked normal map. `mirror=False`: male, right forepaw on a carved embroidered ball (-X side). `mirror=True`: the female partner, left forepaw on a cub (+X side). Another `material` tints the scan by that material's colour. `LION_SCAN = False`: the earlier procedural lion (1.07 x 1.31 x 2.28 m, 77 k; bronze: `material='props_lion_bronze'`). | 0.98 x 1.31 x 2.27 m (x size), 28 k |

```python
props.cauldron_ding(coll, 8.0, lit=True, light=True, name="forge.ding", parent=root, location=(0, 4, 0))
```

### Swords and artifacts

| Signature | What it builds | Size / tris |
|---|---|---|
| `sword(collection, length=1.0, style='jian', glow=True, blade_material='steel', fitting_material='gold', ...)` | `jian` (straight, diamond section, bow guard, cord-wrapped grip, pommel), `dao` (curved sabre, disc guard), `great` (broad heavy sword); red tassel; `glow`: jade-cyan line on the ridge and jade gems on the guard. Points +Z, flat faces -Y, **origin at the guard**. | 0.11 x 1.23 m with tassel, 2.4 k |
| `artifact(collection, kind, size=1.0, ...)` | Floating artifact, `size` m largest dimension, **centred on the origin**, jade-glow accents. `kind` in `ARTIFACT_KINDS`: `sword`, `bell` (Taoist handbell with three prongs), `mirror` (octagonal bagua mirror, glowing trigrams), `orb` (jade pearl in gold rings on a lotus cradle), `fan` (folding fan, glowing moon), `seal` (jade seal, coiled dragon knob, glowing script face tipped toward the viewer), `gourd` (calabash, jade stopper, red cord, curl of qi), `pagoda_treasure` (seven-tier gold pagoda, glowing jade storeys), `ruyi` (jade sceptre with cloud head, posed diagonally), `bead_string` (prayer beads, jade spacers), `flag` (array pennant, glowing trigram), `spear` (leaf head, red horsehair, diagonal), `lotus_lamp` (jade lotus with a flame), `compass` (luopan with rings, trigrams and the 24 mountains, tipped up), `jade_disc` (bi disc, cord, tassel); made for the projects (the forge ring, `forge.FORGE_RING`, holds the winners' artifacts; the mirror, seal, duck censer and blossom fan are off the ring): `command_flag` (the pennant with a gold 令), `treasure_bowl` (red lacquer basin heaped with ingots and cash, glowing pearl, 招财进宝 band; tipped up), `bamboo_slips` (half-unrolled slip book, Analects 1.1, first two columns glowing), `fire_wheel` (Nezha's wheel: gold rims, flame tongues, wind swirls round a jade hub), `spirit_brush` (a brush writing a form, answers in glowing gold), `paper_cranes` (five origami cranes circling a rice bowl), `duck_censer` (golden duck on a jade dish with glowing ripples, qi from its beak; side on), `immortal_peaches` (four peaches and leaves on a celadon plate; tipped up), `blossom_fan` (the fan with an ink peach-blossom branch and glowing pink flowers). | 1 m box, 4.2 k average |

```python
ring = U.empty("forge.artifact_ring", coll, parent=root, location=(0, 4, 9))
for i, kind in enumerate(props.ARTIFACT_KINDS):
    a = 2 * math.pi * i / 15
    props.artifact(coll, kind, 2.0, name="forge.artifact", parent=ring,
                   location=(7 * math.cos(a), 7 * math.sin(a), 0), rotation=(0, 0, a + math.pi / 2))
# orbit: keyframe or drive ring.rotation_euler.z, e.g. driver "frame*0.004"
```

### Chains, ropes, tablets, steles

| Signature | What it builds | Size / tris |
|---|---|---|
| `chain(collection, p0, p1, link_size=0.3, sag=None, material='iron', ...)` | Interlocking links (alternately rotated 90 deg) along an exact catenary from `p0` to `p1` (parent space), dropping `sag` m below the chord midpoint (default 8 % of the span). One geometry-node point instancer, one shared link mesh. Returns that object. | 4 m: 7 k (about 250 tris per link) |
| `rope(collection, p0, p1, sag=None, radius=0.03, material='props_rope', strands=3, ...)` | Three-strand twisted rope along a catenary (default sag 5 %). `strands=0` or very long thin ropes: plain tube. | 4 m: 5.6 k |
| `jade_tablet(collection, height=0.6, glow=True, cord=0.5, text=None, seed=0, ...)` | Jade token with a cloud-arched top, raised gold borders on both faces, gold ring, column of glowing gold characters (`text`, or chosen from `TABLET_TEXTS` by `seed`), red cord up `cord` m to the **suspension point (origin)**, Chinese knot and long tassel below. | 0.3 x 1.59 m below the origin, 2.8 k |
| `stele(collection, height=4.0, glyph_mat='rune_cyan', turtle_base=True, seed=0, material='stone_dark', ..., manual=None)` | Stele: dark slab with a key-fret border, glowing classical text in columns (top to bottom, right to left; a few columns on the back), arched crown with two relief dragons holding a pearl and a four-character title. `manual` (a dict like those in `JIN_YONG_MANUALS`: `title`, `cols`, `back`) carves a Jin Yong martial-arts manual instead: the title in the crown, each `cols` string one front column, `back` on the back (one prototype per manual). `turtle_base`: bixi dragon-turtle with scute shell, raised dragon head, clawed feet, on a ground slab; else a xumizuo base. `glyph_mat`: rune_cyan / rune_gold / rune_silver or any registered emissive name. `seed` picks the text (6 variants). | turtle: 2.1 x 3.5 x 4.0 m, 51 k; plain 1.7 x 0.84 x 4.0 m, 40 k |

```python
props.chain(coll, (30, 0, -2), (60, 6, -25), link_size=1.2, sag=4, name="arena.chain", parent=root)
props.jade_tablet(coll, 1.4, seed=k, cord=1.2, name="mission.role_tablet", parent=root, location=(x, -3, 8))
props.stele(coll, 6.5, "rune_gold", seed=i, name="steles.stele", parent=root, location=(x, y, 0))
```

### Scrolls and books

| Signature | What it builds | Size / tris |
|---|---|---|
| `bamboo_slip_scroll(collection, width=3.0, height=1.2, curve=0.25, glow=True, seed=0, rolled=True, text_material=None, ...)` | Unrolled scroll of jade slips (`jade_slip`), bowed in plan so the ends come `curve` x width toward -Y, two woven red silk cords, a column of glowing classical script per slip (default `rune_gold`; `glow=False`: jade with ink), and a tight roll of slips at the left end. **Origin at the centre.** Unique. For the 22 x 9 m resume scroll use `curve` about 0.08. | 3 x 1.2: 37 k; 22 x 9 (curve 0.25): 23.6 x 6.9 x 9 m, 70 k |
| `floating_scroll(collection, width=1.2, open=True, glow=True, seed=0, ...)` | Hand scroll: gently S-waving aged paper (0.36 x width tall), thick and thin rollers with jade knobs, script columns (glowing gold, or ink), red seal. `open=False`: closed roll with a teal silk tie. Centred. | 1.28 x 0.58 m, 14 k |
| `book_stack(collection, n=4, seed=0, ...)` | Thread-bound books (0.18 x 0.26 m), coloured cloth covers, side stitching, title slips. | 0.22 x 0.30 x 0.10 m, 4.8 k |

### Furniture, forge, small props

| Signature | What it builds | Size / tris |
|---|---|---|
| `stone_table(collection, diameter=1.0, stools=4, material='marble_white', ...)` | Round stone table on a carved vase pedestal (0.78 m high) with drum stools. | 1.6 x 1.6 x 0.78 m, 11 k |
| `tea_set(collection, ...)` | Black lacquer tray, purple-clay teapot, four celadon cups. Origin at the tray bottom (put it at z = 0.78 on a stone table). | 0.42 x 0.28 x 0.13 m, 2.5 k |
| `cushion(collection, diameter=0.6, style='round', material=None, ...)` | `round`: woven straw pu tuan with coils. `square`: puffed silk cushion (cloth_gold) with tassels. | 0.6 x 0.12 m, 4 k |
| `wind_chime(collection, size=1.0, ...)` | Eave bell with a jade bead and a fish-shaped wind plate. **Origin at the hook.** | 0.52 m long, 0.9 k |
| `weapon_rack(collection, width=2.0, seed=0, ...)` | Rosewood rack with spears (red tassels), guandao, ji halberds, tridents, staves. | 2.2 x 0.55 x 2.55 m, 4 k |
| `anvil(collection, size=1.0, ...)` | Iron anvil with horn and heel on a banded stump, hammer on the face. | 0.73 x 0.78 x 0.70 m, 2.8 k |
| `ore_pile(collection, size=1.0, seed=0, ...)` | Dark ore chunks, gold lumps, glowing jade crystals. | 1.4 x 1.4 x 0.5 m, 2.9 k |

### Creatures

| Signature | What it builds | Size / tris |
|---|---|---|
| `crane(collection, pose='standing', size=1.0, ...)` | Red-crowned crane: white body and folded wings, black neck and drooping black tertials, red crown, olive bill, dark legs. `standing`: origin between the feet. `flying`: neck forward (-Y), legs trailing, wings spread with fingered primaries and a black trailing band; origin at the body. | standing 1.55 m tall, 15 k; flying 2.9 m span, 10 k |
| `koi(collection, seed=0, length=0.5, ...)` | Koi swimming toward -Y with a seeded S-bend (6 variants), pattern differs per instance, translucent fins, eyes, barbels. Origin at the body centre; put it just under a water surface. | 0.63 m with tail, 0.6 k |

### Magic layer

| Signature | What it builds | Size / tris |
|---|---|---|
| `rune_ring(collection, radius=5.0, width=0.6, kind='trigram', material='rune_cyan', seed=0, spin=0.0, groove=False, ...)` | Flat glowing ring 8 mm above the origin plane, band of `width` centred on `radius`, two thin border rings. `trigram`: the eight bagua trigrams (solid yang, broken yin, bottom line innermost, Fu Xi order, qian toward +Y), repeated around large rings, diamond markers. `sigil`: procedural talisman sigils linked by arcs. `script`: classical characters standing outward. `spin` (rad/s): frame driver rotating it. `groove`: dark engraved channel under it. Casts no shadow. Returns the ring object. | r5 trigram 2.9 k; r30 w2 script 21 k |
| `light_beam(collection, p0, p1, radius=0.1, material='props_beam_link', core=True, ends=True, ...)` | Additive beam from `p0` to `p1` (parent space): soft silhouette, faded ends, streaks flowing p0 to p1, brighter core, glowing end nodes. No shadow. Shared unit meshes scaled to the span. | 10 m: 0.2 k |
| `light_pillar(collection, height=40.0, radius=1.0, material='light_beam', ..., location=(0,0,0))` | Pillar rising from the origin: additive column fading upward, core, radial glow pool on the ground (`props_flare`), three halo rings. No shadow. | 7 m pool, 2.4 k |
| `spirit_motes(collection, count=200, bounds=((-5,-5,0.5),(5,5,5)), seed=0, size=0.04, material='props_mote', drift=0.25, rise=0.0, ...)` | Tiny glowing motes scattered in a box, drifting with scene time (`drift` m wobble); `rise` m/s makes them float up and wrap. One point instancer. | 200: 16 k |
| `shield_dome(collection, radius=30.0, height=None, material='glass_shield', ring=True, ..., location=(0,0,0))` | Hemispherical glass_shield dome (fresnel rim, energy cells, additive, no shadow) with a glowing ground ring. | r30: 4 k |

```python
for r, w, kind in ((14, 1.4, "trigram"), (26, 1.8, "sigil"), (40, 2.2, "script")):
    props.rune_ring(coll, r, w, kind, spin=0.02, groove=True, name="formation.ring", parent=root)
props.light_beam(coll, node_a, node_b, 0.25, name="formation.link", parent=root)
props.light_pillar(coll, 120, 2.5, name="formation.pillar", parent=root, location=(0, 0, 6))
props.spirit_motes(coll, 400, ((-40, -40, 1), (40, 40, 20)), seed=9, size=0.08, name="formation.motes", parent=root)
props.shield_dome(coll, 56, 38, name="formation.dome", parent=root)
```

### Review targets

`showcase(collection)` and `closeups(collection)` lay everything out (see the CLI above).

## Constants

| Name | Value |
|---|---|
| `ARTIFACT_KINDS` | the 15 kinds, in forge order |
| `CLASSICS` | six classical passages (Dao De Jing, Qian Zi Wen, Qing Jing Jing) used for glyphs |
| `TABLET_TEXTS` | ten four-character mottos for jade tablets |
| `TRIGRAMS`, `BAGUA_ORDER` | trigram lines (bottom first) and the Fu Xi ring order |
| `LUOPAN_24` | the 24 mountains of a feng shui compass |

## Materials registered here (prefix `props_`)

`props_beam_link` (uniform beam, gold variant `props_beam_gold`), `props_flare` (radial glow pool),
`props_shell` (tortoise-shell scutes), `props_molten` (finer, more orange molten),
`props_smoke_wisp` (soft smoke ribbons), `props_heat` (warm aura), `props_mote` /
`props_mote_gold` / `props_flame` (ember-style glows), `props_lantern_silk`, `props_lantern_panel`,
`props_rope`, `props_straw`, `props_feather_white`, `props_feather_black`, `props_crane_crown`,
`props_horn`, `props_leg`, `props_fin`, `props_drum_skin`, `props_ash`, `props_incense`,
`props_zisha`, `props_gourd`, `props_jade_white`, `props_cover_ochre`, `props_cover_brown`,
`props_ore`, `props_lion_bronze`. They are registered on import, built on first use, and are valid
names for any `material=` argument.

## Animation

All animation is driven by the frame, so it renders with no baking:
banner cloth (Wave modifier, ripples travel down the cloth), ding sparks (rise and fade) and spirit
motes (drift) (geometry nodes Scene Time), rune ring `spin` (driver), molten churn and beam streaks
(material drivers). Artifacts do not orbit by themselves: parent them to an Empty and rotate it.

## Notes for area authors

- Large flat ground made from a lathe with a centre pole (one long fan of thin triangles) shows
  radial light/dark streaks with `marble_paving` in EEVEE (the bump node breaks on sliver
  triangles). Use concentric rings or a grid (see the showcase floor).
- Plaques under eaves: `location` is the board centre; with `tilt` 8 deg the top leans toward -Y.
- Stele glyph columns, slip scripts and plaque text are real meshes: no font objects at render.
- `light=True` on a ding adds a point light inside its prototype, so every instance carries one.

## Blender 5.2 facts found while building this

- The geometry-nodes modifier no longer accepts `mod["Socket_2"] = value` ("id properties not
  supported for this type"), and `mod.properties` has no attribute per socket. props bakes the
  instanced object and drift values into a small node group per prototype instead.
- `bmesh.ops.create_uvsphere/create_icosphere/transform` cost O(size of the whole BMesh) per call
  and `create_uvsphere` deletes temporary vertices (freed slots are reused, so "new verts since
  index n" is wrong afterwards). props copies cached primitive templates vertex by vertex and
  tracks the vertices each helper creates: a lion went from 29 s to 0.3 s.
- Metaball element radius vs surface: a lone ball's surface sits at
  `r * sqrt(1 - (threshold/stiffness)^(1/3))` (0.574 r at the defaults); CAPSULE `size_x` is an
  absolute half length. Metaball objects merge by name family, so each conversion uses a unique,
  dot-free family name.
