"""YouTube channel banner (2560x1440) with the "Instrument" identity.

Background: three frames from the Blender sets side by side, darkened. Logo and text sit in the central strip
(1546x423), the only part visible on every device. Usage: py tools/channel_art.py
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ifscape import brand  # noqa: E402
from ifscape.graphics import font, with_shadow  # noqa: E402

W, H = 2560, 1440
SAFE_W, SAFE_H = 1546, 423
OUT = ROOT / "out" / "channel" / "youtube-banner.jpg"

# (video, second of the Blender full.mp4)
FRAMES = [("humans-vanished", 6.0), ("bacteria-disappeared", 9.0), ("pangaea-never-split", 72.0)]


def _frame(slug: str, t: float, work: Path) -> Image.Image:
    out = work / f"{slug}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i",
                    str(ROOT / "build" / slug / "blender" / "full.mp4"), "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def _background(work: Path) -> Image.Image:
    bg = Image.new("RGB", (W, H), brand.VACUO)
    panel_w = W // len(FRAMES)
    for i, (slug, t) in enumerate(FRAMES):
        img = _frame(slug, t, work)
        scale = max(panel_w / img.width, H / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        left, top = (img.width - panel_w) // 2, (img.height - H) // 2
        bg.paste(img.crop((left, top, left + panel_w, top + H)), (i * panel_w, 0))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)

    # Central strip in Vacuum, with soft edges, so the text reads well over any scene.
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    vacuo = Image.new("RGB", (1, 1), brand.VACUO).getpixel((0, 0))
    top, bottom, soft = (H - SAFE_H) // 2 - 40, (H + SAFE_H) // 2 + 40, 160
    for y in range(top - soft, bottom + soft):
        edge = min(y - (top - soft), (bottom + soft) - y)
        alpha = int(215 * min(1.0, edge / soft))
        draw.line([(0, y), (W, y)], fill=(*vacuo, alpha))
    out = bg.convert("RGBA")
    out.alpha_composite(band)
    return out


def _logo(size: int) -> Image.Image:
    """Eclipsed sun: amber crescent."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size - 1, size - 1), fill=brand.LUZ)
    off = int(size * 0.22)
    draw.ellipse((off, -off // 2, size - 1 + off, size - 1 - off // 2), fill=(0, 0, 0, 0))
    return img


def _spaced(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, f, fill, spacing: float) -> None:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + spacing


def _spaced_width(text: str, f, spacing: float) -> float:
    return sum(f.getlength(ch) for ch in text) + spacing * (len(text) - 1)


def make(work: Path) -> Path:
    canvas = _background(work)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    word_f, word_sp = font("bold", 150), 26
    tag_f, cta_f = font("text", 54), font("bold", 54)
    logo = _logo(150)
    word_w = _spaced_width("IFSCAPE", word_f, word_sp)
    gap = 24
    x0 = (W - (logo.width + gap + word_w)) / 2
    y_word = H / 2 - 165
    layer.alpha_composite(logo, (int(x0), int(y_word + 18)))
    _spaced(draw, (x0 + logo.width + gap, y_word), "IFSCAPE", word_f, brand.TEXTO, word_sp)

    draw.text((W / 2, H / 2 + 50), "What if…? Answered with real science.", font=tag_f, fill=brand.TEXTO, anchor="mm")
    draw.text((W / 2, H / 2 + 135), "What should I imagine next?", font=cta_f, fill=brand.LUZ, anchor="mm")

    canvas.alpha_composite(with_shadow(layer))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUT, quality=92)

    # Preview of how it looks on desktop: only the central strip.
    preview = canvas.crop(((W - SAFE_W) // 2, (H - SAFE_H) // 2, (W + SAFE_W) // 2, (H + SAFE_H) // 2))
    preview.convert("RGB").save(OUT.with_name("youtube-banner.desktop-preview.jpg"), quality=90)
    return OUT


if __name__ == "__main__":
    work = ROOT / "build" / "channel"
    work.mkdir(parents=True, exist_ok=True)
    print(make(work))
