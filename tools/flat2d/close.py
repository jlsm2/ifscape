"""'close' shot: FRAMING of the stage (wide.py), not a separate drawing. The 'who' character (default
Sam) is the same figure as in the wide (figure.body_front, front view), standing in the 'bg' set, with the camera zoomed
~3.2 on the head and chest. Same face, same outline and same palette in every shot.

Old 'bg' -> set: shelves -> pharmacy (shelves and the glass door on the right), door -> frontdoor
(glass door with the grille and the street) and street -> busstop. The 'appear' silhouette stays outside, behind
the glass (set mask), and the flashlight beam comes from whoever has 'headlamp' and follows 'light'.
Events: expr, talk, recoil, hand (without 'who' they apply to the close's character), appear, light and knock (only the
shake, which the engine applies).
"""

from . import figure
from .sets import SETS
from .wide import K, Wide

BG_SET = {"shelves": "pharmacy", "door": "frontdoor", "street": "busstop", "alley": "alley"}
BGS = tuple(BG_SET)
ZOOM = (3.1, 3.3)                  # slow camera push during the scene
HEAD_TOP_Y = 700                   # top of the head in the frame: the close's caption sits above (y 560)
WHO_EVENTS = ("expr", "talk", "recoil", "hand", "grab", "keys", "phone")


def head_top(ground: float = 1240) -> float:
    return ground - (figure.HIP_H + figure.TORSO + figure.NECK + 2 * figure.R_HEAD) * K


def framing(z: float, x: float, ground: float = 1240, head_y: float = HEAD_TOP_Y) -> tuple:
    """Focus point (world) so the top of the head lands at head_y in the frame, with zoom z."""
    top = head_top(ground) - head_y / z
    return (x, top + 1920 / (2 * z))


def with_who(events: list[dict], who: str) -> list[dict]:
    return [{**ev, "who": ev.get("who", who)} if ev["do"] in WHO_EVENTS else ev for ev in events]


def Close(flat: dict, events: list[dict], seconds: float, cast: dict | None = None) -> Wide:
    who = flat.get("who", "sam")
    name = BG_SET[flat.get("bg", "shelves")]
    st = SETS[name]
    x = st["close_x"]
    fx = x + 44                                         # the character slightly to the left; the door on the right
    stage = {
        "set": name, "light": flat.get("light", "on"), "infected": 0,
        "actors": [{"id": who, "at": [x, st["ground"]], "_view": "front", "_f": 0, "expr": flat.get("expr", "calm")}],
        "_camera": (ZOOM[0], ZOOM[1], framing(ZOOM[0], fx), framing(ZOOM[1], fx)),
        "_appear": {"start": bool(flat.get("silhouette"))},
    }
    return Wide(stage, with_who(events, who), seconds, cast)
