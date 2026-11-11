"""Opening question as title and video cover (1080x1920).

The question appears already in frame 0, as a title: everything at the same size, in balanced lines, with the
keyword in amber (3 of the 8 viral videos use the first frame as the cover).
(see docs/covers.md).

The cover is frame 0 without the live panel: clean Blender frame (build/<slug>/blender/full.mp4) + the same
title layer + the handle. The title stays inside the middle 3:4 crop (y from 240 to 1680), which is what TikTok
and Instagram show in the profile grid.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import brand, graphics
from .script import Script
from .util import ROOT, build_dir, run

TITLE_SIZE = 100                   # "vanished overnight?" fits in 900 px: 2 lines, no lone word
TITLE_MAX_W = 900
TITLE_LINE = 1.12                  # line height (fraction of the size)
# Top of the title inside the central square (y from 420 to 1500), which shows in any crop: 1:1 (upload
# in the Instagram browser), 4:5 (feed), 3:4 (profile grid) and 9:16. At y = 300 the 1:1 cut off the
# first line.
TOP_Y = 470
# Dark gradient at the top, so the title reads over the lit city: full until near the title and gone before the
# panel (y = 860), which sits under this layer in the video.
SHADE_H = 840
SHADE_ALPHA = 0.72
SHADE_FULL = 0.6                   # fraction of SHADE_H with full dark; then it fades smoothly


def _shade() -> Image.Image:
    """Darkens the top of the image and fades downward (no edge)."""
    shade = Image.new("RGBA", (brand.W, SHADE_H), brand.VACUO)
    alpha = Image.new("L", (1, SHADE_H))
    for y in range(SHADE_H):
        u = max(0.0, (y / SHADE_H - SHADE_FULL) / (1 - SHADE_FULL))
        alpha.putpixel((0, y), int(255 * SHADE_ALPHA * (1 - u * u * (3 - 2 * u))))
    shade.putalpha(alpha.resize((brand.W, SHADE_H)))
    return shade


def _title(question: str, highlight: tuple[str, ...]) -> Image.Image:
    """The centered question, in lines of similar width, with the keyword in amber."""
    f = graphics.font("bold", TITLE_SIZE)
    words = question.split()
    space = f.getlength(" ")
    lines = graphics._balanced_lines(words, [f.getlength(w) for w in words], space, TITLE_MAX_W)
    keys = {h.lower() for h in highlight}
    img = Image.new("RGBA", (brand.W, brand.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x = (brand.W - f.getlength(" ".join(line))) / 2
        y = TOP_Y + i * int(TITLE_SIZE * TITLE_LINE)
        for w in line:
            d.text((x, y), w, font=f, fill=brand.LUZ if w.strip("?!.,").lower() in keys else brand.TEXTO)
            x += f.getlength(w) + space
    return graphics.with_shadow(img)


def _layer(question: str, highlight: tuple[str, ...]) -> Image.Image:
    """Transparent 1080x1920 layer (gradient + title): the same in the video and the cover."""
    layer = Image.new("RGBA", (brand.W, brand.H), (0, 0, 0, 0))
    layer.alpha_composite(_shade(), (0, 0))
    layer.alpha_composite(_title(question, highlight))
    return layer


def hook(question: str, highlight: tuple[str, ...], out: Path) -> Path:
    """Opening question of the video (text format)."""
    _layer(question, highlight).save(out)
    return out


def make(script: Script, handle_png: Path | None = None) -> Path:
    """Cover = frame 0 without the panel: clean Blender frame + title + handle."""
    first = script.scenes[0]
    titled = script.panel                  # "panel": false (2D series) = video without title; the cover too
    if titled and not first.on_screen:
        raise SystemExit("Cover: scene 01 has no 'on_screen' (the question).")
    src = build_dir(script.slug) / "blender" / "full.mp4"
    if not src.exists() and first.flat:
        src = ROOT / "clips" / script.slug / f"{first.id}.mp4"    # 2D clip is already the clean frame (no caption)
    if not src.exists():
        raise SystemExit(f"Cover: the video without text is missing ({src}). Run 'blender' (or 'flat2d') first.")
    work = build_dir(script.slug) / "cover"
    work.mkdir(parents=True, exist_ok=True)
    frame = work / "frame0.png"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={brand.W}:{brand.H}:force_original_aspect_ratio=increase,crop={brand.W}:{brand.H}",
         str(frame)])
    canvas = Image.open(frame).convert("RGBA")
    if titled:
        canvas.alpha_composite(_layer(first.on_screen, first.highlight))
    handle = Image.open(handle_png or graphics.handle(work / "handle.png")).convert("RGBA")
    canvas.alpha_composite(handle, brand.HANDLE_XY)
    out = ROOT / "out" / f"{script.slug}.cover.jpg"
    out.parent.mkdir(exist_ok=True)
    canvas.convert("RGB").save(out, quality=94)
    return out
