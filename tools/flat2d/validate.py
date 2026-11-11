"""Checks a scene's 'flat' field and the series HUD ('clock', 'chip'), without Pillow (script.py calls it on load).

A typo becomes a ValueError with the scene and the field, as in the rest of the script: an event with a wrong name
would be silently ignored and the video would come out without the door locking.
"""

import re

from . import cast as cast_mod
from .places import DOOR_STATES, KNOCK_ON, LIGHT_STATES, PLACES, STAIRS_DOOR, WIDE_DOORS, WIDE_POINTS, WIDE_SETS, WINDOW_STATES

SHOTS = ("plan", "close", "card", "panel", "duo", "wide", "insert")
EXPRS = ("calm", "alert", "scared", "sick", "whisper", "smile")      # = acting.EXPRS (the test checks)
ACTOR_KINDS = ("sam", "people", "infected")
BGS = ("shelves", "door", "street", "alley")                                  # = close.BGS
MAX_BG_INFECTED = 8                                                  # background silhouettes of the 'wide'

# events of each shot type and each event's own fields
EVENTS = {
    "plan": {"heat", "move", "door", "window", "light", "knock", "turn", "bite"},
    "close": {"knock", "appear", "expr", "light", "talk", "recoil", "hand", "phone", "look"},
    "duo": {"knock", "appear", "expr", "light", "talk", "recoil", "hand", "grab", "keys", "look"},
    "wide": {"walk", "run", "move", "recoil", "grab", "hand", "talk", "expr", "knock", "drop", "lock", "light",
             "bite", "turn", "heat", "carry", "door", "hide", "look", "lean", "prop", "keys"},
    "card": set(),
    "panel": set(),
    "insert": {"sink"},
}
EVENT_KEYS = {
    "heat": {"count"}, "move": {"who", "to"}, "walk": {"who", "to"}, "run": {"who", "to"},
    "door": {"state", "door"}, "window": {"state", "window"}, "light": {"state"},
    "knock": {"times", "gap", "who", "on"}, "appear": {"state"}, "expr": {"to", "who"},
    "talk": {"who", "until_word"}, "recoil": {"who"}, "hand": {"who"}, "keys": {"who"}, "phone": {"who"}, "grab": {"who", "target", "item"},
    "turn": {"who"}, "bite": {"who", "target"}, "drop": {"who", "item"}, "lock": {"who", "state"}, "sink": {"who", "spurt"},
    "carry": {"who", "state"}, "hide": {"who", "state"}, "look": {"who", "to"}, "lean": {"who", "hold"},
    "prop": {"kind", "state"},
}
TIME_KEYS = {"do", "at", "word", "offset", "for"}
SHOT_KEYS = {
    "plan": {"shot", "place", "actors", "doors", "windows", "light", "infected", "camera", "events", "caption_y"},
    "close": {"shot", "who", "bg", "expr", "light", "silhouette", "events", "caption_y"},
    "duo": {"shot", "who", "bg", "counter", "expr", "light", "silhouette", "events", "caption_y"},
    "wide": {"shot", "set", "actors", "light", "locked", "infected", "camera", "events", "caption_y", "door", "stairs", "depth", "props"},
    "card": {"shot", "blocks", "caption_y"},
    "insert": {"shot", "kind", "who", "events", "caption_y"},
    "panel": {"shot", "title", "blocks", "footer", "caption_y"},
}
WIDE_ACTOR_KEYS = {"id", "kind", "at", "facing", "behind", "expr", "outside"}
BLOCK_KEYS = {"label", "value", "note", "hot", "at", "word", "offset", "source"}
PANEL_KEYS = BLOCK_KEYS | {"kind", "days", "rows"}
FOOTER_KEYS = {"text", "at", "word", "offset"}
CHIP_KEYS = {"label", "value", "at", "word", "offset", "for", "level"}
CLOCK_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def norm(word: str) -> str:
    return word.strip(".,!?;:\"'()").lower()


def word_index(narration: str, key: str) -> int | None:
    """Index of the word in the narration: 'knocks' (1st) or 'knocks#2' (2nd). None if not found."""
    base, _, nth = key.partition("#")
    n = int(nth) if nth.isdigit() else 1
    hits = [i for i, w in enumerate(narration.split()) if norm(w) == norm(base)]
    return hits[n - 1] if len(hits) >= n else None


def _err(sid: str, msg: str) -> ValueError:
    return ValueError(f"Scene {sid}: flat: {msg}")


def _unknown(sid: str, raw: dict, known: set, where: str) -> None:
    extra = sorted(k for k in raw if k not in known and not str(k).startswith("_"))
    if extra:
        raise _err(sid, f"{where} does not know {extra} (accepts {sorted(known)})")


def _when(sid: str, ev: dict, narration: str, where: str) -> None:
    """'at' (0..1 fraction of the scene) or 'word' (word of the narration), one of the two."""
    if ("at" in ev) == ("word" in ev):
        raise _err(sid, f"{where} needs 'at' (0 to 1) or 'word' (word of the narration), only one of the two")
    if "at" in ev:
        at = ev["at"]
        if not isinstance(at, (int, float)) or not 0 <= at <= 1:
            raise _err(sid, f"{where}: 'at' is a fraction of the scene from 0 to 1 (got {at!r})")
    else:
        if not narration:
            raise _err(sid, f"{where}: 'word' only works in a scene with narration")
        if word_index(narration, str(ev["word"])) is None:
            raise _err(sid, f"{where}: the word '{ev['word']}' is not in the scene's narration")
    for k in ("offset", "for"):
        if k in ev and not isinstance(ev[k], (int, float)):
            raise _err(sid, f"{where}: '{k}' in seconds")
    if "for" in ev and ev["for"] <= 0:
        raise _err(sid, f"{where}: 'for' must be greater than 0")


def _point(sid: str, place: dict, value, where: str) -> None:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
        return
    if value not in place["points"]:
        raise _err(sid, f"{where}: point '{value}' does not exist (points: {sorted(place['points'])}) and is not [x, y]")


def _camera(sid: str, raw: dict, place: dict) -> None:
    cam = raw.get("camera", {})
    _unknown(sid, cam, {"zoom", "focus"}, "'camera'")
    zooms = cam.get("zoom", 1.0)
    for z in (zooms if isinstance(zooms, list) else [zooms]):
        if not isinstance(z, (int, float)) or not 1.0 <= z <= 2.0:
            raise _err(sid, f"'camera.zoom' from 1.0 to 2.0 (number or [from, to]); got {zooms!r}")
    focus = cam.get("focus", "center")
    for f in (focus if isinstance(focus, list) and focus and not isinstance(focus[0], (int, float)) else [focus]):
        _point(sid, place, f, "'camera.focus'")


def _who(sid: str, value, cast: dict, where: str) -> None:
    """Close/duo character: an id from the 'cast' (or 'sam', which has a default look without a cast)."""
    if not isinstance(value, str) or (value not in cast and value != "sam"):
        raise _err(sid, f"{where}: '{value}' is not in the script's 'cast' (cast: {sorted(cast) or 'empty'})")


def _talk(sid: str, ev: dict, narration: str, where: str) -> None:
    if "for" not in ev and "until_word" not in ev:
        return                                                   # default: speaks until the scene's last word
    if "until_word" in ev:
        if "for" in ev:
            raise _err(sid, f"{where}: use 'for' (seconds) or 'until_word' (word), only one of the two")
        end = word_index(narration, str(ev["until_word"]))
        if end is None:
            raise _err(sid, f"{where}: 'until_word' '{ev['until_word']}' is not in the scene's narration")
        if "word" in ev and end < (word_index(narration, str(ev["word"])) or 0):
            raise _err(sid, f"{where}: 'until_word' comes before 'word' in the narration")


def check(sid: str, raw: dict, narration: str = "", cast: dict | None = None) -> dict:
    cast = cast or {}
    if not isinstance(raw, dict):
        raise _err(sid, "must be an object with 'shot'")
    shot = raw.get("shot")
    if shot not in SHOTS:
        raise _err(sid, f"'shot' must be one of {SHOTS} (got {shot!r})")
    _unknown(sid, raw, SHOT_KEYS[shot], f"o plano '{shot}'")
    if "caption_y" in raw and not (isinstance(raw["caption_y"], (int, float)) and 480 <= raw["caption_y"] <= 1500):
        raise _err(sid, "'caption_y' is the center of the caption in px, from 480 to 1500 (below the HUD, above the bottom buttons)")
    place = None
    ids = {"infected"}
    if shot == "plan":
        name = raw.get("place", "pharmacy")
        if name not in PLACES:
            raise _err(sid, f"'place' '{name}' does not exist (places: {sorted(PLACES)})")
        place = PLACES[name]
        for a in raw.get("actors", []):
            named = isinstance(a, dict) and a.get("id") in cast
            if not isinstance(a, dict) or not a.get("id") or (a.get("kind") not in ACTOR_KINDS
                                                              and not (named and "kind" not in a)):
                raise _err(sid, f"each actor is {{id, kind: {'|'.join(ACTOR_KINDS)}, at}} or {{cast id, at}} (got {a!r})")
            _unknown(sid, a, {"id", "kind", "at"}, f"o ator '{a['id']}'")
            _point(sid, place, a.get("at", place["sam"]), f"ator '{a['id']}'")
            ids.add(a["id"])
        for door, state in raw.get("doors", {}).items():
            if door not in place["doors"] or state not in DOOR_STATES:
                raise _err(sid, f"door '{door}': '{state}' (doors: {sorted(place['doors'])}; states: {DOOR_STATES})")
        for win, state in raw.get("windows", {}).items():
            if win not in place["windows"] or state not in WINDOW_STATES:
                raise _err(sid, f"window '{win}': '{state}' (windows: {sorted(place['windows'])}; states: {WINDOW_STATES})")
        if not isinstance(raw.get("infected", 0), int) or raw.get("infected", 0) < 0:
            raise _err(sid, "'infected' is how many infected appear at the start (integer >= 0)")
        if raw.get("infected", 0) > len(place["infected_spots"]):
            raise _err(sid, f"'infected' up to {len(place['infected_spots'])} in this place")
        _camera(sid, raw, place)
    people = []                                                  # who can act (who) in this shot
    if shot == "close":
        who = raw.get("who", "sam")
        _who(sid, who, cast, "'who'")
        people = [who]
    if shot == "insert":
        who = raw.get("who", "rosa")
        _who(sid, who, cast, "'who'")
        people = [who]
        if raw.get("kind", "sink") != "sink":
            raise _err(sid, "insert 'kind': only 'sink' for now")
    if shot == "duo":
        who = raw.get("who")
        if not (isinstance(who, list) and len(who) == 2 and who[0] != who[1]):
            raise _err(sid, "the duo's 'who' is a list of 2 different characters, [left, right]")
        for w in who:
            _who(sid, w, cast, "'who'")
        people = list(who)
        if not isinstance(raw.get("counter", False), bool):
            raise _err(sid, "'counter' is true (counter between the two) or false")
    if shot in ("close", "duo"):
        if raw.get("bg", "shelves") not in BGS:
            raise _err(sid, f"'bg' must be one of {BGS}")
        expr = raw.get("expr", "calm")
        for w, e in (expr.items() if isinstance(expr, dict) else [(people[0], expr)]):
            if w not in people or e not in EXPRS:
                raise _err(sid, f"'expr' is one of {EXPRS} (or {{id: expr}} in the duo); got {expr!r}")
    if shot == "wide":
        name = raw.get("set")
        if name not in WIDE_SETS:
            raise _err(sid, f"'set' must be one of {WIDE_SETS} (got {name!r})")
        place = {"points": WIDE_POINTS[name]}
        for a in raw.get("actors", []):
            if not isinstance(a, dict) or not a.get("id"):
                raise _err(sid, f"each wide actor is {{id, at, kind?, facing?, behind?}} (got {a!r})")
            _unknown(sid, a, WIDE_ACTOR_KEYS, f"o ator '{a['id']}'")
            if a["id"] not in cast and a["id"] != "sam" and a.get("kind") not in ("people", "infected"):
                raise _err(sid, f"actor '{a['id']}': must be in the 'cast' or have kind people/infected")
            if a.get("facing", "right") not in ("left", "right"):
                raise _err(sid, f"actor '{a['id']}': 'facing' is left or right")
            if a.get("expr", "calm") not in EXPRS:
                raise _err(sid, f"actor '{a['id']}': 'expr' one of {EXPRS}")
            _point(sid, place, a.get("at", "center"), f"ator '{a['id']}'")
            people.append(a["id"])
        n = raw.get("infected", 0)
        if not isinstance(n, int) or not 0 <= n <= MAX_BG_INFECTED:
            raise _err(sid, f"'infected' (background silhouettes) from 0 to {MAX_BG_INFECTED}")
        if not isinstance(raw.get("locked", False), bool):
            raise _err(sid, "'locked' is true or false (initial latch state)")
        _camera(sid, raw, place)
        if "stairs" in raw and (raw["stairs"] not in ("open", "closed") or name not in STAIRS_DOOR):
            raise _err(sid, f"the wide's 'stairs' is open or closed and only applies to sets with the stairs door ({sorted(STAIRS_DOOR)})")
        if "door" in raw and (raw["door"] not in ("open", "closed") or name not in WIDE_DOORS):
            raise _err(sid, f"the wide's 'door' is open or closed and only applies to sets with a door ({sorted(WIDE_DOORS)})")
    if shot == "plan":
        people = sorted(ids - {"infected"})
    if raw.get("light", "on") not in LIGHT_STATES:
        raise _err(sid, f"'light' must be one of {LIGHT_STATES}")
    if shot == "panel":
        blocks = raw.get("blocks")
        if not isinstance(blocks, list) or not 1 <= len(blocks) <= 2:
            raise _err(sid, "the panel needs 'blocks' with 1 or 2 bars {kind: water|food, label, value, days, rows}")
        for i, b in enumerate(blocks):
            _unknown(sid, b, PANEL_KEYS, f"barra {i + 1}")
            if b.get("kind") not in ("water", "food") or not isinstance(b.get("days"), int) or not 0 <= b["days"] <= 9:
                raise _err(sid, f"bar {i + 1}: 'kind' water or food and 'days' an integer from 0 to 9")
            if len(str(b.get("value", ""))) > 8 or len(str(b.get("label", ""))) > 12:
                raise _err(sid, f"bar {i + 1}: value up to 8 and label up to 12 characters")
            if "at" in b or "word" in b:
                _when(sid, b, narration, f"barra {i + 1}")
        ft = raw.get("footer")
        if ft:
            _unknown(sid, ft, FOOTER_KEYS, "footer")
            if "at" in ft or "word" in ft:
                _when(sid, ft, narration, "footer")
    if shot == "card":
        blocks = raw.get("blocks")
        if not isinstance(blocks, list) or not 1 <= len(blocks) <= 3:
            raise _err(sid, "the card needs 'blocks' with 1 to 3 blocks {label, value, note?, hot?, at?}")
        for i, b in enumerate(blocks):
            _unknown(sid, b, BLOCK_KEYS, f"bloco {i + 1}")
            if not str(b.get("label", "")).strip() or not str(b.get("value", "")).strip():
                raise _err(sid, f"block {i + 1} needs 'label' and 'value'")
            if len(str(b["value"])) > 12 or len(str(b["label"])) > 22 or len(str(b.get("note", ""))) > 40:
                raise _err(sid, f"block {i + 1}: value up to 12, label up to 22, note up to 40 characters (legibility)")
            if "at" in b or "word" in b:
                _when(sid, b, narration, f"bloco {i + 1}")
    for k, ev in enumerate(raw.get("events", [])):
        where = f"evento {k + 1}"
        do = ev.get("do") if isinstance(ev, dict) else None
        if do not in EVENTS[shot]:
            raise _err(sid, f"{where}: 'do' {do!r} does not apply to the '{shot}' shot (valid: {sorted(EVENTS[shot]) or 'none'})")
        where = f"event {k + 1} ({do})"
        _unknown(sid, ev, TIME_KEYS | EVENT_KEYS[do], where)
        _when(sid, ev, narration, where)
        top = len(place["infected_spots"]) if shot == "plan" else MAX_BG_INFECTED
        if do == "heat" and not (isinstance(ev.get("count"), int) and 0 <= ev["count"] <= top):
            raise _err(sid, f"{where}: 'count' integer from 0 to {top}")
        if do == "move" and shot == "plan":
            if ev.get("who") not in ids:
                raise _err(sid, f"{where}: 'who' '{ev.get('who')}' is not an actor of the scene ({sorted(ids)})")
            _point(sid, place, ev.get("to"), where)
        elif do in ("move", "walk", "run"):
            if ev.get("who") not in people:
                raise _err(sid, f"{where}: 'who' '{ev.get('who')}' is not an actor of the scene ({people})")
            _point(sid, place, ev.get("to"), where)
        # who acts: required where there is no single obvious character (in the close it is the shot's own 'who')
        needs_who = do in ("talk", "turn", "bite", "grab", "drop", "sink", "carry", "hide", "lean") or (
            do == "keys" and shot == "wide") or (
            do in ("recoil", "hand", "expr", "look") and shot in ("duo", "wide"))
        if shot == "close" and do in ("talk", "recoil", "hand", "expr", "look"):
            needs_who = False
        if do == "knock" and shot != "wide":
            needs_who = False
        if (("who" in ev) and do not in ("move", "walk", "run")) or needs_who:
            if ev.get("who") not in people:
                raise _err(sid, f"{where}: 'who' '{ev.get('who')}' must be a character of this shot ({people})")
        if do == "bite" or (do == "grab" and (shot == "wide" or "target" in ev)):
            if ev.get("target") not in people or ev.get("target") == ev.get("who"):
                raise _err(sid, f"{where}: 'target' must be another character of this shot ({people})")
        if do == "talk":
            _talk(sid, ev, narration, where)
        if do == "knock" and "on" in ev and ev["on"] not in KNOCK_ON:
            raise _err(sid, f"{where}: 'on' is one of {KNOCK_ON}")
        if do == "lock" and ev.get("state", "locked") not in ("locked", "unlocked"):
            raise _err(sid, f"{where}: 'state' is locked (default) or unlocked")
        if do == "look" and ev.get("to", "center") not in ("left", "right", "center"):
            raise _err(sid, f"{where}: 'to' is left, right or center")
        if do == "prop" and (ev.get("kind") not in ("jugs", "scarf", "pills") or raw.get("set") != "pharmacy"
                             or ev.get("state", "on") not in ("on", "off")):
            raise _err(sid, f"{where}: 'prop' only in the pharmacy wide, kind jugs, scarf or pills, state on (default) or off")
        if do == "carry" and ev.get("state", "on") not in ("on", "off"):
            raise _err(sid, f"{where}: 'state' is on (default) or off")
        if do == "drop" and ev.get("item", "key") != "key":
            raise _err(sid, f"{where}: 'item' only 'key' for now")
        if do == "door" and shot == "wide" and ev.get("door") == "stairs":
            if raw.get("set") not in STAIRS_DOOR or ev.get("state") not in ("open", "closed"):
                raise _err(sid, f"{where}: the 'stairs' door only exists in the pharmacy and 'state' is open or closed")
        elif do == "door" and shot == "wide":
            if raw.get("set") not in WIDE_DOORS:
                raise _err(sid, f"{where}: set '{raw.get('set')}' has no door that opens (sets with a door: {sorted(WIDE_DOORS)})")
            if ev.get("state") not in ("open", "closed"):
                raise _err(sid, f"{where}: 'state' in the wide is open or closed")
        elif do == "door":
            if ev.get("state") not in DOOR_STATES:
                raise _err(sid, f"{where}: 'state' must be one of {DOOR_STATES}")
            if ev.get("door", next(iter(place["doors"]))) not in place["doors"]:
                raise _err(sid, f"{where}: door '{ev.get('door')}' does not exist ({sorted(place['doors'])})")
        if do == "window":
            if ev.get("state") not in WINDOW_STATES or not place["windows"]:
                raise _err(sid, f"{where}: 'state' one of {WINDOW_STATES} (and the place must have a window)")
            if ev.get("window", next(iter(place["windows"]))) not in place["windows"]:
                raise _err(sid, f"{where}: window '{ev.get('window')}' does not exist")
        if do == "light" and ev.get("state") not in LIGHT_STATES:
            raise _err(sid, f"{where}: 'state' must be one of {LIGHT_STATES}")
        if do == "knock" and not (isinstance(ev.get("times", 3), int) and 1 <= ev.get("times", 3) <= 6):
            raise _err(sid, f"{where}: 'times' from 1 to 6")
        if do == "appear" and ev.get("state", "show") not in ("show", "hide"):
            raise _err(sid, f"{where}: 'state' is 'show' (default) or 'hide'")
        if do == "expr" and ev.get("to") not in EXPRS:
            raise _err(sid, f"{where}: 'to' must be one of {EXPRS}")
    return raw


def check_cast(raw) -> dict:
    """The script's top-level 'cast' (cast.py): {id: resolved character}."""
    return cast_mod.check(raw)


def _hhmm(sid: str, text, where: str) -> None:
    if not isinstance(text, str) or not CLOCK_RE.match(text):
        raise ValueError(f"Scene {sid}: {where} in 24 h, 'HH:MM' (got {text!r})")


def check_hud(sid: str, clock, chip, narration: str = "") -> None:
    """'clock': {day, from, to?} (null hides); 'chip': {label, value, at|word, for?, level?} or a list."""
    if clock is not None:
        if not isinstance(clock, dict):
            raise ValueError(f"Scene {sid}: 'clock' is {{day, from, to}} or null")
        extra = sorted(set(clock) - {"day", "from", "to"})
        if extra or "from" not in clock or not isinstance(clock.get("day", 0), int):
            raise ValueError(f"Scene {sid}: 'clock' needs 'day' (integer) and 'from' ('18:40'); 'to' optional")
        _hhmm(sid, clock["from"], "'clock.from'")
        if "to" in clock:
            _hhmm(sid, clock["to"], "'clock.to'")
    for i, c in enumerate(chip if isinstance(chip, list) else [chip] if chip else []):
        where = f"chip {i + 1}"
        if not isinstance(c, dict):
            raise ValueError(f"Scene {sid}: {where} is {{label, value, at, for, level?}}")
        extra = sorted(set(c) - CHIP_KEYS)
        if extra:
            raise ValueError(f"Scene {sid}: {where} does not know {extra}")
        label, value = str(c.get("label", "")).strip(), str(c.get("value", "")).strip()
        if not label or not value or len(label) > 26 or len(value) > 14:
            raise ValueError(f"Scene {sid}: {where} needs 'label' (up to 26) and 'value' (up to 14 characters)")
        if "level" in c and not (isinstance(c["level"], (int, float)) and 0 <= c["level"] <= 1):
            raise ValueError(f"Scene {sid}: {where}: 'level' from 0 to 1")
        try:
            _when(sid, c, narration, where)
        except ValueError as e:
            raise ValueError(str(e).replace(": flat:", ":")) from None
