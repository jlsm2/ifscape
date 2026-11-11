"""Catalog showcase: grid of models with the id underneath, to pick a piece by image.

    blender -b -P tools/stage/sheet.py -- <folder> <type[,type]> [--pack quaternius/] [--all-seasons] [--cols 8] [--rows 5]
Writes <folder>/sheet_<type>_<n>.png (one page per cols x rows models). Static pieces only (rigged ones
show up in the scene test).
"""

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

import models  # noqa: E402


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = Path(args[0])
    out.mkdir(parents=True, exist_ok=True)
    kinds = args[1].split(",")
    opt = lambda n, d=None: args[args.index(n) + 1] if n in args else d
    cols, rows = int(opt("--cols", 8)), int(opt("--rows", 5))
    for kind in kinds:
        ids = []
        for pack in sorted({i["pack"] for i in models.CATALOG.values() if i["kind"] == kind}):
            if opt("--pack") and opt("--pack") not in pack:
                continue
            spec = {"kind": kind, "pack": pack}
            if args.count("--all-seasons"):
                ids += sorted(i["id"] for i in models.CATALOG.values() if i["kind"] == kind and i["pack"] == pack)
            else:
                ids += models.pool_of(spec)
        ids = [i for i in ids if not models.is_rigged(i)]
        per = cols * rows
        for page, chunk in enumerate([ids[k:k + per] for k in range(0, len(ids), per)], 1):
            kit.reset_scene(1, 30)
            scene = bpy.context.scene
            scene.render.resolution_x, scene.render.resolution_y = 200 * cols, 220 * rows
            scene.render.use_compositing = False
            scene.render.engine = "BLENDER_EEVEE"
            world = bpy.data.worlds.new("w")
            world.use_nodes = True
            bg = world.node_tree.nodes["Background"]
            bg.inputs["Color"].default_value = kit.lin("#DCE6F0")
            bg.inputs["Strength"].default_value = 1.2
            scene.world = world
            sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
            sun.data.energy = 3.0
            sun.rotation_euler = (math.radians(55), 0, math.radians(-30))
            scene.collection.objects.link(sun)
            gap = 2.0
            for n, ident in enumerate(chunk):
                c, r = n % cols, n // cols
                obj = models.static_instance(ident, ident, scene.collection, height=1.5)
                tpl = models.static_template(ident)
                w = tpl.width * obj.scale[0]
                if w > 1.9:                                     # piece too wide: shrinks to fit the cell
                    k = 1.9 / w
                    obj.scale = tuple(s * k for s in obj.scale)
                obj.location = (c * gap, 0, -r * gap * 1.1)
                txt = bpy.data.curves.new(ident, "FONT")
                txt.body = ident if len(ident) < 22 else ident[:21] + "…"
                txt.size = 0.14
                txt.align_x = "CENTER"
                t = bpy.data.objects.new("t" + ident, txt)
                t.rotation_euler = (math.radians(90), 0, 0)
                t.location = (c * gap, 0, -r * gap * 1.1 - 0.22)
                t.data.materials.append(kit.flat("txt", "#101820"))
                scene.collection.objects.link(t)
            cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = max((cols) * gap, (rows) * gap * 1.1 * (1920 / 1080) * 0.6)
            cam.data.ortho_scale = cols * gap
            cam.location = ((cols - 1) * gap / 2, -20, -(rows - 1) * gap * 1.1 / 2 + 0.6)
            cam.rotation_euler = (math.radians(90), 0, 0)
            scene.collection.objects.link(cam)
            scene.camera = cam
            scene.render.filepath = str(out / f"sheet_{kind}_{page}.png")
            bpy.ops.render.render(write_still=True)
            print(f"sheet {kind} {page}: {len(chunk)} modelos")


main()
