"""Test v4: the series HUD (day since the outbreak + time of day, occasional info chip)
and karaoke caption (amber box on the spoken word), over the approved v3 shots (floor plan and close).

    py tools/flat2d/style_v4.py            # stills v4-*.png + folha
    py tools/flat2d/style_v4.py --clip     # 6 s clip with simulated word timings
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_v3 as v3  # noqa: E402

S, W, H = v3.S, v3.W, v3.H
OUT = v3.OUT
AMB, VAC, TXT, QUI = v3.AMB, v3.VAC, v3.TXT, v3.QUI

# the v3 shots without title, old panel or caption
v3.panel = lambda *a, **k: None
v3.caption = lambda *a, **k: None


def clock12(minutes):
    h, m = divmod(int(minutes), 60)
    suf = "PM" if h % 24 >= 12 else "AM"
    return f"{(h % 12) or 12}:{m:02d} {suf}"


def hud(img, day, minutes, chip=None, chip_alpha=1.0, chip_level=None):
    """Fixed clock at the top left + occasional chip below (fade and slide)."""
    d = ImageDraw.Draw(img)
    x, y = 72 * S, 230 * S
    fd = v3.F(v3.brand.FONT_NUMBER, 34)
    fc = ImageFont.truetype(str(v3.ROOT / "fonts" / v3.brand.FONT_CLOCK), 32 * S)
    fc.set_variation_by_axes([400])
    # everything on the same baseline (anchor "ls"); the mono is scaled down so the cap height matches Barlow
    base = y + 34 * S
    d.text((x, base), f"DAY {day}", font=fd, fill=AMB, anchor="ls")
    dx = x + d.textlength(f"DAY {day}", font=fd) + 14 * S
    cap_b = fd.getbbox("D", anchor="ls")[1]
    dot_y = base + cap_b / 2
    d.ellipse([dx, dot_y - 3 * S, dx + 6 * S, dot_y + 3 * S], fill=QUI)
    d.text((dx + 20 * S, base), clock12(minutes), font=fc, fill=TXT, anchor="ls")
    if chip and chip_alpha > 0:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        off = int((1 - chip_alpha) * 24 * S)
        cy = y + 64 * S
        lab, val = chip
        fl = v3.F(v3.brand.FONT_BOLD, 22)
        fv = v3.F(v3.brand.FONT_NUMBER, 40)
        wbox = max(ld.textlength(lab, font=fl), ld.textlength(val, font=fv)) + 44 * S
        a = int(255 * chip_alpha)
        ld.rounded_rectangle([x - off, cy, x - off + wbox, cy + (112 if chip_level is not None else 96) * S], 12 * S,
                             fill=(27, 35, 51, int(230 * chip_alpha)))
        ld.rectangle([x - off, cy, x - off + 6 * S, cy + (112 if chip_level is not None else 96) * S], fill=AMB + (a,))
        ld.text((x - off + 22 * S, cy + 12 * S), lab, font=fl, fill=QUI + (a,))
        ld.text((x - off + 22 * S, cy + 38 * S), val, font=fv, fill=TXT + (a,))
        if chip_level is not None:
            bx0, by = x - off + 22 * S, cy + 94 * S
            bw = wbox - 44 * S
            ld.rectangle([bx0, by, bx0 + bw, by + 6 * S], fill=(60, 68, 84, a))
            ld.rectangle([bx0, by, bx0 + int(bw * chip_level), by + 6 * S], fill=AMB + (a,))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return img


def karaoke(img, words, active, y=1330):
    """Stretch of 1 to 4 words; the spoken one is covered by an amber box with dark text."""
    d = ImageDraw.Draw(img)
    f = v3.F(v3.brand.FONT_NUMBER, 84)
    up = [w.upper() for w in words]
    sp = d.textlength(" ", font=f)
    widths = [d.textlength(w, font=f) for w in up]
    total = sum(widths) + sp * (len(up) - 1)
    x = W / 2 - total / 2
    yy = y * S
    for i, (w, wd) in enumerate(zip(up, widths)):
        if i == active:
            d.rounded_rectangle([x - 14 * S, yy - 56 * S, x + wd + 14 * S, yy + 50 * S], 12 * S, fill=AMB)
            d.text((x, yy), w, font=f, fill=VAC, anchor="lm")
        else:
            d.text((x, yy), w, font=f, fill=TXT, anchor="lm", stroke_width=6 * S, stroke_fill=VAC)
        x += wd + sp
    return img


# simulated speech: (word, start, end) in s; stretches of up to 4 words
LINES = [
    [("They", 0.20, 0.45), ("spread", 0.45, 0.95), ("fast.", 0.95, 1.40)],
    [("Sam", 1.70, 1.95), ("locks", 1.95, 2.30), ("the", 2.30, 2.40), ("door.", 2.40, 2.90)],
    [("Then", 3.40, 3.65), ("someone", 3.65, 4.10), ("knocks.", 4.10, 4.70)],
]


def caption_at(t):
    for ln in LINES:
        if ln[0][1] - 0.15 <= t <= ln[-1][2] + 0.35:
            act = next((i for i, (_, s, e) in enumerate(ln) if s <= t < e), None)
            if act is None:
                act = len(ln) - 1 if t >= ln[-1][2] else -1
            return [w for w, _, _ in ln], act
    return None, None


def frame(t):
    if t < 3.2:
        img = v3.dir_a(min(1.0, t / 3.0))
    else:
        p = min(1.0, (t - 3.2) / 2.8)
        img = v3.dir_c(p)
        n = int((t - 3.2) * 30)
        if any(abs(n - k) < 2 for k in (27, 36, 45)):
            img = img.transform(img.size, Image.AFFINE, (1, 0, 6 * S, 0, 1, 0))
    minutes = 18 * 60 + 40 + t * 0.5
    # chip: supplies enter at 1.8 s and leave at 4.8 s
    a = max(0.0, min(1.0, (t - 1.8) / 0.3, (4.8 - t) / 0.3))
    img = hud(img, 0, minutes, ("SUPPLIES", "9 DAYS"), a, 0.6)
    words, act = caption_at(t)
    if words:
        img = karaoke(img, words, act)
    return img.resize((v3.brand.W, v3.brand.H), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--clip" in sys.argv:
        fr = OUT / "v4-frames"
        fr.mkdir(exist_ok=True)
        for i in range(180):
            frame(i / 30).save(fr / f"{i:04d}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", str(fr / "%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(OUT / "v4-clip.mp4")], check=True)
        print(OUT / "v4-clip.mp4")
        return
    shots = [frame(0.7), frame(2.6), frame(4.2)]
    sheet = Image.new("RGB", (v3.brand.W * 3 // 2 + 40, v3.brand.H // 2), (6, 6, 8))
    for i, im in enumerate(shots):
        im.save(OUT / f"v4-{i + 1}.png")
        sheet.paste(im.resize((v3.brand.W // 2, v3.brand.H // 2)), (i * (v3.brand.W // 2 + 20), 0))
    sheet.save(OUT / "v4-folha.png")
    print(OUT / "v4-folha.png")


if __name__ == "__main__":
    main()
