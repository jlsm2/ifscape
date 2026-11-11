"""'insert' shot: close-up of an object, off the stage (no full-body character). Currently only 'sink': the faucet
of a sink in the foreground, dark tile behind, and the hand of 'who' (cast coat sleeve) that comes down over
the lever and turns; the water coughs in a short, failing jet ('spurt', seconds after the 'sink' event starts)
and then only drips. The hand stays on the faucet until the end of the scene.

Event: {"word": ..., "do": "sink", "who": "rosa", "spurt": 2.28}. cues() gives the jet instant to sound design.
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .cast import look_for
from .common import AMB, FPS, H, VAC, W, WARM, clamp, lerp, mix, smooth
from .tracks import Track

SS = 2                                   # drawing supersample (2160x3840, downsized at the end)
STEM_X, BAR_Y = 480, 800                 # center of the lever (px of the final frame)
SPOUT_TIP = (690, 1010)
BASIN_Y = 1330
REACH_SECONDS = 0.45
TURN_SECONDS = 0.6
SPURT_SECONDS = 0.5
CHROME, CHROME_HI, CHROME_LO = (196, 202, 210), (238, 242, 248), (120, 128, 140)
WATER = (150, 198, 238)


def _p(v):
    return int(round(v * SS))


class Insert:
    def __init__(self, flat: dict, events: list[dict], seconds: float, cast: dict | None = None):
        self.seconds = seconds
        self.look = look_for(cast, flat.get("who", "rosa"))
        self.reach = Track(0.0)           # 0 hand out of frame, 1 hand on the lever
        self.turn = Track(0.0)            # alavanca girada
        self.spurts: list[tuple[float, float]] = []
        for ev in events:
            if ev["do"] == "sink":
                t = ev["t"]
                self.reach.to(t, REACH_SECONDS, 1.0)
                self.turn.to(t + REACH_SECONDS + 0.1, TURN_SECONDS, 1.0)
                s0 = t + ev.get("spurt", 1.0)
                self.spurts.append((s0, s0 + SPURT_SECONDS))
        self._bg = None

    def cues(self) -> list[dict]:
        return [{"do": "sink_spurt", "t": round(a, 3), "frame": round(a * FPS)} for a, _ in self.spurts]

    # ------------------------------------------------------------ fundo parado
    def _background(self) -> Image.Image:
        img = Image.new("RGB", (W * SS, H * SS), VAC)
        d = ImageDraw.Draw(img)
        for k in range(16):                                         # wall darkens toward the ceiling (HUD and caption)
            y0, y1 = k * H / 16, (k + 1) * H / 16
            d.rectangle([0, _p(y0), W * SS, _p(y1)], fill=mix(VAC, (30, 40, 56), 0.25 + 0.75 * k / 15))
        for x in range(0, W + 1, 135):                              # azulejos
            d.line([(_p(x), 0), (_p(x), _p(BASIN_Y))], fill=(40, 52, 70), width=_p(3))
        for y in range(300, BASIN_Y, 135):
            d.line([(0, _p(y)), (W * SS, _p(y))], fill=(40, 52, 70), width=_p(3))
        glow = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))        # amber flashlight glow, from above
        ImageDraw.Draw(glow).ellipse([60 // 4, 500 // 4, 760 // 4, 1100 // 4], fill=tuple(int(c * 0.24) for c in AMB))
        glow = glow.filter(ImageFilter.GaussianBlur(40)).resize(img.size, Image.BILINEAR)
        img = Image.fromarray(np.minimum(255, np.asarray(img, dtype="int16") + np.asarray(glow, dtype="int16")).astype("uint8"))
        d = ImageDraw.Draw(img)
        d.rectangle([0, _p(BASIN_Y - 40), W * SS, _p(H)], fill=(24, 30, 42))           # bancada
        d.rounded_rectangle([_p(110), _p(BASIN_Y), _p(970), _p(1740)], _p(40), fill=(176, 184, 194))
        d.rounded_rectangle([_p(110), _p(BASIN_Y), _p(970), _p(BASIN_Y + 56)], _p(28), fill=(214, 220, 228))
        d.ellipse([_p(180), _p(BASIN_Y + 40), _p(900), _p(1690)], fill=(52, 60, 74))   # cuba
        d.ellipse([_p(220), _p(BASIN_Y + 70), _p(860), _p(1640)], fill=(66, 76, 92))
        d.ellipse([_p(640), _p(1560), _p(740), _p(1592)], fill=(14, 18, 26))           # ralo
        d.rectangle([0, _p(BASIN_Y - 40), W * SS, _p(BASIN_Y)], fill=(58, 68, 84))       # top of the counter, where the faucet rests
        d.line([(0, _p(BASIN_Y - 40)), (W * SS, _p(BASIN_Y - 40))], fill=CHROME_LO, width=_p(3))
        d.rounded_rectangle([_p(STEM_X - 42), _p(840), _p(STEM_X + 42), _p(BASIN_Y - 36)], _p(18), fill=CHROME, outline=WARM, width=_p(3))
        d.rectangle([_p(STEM_X - 22), _p(860), _p(STEM_X - 10), _p(BASIN_Y - 60)], fill=CHROME_HI)
        d.rounded_rectangle([_p(STEM_X - 42), _p(820), _p(SPOUT_TIP[0] + 36), _p(906)], _p(30), fill=CHROME, outline=WARM, width=_p(3))
        d.rounded_rectangle([_p(SPOUT_TIP[0] - 36), _p(860), _p(SPOUT_TIP[0] + 36), _p(SPOUT_TIP[1])], _p(18), fill=CHROME, outline=WARM, width=_p(3))
        d.rectangle([_p(SPOUT_TIP[0] - 20), _p(850), _p(SPOUT_TIP[0] - 8), _p(990)], fill=CHROME_HI)
        d.rounded_rectangle([_p(STEM_X - 66), _p(BASIN_Y - 62), _p(STEM_X + 66), _p(BASIN_Y - 34)], _p(8), fill=CHROME_LO, outline=WARM, width=_p(3))  # base no tampo
        return img

    # ------------------------------------------------------------ frame
    def render(self, t: float) -> Image.Image:
        if self._bg is None:
            self._bg = self._background()
        img = self._bg.copy()
        d = ImageDraw.Draw(img)
        reach, turn = smooth(self.reach.at(t)), smooth(self.turn.at(t))
        ang = math.radians(38) * turn
        grip = (STEM_X + 112 * math.cos(ang), BAR_Y - 112 * math.sin(ang))
        c, s = math.cos(ang), math.sin(ang)
        pts = [(-130, -17), (130, -17), (130, 17), (-130, 17)]                       # lever turning on the stem
        d.polygon([(_p(STEM_X + x * c + y * s), _p(BAR_Y - x * s + y * c)) for x, y in pts], fill=CHROME, outline=WARM)
        d.ellipse([_p(STEM_X - 26), _p(BAR_Y - 26), _p(STEM_X + 26), _p(BAR_Y + 26)], fill=CHROME_HI, outline=WARM, width=_p(3))
        for a, b in self.spurts:
            if a <= t < b:
                self._water(d, (t - a) / (b - a))
        self._drip(d, t)
        if reach > 0.001:
            self._hand(d, grip, reach)
        return img.resize((W, H), Image.LANCZOS)

    def _water(self, d: ImageDraw.ImageDraw, u: float) -> None:
        """Cough: three gushes that thicken and fade, with splashes in the basin."""
        x, y0 = SPOUT_TIP
        burst = max(0.0, math.sin(math.pi * u * 3)) ** 0.7 * math.sin(math.pi * u) ** 0.5
        if burst <= 0.02:
            return
        w = 10 + 36 * burst
        y1 = lerp(y0 + 30, 1590, clamp(burst * 1.6))
        d.rounded_rectangle([_p(x - w / 2), _p(y0), _p(x + w / 2), _p(y1)], _p(w / 2), fill=WATER)
        d.rounded_rectangle([_p(x - w / 6), _p(y0), _p(x), _p(y1)], _p(3), fill=(214, 236, 250))
        for k in range(5):                                           # respingos
            ox = (k - 2) * 26 * burst + 8 * math.sin(u * 40 + k)
            oy = -abs(math.sin(u * 30 + k * 1.7)) * 40 * burst
            r = 5 + 3 * burst
            d.ellipse([_p(x + ox - r), _p(1580 + oy - r), _p(x + ox + r), _p(1580 + oy + r)], fill=WATER)

    def _drip(self, d: ImageDraw.ImageDraw, t: float) -> None:
        """After the cough nothing else comes out: only a drop that forms at the spout and falls every ~1.3 s."""
        last = max((b for _, b in self.spurts), default=None)
        if last is None or t < last + 0.4:
            return
        ph = ((t - last - 0.4) % 1.3) / 1.3
        x, y0 = SPOUT_TIP
        if ph < 0.45:
            r = 4 + 9 * smooth(ph / 0.45)
            d.ellipse([_p(x - r), _p(y0 - r * 0.2), _p(x + r), _p(y0 + r * 1.8)], fill=WATER)
        elif ph < 0.65:
            q = (ph - 0.45) / 0.2
            y = lerp(y0 + 14, 1570, q * q)
            d.ellipse([_p(x - 8), _p(y - 8), _p(x + 8), _p(y + 14)], fill=WATER)

    def _hand(self, d: ImageDraw.ImageDraw, grip: tuple, reach: float) -> None:
        """Sleeve (cast coat color) coming from the top right and the closed hand over the tip of the lever."""
        skin, sleeve = tuple(self.look["skin"]), tuple(self.look["body"])
        off = 1 - reach
        gx, gy = grip[0] + off * 360, grip[1] - 40 - off * 380
        wrist = (gx + 70, gy - 70)
        top = (gx + 1000, gy - 640)
        d.line([(_p(top[0]), _p(top[1])), (_p(wrist[0]), _p(wrist[1]))], fill=mix(sleeve, VAC, 0.35), width=_p(150))
        d.line([(_p(top[0]), _p(top[1])), (_p(wrist[0]), _p(wrist[1]))], fill=sleeve, width=_p(134))
        d.ellipse([_p(gx - 70), _p(gy - 84), _p(gx + 84), _p(gy + 50)], fill=skin, outline=WARM, width=_p(3))      # palma
        for k in range(4):                                                                                         # fingers over the bar
            fx = gx - 58 + k * 36
            d.rounded_rectangle([_p(fx - 17), _p(gy + 6), _p(fx + 17), _p(gy + 70)], _p(17), fill=skin, outline=WARM, width=_p(3))
        d.ellipse([_p(gx + 40), _p(gy - 20), _p(gx + 108), _p(gy + 42)], fill=skin, outline=WARM, width=_p(3))    # polegar
