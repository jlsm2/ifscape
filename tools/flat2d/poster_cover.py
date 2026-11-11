"""Poster covers of the series The Millbrook Outbreak (1080x1920), in the viral-video style (docs/covers.md):
clean clip frame at full screen, the series name small on top and the part number big in amber with a
warm glow. ONLY that: no spoilers. The frame is the same across parts (Sam, the
amber headlamp); only the number changes.

All text sits inside the central square (y 420 to 1500), which shows in 1:1, 4:5, 3:4 and 9:16.

Uso: py tools/flat2d/poster_cover.py [1 2 3 4]    -> out/zombie-outbreak/zombie-outbreak-N.cover.jpg
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ifscape import brand, graphics  # noqa: E402

PARTS = (1, 2, 3, 4)
FRAME = ("zombie-outbreak-1", "02", 2.5)   # clip, scene, second: Sam from the front, no threat or hint of the story
DROP = 340                                  # frame drop in px: puts the face below the text block
HUD_BOX = (40, 200, 440, 420)               # "DAY 0 · time" clock baked into the clip
TITLE = "THE MILLBROOK OUTBREAK"

TOP_Y = 500
KEY_SIZE = 300
KEY_MAX_W = 940
SHADE_H = 1120
SHADE_ALPHA = 0.80
SHADE_FULL = 0.55


def _frame(slug: str, scene: str, t: float, out: Path) -> Image.Image:
    src = ROOT / "clips" / slug / f"{scene}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(src), "-frames:v", "1",
                    "-vf", f"scale={brand.W}:{brand.H}:force_original_aspect_ratio=increase,crop={brand.W}:{brand.H}",
                    str(out)], check=True)
    return Image.open(out).convert("RGBA")


def _clean_hud(img: Image.Image) -> Image.Image:
    """Erases the clip's HUD: fills the box with a gradient between the color just above and just below it."""
    x0, y0, x1, y1 = HUD_BOX
    top = img.crop((x0, y0 - 6, x1, y0 - 2)).resize((1, 1), Image.BOX).getpixel((0, 0))
    bot = img.crop((x0, y1 + 2, x1, y1 + 6)).resize((1, 1), Image.BOX).getpixel((0, 0))
    patch = Image.new("RGBA", (x1 - x0, y1 - y0))
    px = patch.load()
    for y in range(y1 - y0):
        u = y / (y1 - y0 - 1)
        row = tuple(int(top[i] * (1 - u) + bot[i] * u) for i in range(4))
        for x in range(x1 - x0):
            px[x, y] = row
    img.paste(patch, (x0, y0))
    return img


def _shade() -> Image.Image:
    shade = Image.new("RGBA", (brand.W, SHADE_H), brand.VACUO)
    alpha = Image.new("L", (1, SHADE_H))
    for y in range(SHADE_H):
        u = max(0.0, (y / SHADE_H - SHADE_FULL) / (1 - SHADE_FULL))
        alpha.putpixel((0, y), int(255 * SHADE_ALPHA * (1 - u * u * (3 - 2 * u))))
    shade.putalpha(alpha.resize((brand.W, SHADE_H)))
    return shade


def _spaced(d: ImageDraw.ImageDraw, text: str, f, y: int, fill, track: float) -> None:
    """Centered text with letter spacing (series name in caps)."""
    widths = [f.getlength(c) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    x = (brand.W - total) / 2
    for c, w in zip(text, widths):
        d.text((x, y), c, font=f, fill=fill)
        x += w + track


def _fit(text: str):
    size = KEY_SIZE
    while size > 80:
        f = graphics.font("number", size)
        if f.getlength(text) <= KEY_MAX_W:
            return f
        size -= 6
    return graphics.font("number", size)


def _text_layer(part: int) -> Image.Image:
    layer = Image.new("RGBA", (brand.W, brand.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    _spaced(d, TITLE, graphics.font("bold", 52), TOP_Y, brand.TEXTO, 7)
    key = f"PART {part}"
    f = _fit(key)
    kx = (brand.W - f.getlength(key)) / 2
    ky = TOP_Y + 70
    glow = Image.new("RGBA", (brand.W, brand.H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((kx, ky), key, font=f, fill=brand.LUZ)
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(34)))      # warm glow behind the number
    layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d.text((kx, ky), key, font=f, fill=brand.LUZ)
    return graphics.with_shadow(layer)


def make(part: int, out_dir: Path) -> Path:
    slug = f"zombie-outbreak-{part}"
    work = ROOT / "build" / slug / "cover"
    work.mkdir(parents=True, exist_ok=True)
    src_slug, scene, t = FRAME
    frame = _clean_hud(_frame(src_slug, scene, t, work / "poster-frame.png"))
    canvas = Image.new("RGBA", (brand.W, brand.H), brand.VACUO)
    canvas.alpha_composite(frame, (0, DROP))
    canvas.alpha_composite(_shade(), (0, 0))
    canvas.alpha_composite(_text_layer(part))
    handle = Image.open(graphics.handle(work / "handle.png")).convert("RGBA")
    canvas.alpha_composite(handle, brand.HANDLE_XY_SERIES)
    out = out_dir / f"{slug}.cover.jpg"
    canvas.convert("RGB").save(out, quality=94)
    return out


if __name__ == "__main__":
    parts = [int(a) for a in sys.argv[1:]] or list(PARTS)
    out_dir = ROOT / "out" / "zombie-outbreak"
    for p in parts:
        print(make(p, out_dir))
