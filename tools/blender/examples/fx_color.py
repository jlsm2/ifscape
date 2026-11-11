"""Test (a): the same orange fireball in AgX, AgX - Punchy, Standard and Khronos PBR Neutral.

Four faceted balls with the SAME emission color (#FF6A00) and strengths 0.8 / 2 / 5 / 15, plus a brand amber
plate (#F5A524, emission 1.0) to see whether the palette comes out faithful. Renders one image per transform and writes the
on-screen positions of each sample to samples.json (to measure the color afterwards).

    blender -b -P tools/blender/examples/fx_color.py -- <output folder>
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fx_common as fx  # noqa: E402

FIRE = "#FF6A00"
STRENGTHS = (0.8, 2.0, 5.0, 15.0)
VIEWS = (("AgX", "None"), ("AgX", "AgX - Punchy"), ("Standard", "None"), ("Khronos PBR Neutral", "None"))


def build():
    scene = fx.night_scene(cam_loc=(0, -11, 3.0), target=(0, 0, 2.6))
    fx.props(scene, random.Random(3), n=8, y0=6)
    samples = {}
    for k, s in enumerate(STRENGTHS):
        x, z = (-1.7 if k % 2 == 0 else 1.7), (4.6 if k < 2 else 1.8)
        v, f = fx.ico(2, 1.1)
        fx.flat_obj(f"Fire{k}", fx.lumpy(v, seed=k, amount=0.18), f, fx.emitter(f"Fire{k}", FIRE, s), (x, 0, z))
        samples[f"fogo x{s:g}"] = fx.screen_xy(scene, (x, -1.05, z))
    patch = fx.emitter("Brand", "#F5A524", 1.0)
    fx.flat_obj("Brand", [(-0.6, 0, 0), (0.6, 0, 0), (0.6, 0, 0.5), (-0.6, 0, 0.5)], [(0, 1, 2, 3)], patch,
                (0, -1.5, 0.2))
    samples["brand #F5A524 x1"] = fx.screen_xy(scene, (0, -1.5, 0.45))
    return scene, samples


def main():
    out = Path(sys.argv[sys.argv.index("--") + 1])
    out.mkdir(parents=True, exist_ok=True)
    scene, samples = build()
    names = []
    for transform, look in VIEWS:
        fx.view(scene, transform, look)
        name = f"color_{transform}_{look}".replace(" ", "").replace("-", "") + ".png"
        fx.render(scene, out / name)
        names.append([name, f"{transform} / {look}"])
    (out / "color_samples.json").write_text(json.dumps({"images": names, "samples": samples}, indent=1))


main()
