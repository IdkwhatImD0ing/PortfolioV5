"""Clay version of the fly-through: every surface plain grey, so an AI video model can't copy
the blocking's colours and textures and has to paint the look from the prompt and the style
frames. Shapes, camera, sky, volumetric clouds and glowing elements (light pillars, runes,
lanterns, the moon) are kept as cues.

    blender -b out/sect_chase.blend --python sect/clay.py -- --start 1 --end 288 --out out/frames_clay
"""
import argparse
import os
import re
import sys

import bpy

KEEP = re.compile(r"glow|rune|beam|light|lantern|molten|ember|moon|halo|spark|pillar|shield|screen_lit|trail|fire",
                  re.IGNORECASE)


def _output(m):
    for n in m.node_tree.nodes:
        if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output:
            return n
    return None


def clay_material():
    m = bpy.data.materials.get("clay") or bpy.data.materials.new("clay")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def claify():
    clay = clay_material()
    kept, swapped = [], 0
    for m in list(bpy.data.materials):
        if m == clay or not m.use_nodes or m.node_tree is None:
            continue
        out = _output(m)
        volume_only = out is not None and out.inputs["Volume"].is_linked and not out.inputs["Surface"].is_linked
        if volume_only or KEEP.search(m.name):
            kept.append(m.name)
            continue
        m.user_remap(clay)
        swapped += 1
    print("CLAY swapped", swapped, "kept", len(kept), sorted(kept)[:40], flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=288)
    ap.add_argument("--out", default="out/frames_clay")
    a = ap.parse_args(argv)
    claify()
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = a.start, a.end
    sc.render.filepath = os.path.join(os.path.abspath(a.out), "####")
    bpy.ops.render.render(animation=True)
    print("CLAY done", a.start, a.end, flush=True)


if __name__ == "__main__":
    main()
