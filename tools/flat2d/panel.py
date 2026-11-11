"""'panel' shot: enlarged supplies infographic (water and food), full screen over the floor plan grid.

Each block has an icon (water or food), name, the DAYS as a big number, a 9-segment bar (1 segment = 1 day
of one adult; the bar fills as it enters) and two math lines (stock and consumption). The 'footer' is the conclusion on an
amber strip ("WATER ENDS FIRST"). Each block and the footer enter with a fade and slide at their 'at'/'word'.
A number only with math the viewer can follow: the line says the stock and the consumption, the bar shows the result."""

from PIL import Image, ImageDraw

from .card import _grid
from .common import AMB, QUI, TXT, VAC, W, clamp, font, smooth
from .tracks import Track

X0, X1 = 90, 990                 # panel margins (the text ends before x = 990)
TITLE_Y = 660
BLOCK_H = 400
BLOCK_TOP = 730
BLOCK_GAP = 16
SEGMENTS = 9
REVEAL_SECONDS = 0.5
FILL_SECONDS = 1.0
SLIDE = 30
WATER = (104, 150, 192)
CAN = (150, 152, 146)
DIM = (34, 42, 56)               # segmento vazio


def _icon(d: ImageDraw.ImageDraw, kind: str, x: int, y: int, hot: bool) -> None:
    """130 x 130 px icon with its corner at (x, y)."""
    col = AMB if hot else TXT
    if kind == "water":
        cx, cy, r = x + 65, y + 82, 46
        d.polygon([(cx - r * 0.86, cy - r * 0.5), (cx + r * 0.86, cy - r * 0.5), (cx, cy - r * 2.0)], fill=WATER)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WATER)
        d.arc([cx - r * 0.6, cy - r * 0.55, cx + r * 0.6, cy + r * 0.65], 100, 170, fill=TXT, width=5)
    else:
        w, h = 92, 112
        l, t = x + 19, y + 10
        d.rounded_rectangle([l, t, l + w, t + h], 14, fill=CAN)
        d.rectangle([l, t + 34, l + w, t + 78], fill=col)
        d.line([(l + 10, t + 56), (l + w - 10, t + 56)], fill=VAC, width=5)
        d.rounded_rectangle([l - 5, t - 3, l + w + 5, t + 9], 5, fill=QUI)
        d.rounded_rectangle([l - 5, t + h - 9, l + w + 5, t + h + 3], 5, fill=QUI)


class Panel:
    def __init__(self, flat: dict, events: list[dict], seconds: float):
        self.blocks = flat["blocks"]
        self.footer = flat.get("footer")
        self.title = flat.get("title", "")
        self.bg = _grid().resize((W, 1920), Image.LANCZOS)
        self.reveal = []
        for b in self.blocks:
            tr = Track(1.0 if b.get("_t") is None else 0.0)
            if b.get("_t") is not None:
                tr.to(b["_t"], REVEAL_SECONDS, 1.0)
            self.reveal.append(tr)
        self.foot = Track(1.0 if not self.footer or self.footer.get("_t") is None else 0.0)
        if self.footer and self.footer.get("_t") is not None:
            self.foot.to(self.footer["_t"], REVEAL_SECONDS, 1.0)
        self._cache = (None, None)

    def render(self, t: float) -> Image.Image:
        key = tuple(round(tr.at(t), 3) for tr in self.reveal) + (round(self.foot.at(t), 3),)
        starts = tuple(round(clamp((t - (b.get("_t") or 0.0)) / FILL_SECONDS), 2) for b in self.blocks)
        if self._cache[0] == (key, starts):
            return self._cache[1].copy()
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        d.text((X0, TITLE_Y), self.title.upper(), font=font(36, scale=1), fill=QUI)
        d.text((X1, TITLE_Y + 4), "1 SEGMENT = 1 DAY", font=font(30, scale=1), fill=QUI, anchor="ra")
        d.line([(X0, TITLE_Y + 52), (X1, TITLE_Y + 52)], fill=QUI, width=2)
        for i, (b, p) in enumerate(zip(self.blocks, key)):
            if p > 0:
                y = BLOCK_TOP + i * (BLOCK_H + BLOCK_GAP) + SLIDE * (1 - smooth(p))
                self._block(img, b, y, p, smooth(starts[i]))
        fp = key[-1]
        if self.footer and fp > 0:
            self._footer(img, fp)
        self._cache = ((key, starts), img)
        return img.copy()

    def _block(self, img: Image.Image, b: dict, y: float, p: float, fill: float) -> None:
        layer = Image.new("RGBA", (W, BLOCK_H + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        hot = bool(b.get("hot"))
        col = AMB if hot else TXT
        d.rectangle([X0 - 30, 10, X0 - 24, BLOCK_H - 10], fill=AMB if hot else QUI)
        _icon(d, b.get("kind", "food"), X0, 20, hot)
        d.text((X0 + 160, 14), str(b["label"]).upper(), font=font(40, scale=1), fill=QUI)
        d.text((X0 + 156, 54), str(b["value"]).upper(), font=font(150, scale=1), fill=col)
        days = int(b.get("days", 0))
        seg_w = (X1 - X0 - (SEGMENTS - 1) * 8) / SEGMENTS
        by = 214
        shown = days * fill
        for s in range(SEGMENTS):
            x = X0 + s * (seg_w + 8)
            d.rounded_rectangle([x, by, x + seg_w, by + 54], 6, fill=DIM)
            part = clamp(shown - s)
            if part > 0:
                d.rounded_rectangle([x, by, x + seg_w * part, by + 54], 6, fill=col)
            d.text((x + seg_w / 2, by + 84), str(s + 1), font=font(30, scale=1), fill=QUI, anchor="mm")
        for j, (lab, val) in enumerate(b.get("rows", [])):
            x = X0 + 240 + j * 280
            if lab:
                d.text((x, 340), str(lab).upper(), font=font(32, scale=1), fill=QUI)
            if val:
                d.text((x + (0 if not lab else 130), 330), str(val).upper(), font=font(52, scale=1), fill=TXT)
        if p < 1:
            layer.putalpha(layer.getchannel("A").point(lambda a: int(a * smooth(p))))
        img.paste(layer, (0, int(y)), layer)

    def _footer(self, img: Image.Image, p: float) -> None:
        y = BLOCK_TOP + 2 * (BLOCK_H + BLOCK_GAP) + 10
        layer = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle([X0, 0, X1, 100], 10, fill=AMB)
        d.text(((X0 + X1) / 2, 50), str(self.footer["text"]).upper(), font=font(56, scale=1), fill=VAC, anchor="mm")
        layer.putalpha(layer.getchannel("A").point(lambda a: int(a * smooth(p))))
        img.paste(layer, (0, int(y + SLIDE * (1 - smooth(p)))), layer)
