"""Round 59 rock structure (docs/scene/rock-r59.md) as plain numpy: the twin of the node graph that
sect/lib/materials._rock_r59 builds, so its rules can be tested offline (tools/test_rock_struct.py). No bpy.

The graph and this file follow the same steps:
    bed_world      world beds: a bed coordinate t that rises with height (one bed per unit), the bed index i, the
                   position f in the bed (0 at its base, 1 at its top) and the local bed thickness (m)
    protrusion     per bed: hard or soft, and how far it stands out (m)
    bed_profile    the relief height inside a bed (m), continuous across every bed boundary, and the masks the
                   colour and the weathering read: the shelf lip, the overhang recess, the eased bed tone
    joints         one set of near-vertical master joints: a groove of depth `depth` and half width `width`
    fade_geo       where the round's rock relief writes geo_w above 0, the beds and joints fade out
The noise and the hashes differ (Blender's Perlin, White Noise and Voronoi against the callables passed here), so
this twin checks the structure (continuity, ranges, shares), not the exact pattern.

Every default below equals the matching key of materials.py's ROCK_BED / ROCK_JOINT (the test checks it).
"""
import numpy as np

# the bed unevenness: two harmonics of the bed coordinate u (amplitude, frequency per bed, phase in radians). Their
# derivative is 1 + uneven x (0.6165 cos + 0.5962 cos), at least 0.49 for uneven 0.42, so t never runs backward
HARM = ((0.45, 1.37, 0.0), (0.22, 2.71, 1.3))
BED = dict(m=2.75, uneven=0.42, warp=(50.0, 2.0), dip=(0.03, -0.02), hard=0.20, hard_out=(0.25, 0.25),
           soft_out=0.10, edge=0.6, edge_max=0.35, under=0.25, under_w=0.6, shelf=(0.2, 0.3), lip=0.15,
           overhang_w=0.8, tone=0.05, ease=0.2, hard_pale=0.08, steep=(0.62, 0.42), gap=(18.0, 0.38, 0.62, 0.15))
JOINT = dict(master_m=12.0, master_w=0.6, master_d=0.35, wiggle=(20.0, 1.5), tone=0.03, steep=(0.8, 0.5),
             flat=0.5, gap=(24.0, 0.36, 0.60, 0.10))
GEO_FADE = (0.0, 0.25)         # materials.ROCK_GEO_FADE: geo_w from which the beds start to fade, and where they are gone


def smoothstep(e0, e1, x):
    """Blender's Map Range SMOOTHSTEP from e0 to e1 (either order), clamped: 0 at e0, 1 at e1."""
    t = np.clip((np.asarray(x, float) - e0) / (np.asarray(e1, float) - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, f):
    return a + (b - a) * f


def bed_world(x, y, z, noise, bed_m=BED["m"], uneven=BED["uneven"], warp=BED["warp"], dip=BED["dip"]):
    """World beds at points (x, y, z). noise(u, v) -> 0-1, a smooth 2D noise (Blender: Noise 2D on (x, y) at scale
    1 / warp[0]). The bed surfaces wander +-warp[1] m over about warp[0] m and dip dip[0], dip[1] m per m along x, y.
    Returns (t, i, f, thk): the bed coordinate, the bed index floor(t), the position in the bed t - i, and the local
    bed thickness in metres, bed_m / (dt/du)."""
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    n = noise(x / warp[0], y / warp[0])
    zw = z + warp[1] * (2.0 * n - 1.0) + dip[0] * x + dip[1] * y
    u = zw / bed_m
    t = u.copy()
    dtdu = np.ones_like(u)
    for amp, fr, ph in HARM:
        t = t + uneven * amp * np.sin(fr * u + ph)
        dtdu = dtdu + uneven * amp * fr * np.cos(fr * u + ph)
    i = np.floor(t)
    return t, i, t - i, bed_m / dtdu


def thickness_range(bed_m=BED["m"], uneven=BED["uneven"]):
    """(thinnest, thickest) local bed thickness in metres the harmonics allow."""
    k = sum(amp * fr for amp, fr, _ in HARM)
    return bed_m / (1.0 + uneven * k), bed_m / (1.0 - uneven * k)


def protrusion(c_r, c_g, hard=BED["hard"], hard_out=BED["hard_out"], soft_out=BED["soft_out"]):
    """Per bed from its two random values (0-1): (hard 0/1, P). A hard bed (c_r < hard) stands out hard_out[0] +
    hard_out[1] x c_g metres; a soft one +-soft_out."""
    c_r, c_g = np.asarray(c_r, float), np.asarray(c_g, float)
    is_hard = (c_r < hard).astype(float)
    p_hard = hard_out[0] + hard_out[1] * c_g
    p_soft = soft_out * (2.0 * c_g - 1.0)
    return is_hard, mix(p_soft, p_hard, is_hard)


def bed_profile(f, thk, P, P_hi, edge=BED["edge"], edge_max=BED["edge_max"], under=BED["under"],
                under_w=BED["under_w"], shelf=BED["shelf"], lip=BED["lip"], overhang_w=BED["overhang_w"]):
    """Relief inside one bed. f: position in the bed (0-1), thk: bed thickness (m), P: this bed's protrusion, P_hi:
    the bed above's. Over the top e = min(edge / thk, edge_max) of the bed the height eases from P to P_hi
    (smoothstep), so h equals the next bed's P exactly at the boundary. Where the bed above overhangs (P_hi - P past
    shelf), the band under_w m below that ramp is cut back by `under` m. Returns dict(h (m), ramp, s_hi = P - P_hi,
    ledge: the pale lip of a shelf (this bed stands out past the one above), overhang: the dark recess under an
    overhang); ledge and overhang are 0 at both ends of the bed."""
    f, thk = np.asarray(f, float), np.asarray(thk, float)
    e = np.minimum(edge / thk, edge_max)
    top = 1.0 - e
    ramp = smoothstep(top, 1.0, f)
    s_hi = np.asarray(P, float) - np.asarray(P_hi, float)
    ov = smoothstep(-shelf[0], -shelf[1], s_hi)
    sh = smoothstep(shelf[0], shelf[1], s_hi)
    cut = ov * smoothstep(top - under_w / thk, top, f) * (1.0 - ramp)
    h = P + (P_hi - P) * ramp - under * cut
    ledge = sh * smoothstep(top - lip / thk, top, f) * (1.0 - smoothstep(1.0 - 0.25 * e, 1.0, f))
    overhang = ov * smoothstep(top - overhang_w / thk, top, f) * (1.0 - ramp)
    return dict(h=h, ramp=ramp, s_hi=s_hi, ledge=ledge, overhang=overhang)


def eased(v, v_hi, f, ease=BED["ease"]):
    """A per-bed value eased into the next bed's over the top `ease` of the bed: never a step at a boundary."""
    return mix(v, v_hi, smoothstep(1.0 - ease, 1.0, f))


def joint_groove(e_m, width, depth):
    """Master joint groove: e_m the distance to the nearest joint (m, Voronoi distance to edge times the cell),
    width the groove's half width (m), depth (m). Returns (g, h): g 0 on the joint, 1 from `width` away; h = -depth
    x (1 - g), continuous wherever e_m is."""
    g = smoothstep(0.0, width, e_m)
    return g, -depth * (1.0 - g)


def joint_scale(strata, master_m=JOINT["master_m"], master_w=JOINT["master_w"], master_d=JOINT["master_d"]):
    """(cell m, half width m, depth m) of a variant's master joints: everything scales with strata / 2.5 (rock_cliff's
    strata 2.5 m gives 12 m cells, 0.6 m, 0.35 m); no fixed minimum, so a boulder's joints stay a boulder's size."""
    sj = float(strata) / 2.5
    return master_m * sj, master_w * sj, master_d * sj


def steep_mask(nz, steep=JOINT["steep"]):
    """1 on near-vertical faces, 0 on flat tops (|normal z| from steep[0] to steep[1]): joints only on walls, as the
    old graph did (a 2D Voronoi on a flat top reads as crazy paving)."""
    return smoothstep(steep[0], steep[1], np.abs(np.asarray(nz, float)))


def bed_steep_mask(nz, steep=BED["steep"]):
    """1 on near-vertical faces, 0 on slopes and flat tops: the beds' own mask (on a slope a level bed draws wide
    winding ribbons)."""
    return smoothstep(steep[0], steep[1], np.abs(np.asarray(nz, float)))


def gap_mask(n, gap):
    """How strongly the beds (BED["gap"]) or the joints (JOINT["gap"]) show where the 0-1 noise is n: gap[3] where n
    is under gap[1], 1 from gap[2] on. They come and go along a face."""
    return gap[3] + (1.0 - gap[3]) * smoothstep(gap[1], gap[2], n)


def fade_geo(geo_w, fade=GEO_FADE):
    """1 where geo_w is 0 (no relief), 0 from fade[1] on: the material's beds and joints step aside for real ones."""
    return 1.0 - smoothstep(fade[0], fade[1], geo_w)


def wiggle(px, py, pz, noise1, wig=JOINT["wiggle"]):
    """The joints' coordinates (qx, qy): x and y moved by +-wig[1] m, slowly (about wig[0] m) up the wall, so a
    joint is near-vertical, not ruled. noise1(w) -> (r, g), two 0-1 channels of a smooth 1D noise."""
    r, g = noise1(np.asarray(pz, float) / wig[0])
    return px + wig[1] * (2.0 * r - 1.0), py + wig[1] * (2.0 * g - 1.0)


def voronoi_edge(x, y, seed=0):
    """Distance (in cells) to the nearest Voronoi edge of a jittered unit grid, for the tests: the distance to the
    bisector of the two nearest sites, (d2^2 - d1^2) / (2 |s2 - s1|), as Blender's DISTANCE_TO_EDGE measures it."""
    x, y = np.asarray(x, float).ravel(), np.asarray(y, float).ravel()
    cx, cy = np.floor(x), np.floor(y)
    sites = []
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            gx, gy = cx + dx, cy + dy
            h = np.sin(gx * 127.1 + gy * 311.7 + seed * 74.7) * 43758.5453
            j = h - np.floor(h)
            h2 = np.sin(gx * 269.5 + gy * 183.3 + seed * 12.9) * 43758.5453
            k = h2 - np.floor(h2)
            sites.append(np.stack([gx + j, gy + k], 1))
    S = np.stack(sites, 1)                                   # (n, 25, 2)
    d2 = ((S - np.stack([x, y], 1)[:, None, :]) ** 2).sum(2)
    o = np.argsort(d2, 1)
    n = len(x)
    a = S[np.arange(n), o[:, 0]]
    best = np.full(n, np.inf)
    p = np.stack([x, y], 1)
    for m in range(1, 8):                                    # the nearest bisector among the next sites
        b = S[np.arange(n), o[:, m]]
        mid = 0.5 * (a + b)
        nrm = (b - a) / np.maximum(np.linalg.norm(b - a, axis=1, keepdims=True), 1e-12)
        best = np.minimum(best, ((mid - p) * nrm).sum(1))
    return best


def struct_height(h_bed, h_joint, steep, bed_on, joint_on):
    """The one Bump node's height (m): the bed relief times bed_on plus the joint groove times joint_on and the
    steep mask."""
    return bed_on * h_bed + joint_on * steep * h_joint
