"""Ice-Fire Island's steam in the site's clouds.json, round 42 (owner, 2026-10-24: "The smoke from the ice and fire
island isnt matched to the volcano").

    python -I blender/xianxia-sect/tools/icefire_steam_clouds.py                 # client/public/sect/full/clouds.json
    python -I blender/xianxia-sect/tools/icefire_steam_clouds.py path/to/clouds.json [--check]

Why: the Blender puffs in clouds.json (world.cloud.*) are written only by `export_web.py -- clouds --profile full`,
and no batch has run that step since round 7. mist.py keeps whatever Blender puffs the last export left
(out/web/full/site/clouds.json) and copies them to the client. So the site still drew round 7's plume: 16 puffs and 3
wisps from where round 7's lava met its glacier, with the island at a yaw of 352.2 deg. Round 34 turned the island to
142.2 deg and round 36 rebuilt it with a volcano (sect/lib/icefire_island.py), so the old plume hung in the air about
13 m beside the new crater, its base 10.5 m above the molten pool (7.6 m above the rim).

What this writes: round 36's steam (icefire_island.build_steam, STEAM) where that build puts it, in the clouds.json
format (export_web.cmd_clouds): a 10-puff plume from 1 m above the crater's molten pool, drifting toward
STEAM['drift_az'] in the rock's frame, and 5 puffs where the second lava stream runs under the glacier's snout.
Sizes, overlap, drift, densities and each puff's own turn and depth ratio (nature.cloud_puff's U.rng stream, seeds
9100+k and 9200+k) are the build's. Only the build's shared random stream (the jitter of +-0.1 x size sideways and the
0.8-1.0 flatten) is replaced by a fixed one of our own, so `export_web.py clouds` gives the same plume up to those.

Where (three.js space, measured from the shipped library chunk, library.glb.gz's glow.molten piece): the crater's
molten pool ring centres on (313.05, 298.07, -992.75); the second stream ends at about (327.6, 282.06, -987.1). The
round-39 batch log puts the rock at Blender (330.08, 992.67, 281.53), turned 142.2 deg, and the volcano's centre at
(13.5, 10.4, 0.44) in the rock's frame, which lands on the same crater within 3 cm.

Idempotent: first drops the island's untagged puffs above the rock's top (the old plume, or an earlier run of this),
then adds the new ones where the first dropped puff was. --check only reports. The next `export_web.py -- clouds
--profile full` on the round-36 file supersedes this (it writes the build's own puffs at the same place).
"""
import json
import math
import os
import random
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT = os.path.join(ROOT, "client", "public", "sect", "full", "clouds.json")

# the rock (Blender world, metres / degrees): r39 batch log m_icefire.log "PATCH island scenery.island.009 ... at"
ROCK_AT = (330.08, 992.67, 281.53)
ROCK_YAW = 142.2
# rock frame (icefire_island.build_volcano log "centre"; S.stream2_end from the shipped molten stream's end)
VOLCANO_C = (13.5, 10.4, 0.44)
STREAM2_END = (-1.45, 5.92)
TOP_Z = 0.53                         # icefire_island Shape.z_top there (TOP_DOME x (1 - u^2), u = 6 m / 34 m)
# icefire_island constants (round 36)
VOLCANO = dict(height=19.0, crater=3.3)
STEAM = dict(plume=10, plume_size=(3.0, 0.75), snout=5, snout_size=(2.4, 0.6), overlap=0.45, drift_az=105.0,
             density=(0.55, 0.03))
# which existing puffs are the island's steam: untagged, small, over the rock's top (three space)
ISLAND_XZ = (330.08, -992.67)
ISLAND_R = 40.0
ROCK_TOP_Y = 281.0
SMALL = 12.0                         # m: largest semi-axis of a steam puff (the world's banks are 15-60 m)


def seed_from(*parts):
    """sect/lib/util.py seed_from."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def to_world(p):
    """Rock frame -> Blender world."""
    c, s = math.cos(math.radians(ROCK_YAW)), math.sin(math.radians(ROCK_YAW))
    return (ROCK_AT[0] + c * p[0] - s * p[1], ROCK_AT[1] + s * p[0] + c * p[1], ROCK_AT[2] + p[2])


def to_three(v):
    """Blender (x, y, z) -> three.js (x, z, -y) (export_web C3)."""
    return (v[0], v[2], -v[1])


def puff(loc, size, seed, density, flatten):
    """nature.cloud_puff parented to the rock: a unit icosphere scaled (h, h * fy, h * flatten), h = size / 2, turned
    rz about z, in the rock's frame; returned as a clouds.json entry (export_web.cmd_clouds rounding)."""
    r = random.Random(seed_from("nature.cloud", seed))
    rz = r.uniform(0, 2 * math.pi)
    fy = r.uniform(0.75, 1.0)
    h = size * 0.5
    sx, sy, sz = h, h * fy, h * flatten
    yaw = math.radians(ROCK_YAW) + rz
    c, s = math.cos(yaw), math.sin(yaw)
    cols = [(sx * c, sx * s, 0.0), (-sy * s, sy * c, 0.0), (0.0, 0.0, sz)]
    w = to_three(to_world(loc))
    return dict(c=[round(w[0], 2), round(w[1], 2), round(w[2], 2)],
                a=[[round(v, 3) for v in to_three(col)] for col in cols],
                d=round(density * 14.0 / max(1.0, size), 4))


def steam():
    """icefire_island.build_steam with our own stream in place of the build's shared one."""
    rnd = random.Random(seed_from("r42.icefire_steam"))
    t = math.radians(STEAM["drift_az"])
    drift = (math.cos(t), math.sin(t))
    vx, vy, vz = VOLCANO_C
    out = []
    for base, n, size0, dsize, seed0 in (
            ((vx, vy, vz + VOLCANO["height"] - VOLCANO["crater"] + 1.0), STEAM["plume"], STEAM["plume_size"][0],
             STEAM["plume_size"][1], 9100),
            ((STREAM2_END[0], STREAM2_END[1], TOP_Z + 1.0), STEAM["snout"], STEAM["snout_size"][0],
             STEAM["snout_size"][1], 9200)):
        h = 0.0
        for k in range(n):
            size = size0 + dsize * k
            if k:
                h += STEAM["overlap"] * size
            jx, jy = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
            dr = 0.035 * h ** 1.5
            loc = (base[0] + drift[0] * dr + jx * size * 0.1, base[1] + drift[1] * dr + jy * size * 0.1, base[2] + h)
            dens = max(0.16, STEAM["density"][0] - STEAM["density"][1] * k)
            out.append(puff(loc, size, seed0 + k, dens, rnd.uniform(0.8, 1.0)))
    return out


def is_island_steam(p):
    if p.get("k") is not None:
        return False
    x, y, z = p["c"]
    r = max(math.sqrt(sum(v * v for v in a)) for a in p["a"])
    return r < SMALL and y > ROCK_TOP_Y and math.hypot(x - ISLAND_XZ[0], z - ISLAND_XZ[1]) < ISLAND_R


def main(argv):
    check = "--check" in argv
    paths = [a for a in argv if not a.startswith("--")] or [DEFAULT]
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        puffs = data["puffs"]
        old = [i for i, p in enumerate(puffs) if is_island_steam(p)]
        new = steam()
        low = min(old, key=lambda i: puffs[i]["c"][1]) if old else None
        print("%s: %d island steam puffs now (lowest at %s), %d to write (plume base %s, snout base %s)" % (
            path, len(old), puffs[low]["c"] if low is not None else None, len(new), new[0]["c"],
            new[STEAM["plume"]]["c"]))
        if check:
            continue
        at = old[0] if old else len(puffs)
        keep = [p for i, p in enumerate(puffs) if i not in set(old)]
        at -= sum(1 for i in old if i < at)
        data["puffs"] = keep[:at] + new + keep[at:]
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, separators=(",", ":"))           # as mist.py writes it
        print("wrote", path, len(data["puffs"]), "puffs")


if __name__ == "__main__":
    main(sys.argv[1:])
