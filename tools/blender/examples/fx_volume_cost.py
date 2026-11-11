"""Volume cost in Eevee: the same cloud as a matte faceted mesh and as a Principled Volume (noise in the density).
Renders at 1080x1920, 32 samples, and prints the time of each one. Writes vol_mesh.png and vol_volume.png.

    blender -b -P tools/blender/examples/fx_volume_cost.py -- <folder>
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

import fx_common as fx  # noqa: E402
import kit  # noqa: E402
from kit import lin  # noqa: E402


def volume_material():
    mat = bpy.data.materials.new("Vol")
    nt = mat.node_tree
    nt.nodes.remove(kit.principled(mat))
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = lin("#9C8670")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.5
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.45, 0.6
    ramp.inputs["To Max"].default_value = 6.0
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], vol.inputs["Density"])
    out = nt.nodes["Material Output"]
    for link in list(out.inputs["Surface"].links):
        nt.links.remove(link)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1])
    times = {}
    for kind in ("mesh", "volume"):
        scene = fx.night_scene(res=(1080, 1920), samples=32, cam_loc=(0, -9, 1.65), target=(0, 0, 1.6), lens=24)
        v, f = fx.ico(2 if kind == "mesh" else 3, 1.6)
        if kind == "mesh":
            mat = kit.flat("Dust", "#9C8670", rough=1.0)
            kit.principled(mat).inputs["Specular IOR Level"].default_value = 0.0
        else:
            mat = volume_material()
        o = fx.flat_obj("Cloud", fx.lumpy(v, seed=2, amount=0.2), f, mat, (0, 0, 1.6))
        o.visible_shadow = False
        fx.render(scene, out / f"vol_{kind}_warmup.png")         # the 1st render compiles shaders: it does not count
        t0 = time.perf_counter()
        fx.render(scene, out / f"vol_{kind}.png")
        times[kind] = time.perf_counter() - t0
    print("TEMPOS", {k: round(v, 2) for k, v in times.items()})


main()
