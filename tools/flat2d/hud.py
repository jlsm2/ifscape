"""The series HUD (approved; drawing from tools/flat2d/style_v4.py, hud(), ported
with the same values), isolated here so the drawing can be swapped without touching the rest:
  1. fixed clock at the top left: "DAY 0" in amber (Barlow SemiCondensed 34) + gray dot + time
     "6:42 PM" in JetBrains Mono wght 400 size 32, all on the same baseline (anchor "ls"), so the
     cap height matches;
  2. occasional chip below it (amber strip on the left, gray label, large value, optional level
     bar), which enters and leaves with a 0.3 s fade and slide.
No title and no old counter panel. Draws on the final frame (1080x1920), above the camera and the
shake, so the HUD neither wobbles nor scales with the zoom.

Swapping the drawing: only touch draw(); state() is the contract (what appears at each instant).
"""

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .common import AMB, FONT_BOLD, FONT_NUMBER, FONTS, QUI, TXT, clamp, font

XY = (72, 230)               # safe zone: below the TikTok/Reels bar, away from the buttons on the right
CHIP_FADE = 0.3              # chip entry and exit (s), with a CHIP_SLIDE px slide
CHIP_SLIDE = 24
CHIP_BG = (27, 35, 51)       # brand.NEVOA


@lru_cache(maxsize=None)
def _mono(size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / "JetBrainsMono[wght].ttf"), size)
    f.set_variation_by_axes([400])
    return f


def clock12(minutes: float) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{(h % 12) or 12}:{m:02d} {'PM' if h % 24 >= 12 else 'AM'}"


def state(spec: dict, t: float, seconds: float) -> dict:
    """spec = {'clock': (day, min_from, min_to) | None, 'chips': [{label, value, level?, t, for}]}."""
    out = {"clock": None, "chips": []}
    if spec.get("clock"):
        day, a, b = spec["clock"]
        out["clock"] = (day, a + (b - a) * clamp(t / seconds if seconds else 0.0))
    for c in spec.get("chips", []):
        t0, dur = c["t"], c.get("for", 3.0)
        a = clamp(min((t - t0) / CHIP_FADE, (t0 + dur - t) / CHIP_FADE, 1.0))
        if a > 0:
            out["chips"].append({"label": c["label"], "value": c["value"], "level": c.get("level"), "alpha": a})
    return out


def draw(img: Image.Image, st: dict) -> None:
    d = ImageDraw.Draw(img)
    x, y = XY
    if st["clock"]:
        day, minutes = st["clock"]
        fd, fc = font(34, FONT_NUMBER, 1), _mono(32)
        base = y + 34
        d.text((x, base), f"DAY {day}", font=fd, fill=AMB, anchor="ls")
        dx = x + d.textlength(f"DAY {day}", font=fd) + 14
        dot_y = base + fd.getbbox("D", anchor="ls")[1] / 2
        d.ellipse([dx, dot_y - 3, dx + 6, dot_y + 3], fill=QUI)
        d.text((dx + 20, base), clock12(minutes), font=fc, fill=TXT, anchor="ls")
    cy = y + 64
    for c in st["chips"]:
        a = c["alpha"]
        fl, fv = font(22, FONT_BOLD, 1), font(40, FONT_NUMBER, 1)
        lab, val = c["label"].upper(), c["value"].upper()
        wbox = int(max(fl.getlength(lab), fv.getlength(val)) + 44)
        h = 112 if c["level"] is not None else 96
        layer = Image.new("RGBA", (wbox + 1, h + 1), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([0, 0, wbox, h], 12, fill=CHIP_BG + (230,))
        ld.rectangle([0, 0, 6, h], fill=AMB)
        ld.text((22, 12), lab, font=fl, fill=QUI)
        ld.text((22, 38), val, font=fv, fill=TXT)
        if c["level"] is not None:
            bw = wbox - 44
            ld.rectangle([22, 94, 22 + bw, 100], fill=(60, 68, 84))
            ld.rectangle([22, 94, 22 + int(bw * clamp(c["level"])), 100], fill=AMB)
        if a < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
        img.paste(layer, (x - int((1 - a) * CHIP_SLIDE), cy), layer)
        cy += h + 12
