"""2D style test v2, in the line of a reference channel: flat color without outline, dark background,
simple characters (round head, dot eye, block body, thin limbs), infected as black silhouettes,
explainer card in the middle of the story, caption in caps on a strip and pill-shaped stamp.

    py tools/flat2d/style_v2.py [--clip]
Outputs in build/zombie-outbreak-1/style-test/v2-*.png (+ v2-clip.mp4).
"""

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ifscape import brand  # noqa: E402

OUT = ROOT / "build" / "zombie-outbreak-1" / "style-test"
S = 2
W, H = brand.W * S, brand.H * S
FPS = 30

BG = (38, 42, 54)
BG2 = (30, 33, 44)
WALL = (52, 57, 72)
WALL2 = (44, 48, 62)
FLOOR = (64, 46, 36)
LIT = (245, 190, 90)
AMBER = (245, 165, 36)
RED = (214, 72, 52)
SIL = (14, 14, 18)
CREAM = (238, 226, 200)


def F(name, size):
    return ImageFont.truetype(str(ROOT / "fonts" / name), int(size * S))


def rr(d, box, r, fill):
    d.rounded_rectangle([int(v) for v in box], int(r), fill=fill)


def line(d, a, b, w, fill):
    d.line([a, b], fill=fill, width=int(w))
    for p in (a, b):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=fill)


# ---------- personagens ----------

def person(d, x, feet, k, shirt, pants, skin=(214, 160, 120), hair=(40, 30, 26), coat=False, cap=None,
           grey=False, glasses=False, walk=0.0, look=0.0, scared=0.0, kid=False):
    """Flat character. x = center, feet = floor y, k = scale, walk = step phase (0 = still)."""
    u = S * k * (0.72 if kid else 1.0)
    bob = abs(math.sin(walk)) * 6 * u if walk else 0
    hip = feet - 150 * u - bob
    sh = hip - 150 * u
    hc = (x, sh - 62 * u)
    sw = math.sin(walk) * 0.45 if walk else 0
    # pernas
    for s, sg in ((-1, sw), (1, -sw)):
        h0 = (x + s * 16 * u, hip)
        f0 = (h0[0] + math.sin(sg) * 150 * u, hip + math.cos(sg) * 150 * u)
        line(d, h0, f0, 22 * u, pants)
        rr(d, (f0[0] - 14 * u, f0[1] - 8 * u, f0[0] + 26 * u, f0[1] + 10 * u), 8 * u, (28, 26, 30))
    # arms (behind the torso)
    arm_col = CREAM if coat else shirt
    for s, sg in ((-1, -sw), (1, sw)):
        a0 = (x + s * 40 * u, sh + 18 * u)
        hang = (a0[0] + s * 18 * u + math.sin(sg) * 120 * u, a0[1] + math.cos(sg) * 128 * u)
        up = (x + s * 22 * u, sh + 30 * u)                      # scare: hands rise to the chest
        a1 = (hang[0] + (up[0] - hang[0]) * scared, hang[1] + (up[1] - hang[1]) * scared)
        elbow = (a0[0] + s * 34 * u * (0.4 + scared), (a0[1] + a1[1]) / 2 + 20 * u * scared)
        line(d, a0, elbow, 18 * u, arm_col)
        line(d, elbow, a1, 18 * u, arm_col)
        d.ellipse([a1[0] - 12 * u, a1[1] - 12 * u, a1[0] + 12 * u, a1[1] + 12 * u], fill=skin)
    # tronco
    rr(d, (x - 46 * u, sh, x + 46 * u, hip + 20 * u), 26 * u, shirt)
    if coat:
        rr(d, (x - 50 * u, sh, x - 10 * u, hip + 60 * u), 18 * u, CREAM)
        rr(d, (x + 10 * u, sh, x + 50 * u, hip + 60 * u), 18 * u, CREAM)
    # head
    r = 58 * u
    d.ellipse([hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r], fill=skin)
    hcol = (205, 205, 210) if grey else hair
    d.chord([hc[0] - r, hc[1] - r - 4 * u, hc[0] + r, hc[1] + r * 0.5], 180, 360, fill=hcol)
    if cap:
        d.chord([hc[0] - r - 2 * u, hc[1] - r - 10 * u, hc[0] + r + 2 * u, hc[1] + r * 0.3], 180, 360, fill=cap)
        rr(d, (hc[0], hc[1] - 18 * u, hc[0] + r + 34 * u, hc[1] - 4 * u), 7 * u, cap)
    ex = hc[0] + look * 14 * u
    ey = hc[1] + 6 * u
    er = (7 + 3 * scared) * u
    for dx in (-20 * u, 20 * u):
        d.ellipse([ex + dx - er, ey - er, ex + dx + er, ey + er], fill=(26, 22, 22))
    if glasses:
        for dx in (-20 * u, 20 * u):
            d.ellipse([ex + dx - 15 * u, ey - 13 * u, ex + dx + 15 * u, ey + 13 * u], outline=(30, 30, 30), width=int(4 * u))
    if scared > 0.5:
        d.ellipse([ex - 9 * u, ey + 22 * u, ex + 9 * u, ey + 40 * u], fill=(60, 26, 26))
    else:
        d.arc([ex - 16 * u, ey + 10 * u, ex + 16 * u, ey + 32 * u], 20, 160, fill=(60, 30, 28), width=int(5 * u))


def silhouette(d, x, feet, k, phase=0.0, lean=1):
    """Infected: curved black silhouette, arms hanging forward (no wound, no blood)."""
    u = S * k
    sway = math.sin(phase) * 8 * u
    hip = feet - 150 * u
    sh = hip - 140 * u
    hc = (x + lean * 34 * u + sway, sh - 46 * u)
    for s in (-1, 1):
        line(d, (x + s * 16 * u, hip), (x + s * 26 * u + math.sin(phase + s) * 14 * u, feet), 24 * u, SIL)
    d.polygon([(x - 42 * u, hip + 20 * u), (x + 42 * u, hip + 20 * u), (x + lean * 60 * u + 40 * u, sh),
               (x + lean * 60 * u - 44 * u, sh)], fill=SIL)
    for s in (-1, 1):
        a0 = (x + lean * 50 * u + s * 30 * u, sh + 20 * u)
        line(d, a0, (a0[0] + lean * 70 * u, a0[1] + 110 * u + s * 10 * u + sway), 20 * u, SIL)
    d.ellipse([hc[0] - 52 * u, hc[1] - 52 * u, hc[0] + 52 * u, hc[1] + 52 * u], fill=SIL)


# ---------- cenas ----------

def street(t_dark=0.0, lamp=1.0):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    sky_top = (int(46 - 16 * t_dark), int(42 - 14 * t_dark), int(66 - 14 * t_dark))
    sky_low = (int(150 - 90 * t_dark), int(84 - 44 * t_dark), int(70 - 30 * t_dark))
    hz = int(H * 0.58)
    for y in range(0, hz, 6):
        f = y / hz
        d.rectangle([0, y, W, y + 6], fill=tuple(int(sky_top[i] + (sky_low[i] - sky_top[i]) * f ** 1.6) for i in range(3)))
    # background buildings (only blocks and windows)
    k = 11
    x = -30 * S
    while x < W:
        k = (k * 1103515245 + 12345) & 0x7FFFFFFF
        w = (160 + k % 140) * S
        h = (260 + (k >> 8) % 380) * S
        d.rectangle([x, hz - h, x + w, hz], fill=WALL2)
        for wy in range(hz - h + 40 * S, hz - 50 * S, 80 * S):
            for wx in range(x + 30 * S, x + w - 40 * S, 70 * S):
                k = (k * 1103515245 + 12345) & 0x7FFFFFFF
                if k % 100 < 30:
                    d.rectangle([wx, wy, wx + 30 * S, wy + 40 * S], fill=LIT)
        x += w + 12 * S
    # pharmacy
    fx0, fx1, ft = 60 * S, 700 * S, int(H * 0.36)
    d.rectangle([fx0, ft, fx1, hz + 40 * S], fill=WALL)
    rr(d, (fx0 + 70 * S, ft + 50 * S, fx1 - 70 * S, ft + 150 * S), 14 * S, (32, 70, 58))
    d.text(((fx0 + fx1) // 2 + 30 * S, ft + 100 * S), "PHARMACY", font=F(brand.FONT_NUMBER, 60), fill=CREAM, anchor="mm")
    cx, cy = fx0 + 130 * S, ft + 100 * S
    g = (110, 230, 150)
    d.rectangle([cx - 10 * S, cy - 30 * S, cx + 10 * S, cy + 30 * S], fill=g)
    d.rectangle([cx - 30 * S, cy - 10 * S, cx + 30 * S, cy + 10 * S], fill=g)
    d.rectangle([fx0 + 50 * S, ft + 220 * S, fx0 + 360 * S, hz - 20 * S], fill=(232, 200, 130))
    d.rectangle([fx0 + 420 * S, ft + 220 * S, fx0 + 580 * S, hz + 40 * S], fill=(120, 84, 56))
    d.ellipse([fx0 + 550 * S, ft + 420 * S, fx0 + 566 * S, ft + 436 * S], fill=AMBER)
    # floor
    d.rectangle([0, hz + 40 * S, W, hz + 160 * S], fill=(74, 76, 88))
    d.rectangle([0, hz + 160 * S, W, H], fill=(34, 36, 46))
    for x in range(0, W, 240 * S):
        d.rectangle([x, hz + 420 * S, x + 130 * S, hz + 436 * S], fill=(120, 110, 70))
    # street lamp + light
    px = 880 * S
    d.rectangle([px - 8 * S, int(H * 0.34), px + 8 * S, hz + 120 * S], fill=(24, 24, 30))
    d.rectangle([px - 90 * S, int(H * 0.34) - 8 * S, px, int(H * 0.34) + 8 * S], fill=(24, 24, 30))
    if lamp > 0:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.polygon([(px - 80 * S, int(H * 0.34)), (px - 300 * S, hz + 150 * S), (px + 130 * S, hz + 150 * S)], fill=(255, 210, 130, int(60 * lamp)))
        img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(24 * S))).convert("RGB")
        d = ImageDraw.Draw(img)
    d.ellipse([px - 110 * S, int(H * 0.34) - 10 * S, px - 60 * S, int(H * 0.34) + 24 * S], fill=LIT if lamp > 0 else (90, 90, 90))
    return img, hz + 120 * S


def ui(img, caption, key, stamp):
    d = ImageDraw.Draw(img)
    f = F(brand.FONT_NUMBER, 30)
    tw = d.textlength(stamp, font=f)
    rr(d, (W / 2 - tw / 2 - 20 * S, 300 * S, W / 2 + tw / 2 + 20 * S, 352 * S), 10 * S, RED)
    d.text((W / 2, 326 * S), stamp, font=f, fill=(250, 240, 230), anchor="mm")
    d.text((W / 2, 240 * S), "THE HARLOW OUTBREAK", font=F(brand.FONT_BOLD, 28), fill=AMBER, anchor="mm")
    if caption:
        f = F(brand.FONT_NUMBER, 56)
        maxw = brand.CAPTION_MAX_W * S
        lines, cur = [], []
        for w in caption.upper().split():
            if cur and d.textlength(" ".join(cur + [w]), font=f) > maxw:
                lines.append(cur)
                cur = []
            cur.append(w)
        lines.append(cur)
        y0 = 1440 * S
        for li, ws in enumerate(lines):
            y = y0 + li * 84 * S
            total = d.textlength(" ".join(ws), font=f)
            rr(d, (W / 2 - total / 2 - 22 * S, y - 42 * S, W / 2 + total / 2 + 22 * S, y + 40 * S), 10 * S, (12, 12, 14))
            x = W / 2 - total / 2
            for w in ws:
                d.text((x, y), w, font=f, fill=AMBER if w.strip(".,").lower() == key.strip(".,") else (248, 246, 240), anchor="lm")
                x += d.textlength(w + " ", font=f)
    return img


def still_street(t=3.0, total=4.0):
    p = t / total
    img, ground = street(t_dark=0.3 + 0.5 * p, lamp=1.0 if p > 0.4 else 0.0)
    d = ImageDraw.Draw(img)
    silhouette(d, W - (110 + 170 * p) * S, ground - 30 * S, 0.8, phase=t * 4, lean=-1)
    walk_t = min(p / 0.6, 1)
    x = (300 + 260 * walk_t) * S
    scared = max(0.0, min(1.0, (p - 0.65) / 0.2))
    person(d, x, ground, 1.0, shirt=(62, 110, 160), pants=(46, 50, 66), coat=True,
           walk=(t * 8 if walk_t < 1 else 0), look=1.0 if p > 0.6 else 0.3, scared=scared)
    cap = ("Sam closes the pharmacy at sunset.", "sunset.") if p < 0.55 else ("Then he sees the man at the bus stop.", "man")
    return ui(img, cap[0], cap[1], f"HOUR 0 · 00:{int(t * 3):02d}")


def still_cast():
    img = Image.new("RGB", (W, H), BG2)
    d = ImageDraw.Draw(img)
    d.rectangle([0, int(H * 0.70), W, H], fill=FLOOR)
    d.rectangle([140 * S, 500 * S, 560 * S, 1000 * S], fill=(22, 24, 32))
    d.line([(350 * S, 500 * S), (350 * S, 1000 * S)], fill=(60, 62, 74), width=8 * S)
    d.line([(140 * S, 750 * S), (560 * S, 750 * S)], fill=(60, 62, 74), width=8 * S)
    d.rectangle([700 * S, 640 * S, 940 * S, int(H * 0.70)], fill=(120, 84, 56))
    g = int(H * 0.70) + 10 * S
    person(d, 230 * S, g, 1.0, shirt=(62, 110, 160), pants=(46, 50, 66), coat=True, look=0.4)
    person(d, 440 * S, g, 1.0, shirt=(230, 170, 50), pants=(60, 90, 140), skin=(120, 80, 56), hair=(20, 16, 14), look=-0.3)
    person(d, 640 * S, g, 1.0, shirt=(120, 84, 60), pants=(36, 36, 44), grey=True, glasses=True, skin=(232, 196, 168))
    person(d, 830 * S, g, 1.0, shirt=(120, 140, 90), pants=(60, 70, 90), skin=(214, 170, 140), hair=(120, 70, 40), kid=True, cap=(230, 180, 40))
    return ui(img, "Sam, Rosa, Mr. Hale and Theo.", "sam,", "HOUR 0 · 00:41")


def still_card():
    img = Image.new("RGB", (W, H), BG2)
    d = ImageDraw.Draw(img)
    rr(d, (220 * S, 560 * S, 860 * S, 760 * S), 16 * S, CREAM)
    d.text((540 * S, 610 * S), "RABIES", font=F(brand.FONT_NUMBER, 40), fill=(90, 80, 70), anchor="mm")
    d.text((540 * S, 690 * S), "WEEKS TO SHOW", font=F(brand.FONT_NUMBER, 64), fill=(30, 28, 26), anchor="mm")
    rr(d, (220 * S, 820 * S, 860 * S, 1020 * S), 16 * S, AMBER)
    d.text((540 * S, 870 * S), "HARLOW", font=F(brand.FONT_NUMBER, 40), fill=(70, 40, 10), anchor="mm")
    d.text((540 * S, 950 * S), "MINUTES", font=F(brand.FONT_NUMBER, 64), fill=(30, 20, 10), anchor="mm")
    for i in range(12):
        x = 230 * S + i * 54 * S
        d.ellipse([x, 1120 * S, x + 40 * S, 1160 * S], fill=SIL if i > 0 else RED)
    d.text((540 * S, 1200 * S), "1 BITE, 40 IN AN HOUR", font=F(brand.FONT_NUMBER, 34), fill=(200, 200, 210), anchor="mm")
    return ui(img, "This one moves in minutes, not weeks.", "minutes,", "HOUR 0 · 00:12")


def small(img):
    return img.resize((brand.W, brand.H), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--clip" in sys.argv:
        frames = OUT / "v2-frames"
        frames.mkdir(exist_ok=True)
        for i in range(int(4 * FPS)):
            small(still_street(i / FPS, 4.0)).save(frames / f"{i:04d}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(OUT / "v2-clip.mp4")], check=True)
    else:
        shots = [small(still_street(3.4)), small(still_cast()), small(still_card())]
        for n, im in zip(("street", "cast", "card"), shots):
            im.save(OUT / f"v2-{n}.png")
        sheet = Image.new("RGB", (brand.W * 3 // 2 + 40, brand.H // 2), (10, 10, 12))
        for i, im in enumerate(shots):
            sheet.paste(im.resize((brand.W // 2, brand.H // 2)), (i * (brand.W // 2 + 20), 0))
        sheet.save(OUT / "v2-folha.png")
    print(OUT)


if __name__ == "__main__":
    main()
