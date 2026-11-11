"""Style test v3: the 3 own-identity directions, at the same story moment (Hour 0, 00:41:
Sam locked in the pharmacy,
infected in the street).

    py tools/flat2d/style_v3.py [--clip]   # stills or 5 s clip (floor plan + close)
Outputs in build/zombie-outbreak-1/style-test/v3-{a,b,c}.png and v3-sheet.png.
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ifscape import brand  # noqa: E402

OUT = ROOT / "build" / "zombie-outbreak-1" / "style-test"
S = 2
W, H = brand.W * S, brand.H * S

VAC = (11, 15, 23)
AMB = (245, 165, 36)
AMB_D = (120, 82, 24)
TXT = (244, 246, 248)
QUI = (138, 148, 166)
INF = (96, 120, 150)


def F(name, size):
    return ImageFont.truetype(str(ROOT / "fonts" / name), int(size * S))


def panel(d, clock, rows):
    x, y = brand.STAMP_XY[0] * S, 250 * S
    d.text((x, y), "THE HARLOW OUTBREAK · PART 1", font=F(brand.FONT_BOLD, 26), fill=QUI)
    f = ImageFont.truetype(str(ROOT / "fonts" / brand.FONT_CLOCK), 70 * S)
    f.set_variation_by_axes([300])
    d.text((x, y + 44 * S), clock, font=f, fill=TXT)
    for i, (lab, val, hot) in enumerate(rows):
        yy = y + 150 * S + i * 52 * S
        d.ellipse([x, yy + 12 * S, x + 16 * S, yy + 28 * S], fill=AMB if hot else QUI)
        d.text((x + 30 * S, yy), f"{lab}  {val}", font=F(brand.FONT_BOLD, 34), fill=AMB if hot else TXT)


def caption(d, words, key):
    f = F(brand.FONT_NUMBER, 92)
    text = " ".join(words).upper()
    tw = d.textlength(text, font=f)
    x = W / 2 - tw / 2
    y = 1330 * S
    for w in words:
        wu = w.upper()
        d.text((x, y), wu, font=f, fill=AMB if w.lower() == key else TXT, anchor="lm",
               stroke_width=6 * S, stroke_fill=VAC)
        x += d.textlength(wu + " ", font=f)


# ---------- A: live floor plan ----------

def dir_a(p=1.0):
    img = Image.new("RGB", (W, H), VAC)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 40 * S):                       # technical paper grid
        d.line([(gx, 0), (gx, H)], fill=(18, 24, 34), width=S)
    for gy in range(0, H, 40 * S):
        d.line([(0, gy), (W, gy)], fill=(18, 24, 34), width=S)
    lw = 4 * S
    # cutaway: pharmacy on the left, street on the right
    x0, x1, y0, y1 = 110 * S, 640 * S, 640 * S, 1180 * S
    d.rectangle([x0, y0, x1, y1], outline=AMB, width=lw)
    d.line([(x0, y0 + 260 * S), (x0 + 340 * S, y0 + 260 * S)], fill=AMB, width=lw)        # counter
    for sx in range(x0 + 30 * S, x0 + 330 * S, 70 * S):                                 # prateleiras
        d.rectangle([sx, y0 + 40 * S, sx + 50 * S, y0 + 200 * S], outline=AMB_D, width=2 * S)
    d.line([(x1, y0 + 330 * S), (x1, y1)], fill=VAC, width=lw + 2 * S)                  # door opening
    d.arc([x1 - 210 * S, y0 + 330 * S - 210 * S + 210 * S, x1 + 210 * S, y1 + 210 * S - 210 * S], 180, 270, fill=AMB, width=2 * S)
    shut = max(0.0, min(1.0, (p - 0.7) / 0.15))
    ang = math.radians(90 * (1 - shut))
    d.line([(x1, y0 + 330 * S), (x1 - 210 * S * math.cos(ang), y0 + 330 * S + 210 * S * math.sin(ang))], fill=AMB, width=lw)
    if shut >= 1:
        d.rectangle([x1 - 30 * S, y0 + 345 * S, x1 - 6 * S, y0 + 375 * S], fill=AMB)     # tranca
    d.text((x0, y0 - 46 * S), "PHARMACY · GROUND FLOOR", font=F(brand.FONT_NUMBER, 30), fill=AMB)
    d.text((x1 - 200 * S, y0 + 390 * S), "DOOR · LOCKED" if p > 0.85 else "DOOR · OPEN", font=F(brand.FONT_NUMBER, 24), fill=AMB)
    # cotas
    d.line([(x0, y1 + 40 * S), (x1, y1 + 40 * S)], fill=AMB_D, width=2 * S)
    for xx in (x0, x1):
        d.line([(xx, y1 + 28 * S), (xx, y1 + 52 * S)], fill=AMB_D, width=2 * S)
    d.text(((x0 + x1) / 2, y1 + 66 * S), "12 m", font=F(brand.FONT_NUMBER, 24), fill=AMB_D, anchor="mm")
    # rua
    d.line([(x1 + 60 * S, y0 - 60 * S), (x1 + 60 * S, y1 + 120 * S)], fill=AMB_D, width=2 * S)
    d.text((x1 + 80 * S, y0 - 50 * S), "MAIN ST", font=F(brand.FONT_NUMBER, 24), fill=AMB_D)
    # infected: heat blobs
    heat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(heat)
    for i, (cx, cy, r) in enumerate(((900, 1010, 120), (820, 860, 90), (780, 1100, 70), (960, 780, 60))):
        g = max(0.0, min(1.0, p * 1.6 - i * 0.25))
        r = r * g
        hd.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=INF + (150,))
    heat = heat.filter(ImageFilter.GaussianBlur(30 * S))
    img = Image.alpha_composite(img.convert("RGBA"), heat).convert("RGB")
    d = ImageDraw.Draw(img)
    n_inf = 1 + int(6 * min(1.0, p * 1.3))
    for cx, cy in ((900, 1010), (870, 960), (930, 1060), (820, 860), (840, 920), (780, 1100), (960, 780))[:n_inf]:
        d.ellipse([(cx - 9) * S, (cy - 9) * S, (cx + 9) * S, (cy + 9) * S], fill=(170, 190, 215))
    # Sam
    run = max(0.0, min(1.0, (p - 0.2) / 0.5))
    run = run * run * (3 - 2 * run)
    sx, sy = (260 + 300 * run) * S, (1000 - 30 * run) * S
    d.ellipse([sx - 40 * S, sy - 40 * S, sx + 40 * S, sy + 40 * S], outline=AMB, width=3 * S)
    d.ellipse([sx - 16 * S, sy - 16 * S, sx + 16 * S, sy + 16 * S], fill=AMB)
    d.text((sx + 54 * S, sy - 20 * S), "SAM", font=F(brand.FONT_NUMBER, 34), fill=AMB)
    t = 38.0 + 3.0 * p
    panel(d, f"00:{int(t):02d}.{int((t % 1) * 100):02d}", [("INFECTED", str(n_inf), True), ("DOOR", "LOCKED" if p > 0.85 else "OPEN", False)])
    if p < 0.45:
        caption(d, ["They", "spread."], "spread.")
    else:
        caption(d, ["Lock", "it."], "lock")
    return img


# ---------- B: isometric diorama ----------

def iso(ox, oy, x, y, z, k=60):
    return (ox + (x - y) * k * 0.866 * S, oy + (x + y) * k * 0.5 * S - z * k * S)


def dir_b():
    img = Image.new("RGB", (W, H), VAC)
    d = ImageDraw.Draw(img)
    ox, oy = 540 * S, 760 * S
    P = lambda x, y, z: iso(ox, oy, x, y, z)
    floor = (72, 62, 58)
    wl, wr = (48, 54, 70), (38, 44, 58)
    d.polygon([P(0, 0, 0), P(6, 0, 0), P(6, 6, 0), P(0, 6, 0)], fill=floor)
    d.polygon([P(0, 0, 0), P(0, 6, 0), P(0, 6, 4), P(0, 0, 4)], fill=wl)              # left wall
    d.polygon([P(0, 0, 0), P(6, 0, 0), P(6, 0, 4), P(0, 0, 4)], fill=wr)              # right wall
    d.polygon([P(0, 0, 0), P(6, 0, 0), P(6, 0.3, 0), P(0, 0.3, 0)], fill=(30, 34, 46))
    # window with street
    d.polygon([P(1.5, 0, 1.2), P(4.5, 0, 1.2), P(4.5, 0, 3), P(1.5, 0, 3)], fill=(22, 26, 36))
    for gx, gz in ((2.2, 1.2), (3.0, 1.2), (3.7, 1.2)):                                 # silhouettes outside
        cx, cy = P(gx, 0, gz + 0.55)
        d.ellipse([cx - 16 * S, cy - 16 * S, cx + 16 * S, cy + 16 * S], fill=(70, 80, 96))
        bx, by = P(gx, 0, gz)
        d.rounded_rectangle([bx - 18 * S, cy + 12 * S, bx + 18 * S, by], 10 * S, fill=(70, 80, 96))
    # shelves on the left wall
    for zz in (1.0, 2.0, 3.0):
        d.polygon([P(0, 1, zz), P(0, 5, zz), P(0.5, 5, zz), P(0.5, 1, zz)], fill=(110, 86, 64))
        for yy in (1.4, 2.2, 3.0, 3.8, 4.4):
            a, b = P(0.1, yy, zz), P(0.1, yy + 0.4, zz + 0.5)
            d.rectangle([min(a[0], b[0]), b[1], max(a[0], b[0]), a[1]], fill=(200, 90, 80) if yy < 3 else (90, 150, 200))
    # counter (box)
    def box(x0, y0, x1, y1, z1, top, l, r):
        d.polygon([P(x0, y1, 0), P(x1, y1, 0), P(x1, y1, z1), P(x0, y1, z1)], fill=l)
        d.polygon([P(x1, y0, 0), P(x1, y1, 0), P(x1, y1, z1), P(x1, y0, z1)], fill=r)
        d.polygon([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], fill=top)
    box(2.5, 3.0, 5.2, 3.8, 1.3, (150, 120, 90), (110, 86, 64), (90, 70, 54))
    # Sam: capsule + head, amber flashlight
    sx, sy = P(2.0, 4.6, 0)
    d.rounded_rectangle([sx - 22 * S, sy - 120 * S, sx + 22 * S, sy], 20 * S, fill=(230, 226, 214))
    d.ellipse([sx - 24 * S, sy - 170 * S, sx + 24 * S, sy - 122 * S], fill=(214, 170, 130))
    d.rectangle([sx - 24 * S, sy - 156 * S, sx + 24 * S, sy - 148 * S], fill=AMB)
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bd.polygon([(sx + 10 * S, sy - 152 * S), P(4.8, 0, 3.2), P(2.0, 0, 0.6)], fill=AMB + (70,))
    img = Image.alpha_composite(img.convert("RGBA"), beam.filter(ImageFilter.GaussianBlur(10 * S))).convert("RGB")
    d = ImageDraw.Draw(img)
    panel(d, "00:41.08", [("INFECTED", "7", True), ("BATTERY", "82%", False)])
    caption(d, ["Don't", "move."], "move.")
    return img


# ---------- C: personagem-instrumento ----------

def dir_c(p=1.0):
    img = Image.new("RGB", (W, H), VAC)
    d = ImageDraw.Draw(img)
    warm = (70, 62, 58)
    # layers: shelves in the back, haze, counter
    for i, x in enumerate(range(-40 * S, W, 230 * S)):
        d.rectangle([x, 520 * S, x + 200 * S, 1250 * S], fill=(22, 28, 40), outline=warm, width=2 * S)
        for yy in range(580 * S, 1200 * S, 120 * S):
            d.line([(x + 10 * S, yy), (x + 190 * S, yy)], fill=warm, width=2 * S)
    fog = Image.new("RGBA", (W, H), (11, 15, 23, 110))
    img = Image.alpha_composite(img.convert("RGBA"), fog).convert("RGB")
    d = ImageDraw.Draw(img)
    # Sam in close-up (bust), headlamp
    cx, cy = 560 * S, 1150 * S
    d.rounded_rectangle([cx - 230 * S, cy - 40 * S, cx + 230 * S, cy + 600 * S], 140 * S, fill=(226, 222, 210), outline=warm, width=3 * S)
    d.polygon([(cx - 60 * S, cy - 40 * S), (cx + 60 * S, cy - 40 * S), (cx, cy + 160 * S)], fill=(62, 104, 150))
    d.ellipse([cx - 170 * S, cy - 400 * S, cx + 170 * S, cy - 40 * S], fill=(214, 168, 128), outline=warm, width=3 * S)
    d.chord([cx - 172 * S, cy - 410 * S, cx + 172 * S, cy - 160 * S], 180, 360, fill=(52, 38, 30))
    d.rectangle([cx - 172 * S, cy - 300 * S, cx + 172 * S, cy - 270 * S], fill=(30, 30, 34))
    d.rounded_rectangle([cx - 40 * S, cy - 320 * S, cx + 40 * S, cy - 250 * S], 14 * S, fill=AMB)
    for dx in (-60 * S, 60 * S):
        d.ellipse([cx + dx - 16 * S, cy - 200 * S, cx + dx + 16 * S, cy - 168 * S], fill=(24, 20, 20))
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bd.polygon([(cx - 30 * S, cy - 290 * S), (cx + 30 * S, cy - 290 * S), (W + 200 * S, 300 * S), (W + 200 * S, 1100 * S)], fill=AMB + (60,))
    img = Image.alpha_composite(img.convert("RGBA"), beam.filter(ImageFilter.GaussianBlur(16 * S))).convert("RGB")
    d = ImageDraw.Draw(img)
    # silhouette at the glass door on the right, inside the beam
    hx, hy = 920 * S, 760 * S
    sil = min(1.0, p / 0.5)
    shade = tuple(int(c * (1 - sil) + v * sil) for c, v in zip((40, 36, 30), (6, 8, 12)))
    if p > 0.15:
        d.ellipse([hx - 44 * S, hy - 44 * S, hx + 44 * S, hy + 44 * S], fill=shade)
        d.polygon([(hx - 70 * S, hy + 40 * S), (hx + 70 * S, hy + 40 * S), (hx + 90 * S, hy + 400 * S), (hx - 90 * S, hy + 400 * S)], fill=shade)
    t = 41.0 + 2.0 * p
    panel(d, f"00:{int(t):02d}.{int((t % 1) * 100):02d}", [("INFECTED", "7", True), ("BATTERY", "82%", False)])
    caption(d, ["Someone", "knocks."], "knocks.")
    return img


def clip():
    import subprocess
    fr = OUT / "v3-frames"
    fr.mkdir(exist_ok=True)
    n = 0
    for i in range(90):                      # 0-3 s: planta
        dir_a(i / 89).resize((brand.W, brand.H), Image.LANCZOS).save(fr / f"{n:04d}.png"); n += 1
    for i in range(60):                      # 3-5 s: close-up; shake on the 3 hits
        p = i / 59
        im = dir_c(p)
        knock = any(abs(i - k) < 2 for k in (18, 30, 42))
        if knock:
            im = im.transform(im.size, Image.AFFINE, (1, 0, 6 * S, 0, 1, 0))
        im.resize((brand.W, brand.H), Image.LANCZOS).save(fr / f"{n:04d}.png"); n += 1
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", str(fr / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(OUT / "v3-clip.mp4")], check=True)
    print(OUT / "v3-clip.mp4")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--clip" in sys.argv:
        clip()
        return
    shots = []
    for n, fn in (("a", dir_a), ("b", dir_b), ("c", dir_c)):
        im = fn().resize((brand.W, brand.H), Image.LANCZOS)
        im.save(OUT / f"v3-{n}.png")
        shots.append(im)
    lab = ["A  Live Floor Plan", "B  Isometric diorama", "C  Character-instrument"]
    sheet = Image.new("RGB", (brand.W * 3 // 2 + 40, brand.H // 2 + 70), (6, 6, 8))
    sd = ImageDraw.Draw(sheet)
    lf = ImageFont.truetype(str(ROOT / "fonts" / brand.FONT_BOLD), 34)
    for i, im in enumerate(shots):
        x = i * (brand.W // 2 + 20)
        sheet.paste(im.resize((brand.W // 2, brand.H // 2)), (x, 70))
        sd.text((x + 10, 16), lab[i], font=lf, fill=TXT)
    sheet.save(OUT / "v3-sheet.png")
    print(OUT / "v3-sheet.png")


if __name__ == "__main__":
    main()
