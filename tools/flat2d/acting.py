"""A character's acting over the scene (close, duo and wide): expression, blinking, mouth during speech, gestures
(recoil, grab, hand, knock, lock, drop), bite and transformation. Only tracks and math, no drawing.

The mouth only moves inside a 'talk': each word of that stretch's voice.json becomes 1 to 4 syllables (groups of
vowels), each syllable opens into one of the MOUTHS shapes and closes at the end; between words the mouth closes. The
narrator never moves anyone's mouth.
"""

import re

from .common import clamp, noise, smooth
from .tracks import Track

# (eye half-height, eyebrow raise, tilt of the inner tip, mouth width, mouth opening,
# mouth curve (+ smile, - sad), paleness, sweat, vacant gaze). The first 5 are the prototype's.
EXPRS = {
    "calm": (15.0, 0.0, 0.0, 56.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "alert": (18.0, -10.0, 2.0, 40.0, 9.0, 0.0, 0.0, 0.0, 0.0),
    "scared": (22.0, -18.0, 12.0, 46.0, 26.0, 0.0, 0.0, 0.0, 0.0),
    "sick": (10.0, 4.0, 6.0, 40.0, 0.0, -7.0, 1.0, 1.0, 1.0),
    "whisper": (13.0, -4.0, 5.0, 24.0, 7.0, 0.0, 0.0, 0.0, 0.0),
    "smile": (12.0, -4.0, -3.0, 62.0, 0.0, 14.0, 0.0, 0.0, 0.0),
}
# mouth shapes during speech: (fraction of the expression's width, opening in px at the close)
MOUTHS = {1: (0.62, 14.0), 2: (0.78, 28.0), 3: (0.42, 22.0)}       # 1 half, 2 open, 3 "o"
EXPR_SECONDS = 0.3
TURN_SECONDS = 0.6
RECOIL = (0.12, 0.5)            # recoils fast and returns slowly (s)
REACH_SECONDS = 0.3
HAND_SECONDS = 0.4
WORD_CLOSE = 0.06               # the mouth closes this long before the end of each word
VOWELS = re.compile(r"[aeiouy]+")


def syllables(word: str) -> list[int]:
    """Mouth shapes of each syllable: 'o'/'u' purse (3), 'a' opens (2), the rest half open (1)."""
    groups = VOWELS.findall(word.lower()) or ["e"]
    out = []
    for g in groups[:4]:
        out.append(3 if g[0] in "ou" else 2 if g[0] == "a" else 1)
    return out


class Acting:
    def __init__(self, look: dict, seconds: float, seed: float = 0.0, expr: str = "calm"):
        self.look = look
        self.seconds = seconds
        self.expr = Track(EXPRS[expr])
        self.talks: list[tuple[float, float, list]] = []
        self.recoil = Track(0.0)
        self.reach = Track(0.0)             # grab: 0 still, 1 hand on the other's arm
        self.reach_target = None
        self.reach_item = None              # grab with an item: what goes in the outstretched hand ("cup")
        self.hand = Track(0.0)              # bandaged hand shown
        self.keys = Track(0.0)              # keys in hand, trembling
        self.phone = Track(0.0)             # phone raised in front of the face
        self.carry = Track(0.0)             # water jug in each hand, hanging (wide, in profile)
        self.look = Track(0.0)              # gaze: -1 left, 0 front, 1 right (eyes first, head after)
        self.turn = Track(0.0)              # 0 person, 1 infected
        self.lean = Track(0.0)              # bite: leans over the target's shoulder
        self.lock = Track(0.0)              # hand on the latch
        self.knocks: list[tuple[float, float, list, str]] = []   # (start, end, hits, where)
        self.drops: list[float] = []
        # blinks: every ~3.4 s with variation, never in the first half second (seed separates the characters)
        self.blinks, b = [], 1.1 + 0.9 * (0.5 + 0.5 * noise(seed, 2.0)) * (1 if seed else 0)
        while b < seconds:
            self.blinks.append(b)
            b += 3.0 + 1.2 * (0.5 + 0.5 * noise(b + seed, 1.0))

    # eventos
    def apply(self, ev: dict) -> None:
        t, do = ev["t"], ev["do"]
        if do == "expr":
            self.expr.to(t, ev.get("for", EXPR_SECONDS), EXPRS[ev["to"]])
        elif do == "talk":
            self.talks.append((t, ev["t_end"], ev.get("_words", [])))
        elif do == "recoil":
            self.recoil.to(t, RECOIL[0], 1.0)
            self.recoil.to(t + RECOIL[0], RECOIL[1], 0.0)
        elif do == "grab":
            self.reach_target = ev.get("target")
            self.reach_item = ev.get("item")
            self.reach.to(t, REACH_SECONDS, 1.0)
            self.reach.to(t + REACH_SECONDS + ev.get("for", 1.5), REACH_SECONDS, 0.0)
        elif do == "hand":
            self.hand.to(t, HAND_SECONDS, 1.0)
            self.hand.to(t + HAND_SECONDS + ev.get("for", 2.0), HAND_SECONDS, 0.0)
        elif do == "phone":
            self.phone.to(t, REACH_SECONDS, 1.0)
            self.phone.to(t + REACH_SECONDS + ev.get("for", 2.5), REACH_SECONDS, 0.0)
        elif do == "keys":
            self.keys.to(t, HAND_SECONDS, 1.0)
            self.keys.to(t + HAND_SECONDS + ev.get("for", 2.0), HAND_SECONDS, 0.0)
        elif do == "carry":
            if t <= 0.05 and ev.get("state") != "off":
                self.carry.start = 1.0              # already arrives carrying: the jug is not born in the hand at every cut
            else:                                   # 'for' longo = agacha, pega/pousa e levanta (inclina o tronco)
                self.carry.to(t, ev.get("for", HAND_SECONDS), 0.0 if ev.get("state") == "off" else 1.0)
        elif do == "look":
            self.look.to(t, ev.get("for", 0.2), {"right": 1.0, "left": -1.0}.get(ev.get("to"), 0.0))
        elif do == "turn":
            self.turn.to(t, ev.get("for", TURN_SECONDS), 1.0)
            self.expr.to(t, ev.get("for", TURN_SECONDS), EXPRS["sick"])
        elif do == "lean":
            self.lean.to(t, ev.get("for", 0.35), 1.0)
            self.lean.to(t + ev.get("for", 0.35) + ev.get("hold", 0.8), 0.5, 0.0)
        elif do == "lock":
            self.lock.to(t, 0.35, 1.0)
            self.lock.to(t + 0.35 + 0.7, 0.35, 0.0)
        elif do == "knock":
            hits = ev["_hits"]
            self.knocks.append((t - 0.3, hits[-1] + 0.35, hits, ev.get("on", "door")))
        elif do == "drop":
            self.drops.append(t)

    # estado no instante t
    def params(self, t: float) -> tuple:
        return self.expr.at(t)

    def blink(self, t: float) -> float:
        out = 1.0
        for b in self.blinks:
            dist = abs(t - b)
            if dist < 0.09:
                out = min(out, 0.08 + 0.92 * smooth(dist / 0.09))
        return out

    def mouth(self, t: float) -> int:
        """0 = the expression's mouth; 1..3 = speech shape (MOUTHS)."""
        for t0, t1, words in self.talks:
            if not t0 <= t < t1:
                continue
            for s, e, text in words:
                end = e - min(WORD_CLOSE, 0.25 * (e - s))
                if s <= t < end:
                    shapes = syllables(text)
                    span = (end - s) / len(shapes)
                    k = min(len(shapes) - 1, int((t - s) / span))
                    # each syllable: opens in the first 70% and closes in the rest
                    return shapes[k] if (t - s - k * span) < 0.7 * span else 0
            return 0
        return 0

    def talking(self, t: float) -> bool:
        return any(t0 <= t < t1 for t0, t1, _ in self.talks)

    def recoil_at(self, t: float) -> float:
        return self.recoil.at(t)

    def knock_at(self, t: float) -> tuple[float, str] | None:
        """(how raised the fist is 0..1, where) inside a 'knock'; None outside."""
        for t0, t1, hits, on in self.knocks:
            if t0 <= t <= t1:
                dn = min(abs(t - h) for h in hits)
                v = min(clamp(dn / 0.14), 1.0)
                ramp = min(smooth((t - t0) / 0.3), smooth((t1 - t) / 0.3))
                ramp *= clamp((0.5 - dn) / 0.2)          # slow knock (gap > ~0.9 s): the arm lowers between hits
                return smooth(v), on, ramp
        return None
