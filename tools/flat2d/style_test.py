"""2D style test: detailed stick figure on a small-town street at dusk.

Prototype to approve the look of the "The Harlow Outbreak" season before building the 2D pipeline.
Draws everything in code (Pillow, 2x supersample) and builds the clip with FFmpeg; no new dependency.

    py tools/flat2d/style_test.py [--clip]   # stills 2d.png and 2d-stickman.png (+ 4 s clip of the stickman)
Outputs in build/zombie-outbreak-1/style-test/.
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
S = 2                      # supersample
W, H = brand.W * S, brand.H * S
FPS = 30

INK = (20, 18, 28)         # contorno
SKIN = (246, 240, 232)
COAT = (250, 250, 252)
SHIRT = (64, 110, 160)
PANTS = (48, 52, 70)
HAIR = (58, 40, 30)
SICK = (122, 140, 118)     # infected skin (no blood)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def font(name, size):
    return ImageFont.truetype(str(ROOT / "fonts" / name), size * S)


# ---------- set ----------

def sky(t_dark):
    """Dusk gradient that darkens with t_dark (0 = sunset, 1 = night)."""
    top = lerp((70, 60, 120), (14, 16, 36), t_dark)
    mid = lerp((236, 120, 80), (60, 40, 80), t_dark)
    low = lerp((250, 190, 110), (90, 60, 90), t_dark)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        f = y / (H * 0.62)
        c = lerp(top, mid, min(f * 1.6, 1)) if f < 0.62 else lerp(mid, low, min((f - 0.62) / 0.38, 1))
        d.rectangle([0, y, W, y + 4], fill=c)
    return img


def buildings(d, t_dark, seed_layer, base_y, color, hmin, hmax, wmin, wmax, windows):
    x = -40 * S
    k = seed_layer
    while x < W:
        k = (k * 1103515245 + 12345) & 0x7FFFFFFF
        w = wmin + k % (wmax - wmin)
        k = (k * 1103515245 + 12345) & 0x7FFFFFFF
        h = hmin + k % (hmax - hmin)
        d.rectangle([x, base_y - h, x + w, base_y], fill=color)
        if windows:
            lit = lerp((255, 214, 140), (255, 200, 110), t_dark)
            off = lerp(color, (30, 30, 46), 0.3)
            for wy in range(base_y - h + 30 * S, base_y - 40 * S, 70 * S):
                for wx in range(x + 22 * S, x + w - 40 * S, 64 * S):
                    k = (k * 1103515245 + 12345) & 0x7FFFFFFF
                    on = (k % 100) < 25 + 55 * t_dark
                    d.rectangle([wx, wy, wx + 26 * S, wy + 36 * S], fill=lit if on else off)
        x += w + 6 * S


def street(t_dark, lamp_on):
    img = sky(t_dark)
    d = ImageDraw.Draw(img)
    horizon = int(H * 0.60)
    buildings(d, t_dark, 7, horizon - 40 * S, lerp((120, 80, 120), (34, 30, 56), t_dark), 260 * S, 520 * S, 140 * S, 260 * S, False)
    buildings(d, t_dark, 3, horizon + 10 * S, lerp((92, 60, 92), (28, 26, 44), t_dark), 200 * S, 420 * S, 180 * S, 320 * S, True)

    # pharmacy in the foreground (no brand: generic green cross)
    fx0, fx1, ftop, fbase = 40 * S, 760 * S, int(H * 0.30), int(H * 0.70)
    wall = lerp((196, 150, 120), (74, 60, 70), t_dark)
    d.rectangle([fx0, ftop, fx1, fbase], fill=wall, outline=INK, width=6 * S)
    d.rectangle([fx0 - 20 * S, ftop - 30 * S, fx1 + 20 * S, ftop + 10 * S], fill=lerp((120, 80, 70), (50, 40, 50), t_dark), outline=INK, width=6 * S)
    # toldo listrado
    aw_y0, aw_y1 = ftop + 210 * S, ftop + 300 * S
    for i, x in enumerate(range(fx0, fx1, 60 * S)):
        col = (60, 140, 110) if i % 2 == 0 else (236, 236, 228)
        col = lerp(col, (40, 50, 60), t_dark * 0.6)
        d.polygon([(x, aw_y0), (x + 60 * S, aw_y0), (x + 70 * S, aw_y1), (x + 10 * S, aw_y1)], fill=col)
    d.line([(fx0, aw_y0), (fx1, aw_y0)], fill=INK, width=6 * S)
    d.line([(fx0 + 10 * S, aw_y1), (fx1 + 10 * S, aw_y1)], fill=INK, width=6 * S)
    # letreiro
    d.rounded_rectangle([fx0 + 90 * S, ftop + 60 * S, fx1 - 90 * S, ftop + 170 * S], 18 * S, fill=(30, 60, 52), outline=INK, width=5 * S)
    d.text(((fx0 + fx1) // 2 + 40 * S, ftop + 115 * S), "PHARMACY", font=font(brand.FONT_BOLD, 54), fill=(236, 246, 236), anchor="mm")
    cx, cy, r = fx0 + 150 * S, ftop + 115 * S, 30 * S
    glow = (90, 230, 140) if lamp_on else (60, 150, 100)
    d.rectangle([cx - r // 3, cy - r, cx + r // 3, cy + r], fill=glow)
    d.rectangle([cx - r, cy - r // 3, cx + r, cy + r // 3], fill=glow)
    # shop window and door
    vit = lerp((180, 220, 230), (250, 220, 150), t_dark)
    d.rectangle([fx0 + 50 * S, aw_y1 + 40 * S, fx0 + 400 * S, fbase - 60 * S], fill=vit, outline=INK, width=6 * S)
    for sx in range(fx0 + 80 * S, fx0 + 380 * S, 70 * S):   # shelves with little boxes
        for sy in range(aw_y1 + 90 * S, fbase - 120 * S, 90 * S):
            d.rectangle([sx, sy, sx + 40 * S, sy + 50 * S], fill=lerp((210, 90, 80), (90, 160, 210), (sx // S % 3) / 2), outline=INK, width=3 * S)
    d.rectangle([fx0 + 470 * S, aw_y1 + 40 * S, fx0 + 650 * S, fbase], fill=lerp((110, 70, 50), (60, 40, 40), t_dark), outline=INK, width=6 * S)
    d.rectangle([fx0 + 490 * S, aw_y1 + 70 * S, fx0 + 630 * S, aw_y1 + 260 * S], fill=vit, outline=INK, width=4 * S)
    d.ellipse([fx0 + 600 * S, fbase - 300 * S, fx0 + 620 * S, fbase - 280 * S], fill=(230, 190, 80), outline=INK, width=3 * S)

    # sidewalk and street
    d.rectangle([0, fbase, W, fbase + 120 * S], fill=lerp((170, 160, 160), (70, 66, 80), t_dark))
    d.line([(0, fbase), (W, fbase)], fill=INK, width=6 * S)
    d.rectangle([0, fbase + 120 * S, W, H], fill=lerp((70, 70, 84), (30, 30, 40), t_dark))
    d.line([(0, fbase + 120 * S), (W, fbase + 120 * S)], fill=INK, width=6 * S)
    for x in range(0, W, 220 * S):
        d.rectangle([x, fbase + 330 * S, x + 120 * S, fbase + 346 * S], fill=lerp((230, 210, 120), (120, 110, 70), t_dark))

    # poste
    px = 900 * S
    d.rectangle([px - 10 * S, int(H * 0.36), px + 10 * S, fbase + 60 * S], fill=(50, 50, 64), outline=INK, width=4 * S)
    d.line([(px, int(H * 0.36)), (px - 90 * S, int(H * 0.36))], fill=INK, width=14 * S)
    lamp = (255, 226, 150) if lamp_on else (120, 116, 110)
    d.ellipse([px - 120 * S, int(H * 0.36) - 10 * S, px - 60 * S, int(H * 0.36) + 30 * S], fill=lamp, outline=INK, width=4 * S)
    if lamp_on:
        cone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cone)
        cd.polygon([(px - 90 * S, int(H * 0.36)), (px - 300 * S, fbase + 100 * S), (px + 120 * S, fbase + 100 * S)], fill=(255, 220, 140, 46))
        img = Image.alpha_composite(img.convert("RGBA"), cone.filter(ImageFilter.GaussianBlur(30 * S))).convert("RGB")
    return img, fbase


# ---------- bonequinho ----------

def pt(o, ang, length):
    return (o[0] + math.sin(ang) * length, o[1] - math.cos(ang) * length)


def limb(d, a, b, c, width, color):
    """Limb with outline: all the outline first, then all the fill (no ring at the joints)."""
    for w, col in ((width + 8 * S, INK), (width, color)):
        d.line([a, b, c], fill=col, width=w, joint="curve")
        for p in (a, c):
            r = w / 2
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)


def figure(d, hip, pose, scale=1.0, detailed=True, sick=False, facing=1, flat=False):
    """pose: dict of angles (rad) — torso, head, lth/lsh (thigh/shin), rth/rsh, lua/lfa (arm/forearm), rua/rfa.
    flat=True: 2D cartoon character (thick limbs, wide torso, big head), not a stick figure."""
    u = 1.0 * S * scale
    skin = SICK if sick else SKIN
    lw = int((44 if flat else 24 if detailed else 14) * u)
    bw = 66 if flat else 44
    neck = pt(hip, pose["torso"], 190 * u)
    head_c = pt(neck, pose["torso"] + pose.get("head", 0), (84 if flat else 70) * u)
    sh_c = pt(hip, pose["torso"], 172 * u)

    def leg(th, sh, col, side):
        h = (hip[0] + side * (bw * 0.45) * u, hip[1])
        knee = pt(h, math.pi + th * facing, 110 * u)
        foot = pt(knee, math.pi + (th + sh) * facing, 110 * u)
        limb(d, h, knee, foot, lw, col)
        d.ellipse([foot[0] - 24 * u + 12 * u * facing, foot[1] - 12 * u, foot[0] + 24 * u + 12 * u * facing, foot[1] + 14 * u], fill=INK)

    def arm(ua, fa, col, side):
        s0 = (sh_c[0] + side * (bw - lw / u * 0.35) * u, sh_c[1] + 10 * u)
        elbow = pt(s0, math.pi + ua * facing, 95 * u)
        hand = pt(elbow, math.pi + (ua + fa) * facing, 88 * u)
        limb(d, s0, elbow, hand, int(lw * 0.85), col)
        r = (20 if flat else 15) * u
        d.ellipse([hand[0] - r, hand[1] - r, hand[0] + r, hand[1] + r], fill=skin, outline=INK, width=int(5 * u))

    pants = PANTS if detailed else INK
    sleeve = (COAT if not sick else (110, 100, 90)) if detailed else INK
    leg(pose["rth"], pose["rsh"], pants, 1)
    leg(pose["lth"], pose["lsh"], pants, -1)
    if detailed:
        # tronco: camisa + jaleco aberto
        body = [(hip[0] - (bw - 6) * u, hip[1] + 14 * u), (hip[0] + (bw - 6) * u, hip[1] + 14 * u),
                (sh_c[0] + bw * u, sh_c[1]), (sh_c[0] - bw * u, sh_c[1])]
        d.polygon(body, fill=SHIRT if not sick else (90, 84, 80), outline=INK, width=int(6 * u))
        if not sick:
            for sd in (-1, 1):
                coat = [(hip[0] + sd * (bw + 6) * u, hip[1] + 70 * u), (hip[0] + sd * 10 * u, hip[1] + 70 * u),
                        (sh_c[0] + sd * 12 * u, sh_c[1] + 40 * u), (sh_c[0] + sd * bw * u, sh_c[1])]
                d.polygon(coat, fill=COAT, outline=INK, width=int(6 * u))
    else:
        d.line([hip, neck], fill=INK, width=lw)
    arm(-pose["rua"] - 0.15, pose["rfa"], sleeve, 1)
    arm(pose["lua"] + 0.15, -pose["lfa"], sleeve, -1)

    # head
    r = (84 if flat else 68) * u
    d.ellipse([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r], fill=skin, outline=INK, width=int(8 * u))
    if detailed and not sick:
        d.chord([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r * 0.2], 180, 360, fill=HAIR, outline=INK, width=int(8 * u))
    ex = head_c[0] + 22 * u * facing
    look = pose.get("eyes", 0) * 8 * u
    for dx in (-20 * u, 20 * u):
        if sick:
            d.ellipse([ex + dx - 9 * u, head_c[1] - 4 * u, ex + dx + 9 * u, head_c[1] + 14 * u], fill=(236, 236, 200), outline=INK, width=int(3 * u))
        else:
            d.ellipse([ex + dx - 7 * u + look, head_c[1] - 6 * u, ex + dx + 7 * u + look, head_c[1] + 12 * u], fill=INK)
    if detailed and not sick:
        brow = pose.get("brow", 0) * 8 * u
        d.line([(ex - 32 * u, head_c[1] - 22 * u - brow), (ex - 10 * u, head_c[1] - 18 * u)], fill=INK, width=int(6 * u))
        d.line([(ex + 10 * u, head_c[1] - 18 * u), (ex + 32 * u, head_c[1] - 22 * u - brow)], fill=INK, width=int(6 * u))
        mo = pose.get("mouth", 0)
        if mo > 0.5:
            d.ellipse([ex - 10 * u, head_c[1] + 26 * u, ex + 10 * u, head_c[1] + 46 * u], fill=INK)
        else:
            d.line([(ex - 14 * u, head_c[1] + 36 * u), (ex + 14 * u, head_c[1] + 34 * u)], fill=INK, width=int(6 * u))


def walk_pose(phase, alarm=0.0):
    s = math.sin(phase)
    return dict(torso=0.04 * facing_sign(), head=-0.1 * alarm,
                lth=0.45 * s, lsh=-0.35 * max(0, -s) - 0.05, rth=-0.45 * s, rsh=-0.35 * max(0, s) - 0.05,
                lua=-0.45 * s, lfa=0.4, rua=0.45 * s, rfa=0.4, brow=alarm, mouth=alarm, eyes=-alarm)


def facing_sign():
    return 1


def sick_pose(phase):
    s = math.sin(phase)
    return dict(torso=0.35 + 0.05 * s, head=0.35,
                lth=0.25 * s, lsh=-0.3, rth=-0.25 * s, rsh=-0.3,
                lua=1.4 + 0.15 * s, lfa=0.2, rua=1.2 - 0.15 * s, rfa=0.3)


STAND = dict(torso=0.0, head=0.0, lth=0.12, lsh=-0.05, rth=-0.12, rsh=-0.05, lua=-0.2, lfa=0.3, rua=0.2, rfa=0.3)


# ---------- overlays ----------

def overlay(img, caption, clock, infected):
    d = ImageDraw.Draw(img)
    x, y = brand.STAMP_XY[0] * S, 330 * S
    d.text((x, y), clock, font=ImageFont.truetype(str(ROOT / "fonts" / brand.FONT_CLOCK), 64 * S), fill=brand.TEXTO, stroke_width=3 * S, stroke_fill=brand.VACUO)
    d.text((x, y + 86 * S), f"INFECTED  {infected}", font=font(brand.FONT_BOLD, 34), fill=brand.LUZ, stroke_width=3 * S, stroke_fill=brand.VACUO)
    d.text((x, y - 70 * S), "THE HARLOW OUTBREAK · PART 1", font=font(brand.FONT_BOLD, 28), fill=brand.QUIETO, stroke_width=2 * S, stroke_fill=brand.VACUO)
    if caption:
        f = font(brand.FONT_BOLD, 58)
        d.text((W // 2, brand.CAPTION_CENTER_Y * S + 280 * S), caption, font=f, fill=brand.TEXTO, anchor="mm", stroke_width=5 * S, stroke_fill=brand.VACUO)
    return img


def frame(t, total, detailed=True, with_overlay=True, flat=False):
    p = t / total
    img, fbase = street(0.15 + 0.35 * p, lamp_on=p > 0.45)
    d = ImageDraw.Draw(img)
    # infected in the background, staggering from the right to the middle
    sx = W - (40 + 120 * p) * S
    figure(d, (sx, fbase + 40 * S - 220 * S * 0.6), sick_pose(t * 5), scale=0.6, detailed=detailed, sick=True, facing=-1, flat=flat)
    # Sam leaves the door and stops on seeing
    walk_t = min(p / 0.6, 1)
    hx = (520 + 260 * walk_t) * S
    alarm = max(0, (p - 0.6) / 0.25)
    pose = walk_pose(t * 7, 0) if walk_t < 1 else dict(STAND, brow=min(alarm, 1), mouth=min(alarm, 1), head=-0.08 * min(alarm, 1), eyes=1)
    figure(d, (hx - 120 * S, fbase + 95 * S - 220 * S), pose, scale=1.0, detailed=detailed, facing=1, flat=flat)
    if with_overlay:
        cap = "Sam closes the pharmacy at sunset." if p < 0.55 else "Then he sees the man at the bus stop."
        sec = int(t)
        overlay(img, cap, f"00:{sec:02d}.{int((t % 1) * 100):02d}", 1)
    return img.resize((brand.W, brand.H), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--clip" not in sys.argv:
        frame(3.2, 4.0, detailed=True, with_overlay=False, flat=True).save(OUT / "2d.png")
        frame(3.2, 4.0, detailed=True, with_overlay=False).save(OUT / "2d-stickman.png")
    else:
        frames = OUT / "frames"
        frames.mkdir(exist_ok=True)
        for i in range(int(4.0 * FPS)):
            frame(i / FPS, 4.0, detailed=True).save(frames / f"{i:04d}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(OUT / "clip-stickman.mp4")], check=True)
    print(OUT)


if __name__ == "__main__":
    main()
