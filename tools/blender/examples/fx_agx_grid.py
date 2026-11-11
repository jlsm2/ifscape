"""Emission map in AgX: grid of emissive squares (green/red x strength) to find the INPUT that gives
a target screen color (e.g. amber #F5A524 or orange #FF6A00). Orthographic camera, no light, no shadow.

    blender -b -P tools/blender/examples/fx_agx_grid.py -- <folder> [AgX|Standard] [look]
Writes agx_grid_<view>.png and agx_grid.json (input of each cell). Searching for the best cell is fx_sheet's job.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

import fx_common as fx  # noqa: E402
import kit  # noqa: E402

N = 16
GREENS = [0.10 + 0.04 * i for i in range(N)]              # g/r of the linear input color (b = 0)
STRENGTHS = [0.35 * (1.18 ** j) for j in range(N)]         # 0.35 .. ~4.8


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = Path(args[0])
    transform = args[1] if len(args) > 1 else "AgX"
    look = args[2] if len(args) > 2 else "None"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = N * 40
    scene.eevee.taa_render_samples = 1
    fx.view(scene, transform, look)
    cells = []
    for i, g in enumerate(GREENS):
        for j, s in enumerate(STRENGTHS):
            mat = bpy.data.materials.new(f"c{i}_{j}")
            p = kit.principled(mat)
            p.inputs["Base Color"].default_value = (0, 0, 0, 1)
            p.inputs["Specular IOR Level"].default_value = 0.0
            p.inputs["Emission Color"].default_value = (1.0, g, 0.0, 1)
            p.inputs["Emission Strength"].default_value = s
            kit.mesh_object(f"q{i}_{j}", [(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)],
                            [(0, 1, 2, 3)], [mat])
            cells.append({"g": round(g, 3), "strength": round(s, 3), "px": [i * 40 + 20, (N - 1 - j) * 40 + 20]})
    cam_data = bpy.data.cameras.new("Ortho")
    cam_data.type, cam_data.ortho_scale = "ORTHO", N
    cam = bpy.data.objects.new("Ortho", cam_data)
    cam.location = (N / 2, N / 2, 10)
    scene.collection.objects.link(cam)
    scene.camera = cam
    tag = f"{transform}_{look}".replace(" ", "").replace("-", "")
    fx.render(scene, out / f"agx_grid_{tag}.png")
    (out / "agx_grid.json").write_text(json.dumps(cells))


main()
