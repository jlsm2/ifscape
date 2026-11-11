"""Builds a 2D scene frame by frame: resolves each event's time ('at' as a fraction of the scene or 'word' on the
spoken word, from voice.json), creates the right shot (plan/close/duo/wide/card/panel/insert), applies the knock shake
and the HUD. 'talk' receives the words (start, end, text) of its stretch, so the mouth follows the speech; the
'knock' receives the hit instants, the same ones as the shake and the timeline's 'knock_hit'.

    clip = Clip(scene.flat, seconds, scene.narration, words, hud, cast)
    img = clip.frame(i)          # PIL.Image 1080x1920 RGB, frame i of the scene (30 fps)
"""

from PIL import Image

from .card import Card
from .insert import Insert
from .panel import Panel
from .close import Close
from .common import FPS, VAC, clamp
from .duo import Duo
from . import hud as hud_mod
from .plan import Plan
from .validate import norm, word_index
from .wide import Wide

SHOTS = {"plan": Plan, "close": Close, "card": Card, "panel": Panel, "duo": Duo, "wide": Wide, "insert": Insert}
KNOCK_GAP = 0.35
SHAKE = (6, -4)            # offset in px over the 2 frames of each hit (style_v3: 6 px)
TAIL = 0.45                # = timing.TAIL_SECONDS (estimate of the word without voice.json)


def word_time(narration: str, words: list | None, key: str, seconds: float) -> float:
    """Start of the word in the line (n-th with 'word#n'); without generated voice, estimates from position in the text."""
    base, _, nth = str(key).partition("#")
    n = int(nth) if nth.isdigit() else 1
    if words:
        hits = [w for w in words if norm(w["word"]) == norm(base)]
        if len(hits) >= n:
            return float(hits[n - 1]["start"])
    idx = word_index(narration, key) or 0
    return idx / max(1, len(narration.split())) * max(0.0, seconds - TAIL)


def when(item: dict, narration: str, words: list | None, seconds: float) -> float:
    t = item["at"] * seconds if "at" in item else word_time(narration, words, item["word"], seconds)
    return clamp(t + float(item.get("offset", 0.0)), 0.0, seconds)


def timed_words(narration: str, words: list | None, seconds: float) -> list[tuple[float, float, str]]:
    """(start, end, word) of each word in the scene: from voice.json; without generated voice, evenly across the line."""
    if words:
        return [(float(w["start"]), float(w["end"]), str(w["word"])) for w in words]
    toks = narration.split()
    step = max(0.0, seconds - TAIL) / max(1, len(toks))
    return [(i * step, (i + 1) * step, w) for i, w in enumerate(toks)]


def _talk_span(ev: dict, narration: str, words: list | None, seconds: float, timed: list) -> None:
    """End of the 'talk' ('for' in seconds, 'until_word' at the end of the word, or the scene's last word) and the
    words of the stretch."""
    t0 = ev["t"]
    if "until_word" in ev:
        base, _, nth = str(ev["until_word"]).partition("#")
        n = int(nth) if nth.isdigit() else 1
        hits = [w for w in timed if norm(w[2]) == norm(base)]
        t1 = hits[n - 1][1] if len(hits) >= n else word_time(narration, words, ev["until_word"], seconds) + 0.3
    elif "for" in ev:
        t1 = t0 + float(ev["for"])
    else:
        t1 = timed[-1][1] if timed else seconds
    ev["t_end"] = min(seconds, t1 + 0.05)
    ev["_words"] = [w for w in timed if w[0] >= t0 - 0.05 and w[0] < ev["t_end"]]


class Clip:
    def __init__(self, flat: dict, seconds: float, narration: str = "", words: list | None = None,
                 hud: dict | None = None, cast: dict | None = None):
        self.seconds = seconds
        self.frames = max(1, round(seconds * FPS))
        events = sorted(({**ev, "t": when(ev, narration, words, seconds)} for ev in flat.get("events", [])),
                        key=lambda ev: ev["t"])
        timed = timed_words(narration, words, seconds)
        for ev in events:
            if ev["do"] == "talk":
                _talk_span(ev, narration, words, seconds, timed)
            elif ev["do"] == "knock":
                ev["_hits"] = [ev["t"] + k * ev.get("gap", KNOCK_GAP) for k in range(ev.get("times", 3))]
        flat = dict(flat)
        if flat["shot"] in ("card", "panel"):
            flat["blocks"] = [{**b, "_t": when(b, narration, words, seconds) if ("at" in b or "word" in b) else None}
                              for b in flat["blocks"]]
        if flat["shot"] == "panel" and flat.get("footer"):
            ft = flat["footer"]
            flat["footer"] = {**ft, "_t": when(ft, narration, words, seconds) if ("at" in ft or "word" in ft) else None}
        shot = SHOTS[flat["shot"]]
        self.shot = shot(flat, events, seconds) if shot in (Card, Panel) else shot(flat, events, seconds, cast)
        self.hits = sorted(h for ev in events if ev["do"] == "knock" for h in ev["_hits"])
        self.shake = {}
        for h in self.hits:
            f = round(h * FPS)
            for k, dx in enumerate(SHAKE):
                self.shake.setdefault(f + k, dx)
        hud = dict(hud or {})
        hud["chips"] = [{**c, "t": when(c, narration, words, seconds)} for c in hud.get("chips", [])]
        self.hud = hud
        self.events = events
        self.blocks = flat.get("blocks", [])

    def frame(self, i: int) -> Image.Image:
        t = i / FPS
        img = self.shot.render(t)
        dx = self.shake.get(i)
        if dx:
            img = img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0), fillcolor=VAC)
        hud_mod.draw(img, hud_mod.state(self.hud, t, self.seconds))
        return img

    def cues(self) -> list[dict]:
        """Events with the scene frame (for sound design): hits one by one, blocks and chips."""
        out = []
        for ev in self.events:
            row = {k: v for k, v in ev.items() if k not in ("t", "at", "word", "offset", "t_end")
                   and not k.startswith("_")}
            if ev["do"] == "knock":
                continue
            if ev["do"] == "talk":
                row["end_frame"] = round(ev["t_end"] * FPS)
            out.append({**row, "t": round(ev["t"], 3), "frame": round(ev["t"] * FPS)})
        out += getattr(self.shot, "cues", lambda: [])()     # bite contact and the turn it triggers
        out += [{"do": "knock_hit", "t": round(h, 3), "frame": round(h * FPS)} for h in self.hits]
        out += [{"do": "block", "label": b["label"], "t": round(b["_t"], 3), "frame": round(b["_t"] * FPS)}
                for b in self.blocks if b.get("_t") is not None]
        for c in self.hud.get("chips", []):
            out.append({"do": "chip", "label": c["label"], "t": round(c["t"], 3), "frame": round(c["t"] * FPS),
                        "out_frame": round((c["t"] + c.get("for", 3.0)) * FPS)})
        return sorted(out, key=lambda r: r["t"])
