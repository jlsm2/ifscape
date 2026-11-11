"""Sets of the 2D stage (side view), used by the 'wide' and by the 'close' and 'duo' framings: flat,
Vacuum background and dark tones, warm amber light (shop window, street lamp, ceiling lamp), thin warm outline, 2 or 3 layers
with haze between them for depth.

Each set has 2 versions of the still background (shop light on and off, for the 'light' event) and:
- 'ground' and 'points': y of the floor and named points (x, y of the foot), these in places.WIDE_POINTS (no Pillow);
- 'targets': where the fist hits ('knock' with 'on') and the latch; x0..x1 is the object's span;
- 'glass': rectangles through which the outside is seen, and 'glass_block': what stays IN FRONT of it (frame,
  bar, grille, lamp post, shelter columns). The 'appear' silhouette and the infected in the background are cut by this
  mask: they always stay behind the glass, never over the frame or the grille;
- 'lane': strip of the infected in the background (y of the foot, x from/to, scale);
- 'front': piece drawn IN FRONT of whoever has 'behind': true (the counter), kept as an RGBA layer;
- 'close_x' and 'sil_x': where the close and the duo place the character and the 'appear' silhouette.
To add a set: write _draw_<name>(lit) and the entry in SETS; check on a still.
Everything that matters stays at x < 930. The ceiling lamp stays below y 540 so it does not touch the HUD clock.
"""

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .common import AMB, AMB_D, H, P, S, VAC, W, WARM, font, mix
from .places import WIDE_POINTS

FOG = (20, 26, 38)
WALL = (15, 19, 28)
FLOOR = (12, 15, 22)
COUNTER = (40, 34, 30)
COUNTER_TOP = (72, 58, 42)
WOOD_LINE = (54, 46, 40)
GRATE = (44, 48, 56)


def _add_glow(img: Image.Image, spots: list[tuple], blur: float = 30) -> Image.Image:
    """Added light (lamp, street lamp, shop window): amber ellipses or polygons blurred at 1/4 of the resolution."""
    small = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
    d = ImageDraw.Draw(small)
    for spot in spots:
        if spot[0] == "poly":
            _, pts, amount = spot
            d.polygon([(x / 4, y / 4) for x, y in pts], fill=tuple(int(c * amount / 255) for c in AMB))
        else:
            x0, y0, x1, y1, amount = spot
            d.ellipse([x0 / 4, y0 / 4, x1 / 4, y1 / 4], fill=tuple(int(c * amount / 255) for c in AMB))
    small = small.filter(ImageFilter.GaussianBlur(blur / 4))
    return ImageChops.add(img, small.resize(img.size, Image.BILINEAR))


def _fog(img: Image.Image, amount: float) -> Image.Image:
    return Image.blend(img, Image.new("RGB", img.size, FOG), amount)


def _buildings(d, ground: float, x0: float = -40, x1: float = 1120, seed: int = 3, top: float = 520) -> None:
    x, i = x0, 0
    while x < x1:
        w = 150 + (seed * 37 + i * 53) % 120
        h = top + (seed * 29 + i * 71) % 260
        d.rectangle([P(x), P(ground - h), P(x + w), P(ground)], fill=(17, 22, 32))
        for wy in range(int(ground - h + 40), int(ground - 50), 80):
            for wx in range(int(x + 24), int(x + w - 34), 56):
                lit = (wx * 7 + wy * 3 + seed) % 13 == 0
                d.rectangle([P(wx), P(wy), P(wx + 22), P(wy + 34)], fill=(74, 56, 28) if lit else (21, 27, 38))
        x += w + 14
        i += 1


def _street_through(d, x0, y0, x1, y1, ground) -> None:
    """The dark street seen through glass: buildings across, sidewalk and curb."""
    d.rectangle([P(x0), P(y0), P(x1), P(y1)], fill=(8, 11, 17))
    _buildings(d, ground - 40, x0 - 30, x1, seed=5, top=260)
    d.rectangle([P(x0), P(ground - 40), P(x1), P(y1)], fill=(11, 14, 21))
    d.line([(P(x0), P(ground - 10)), (P(x1), P(ground - 10))], fill=(56, 46, 32), width=2 * S)


# ------------------------------------------------------------------ pharmacy interior

PH_DOOR = (780, 620, 945, 1240)
PH_COUNTER = (150, 1050, 560, 1240)
PH_LAMP_Y = 556                                   # ceiling lamp (below the HUD clock at any zoom)


def _draw_pharmacy(lit: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), WALL)
    d = ImageDraw.Draw(img)
    for k in range(10):                                               # wall darkens toward the ceiling (HUD)
        d.rectangle([P(0), P(k * 56), P(W), P(k * 56 + 56)], fill=mix(VAC, WALL, k / 9))
    x0, y0, x1, y1 = PH_DOOR
    _street_through(d, x0, y0, x1, y1, 1220)
    img = _add_glow(img, [(820, 640, 1060, 880, 60)], 50)            # street lamp outside, seen through the door
    d = ImageDraw.Draw(img)
    d.rectangle([P(x0), P(y0), P(x1), P(y1)], outline=WARM, width=5 * S)
    d.line([(P(x0 + 10), P(980)), (P(x1 - 10), P(980))], fill=(48, 48, 52), width=6 * S)   # door bar
    img = _fog(img, 0.22)
    d = ImageDraw.Draw(img)
    for i, sx in enumerate((40, 280, 520)):                           # wall shelves
        d.rectangle([P(sx), P(620), P(sx + 220), P(1180)], fill=(22, 28, 40), outline=WARM, width=2 * S)
        for k, yy in enumerate(range(680, 1160, 110)):
            d.line([(P(sx + 8), P(yy + 60)), (P(sx + 212), P(yy + 60))], fill=WARM, width=2 * S)
            for j in range(6):
                bx = sx + 14 + j * 34
                hh = 30 + ((i * 7 + k * 5 + j * 3) % 4) * 6
                c = ((70, 74, 84), (88, 70, 52), (58, 84, 78), (84, 80, 60))[(i + k + j) % 4]
                d.rectangle([P(bx), P(yy + 58 - hh), P(bx + 24), P(yy + 58)], fill=c)
    img = _fog(img, 0.16)
    d = ImageDraw.Draw(img)
    d.rectangle([P(0), P(1240), P(W), P(H)], fill=FLOOR)
    d.line([(P(0), P(1240)), (P(W), P(1240))], fill=AMB_D, width=3 * S)
    for k in range(1, 6):
        y = 1240 + k * k * 22
        d.line([(P(0), P(y)), (P(W), P(y))], fill=(18, 22, 31), width=S)
    for lx in (250, 620):                                             # ceiling lamps
        d.line([(P(lx), P(PH_LAMP_Y - 60)), (P(lx), P(PH_LAMP_Y - 14))], fill=(40, 40, 44), width=3 * S)
        d.rectangle([P(lx - 70), P(PH_LAMP_Y - 14), P(lx + 70), P(PH_LAMP_Y)], fill=AMB if lit else (60, 52, 40))
    if lit:
        y = PH_LAMP_Y
        img = _add_glow(img, [("poly", [(180, y), (320, y), (420, 1300), (80, 1300)], 46),
                              ("poly", [(550, y), (690, y), (790, 1300), (450, 1300)], 46),
                              (60, 1180, 860, 1340, 40)], 40)
    return img


def _front_pharmacy(d, level: float) -> None:
    """Counter (in front of whoever is 'behind'): panel, top with an amber thread and the cash register."""
    x0, y0, x1, y1 = PH_COUNTER
    c = mix(VAC, COUNTER, 0.55 + 0.45 * level)
    top = mix(VAC, COUNTER_TOP, 0.55 + 0.45 * level)
    d.rectangle([P(x0), P(y0), P(x1), P(y1)], fill=c, outline=WARM, width=2 * S)
    for x in range(x0 + 70, x1, 90):
        d.line([(P(x), P(y0 + 30)), (P(x), P(y1 - 10))], fill=WOOD_LINE, width=2 * S)
    d.rectangle([P(x0 - 14), P(y0 - 16), P(x1 + 14), P(y0 + 6)], fill=top)
    d.line([(P(x0 - 14), P(y0 - 16)), (P(x1 + 14), P(y0 - 16))], fill=mix(top, AMB, 0.4 * level + 0.1), width=3 * S)
    d.rectangle([P(x0 + 60), P(y0 - 76), P(x0 + 150), P(y0 - 16)], fill=mix(VAC, (50, 54, 62), 0.6 + 0.4 * level),
                outline=WARM, width=2 * S)


# ------------------------------------------------------------------ bus stop

def _draw_busstop(lit: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), VAC)
    d = ImageDraw.Draw(img)
    for k in range(12):                                               # sky: Vacuum lightening near the horizon
        y = 560 + k * 40
        d.rectangle([P(0), P(y), P(W), P(y + 40)], fill=mix(VAC, (22, 28, 40), k / 11))
    _buildings(d, 1150, seed=2, top=420)
    img = _add_glow(img, [(900, 860, 1200, 1160, 34)], 60)           # far lamp post: backlight of the infected
    img = _fog(img, 0.35)
    d = ImageDraw.Draw(img)
    d.rectangle([P(-10), P(560), P(390), P(1240)], fill=(24, 26, 34), outline=WARM, width=2 * S)   # fachada
    d.rectangle([P(10), P(680), P(370), P(760)], fill=(30, 30, 34), outline=WARM, width=2 * S)
    d.text((P(190), P(720)), "PHARMACY", font=font(40), fill=AMB if lit else AMB_D, anchor="mm")
    d.rectangle([P(30), P(820), P(270), P(1160)], fill=(58, 44, 24) if lit else (16, 19, 26), outline=WARM, width=3 * S)
    for sx in (60, 150):
        d.rectangle([P(sx), P(880), P(sx + 70), P(1160)], outline=(90, 70, 40) if lit else (30, 34, 44), width=2 * S)
    d.rectangle([P(290), P(860), P(370), P(1240)], fill=(14, 17, 25), outline=WARM, width=3 * S)  # door
    d.rectangle([P(462), P(600), P(476), P(1240)], fill=(30, 34, 44))                              # poste
    d.line([(P(469), P(606)), (P(540), P(606))], fill=(30, 34, 44), width=8 * S)
    d.rounded_rectangle([P(510), P(596), P(570), P(618)], P(6), fill=AMB)
    d.rectangle([P(600), P(800), P(925), P(830)], fill=(40, 44, 52), outline=WARM, width=2 * S)    # abrigo
    d.rectangle([P(612), P(830), P(912), P(1170)], outline=(64, 74, 88), width=2 * S)
    for px in (606, 912):
        d.rectangle([P(px), P(830), P(px + 10), P(1240)], fill=(46, 50, 58))
    d.rectangle([P(660), P(1104), P(860), P(1124)], fill=(52, 46, 40), outline=WARM, width=2 * S)  # banco
    d.rectangle([P(690), P(1124), P(700), P(1240)], fill=(40, 40, 44))
    d.rectangle([P(820), P(1124), P(830), P(1240)], fill=(40, 40, 44))
    d.rectangle([P(640), P(850), P(760), P(900)], fill=(30, 34, 44), outline=WARM, width=2 * S)
    d.text((P(700), P(876)), "BUS 14", font=font(26), fill=AMB_D, anchor="mm")
    d.rectangle([P(0), P(1240), P(W), P(1300)], fill=(20, 23, 30))                                 # sidewalk
    d.line([(P(0), P(1240)), (P(W), P(1240))], fill=(60, 52, 40), width=2 * S)
    d.rectangle([P(0), P(1300), P(W), P(H)], fill=(10, 13, 19))
    d.line([(P(0), P(1300)), (P(W), P(1300))], fill=AMB_D, width=3 * S)
    for x in range(20, W, 140):
        d.rectangle([P(x), P(1540), P(x + 70), P(1550)], fill=(52, 46, 34))
    spots = [("poly", [(510, 618), (570, 618), (700, 1300), (380, 1300)], 54), (360, 1200, 700, 1320, 40)]
    if lit:
        spots += [(0, 760, 320, 1240, 50), (0, 1200, 360, 1320, 34)]
    return _add_glow(img, spots, 40)


# ------------------------------------------------------------------ front door seen from inside

FD_DOOR = (200, 520, 880, 1240)
FD_LOCK = (830, 930)
FD_BARS: list = []                # no grille: ordinary pharmacy glass door
FD_RAILS = [(FD_DOOR[0] + 8, 1150, FD_DOOR[2] - 8, 1162)]   # metal kick plate of the door
FD_PUSH = [(bx, 970, bx + 300, 990) for bx in (FD_DOOR[0] + 20, 560)]


def _draw_frontdoor(lit: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), WALL)
    d = ImageDraw.Draw(img)
    for k in range(10):
        d.rectangle([P(0), P(k * 52), P(W), P(k * 52 + 52)], fill=mix(VAC, WALL, k / 9))
    x0, y0, x1, y1 = FD_DOOR
    _street_through(d, x0, y0, x1, y1, 1190)
    img = _add_glow(img, [(560, 560, 900, 900, 70)], 60)              # lamp post across the street
    img = _fog(img, 0.22)
    d = ImageDraw.Draw(img)
    for r in FD_RAILS:                                                # metal kick plate
        d.rectangle([P(v) for v in r], fill=GRATE)
    for gx0, gx1 in ((x0 + 40, x0 + 120), (560, 640)):                # reflexo diagonal no vidro
        d.polygon([(P(gx0), P(y1 - 120)), (P(gx0 + 50), P(y1 - 120)), (P(gx1 + 50), P(y0 + 60)), (P(gx1), P(y0 + 60))],
                  fill=mix(WALL, (60, 70, 90), 0.35))
    d.rectangle([P(x0), P(y0), P(x1), P(y1)], outline=WARM, width=7 * S)
    d.line([(P(540), P(y0)), (P(540), P(y1))], fill=WARM, width=6 * S)
    for r in FD_PUSH:                                                 # push bars
        d.rounded_rectangle([P(v) for v in r], P(8), fill=(46, 46, 50))
    d.rectangle([P(0), P(1240), P(W), P(H)], fill=FLOOR)
    d.line([(P(0), P(1240)), (P(W), P(1240))], fill=AMB_D, width=3 * S)
    d.rectangle([P(x0 - 30), P(1240), P(x1 + 30), P(1262)], fill=(30, 30, 34))   # soleira
    lx, ly = FD_LOCK
    d.rounded_rectangle([P(lx - 22), P(ly - 40), P(lx + 22), P(ly + 40)], P(10), fill=(54, 54, 58), outline=WARM,
                        width=2 * S)
    if lit:
        img = _add_glow(img, [("poly", [(40, 440), (240, 440), (420, 1300), (0, 1300)], 42), (0, 1180, 700, 1340, 30)], 50)
    return img


# ------------------------------------------------------------------ alley behind the pharmacy

AL_MOUTH = (800, 700, 1100, 1236)               # alley mouth: the street with the lamp post, where the figure appears
AL_PALLET = (430, 1070, 700, 1240)


def _draw_alley(lit: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), VAC)
    d = ImageDraw.Draw(img)
    for k in range(12):                                               # sliver of sky between the buildings
        y = 520 + k * 50
        d.rectangle([P(0), P(y), P(W), P(y + 50)], fill=mix(VAC, (20, 26, 38), k / 11))
    x0, y0, x1, y1 = AL_MOUTH                                         # the street at the end of the alley
    _street_through(d, x0, y0, x1, y1, 1220)
    img = _add_glow(img, [(800, 700, 1120, 1260, 115)], 70)
    img = _fog(img, 0.25)
    d = ImageDraw.Draw(img)
    d.rectangle([P(-10), P(520), P(780), P(1240)], fill=(20, 24, 33))   # pharmacy brick wall (back)
    for ry in range(560, 1240, 36):
        d.line([(P(-10), P(ry)), (P(780), P(ry))], fill=(26, 31, 42), width=S)
        for rx in range(-10 + (ry // 36 % 2) * 30, 780, 60):
            d.line([(P(rx), P(ry)), (P(rx), P(ry + 36))], fill=(26, 31, 42), width=S)
    d.rectangle([P(1090), P(520), P(W + 10), P(1240)], fill=(18, 22, 30))   # neighboring building wall
    d.rectangle([P(40), P(730), P(220), P(1240)], fill=(30, 34, 44), outline=WARM, width=4 * S)   # steel door (taller than Sam)
    d.line([(P(130), P(740)), (P(130), P(1236))], fill=(44, 48, 58), width=2 * S)
    d.rounded_rectangle([P(186), P(1010), P(206), P(1060)], P(6), fill=AMB_D)
    d.text((P(130), P(700)), "BACK", font=font(30), fill=AMB if lit else AMB_D, anchor="mm")
    d.rectangle([P(250), P(700), P(262), P(1240)], fill=(34, 38, 48))   # downspout
    d.rectangle([P(310), P(1090), P(400), P(1240)], fill=(34, 40, 36), outline=WARM, width=2 * S)   # dumpster
    d.rectangle([P(300), P(1076), P(410), P(1096)], fill=(40, 46, 42), outline=WARM, width=2 * S)
    px0, py0, px1, py1 = AL_PALLET                                    # wrapped pallet of bottled water
    d.rectangle([P(px0), P(py1 - 30), P(px1), P(py1)], fill=(52, 42, 30), outline=WARM, width=2 * S)
    for k in range(3):
        d.line([(P(px0 + 20 + k * 110), P(py1 - 30)), (P(px0 + 20 + k * 110), P(py1))], fill=(34, 28, 22), width=3 * S)
    for row in range(3):
        for col in range(4):
            bx = px0 + 10 + col * 66
            by = py0 + 6 + row * 44
            d.rectangle([P(bx), P(by), P(bx + 60), P(by + 40)], fill=(40, 62, 74), outline=(70, 100, 120), width=S)
    d.rectangle([P(px0 - 4), P(py0 - 4), P(px1 + 4), P(py1 - 30)], outline=(150, 170, 190), width=2 * S)   # plastic wrap
    d.text(((px0 + px1) // 2 * S, (py0 + 60) * S), "WATER", font=font(34), fill=(180, 210, 230), anchor="mm")
    d.rectangle([P(0), P(1240), P(W), P(H)], fill=FLOOR)
    d.line([(P(0), P(1240)), (P(W), P(1240))], fill=AMB_D, width=3 * S)
    for k in range(1, 6):
        y = 1240 + k * k * 22
        d.line([(P(0), P(y)), (P(W), P(y))], fill=(18, 22, 31), width=S)
    for ty, tw in ((1268, 5), (1296, 5)):                             # truck tire marks, from the alley mouth to the pallet
        d.line([(P(1120), P(ty + 10)), (P(840), P(ty + 4)), (P(660), P(ty - 8)), (P(480), P(ty - 22))],
               fill=(30, 36, 48), width=tw * S)
    spots = [(780, 800, 1100, 1300, 38)]
    if lit:
        spots += [(30, 780, 330, 1260, 26)]
    return _add_glow(img, spots, 50)


def _inset(r, k):
    return (r[0] + k, r[1] + k, r[2] - k, r[3] - k)


SETS = {
    "pharmacy": {
        "draw": _draw_pharmacy, "ground": 1240, "front": _front_pharmacy, "front_box": (130, 960, 580, 1240),
        "points": WIDE_POINTS["pharmacy"],
        "targets": {"counter": (PH_COUNTER[0] + 20, PH_COUNTER[2] + 10, PH_COUNTER[1] - 14, "top"),
                    "door": (PH_DOOR[0], PH_DOOR[0], 900, "side"), "lock": (PH_DOOR[0] + 16, PH_DOOR[0] + 16, 940, "side")},
        "glass": [_inset(PH_DOOR, 6)], "glass_block": [(PH_DOOR[0], 974, PH_DOOR[2], 986)],
        "lane": {"y": 1205, "x": (PH_DOOR[0] + 10, PH_DOOR[2] - 10), "k": 0.34},
        "lock_xy": (PH_DOOR[0] + 16, 940), "close_x": 725, "sil_x": 860, "sil_y": 1215, "duo_x": 600,
        "carry_low": 975,                       # hand height when setting the jugs on the counter (top at y 1034)
    },
    "busstop": {
        "draw": _draw_busstop, "ground": 1240, "front": None,
        "points": WIDE_POINTS["busstop"],
        "targets": {"door": (290, 290, 1000, "side"), "lock": (296, 296, 1010, "side"),
                    "counter": (660, 860, 1100, "top")},
        "glass": [(390, 560, 1080, 1238)],
        "glass_block": [(460, 596, 478, 1240), (600, 798, 927, 832), (604, 830, 618, 1240), (910, 830, 924, 1240),
                        (658, 1102, 862, 1126), (688, 1124, 702, 1240), (818, 1124, 832, 1240), (508, 594, 572, 620)],
        "lane": {"y": 1150, "x": (400, 1070), "k": 0.27},
        "lock_xy": (296, 1010), "close_x": 420, "sil_x": 545, "sil_y": 1150, "sil_k": 0.45, "duo_x": 560,
    },
    "frontdoor": {
        "draw": _draw_frontdoor, "ground": 1240, "front": None,
        "points": WIDE_POINTS["frontdoor"],
        "targets": {"door": (FD_DOOR[0] + 30, FD_DOOR[2] - 30, 900, "glass"), "lock": (FD_LOCK[0], FD_LOCK[0], FD_LOCK[1], "side"),
                    "counter": (300, 300, 1060, "top")},
        "glass": [_inset(FD_DOOR, 8)],
        "glass_block": FD_BARS + FD_RAILS + FD_PUSH + [(533, FD_DOOR[1], 547, FD_DOOR[3])],
        "lane": {"y": 1180, "x": (FD_DOOR[0] + 20, FD_DOOR[2] - 20), "k": 0.5},
        "lock_xy": FD_LOCK, "close_x": 430, "sil_x": 600, "sil_y": 1200, "sil_k": 0.64, "duo_x": 540,
    },
    "alley": {
        "draw": _draw_alley, "ground": 1240, "front": None,
        "points": WIDE_POINTS["alley"],
        "targets": {"door": (230, 230, 1040, "side"), "lock": (210, 210, 1040, "side"), "counter": (520, 520, 1070, "top")},
        "glass": [AL_MOUTH], "glass_block": [],
        "lane": {"y": 1226, "x": (AL_MOUTH[0] + 40, AL_MOUTH[2] - 40), "k": 0.55},
        "lock_xy": (-300, -300), "close_x": 470, "sil_x": 960, "sil_y": 1222, "sil_k": 0.8, "duo_x": 520,
        "carry_low": 1010,                      # hands when picking the jugs from the pallet (top at y 1070)
    },
}

_GLASS: dict = {}


def glass_mask(name: str) -> Image.Image:
    """Mask (L, 1x world frame) of where the outside is seen, without what is in front of the glass."""
    if name not in _GLASS:
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        for r in SETS[name]["glass"]:
            d.rectangle(r, fill=255)
        for r in SETS[name]["glass_block"]:
            d.rectangle(r, fill=0)
        _GLASS[name] = m
    return _GLASS[name]


def glass_box(name: str) -> tuple:
    rs = SETS[name]["glass"]
    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))
