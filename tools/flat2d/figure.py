"""Drawing of the cast character: ONE figure only, in three views, on the enlarged frame (P() converts).

- body_side: full body in profile (walk, run, hit, bite);
- body_front: the same body from the front (f = 0) or in 3/4 (f = +1 looks right, -1 looks left),
  used in the 'close' and 'duo' framings and for anyone standing still in the 'wide'.
Simple cartoon: big head, blocky torso, arms and legs with volume (thick line with a round tip),
knee and elbow by 2-bone IK. The face (eye, eyebrow, speech mouth, sweat, paleness) uses the same
measurements in all three views and at any scale k; the warm outline thickens along with k (ow()), so the close
has the same stroke as the wide.

The look comes from the 'cast' (cast.py): skin, hair (short/long/bald/grey), shirt, lab coat and accessory
(headlamp/bandage/scarf/glasses). No wounds or blood: the infected is grayish skin and posture.
"""

import math

from .common import AMB, P, S, VAC, WARM, mix

BAND, EYE, MOUTH = (30, 30, 34), (24, 20, 20), (70, 34, 30)
LAMP_OFF = (90, 70, 40)
PALE = (176, 184, 178)            # paleness of 'sick'
TURNED = (138, 148, 150)          # infected skin (blue-gray, no wound)
SWEAT = (196, 212, 224)
SCARF = (190, 150, 50)            # mustard: reads well on the Vacuum and is not red
GAUZE, GAUZE_LINE = (232, 232, 226), (180, 180, 172)
SHOE = (24, 26, 30)
KEY = (196, 172, 104)
MOUTHS_PX = {1: (0.62, 14.0), 2: (0.78, 28.0), 3: (0.42, 22.0)}   # = acting.MOUTHS

# measurements in px with k = 1 (big head, simple cartoon)
R_HEAD, NECK, TORSO, TORSO_W = 70, 18, 190, 112
THIGH, SHIN, LEG_W = 108, 104, 40
UPPER, LOWER, ARM_W, HAND_R = 88, 84, 30, 17
EYE_RX, EYE_RY = 6.5, 7.5         # single eye: half-width and half-height (px with k = 1), the same for everyone
HIP_H = 205                       # hip height standing (leg almost straight)
K_REF = 0.85                      # wide scale: the outline is 2 px at it and grows along with k


def ow(k: float) -> int:
    """Outline width in px of the final frame: the same stroke at all scales."""
    return max(1, round(2 * k / K_REF))


def skin_of(look: dict, pale: float = 0.0, turn: float = 0.0) -> tuple:
    c = look["skin"]
    if pale > 0:
        c = mix(c, PALE, 0.55 * pale)
    if turn > 0:
        c = mix(c, TURNED, turn)
    return c


def _hair_color(look: dict, turn: float = 0.0) -> tuple:
    return mix(look["hair"], (90, 94, 98), 0.4 * turn) if turn else look["hair"]


def ik(a: tuple, b: tuple, l1: float, l2: float, side: float) -> tuple[tuple, tuple]:
    """Middle joint (knee, elbow) of 2 bones from a to b; side chooses which way it bends.
    Returns (joint, tip); the tip shortens if b is out of reach."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy) or 1e-6
    reach = l1 + l2 - 0.01
    if dist > reach:
        b = (a[0] + dx / dist * reach, a[1] + dy / dist * reach)
        dist = reach
    dist = max(dist, abs(l1 - l2) + 0.01)
    cos_a = max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)))
    th = math.atan2(dy, dx) + side * math.acos(cos_a)
    return (a[0] + l1 * math.cos(th), a[1] + l1 * math.sin(th)), b


def ik_arm(a: tuple, b: tuple, l1: float, l2: float) -> tuple[tuple, tuple]:
    """Arm by IK with the elbow always on the lower side (hanging, natural): it does not flip sideways mid-gesture."""
    e1, h = ik(a, b, l1, l2, 1.0)
    e2, _ = ik(a, b, l1, l2, -1.0)
    return (e1 if e1[1] >= e2[1] else e2), h


def limb(d, pts: list, width: float, color: tuple, outline: tuple | None = None, k: float = K_REF) -> None:
    """Limb with volume: thick line with round joints and tips; 'outline' draws a thin outline
    (the lab coat sleeve disappears against the lab coat without it)."""
    if outline is not None:
        limb(d, pts, width + 2 * ow(k), outline)
    w = max(2, int(width * S))
    d.line([(P(x), P(y)) for x, y in pts], fill=color, width=w, joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=color)


def block(d, cx: float, cy: float, w: float, h: float, r: float, ang: float, fill: tuple,
          outline: tuple | None = None, width: int = 2) -> None:
    """Rotated rounded rectangle (blocky torso): polygon with arc corners."""
    pts = []
    hw, hh = w / 2 - r, h / 2 - r
    for (sx, sy), a0 in (((1, 1), 0), ((-1, 1), 90), ((-1, -1), 180), ((1, -1), 270)):
        for k in range(7):
            a = math.radians(a0 + k * 15)
            pts.append((sx * hw + r * math.cos(a), sy * hh + r * math.sin(a)))
    ca, sa = math.cos(ang), math.sin(ang)
    poly = [(P(cx + x * ca - y * sa), P(cy + x * sa + y * ca)) for x, y in pts]
    d.polygon(poly, fill=fill, outline=outline, width=width * S if outline else 1)


def _ellipse(d, x: float, y: float, rx: float, ry: float, fill=None, outline=None, width: int = 0) -> None:
    d.ellipse([P(x - rx), P(y - ry), P(x + rx), P(y + ry)], fill=fill, outline=outline,
              width=width * S if outline else 0)


def _mouth(d, mx: float, my: float, k: float, prm: tuple, mouth: int, turn: float, f: int) -> None:
    """Mouth in any view: speech shape (1 to 3), open (fear), curve (smile/sad) or a line."""
    mouth_w, mouth_open, curve = prm[3], prm[4], prm[5]
    if mouth:
        fw, op = MOUTHS_PX[mouth]
        w = max(8.0, mouth_w * fw * 0.32) * k
        op = op * 0.42 * k * (0.8 if mouth_w < 30 else 1.0)
        _ellipse(d, mx, my, w / 2, op / 2, fill=MOUTH)
    elif mouth_open > 1.5 or turn > 0.5:
        op = max(mouth_open, 10 * turn) * 0.42 * k
        _ellipse(d, mx, my, mouth_w * 0.15 * k, op / 2, fill=MOUTH)
    elif abs(curve) > 0.5:
        pts = []
        for i in range(9):
            u = i / 4 - 1
            pts.append((P(mx + u * mouth_w * 0.16 * k + f * 2 * k), P(my + curve * 0.3 * k * (1 - u * u) - curve * 0.1 * k)))
        d.line(pts, fill=MOUTH, width=max(2, int(4 * k * S)), joint="curve")
    else:
        d.line([(P(mx - mouth_w * 0.16 * k), P(my)), (P(mx + mouth_w * 0.16 * k), P(my))], fill=MOUTH,
               width=max(2, int(4 * k * S)))


def _eye(d, ex: float, ey: float, k: float, prm: tuple, blink: float, turn: float, side: int, far: bool,
         skin: tuple) -> None:
    """Single-size eye (EYE_RX x EYE_RY) on every character, view and expression (including the far eye
    of the 3/4); the expression comes from the eyebrow, the mouth and the eyelid (covers the top of the eye: tiredness, smile)."""
    eye_h, brow_up, tilt = prm[0], prm[1], prm[2]
    ry = max(1.2, EYE_RY * k * blink)
    _ellipse(d, ex, ey, EYE_RX * k, ry, fill=mix(EYE, (150, 160, 166), 0.6 * turn))
    cover = max(0.0, (14.0 - eye_h) / 14.0)              # fraction of the eye covered by the eyelid (sick 0.29)
    if cover > 0.02 and blink > 0.9:
        edge = ey - EYE_RY * k + 2 * EYE_RY * k * cover   # bottom edge of the eyelid
        _ellipse(d, ex, edge - EYE_RY * k * 1.05, EYE_RX * k * 1.1, EYE_RY * k * 1.05, fill=skin)
    by = ey - 16 * k + brow_up * 0.4 * k
    # side = which side the nose is on (+1 to the right of the eye): the inner tip rises with fear
    d.line([(P(ex - side * 10 * k * (0.75 if far else 1)), P(by)), (P(ex + side * 8 * k), P(by - tilt * 0.4 * k))],
           fill=BAND, width=max(2, int(5 * k * S)))


def _sweat(d, x: float, y: float, k: float, sweat: float) -> None:
    if sweat > 0.3:
        r = 5 * k * sweat
        _ellipse(d, x, y, r, r, fill=SWEAT)
        d.polygon([(P(x - r * 0.8), P(y - r * 0.4)), (P(x + r * 0.8), P(y - r * 0.4)), (P(x), P(y - r * 2.4))], fill=SWEAT)


# ---------------------------------------------------------------- head in profile

def side_head(d, look: dict, c: tuple, k: float, f: int, prm: tuple, mouth: int, blink: float, lamp: float,
              turn: float) -> tuple:
    """Head in profile; returns where the flashlight sits (for the beam)."""
    R = R_HEAD * k
    hx, hy = c
    hair = _hair_color(look, turn)
    skin = skin_of(look, prm[6], turn)
    style = look["hair_style"]
    if style == "long":
        d.rounded_rectangle([P(hx - f * R * 0.95 - R * 0.5), P(hy - R * 0.4), P(hx - f * R * 0.95 + R * 0.5), P(hy + R * 1.5)],
                            P(R * 0.4), fill=hair)
    bbox = [P(hx - R), P(hy - R), P(hx + R), P(hy + R)]
    d.ellipse(bbox, fill=skin, outline=WARM, width=ow(k) * S)
    if style in ("short", "long", "grey"):
        a0, a1 = (135, 315) if f > 0 else (225, 405)
        if style == "grey":
            a0, a1 = (150, 300) if f > 0 else (240, 390)
        d.chord(bbox, a0, a1, fill=hair)
    else:                                             # bald: only the back fringe
        a0, a1 = (150, 215) if f > 0 else (-35, 30)
        d.chord(bbox, a0, a1, fill=hair)
    ex = hx - f * R * 0.12                            # orelha
    d.ellipse([P(ex - R * 0.14), P(hy - R * 0.12), P(ex + R * 0.14), P(hy + R * 0.22)], fill=mix(skin, (60, 40, 30), 0.2))
    gaze = prm[8]
    ex, ey = hx + f * R * 0.5, hy - R * 0.08 + gaze * 3 * k
    _eye(d, ex, ey, k, prm, blink, turn, f, False, skin)
    _mouth(d, hx + f * R * 0.66, hy + R * 0.48, k, prm, mouth, turn, f)
    acc = look["accessory"]
    lamp_xy = None
    if acc == "headlamp":
        y = hy - R * 0.42
        d.line([(P(hx - f * R * 0.85), P(y - R * 0.1)), (P(hx + f * R * 0.8), P(y))], fill=BAND, width=max(2, int(9 * k * S)))
        lx = hx + f * R * 0.86
        d.rounded_rectangle([P(lx - 12 * k), P(y - 14 * k), P(lx + 12 * k), P(y + 12 * k)], P(5 * k),
                            fill=mix(LAMP_OFF, AMB, lamp))
        lamp_xy = (lx + f * 10 * k, y)
    elif acc == "glasses":
        d.rounded_rectangle([P(ex - 14 * k), P(ey - 11 * k), P(ex + 14 * k), P(ey + 11 * k)], P(4 * k), outline=BAND,
                            width=max(2, int(3 * k * S)))
        d.line([(P(ex - f * 14 * k), P(ey - 4 * k)), (P(hx - f * R * 0.15), P(hy - R * 0.05))], fill=BAND,
               width=max(2, int(3 * k * S)))
    _sweat(d, hx + f * R * 0.2, hy - R * 0.55, k, prm[7])
    return lamp_xy


# ---------------------------------------------------------------- head from the front and 3/4

def front_head(d, look: dict, c: tuple, k: float, f: int, prm: tuple, mouth: int, blink: float, lamp: float,
               turn: float, down: float = 0.0, gx: float = 0.0) -> tuple:
    """Head from the front (f = 0) or 3/4 (f = ±1), with the same face measurements as the profile."""
    R = R_HEAD * k
    hx, hy = c
    hair = _hair_color(look, turn)
    skin = skin_of(look, prm[6], turn)
    ear_c = mix(skin, (60, 40, 30), 0.2)
    style = look["hair_style"]
    if style == "long":
        bx = hx - f * R * 0.12
        d.rounded_rectangle([P(bx - R * 1.0), P(hy - R * 0.5), P(bx + R * 1.0), P(hy + R * 1.12)], P(R * 0.45), fill=hair)
    if not f:
        for s in (-1, 1):
            _ellipse(d, hx + s * R * 0.96, hy + R * 0.05, R * 0.15, R * 0.2, fill=ear_c, outline=WARM, width=ow(k))
    bbox = [P(hx - R), P(hy - R), P(hx + R), P(hy + R)]
    d.ellipse(bbox, fill=skin, outline=WARM, width=ow(k) * S)
    if style in ("short", "long"):
        d.chord(bbox, 196, 344, fill=hair)
    elif style == "grey":
        d.chord(bbox, 208, 332, fill=hair)
    if f:                                             # nape on the far side (bald and grey: just a tuft)
        a0, a1 = (128, 232) if f > 0 else (-52, 52)
        if style in ("bald", "grey"):
            a0, a1 = (150, 210) if f > 0 else (-30, 30)
        d.chord(bbox, a0, a1, fill=hair)
    elif style in ("bald", "grey"):                   # from the front: tufts on the sides
        d.chord(bbox, 158, 205, fill=hair)
        d.chord(bbox, -25, 22, fill=hair)
    if f:                                             # ear on the far side
        _ellipse(d, hx - f * R * 0.74, hy + R * 0.05, R * 0.13, R * 0.19, fill=ear_c, outline=WARM, width=ow(k))
    gaze = prm[8]
    shift = f * R * 0.3
    eyes = []
    for side in (-1, 1):
        far = bool(f) and side == f
        ex = hx + shift + side * R * 0.36 * (0.82 if f else 1.0) + gaze * 3 * k * (f or 1) + gx * R * 0.2
        ey = hy - R * 0.05 + gaze * 3 * k + down * R * 0.26
        _eye(d, ex, ey, k, prm, blink, turn, -side, far, skin)
        eyes.append((ex, ey))
    _mouth(d, hx + shift * 1.05, hy + R * 0.48, k, prm, mouth, turn, f)
    acc = look["accessory"]
    lamp_xy = None
    if acc == "headlamp":
        y = hy - R * 0.45
        d.line([(P(hx - R * 0.9), P(y)), (P(hx + R * 0.9), P(y))], fill=BAND, width=max(2, int(9 * k * S)))
        lx = hx + shift * 0.8
        d.rounded_rectangle([P(lx - 14 * k), P(y - 13 * k), P(lx + 14 * k), P(y + 11 * k)], P(5 * k),
                            fill=mix(LAMP_OFF, AMB, lamp))
        lamp_xy = (lx, y)
    elif acc == "glasses":
        for ex, ey in eyes:
            d.rounded_rectangle([P(ex - 14 * k), P(ey - 11 * k), P(ex + 14 * k), P(ey + 11 * k)], P(4 * k), outline=BAND,
                                width=max(2, int(3 * k * S)))
        (ax, ay), (bx, by) = eyes
        d.line([(P(ax + 14 * k), P(ay - 4 * k)), (P(bx - 14 * k), P(by - 4 * k))], fill=BAND, width=max(2, int(3 * k * S)))
    _sweat(d, hx + R * 0.45 + shift, hy - R * 0.55, k, prm[7])
    return lamp_xy


# ---------------------------------------------------------------- body in profile

def _shoe_side(d, ft: tuple, k: float, f: int, col: tuple) -> None:
    d.rounded_rectangle([P(min(ft[0] - f * 10 * k, ft[0] + f * 40 * k)), P(ft[1] - 8 * k),
                         P(max(ft[0] - f * 10 * k, ft[0] + f * 40 * k)), P(ft[1] + 14 * k)], P(10 * k), fill=col)


def _hand(d, look: dict, hand: tuple, k: float, col: tuple, near: bool, shade) -> None:
    bandaged = look["accessory"] == "bandage" and near
    r = HAND_R * k
    _ellipse(d, hand[0], hand[1], r, r, fill=shade(GAUZE) if bandaged else col)


def _cup(d, hand: tuple, k: float) -> None:
    """Cup of water in the hand (clear glass, band of water), slightly above the center of the hand."""
    x, y = hand[0], hand[1] - HAND_R * k * 0.9
    w, h = 26 * k, 40 * k
    d.rounded_rectangle([P(x - w / 2), P(y - h), P(x + w / 2), P(y)], P(5 * k), fill=(178, 196, 210), outline=WARM,
                        width=max(2, ow(k) * S // 2))
    d.rectangle([P(x - w / 2 + 3 * k), P(y - h * 0.55), P(x + w / 2 - 3 * k), P(y - 4 * k)], fill=(104, 150, 192))


def _jug(d, hand: tuple, k: float, tone: float = 1.0) -> None:
    """Water jug hanging from the hand (clear plastic, blue water, amber cap and handle): 5 liters. `tone` < 1 darkens
    the far hand's jug (reads depth without disappearing behind the torso)."""
    x, y = hand[0], hand[1] + HAND_R * k * 0.4
    w, h = 50 * k, 70 * k
    dim = lambda c: mix(VAC, c, tone)
    d.arc([P(x - 14 * k), P(y - 10 * k), P(x + 14 * k), P(y + 14 * k)], 180, 360, fill=dim(WARM), width=max(2, int(3 * S)))
    d.rounded_rectangle([P(x - w / 2), P(y + 4 * k), P(x + w / 2), P(y + 4 * k + h)], P(8 * k), fill=dim((178, 196, 210)),
                        outline=dim(WARM), width=max(2, ow(k) * S // 2))
    d.rectangle([P(x - w / 2 + 4 * k), P(y + 4 * k + h * 0.35), P(x + w / 2 - 4 * k), P(y + 4 * k + h - 5 * k)],
                fill=dim((104, 150, 192)))
    d.rectangle([P(x - 8 * k), P(y - 2 * k), P(x + 8 * k), P(y + 5 * k)], fill=dim(AMB))


def jug_shape(d, cx: float, base_y: float, k: float) -> None:
    """Jug standing on a surface (counter): base at `base_y`."""
    _jug(d, (cx, base_y - 74 * k - HAND_R * k * 0.4), k)


def scarf_shape(d, cx: float, base_y: float, k: float, shade=lambda c: c) -> None:
    """Rosa's forgotten scarf on the counter: a band lying on the top and one end hanging over the front."""
    col, edge = shade(SCARF), shade(mix(SCARF, VAC, 0.4))
    d.rounded_rectangle([P(cx - 70 * k), P(base_y - 18 * k), P(cx + 56 * k), P(base_y)], P(9 * k), fill=col,
                        outline=edge, width=max(2, int(2 * k * S)))
    d.rounded_rectangle([P(cx + 30 * k), P(base_y - 4 * k), P(cx + 56 * k), P(base_y + 78 * k)], P(9 * k), fill=col,
                        outline=edge, width=max(2, int(2 * k * S)))
    d.line([(P(cx - 40 * k), P(base_y - 12 * k)), (P(cx + 20 * k), P(base_y - 6 * k))], fill=edge, width=max(2, int(2 * k * S)))


def pills_shape(d, cx: float, base_y: float, k: float, shade=lambda c: c) -> None:
    """Paper bag with Rosa's mother's medicine, on the counter: brown bag with a folded rim and an amber bottle."""
    bag, edge, fold = shade((176, 140, 98)), shade((92, 70, 46)), shade((206, 170, 124))
    d.polygon([(P(cx - 40 * k), P(base_y)), (P(cx + 40 * k), P(base_y)), (P(cx + 34 * k), P(base_y - 86 * k)),
               (P(cx - 34 * k), P(base_y - 86 * k))], fill=bag, outline=edge)
    d.rectangle([P(cx - 36 * k), P(base_y - 94 * k), P(cx + 36 * k), P(base_y - 82 * k)], fill=fold, outline=edge,
                width=max(2, int(2 * k * S)))
    d.line([(P(cx - 40 * k), P(base_y)), (P(cx - 34 * k), P(base_y - 86 * k))], fill=edge, width=max(2, int(2 * k * S)))
    d.line([(P(cx + 40 * k), P(base_y)), (P(cx + 34 * k), P(base_y - 86 * k))], fill=edge, width=max(2, int(2 * k * S)))
    bx = cx + 64 * k                                      # bottle beside the bag
    d.rounded_rectangle([P(bx - 15 * k), P(base_y - 46 * k), P(bx + 15 * k), P(base_y)], P(5 * k), fill=shade((214, 126, 28)),
                        outline=edge, width=max(2, int(2 * k * S)))
    d.rectangle([P(bx - 17 * k), P(base_y - 58 * k), P(bx + 17 * k), P(base_y - 46 * k)], fill=shade((232, 232, 226)),
                outline=edge, width=max(2, int(2 * k * S)))
    d.rectangle([P(bx - 10 * k), P(base_y - 36 * k), P(bx + 10 * k), P(base_y - 16 * k)], fill=shade((238, 236, 226)))


def _keys(d, hand: tuple, k: float) -> None:
    """Bunch of keys hanging from the hand (big, to read on a phone screen): amber ring and three keys."""
    k = k * 2.0
    x, y = hand[0], hand[1] + HAND_R * k * 0.15
    d.ellipse([P(x - 11 * k), P(y - 4 * k), P(x + 11 * k), P(y + 18 * k)], outline=AMB, width=int(3 * S))
    for dx, ln in ((-10, 34), (0, 44), (10, 34)):
        cx = x + dx * k
        d.rounded_rectangle([P(cx - 3.5 * k), P(y + 14 * k), P(cx + 3.5 * k), P(y + (14 + ln) * k)],
                            P(2 * k), fill=(214, 164, 58), outline=(40, 30, 14), width=2 * S)
        d.rectangle([P(cx), P(y + (14 + ln - 8) * k), P(cx + 9 * k), P(y + (14 + ln - 3) * k)], fill=(214, 164, 58))


def _phone(d, hand: tuple, k: float) -> None:
    """Phone pulled to the belly, seen from behind (the screen faces the user): dark body with the lens."""
    w, h = 50 * k, 92 * k
    x0, y1 = hand[0] - w / 2, hand[1] + 8 * k
    y0 = y1 - h
    d.rounded_rectangle([P(x0), P(y0), P(x0 + w), P(y1)], P(8 * k), fill=(38, 42, 52), outline=(150, 154, 162),
                        width=max(2, int(2 * k) * S // 2))
    d.ellipse([P(x0 + 7 * k), P(y0 + 7 * k), P(x0 + 19 * k), P(y0 + 19 * k)], fill=(18, 20, 28), outline=(96, 102, 114))


def body_side(d, look: dict, pose: dict, k: float, prm: tuple, mouth: int, blink: float, lamp: float,
              shade=lambda c: c) -> dict:
    """Full body in profile. pose: hip (x, y), lean (rad, + forward), f, feet [back, front],
    hands [back, front] (target point or None), swing (arm angle), turn, hunch, head_dx.
    Returns useful points (shoulder, front hand, head, flashlight) for whoever draws on top."""
    f, turn = pose["f"], pose.get("turn", 0.0)
    hip = pose["hip"]
    lean = pose.get("lean", 0.0)
    ux, uy = f * math.sin(lean), -math.cos(lean)       # torso axis, from the hip upward
    sh = (hip[0] + ux * TORSO * k, hip[1] + uy * TORSO * k)
    hunch = pose.get("hunch", 0.0)
    head = (sh[0] + ux * (NECK + R_HEAD) * k + f * (hunch * 26 + pose.get("head_dx", 0.0)) * k,
            sh[1] + uy * (NECK + R_HEAD) * k + hunch * 22 * k)
    pants = shade(look.get("pants", (44, 50, 64)))
    body = shade(look["body"])
    skin = shade(skin_of(look, prm[6], turn))
    back = lambda c: mix(c, VAC, 0.35)               # back limb darker: reads depth
    sj = (sh[0] - ux * 26 * k, sh[1] - uy * 26 * k)  # shoulder joint, slightly below the top of the torso
    swing = pose.get("swing", (0.0, 0.0))
    arms = []
    for i in (0, 1):
        tgt = pose.get("hands", (None, None))[i]
        if tgt is not None:
            el, hand = ik_arm(sj, tgt, UPPER * k, LOWER * k)
        else:
            a = swing[i]
            bend = pose.get("elbow", 0.25) + (0.4 * turn)
            el = (sj[0] + f * math.sin(a) * UPPER * k, sj[1] + math.cos(a) * UPPER * k)
            hand = (el[0] + f * math.sin(a + bend) * LOWER * k, el[1] + math.cos(a + bend) * LOWER * k)
        arms.append((el, hand))
    legs = [ik(hip, pose["feet"][i], THIGH * k, SHIN * k, -f) for i in (0, 1)]

    def draw_leg(i, col):
        knee, ft = legs[i]
        limb(d, [hip, knee, ft], LEG_W * k, col)
        _shoe_side(d, ft, k, f, back(SHOE) if i == 0 else SHOE)

    def draw_arm(i, col, scol):
        el, hand = arms[i]
        limb(d, [sj, el, hand], ARM_W * k, col, WARM if i == 1 else None, k)
        _hand(d, look, hand, k, scol, i == 1, shade)
        if i == 1 and pose.get("item") == "cup":
            _cup(d, hand, k)
        elif i == 1 and pose.get("item") == "jug":
            _jug(d, hand, k)
        elif i == 1 and pose.get("item") == "keys":
            _keys(d, hand, k)

    draw_arm(0, back(body), back(skin))
    draw_leg(0, back(pants))
    draw_leg(1, pants)
    mid = ((hip[0] + sh[0]) / 2, (hip[1] + sh[1]) / 2)
    if look["coat"]:                                   # lab coat: longer block, shirt in front
        cl = TORSO * k + 80 * k
        cmid = (mid[0] - ux * 40 * k, mid[1] - uy * 40 * k)
        block(d, cmid[0], cmid[1], TORSO_W * k + 8 * k, cl, 30 * k, lean * f, body, WARM, ow(k))
        nx, ny = f * -uy, f * ux                     # torso normal, toward the front side
        off = (TORSO_W / 2 - 14) * k
        block(d, mid[0] + nx * off + ux * 30 * k, mid[1] + ny * off + uy * 30 * k, 16 * k, TORSO * k * 0.55, 6 * k,
              lean * f, shade(look["collar"]))
    else:
        block(d, mid[0], mid[1], TORSO_W * k, TORSO * k + 30 * k, 36 * k, lean * f, body, WARM, ow(k))
    if look["accessory"] == "scarf":
        nk = (sh[0] + ux * 6 * k, sh[1] + uy * 6 * k)
        limb(d, [(nk[0] - f * 34 * k, nk[1]), (nk[0] + f * 34 * k, nk[1])], 26 * k, shade(SCARF))
        limb(d, [(nk[0] + f * 20 * k, nk[1]), (nk[0] + f * 30 * k, nk[1] + 90 * k)], 20 * k, shade(SCARF))
    if pose.get("item") == "jug":                      # the back hand's jug goes over the torso, darker
        _jug(d, arms[0][1], k, 0.72)
    lamp_xy = side_head(d, look, head, k, f, prm, mouth, blink, lamp, turn)
    draw_arm(1, body, skin)
    return {"shoulder": sh, "hand": arms[1][1], "head": head, "hip": hip, "lamp": lamp_xy, "dir": (f, 0.12)}


# ---------------------------------------------------------------- body from the front and 3/4

def front_width(k: float, f: int) -> float:
    return TORSO_W * k * (1.25 if f else 1.5)


def front_shoulders(hip: tuple, k: float, f: int) -> tuple:
    """Shoulder joints (left, right on screen) of the front/3/4 body."""
    tw = front_width(k, f)
    cx, y = hip[0] + f * 4 * k, hip[1] - TORSO * k + 24 * k
    return ((cx - tw / 2 + ARM_W * k * 0.55, y), (cx + tw / 2 - ARM_W * k * 0.55, y))


def body_front(d, look: dict, pose: dict, k: float, prm: tuple, mouth: int, blink: float, lamp: float,
               shade=lambda c: c) -> dict:
    """Full body from the front (pose f = 0) or 3/4 (f = ±1). pose: hip, ground, f, hands [left, right] (target or
    None), turn, hunch. The arm on the side it looks toward (3/4) stays behind the torso, unless it has a target."""
    f, turn = pose["f"], pose.get("turn", 0.0)
    hip = pose["hip"]
    ground = pose.get("ground", hip[1] + HIP_H * k)
    tw = front_width(k, f)
    cx = hip[0] + f * 4 * k
    sh_y = hip[1] - TORSO * k
    hunch = pose.get("hunch", 0.0)
    head = (cx + f * 10 * k + f * hunch * 10 * k + pose.get("head_x", 0.0) * 9 * k,
            sh_y - (NECK + R_HEAD) * k + hunch * 20 * k)
    pants = shade(look.get("pants", (44, 50, 64)))
    body = shade(look["body"])
    skin = shade(skin_of(look, prm[6], turn))
    back = lambda c: mix(c, VAC, 0.3)
    shoulders = front_shoulders(hip, k, f)
    hands_t = pose.get("hands", (None, None))
    arms = []
    for i, s in enumerate((-1, 1)):
        sj = shoulders[i]
        tgt = hands_t[i]
        if tgt is not None:
            el, hand = ik_arm(sj, tgt, UPPER * k, LOWER * k)
        else:
            up = 0.55 * turn                              # infected: arms forward (shortened)
            el = (sj[0] + s * (8 - 14 * up) * k, sj[1] + UPPER * k * (0.98 - 0.4 * up))
            hand = (el[0] + s * (4 - 30 * up) * k, el[1] + LOWER * k * (0.96 - 0.5 * up))
        arms.append((el, hand))
    far_i = (1 if f > 0 else 0) if f else None

    def draw_arm(i, col, scol):
        el, hand = arms[i]
        limb(d, [shoulders[i], el, hand], ARM_W * k, col, WARM, k)
        _hand(d, look, hand, k, scol, True, shade)
        if i == pose.get("item_hand", 1) and pose.get("item") == "cup":
            _cup(d, hand, k)
        elif i == pose.get("item_hand", 1) and pose.get("item") == "keys":
            _keys(d, hand, k)
        elif i == pose.get("item_hand", 1) and pose.get("item") == "phone":
            _phone(d, hand, k)

    for i, s in enumerate((-1, 1)):                       # legs: straight, one step apart
        hj = (cx + s * tw * 0.24, hip[1] + 6 * k)
        ft = (cx + s * tw * 0.27 + f * 8 * k, ground)
        knee = ((hj[0] + ft[0]) / 2 + s * 3 * k, (hj[1] + ft[1]) / 2)
        col = back(pants) if far_i == i else pants
        limb(d, [hj, knee, ft], LEG_W * k, col)
        d.rounded_rectangle([P(ft[0] - 24 * k + f * 10 * k), P(ft[1] - 9 * k), P(ft[0] + 24 * k + f * 14 * k),
                             P(ft[1] + 12 * k)], P(10 * k), fill=SHOE)
    if far_i is not None and hands_t[far_i] is None:
        draw_arm(far_i, back(body), back(skin))
    mid_y = (hip[1] + sh_y) / 2
    if look["coat"]:
        block(d, cx, mid_y + 40 * k, tw + 8 * k, TORSO * k + 110 * k, 30 * k, 0.0, body, WARM, ow(k))
    else:
        block(d, cx, mid_y + 4 * k, tw, TORSO * k + 38 * k, 36 * k, 0.0, body, WARM, ow(k))
    nx = cx + f * tw * 0.12                               # V collar (shirt under the lab coat)
    v = [(P(nx - 26 * k), P(sh_y - 12 * k)), (P(nx + 26 * k), P(sh_y - 12 * k)), (P(nx + f * 4 * k), P(sh_y + 58 * k))]
    d.polygon(v, fill=shade(look["collar"]))
    if look["coat"]:
        for s in (-1, 1):
            d.line([(P(nx + s * 26 * k), P(sh_y - 12 * k)), (P(nx + s * 44 * k), P(sh_y + 110 * k))], fill=WARM,
                   width=ow(k) * S)
    if look["accessory"] == "scarf":
        limb(d, [(cx - tw * 0.34, sh_y - 6 * k), (cx + tw * 0.34, sh_y - 6 * k)], 28 * k, shade(SCARF))
        tx = cx + (f or 1) * tw * 0.2
        limb(d, [(tx, sh_y), (tx + (f or 1) * 4 * k, sh_y + 100 * k)], 22 * k, shade(SCARF))
    lamp_xy = front_head(d, look, head, k, f, prm, mouth, blink, lamp, turn, pose.get("look_down", 0.0),
                         pose.get("look_x", 0.0))
    for i in (0, 1):
        if i != far_i or hands_t[i] is not None:
            draw_arm(i, body, skin)
    near = 1 if f >= 0 else 0
    return {"shoulders": shoulders, "hand": arms[near][1], "hands": [a[1] for a in arms], "head": head, "hip": hip,
            "lamp": lamp_xy, "dir": (0.85, -0.42) if not f else (f, -0.95)}


# ---------------------------------------------------------------- objects and close-up hand

def hand_shape(d, x: float, y: float, k: float, skin: tuple, bandage: bool, f: int = 1) -> None:
    """Open hand, palm toward the camera; with 'bandage', rolled-up clear gauze (no stain)."""
    w = ow(k * 2.5)
    d.rounded_rectangle([P(x - 52 * k), P(y - 40 * k), P(x + 52 * k), P(y + 70 * k)], P(30 * k), fill=skin,
                        outline=WARM, width=w * S)
    for i, fx in enumerate((-36, -12, 12, 36)):
        top = y - (88 if i in (1, 2) else 76) * k
        d.rounded_rectangle([P(x + fx * k - 11 * k), P(top), P(x + fx * k + 11 * k), P(y - 20 * k)], P(11 * k), fill=skin,
                            outline=WARM, width=w * S)
    tx = x + f * 58 * k                                # polegar
    d.rounded_rectangle([P(min(tx, tx + f * 34 * k) - 12 * k), P(y - 10 * k), P(max(tx, tx + f * 34 * k) + 12 * k),
                         P(y + 22 * k)], P(14 * k), fill=skin, outline=WARM, width=w * S)
    if bandage:
        d.rounded_rectangle([P(x - 56 * k), P(y - 26 * k), P(x + 56 * k), P(y + 62 * k)], P(22 * k), fill=GAUZE,
                            outline=GAUZE_LINE, width=w * S)
        for yy in (-4, 20, 44):
            d.line([(P(x - 50 * k), P(y + (yy - 6) * k)), (P(x + 50 * k), P(y + (yy + 6) * k))], fill=GAUZE_LINE,
                   width=w * S)


def key_shape(d, x: float, y: float, k: float, ang: float = 0.0) -> None:
    """Fallen bunch of keys (the 'drop' object): the same amber ring and the 3 keys from Sam's hand, lying on the ground."""
    r = 10 * k
    d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], outline=KEY, width=max(2, int(4 * k * S)))
    for da, ln in ((-0.5, 28), (0.0, 36), (0.5, 28)):
        a = ang + da
        sx, sy = x + math.cos(a) * r, y + math.sin(a) * r
        ex, ey = x + math.cos(a) * (r + ln * k), y + math.sin(a) * (r + ln * k)
        d.line([(P(sx), P(sy)), (P(ex), P(ey))], fill=KEY, width=max(2, int(5 * k * S)))
        d.line([(P(ex), P(ey)), (P(ex - math.sin(a) * 8 * k), P(ey + math.cos(a) * 8 * k))], fill=KEY,
               width=max(2, int(4 * k * S)))
