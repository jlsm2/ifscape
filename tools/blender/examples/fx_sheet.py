"""Builds a side-by-side sheet with labels (Pillow, outside Blender) and measures the color of the fx_color samples.

    py tools/blender/examples/fx_sheet.py <output.png> <img1> <label1> [<img2> <label2> ...]
    py tools/blender/examples/fx_sheet.py --color build/fx-tests      (sheet + measurement of the color test)
"""

import colorsys
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parents[3] / "fonts" / "Barlow-SemiBold.ttf"


def sheet(out, items, width=540):
    imgs = [Image.open(p).convert("RGB") for p, _ in items]
    imgs = [im.resize((width, int(im.height * width / im.width))) for im in imgs]
    h = max(im.height for im in imgs)
    canvas = Image.new("RGB", (width * len(imgs) + 8 * (len(imgs) - 1), h + 56), "#0B0F17")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(FONT), 30) if FONT.exists() else ImageFont.load_default()
    for k, (im, (_, label)) in enumerate(zip(imgs, items)):
        x = k * (width + 8)
        canvas.paste(im, (x, 56))
        draw.text((x + 12, 12), label, fill="#F4F6F8", font=font)
    canvas.save(out)
    return out


def measure(folder):
    """5x5 px average on each sample: hex, hue (degrees) and HSV saturation of each image."""
    folder = Path(folder)
    data = json.loads((folder / "color_samples.json").read_text())
    rows = []
    for name, label in data["images"]:
        im = Image.open(folder / name).convert("RGB")
        for sample, (x, y) in data["samples"].items():
            px = [im.getpixel((x + dx, y + dy)) for dx in range(-2, 3) for dy in range(-2, 3)]
            r, g, b = (sum(c[i] for c in px) // len(px) for i in range(3))
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            rows.append(f"| {label} | {sample} | #{r:02X}{g:02X}{b:02X} | {hh * 360:.0f} | {ss:.2f} | {vv:.2f} |")
    print("| Transform | Sample | Screen color | Hue | Saturation | Value |\n|---|---|---|---|---|---|")
    print("\n".join(rows))
    sheet(folder / "a_color_side_by_side.png", [(folder / n, lbl) for n, lbl in data["images"]], width=432)


if __name__ == "__main__":
    if sys.argv[1] == "--color":
        measure(sys.argv[2])
    else:
        args = sys.argv[2:]
        sheet(sys.argv[1], list(zip(args[::2], args[1::2])))
