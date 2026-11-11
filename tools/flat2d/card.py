"""'card' shot: explainer card with 1 to 3 comparison blocks ("RABIES · WEEKS" × "HARLOW · MINUTES"),
on the same grid as the floor plan. Each block enters with a fade and a short slide at its 'at'/'word'.
A number only with a source ('source' on the block; lint warns about a block with a digit and no source)."""

from PIL import Image, ImageDraw

from .common import AMB, GRID, H, P, QUI, S, TXT, VAC, W, font, smooth
from .tracks import Track

X = 150                    # left margin of the blocks (the text ends before x = 930)
BLOCK_H = 300
REVEAL_SECONDS = 0.45
SLIDE = 30


def _grid() -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), VAC)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 40):
        d.line([(P(gx), 0), (P(gx), H * S)], fill=GRID, width=S)
    for gy in range(0, H, 40):
        d.line([(0, P(gy)), (W * S, P(gy))], fill=GRID, width=S)
    return img


class Card:
    def __init__(self, flat: dict, events: list[dict], seconds: float):
        self.blocks = flat["blocks"]
        self.bg = _grid().resize((W, H), Image.LANCZOS)
        n = len(self.blocks)
        gap = 90 if n > 1 else 0
        top = 950 - (n * BLOCK_H + (n - 1) * gap) / 2      # center of the set at y 950
        self.ys = [top + i * (BLOCK_H + gap) for i in range(n)]
        self.reveal = []
        for b in self.blocks:
            tr = Track(1.0 if b.get("_t") is None else 0.0)
            if b.get("_t") is not None:
                tr.to(b["_t"], REVEAL_SECONDS, 1.0)
            self.reveal.append(tr)
        self._cache = (None, None)

    def render(self, t: float) -> Image.Image:
        ps = tuple(round(tr.at(t), 3) for tr in self.reveal)
        if self._cache[0] == ps:
            return self._cache[1].copy()
        img = self.bg.copy()
        for i, (b, p) in enumerate(zip(self.blocks, ps)):
            if p > 0:
                self._block(img, b, self.ys[i] + SLIDE * (1 - smooth(p)), p)
            if i and p > 0:                               # "VS" between the blocks, with the second
                d = ImageDraw.Draw(img)
                y = self.ys[i] - 45
                c = tuple(int(VAC[k] + (QUI[k] - VAC[k]) * p) for k in range(3))
                d.line([(X, y), (X + 260, y)], fill=c, width=2)
                d.text((X + 290, y), "VS", font=font(28, scale=1), fill=c, anchor="lm")
                d.line([(X + 340, y), (X + 600, y)], fill=c, width=2)
        self._cache = (ps, img)
        return img.copy()

    def _block(self, img: Image.Image, b: dict, y: float, p: float) -> None:
        layer = Image.new("RGBA", (W, BLOCK_H + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        hot = bool(b.get("hot"))
        d.rectangle([X - 30, 10, X - 24, BLOCK_H - 10], fill=AMB if hot else QUI)
        d.text((X, 10), str(b["label"]).upper(), font=font(40, scale=1), fill=QUI)
        d.text((X - 4, 60), str(b["value"]).upper(), font=font(150, scale=1), fill=AMB if hot else TXT)
        if b.get("note"):
            d.text((X, 236), str(b["note"]).upper(), font=font(30, scale=1), fill=QUI)
        if p < 1:
            layer.putalpha(layer.getchannel("A").point(lambda a: int(a * smooth(p))))
        img.paste(layer, (0, int(y)), layer)
