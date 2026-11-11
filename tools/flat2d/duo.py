"""'duo' shot: FRAMING of the stage (wide.py) with two cast characters facing each other in 3/4
('who': [left, right]), the same figure as in the wide and the close, in the 'bg' set (as in close.py), with the
camera zoomed ~2.4. 'counter': true puts the counter in the foreground at waist height. The caption sits in the
top gap (y 560): the heads start at y ~680.

Gestures: grab (one's hand holds the other's arm; default 'target' = the other), recoil (steps back 20 px and returns),
hand (shows the bandaged hand), talk and expr (with 'who'), appear, light and knock (shake).
"""

from .close import BG_SET, framing, with_who
from .sets import SETS
from .wide import Wide

ZOOM = (2.35, 2.45)
GAP = 100                          # each one's distance to the center (world)
HEAD_TOP_Y = 680


def Duo(flat: dict, events: list[dict], seconds: float, cast: dict | None = None) -> Wide:
    a, b = flat["who"]
    name = BG_SET[flat.get("bg", "shelves")]
    st = SETS[name]
    cx = st["duo_x"]
    expr = flat.get("expr", "calm")
    ex = (lambda w: expr.get(w, "calm")) if isinstance(expr, dict) else (lambda w: expr)
    stage = {
        "set": name, "light": flat.get("light", "on"), "infected": 0,
        "actors": [{"id": a, "at": [cx - GAP, st["ground"]], "_view": "34", "_f": 1, "expr": ex(a)},
                   {"id": b, "at": [cx + GAP, st["ground"]], "_view": "34", "_f": -1, "expr": ex(b)}],
        "_camera": (ZOOM[0], ZOOM[1], framing(ZOOM[0], cx, head_y=HEAD_TOP_Y), framing(ZOOM[1], cx, head_y=HEAD_TOP_Y)),
        "_appear": {"start": bool(flat.get("silhouette"))},
        "_counter": bool(flat.get("counter")),
    }
    return Wide(stage, with_who(events, a), seconds, cast)
