"""Validation of a scene's 'stage' field (pure Python, no Blender): a typo or an id that does not exist
becomes a clear message when the script loads, not a Traceback in the middle of the render.

presets.py and cameras.py check their own names against these lists on load (if they diverge, it fails early).
"""

import difflib
import json
from pathlib import Path

SETS = ("meadow", "savanna", "forest", "desert", "vacuo", "ocean", "park", "riverside")
LIGHTS = ("noon", "dawn", "dusk", "night", "overcast", "dry-noon", "afternoon", "golden")
CAMERAS = ("pov", "static", "dolly_in", "dolly_out", "truck", "orbit", "crane", "path", "macro")
LAYOUTS = ("single", "scatter", "herd", "line", "ring", "grid")
CUES = ("pop", "vanish", "move", "action", "shake", "light", "grow", "meteor", "still", "water", "dive", "dust",
        "react", "sink", "fall", "crack", "sag", "bend", "dry", "slump")
# targets the stage creates on its own (riverside: footbridge, crane, kiosk, sequoia, mountain range); the build checks they exist
SET_TARGETS = ("bridge", "crane", "kiosk", "tree_tall", "ridge", "river")
GESTURES = ("drink", "cast", "bite", "drill")          # synthesized action (procedural.gesture), needs 'rod'
STAGE_KEYS = {"set", "light", "props", "camera", "cues"}
PROP_KEYS = {"id", "kind", "pack", "tag", "season", "name", "at", "layout", "n", "area", "spread", "to", "gap", "rows",
             "cols", "h", "len", "face", "action", "path", "speed", "wait", "z", "rate", "span", "loop", "must_see",
             "rod", "carry", "dive", "radius", "alt", "ready", "variant", "jump", "slack", "rod_at",
             "scale_with_ants", "trail", "food", "clear", "density", "count", "crumb", "colors", "blade",
             "puddle", "seeds", "seed", "grains"}
CAMERA_KEYS = {"preset", "at", "look", "dist", "arc", "lens", "z", "sway", "path"}
WAYPOINT_KEYS = {"t", "frac", "at", "z", "look", "lens", "prev"}
CUE_KEYS = {"word", "nth", "off", "t", "frac", "do", "target", "to", "dur", "action", "amp", "light", "from", "size",
            "stagger", "keep", "color", "reach", "n", "rest", "look", "look_z", "turn", "lean", "snap", "hold", "back",
            "z", "g", "dy", "deg", "face"}
CATALOG = Path(__file__).resolve().parent / "catalog.json"
_items: list | None = None


def _catalog() -> list:
    global _items
    if _items is None:
        _items = json.loads(CATALOG.read_text(encoding="utf-8"))["items"]
    return _items


def _keys(keys, known, where):
    for k in keys:
        if k in known or str(k).startswith("_"):
            continue
        near = difflib.get_close_matches(str(k), sorted(known), n=1)
        raise ValueError(f"{where}: unknown field '{k}'" + (f" (did you mean '{near[0]}'?)" if near else "") + ".")


def _choice(value, options, where):
    if value not in options:
        near = difflib.get_close_matches(str(value), options, n=1)
        raise ValueError(f"{where}: '{value}' does not exist" + (f" (did you mean '{near[0]}'?)" if near else "")
                         + f". Options: {', '.join(options)}.")


def _xy(value, where):
    if not (isinstance(value, (list, tuple)) and len(value) in (2, 3) and all(isinstance(v, (int, float)) for v in value)):
        raise ValueError(f"{where}: must be [x, y] in meters, not {value!r}.")


def prop_names(stage: dict) -> set[str]:
    """Names that the camera and cues may cite: 'rex' (one) or 'herd' (group; the members are herd0, herd1...)."""
    names = set()
    for p in stage.get("props", []):
        base = p.get("name") or p.get("id") or p.get("kind")
        names.add(base)
        if int(p.get("n", 1)) > 1:
            names |= {f"{base}{k}" for k in range(int(p["n"]))}
    return names


def check(sid: str, stage: dict, carried=frozenset()) -> None:
    where = f"Cena {sid}, stage"
    if not isinstance(stage, dict):
        raise ValueError(f"{where}: must be an object.")
    _keys(stage, STAGE_KEYS, where)
    _choice(stage.get("set", "meadow"), SETS + ("same",), f"{where}.set")
    # with set 'same', 'light' changes the light state AT THE CUT (time jump: channel rule); inside the scene, the 'light' cue
    _choice(stage.get("light", "noon"), LIGHTS, f"{where}.light")
    cam = stage.get("camera")
    names = prop_names(stage) | set(carried)          # 'carried': pieces with 'span' from earlier scenes of the same stage
    if not isinstance(cam, dict):
        raise ValueError(f"{where}: 'camera' is required.")
    _keys(cam, CAMERA_KEYS, f"{where}.camera")
    _choice(cam.get("preset", "pov"), CAMERAS, f"{where}.camera.preset")
    if cam.get("preset") == "path":
        path = cam.get("path")
        if not isinstance(path, list) or len(path) < 2:
            raise ValueError(f"{where}.camera: 'path' needs a list with 2 points or more ({{t, at, look}}).")
        for k, w in enumerate(path, 1):
            ww = f"{where}.camera.path[{k}]"
            _keys(w, WAYPOINT_KEYS, ww)
            if not ({"t", "frac"} & w.keys()):
                raise ValueError(f"{ww}: say when: 't' (seconds since the start of the scene) or 'frac' (0 to 1).")
            if not w.get("prev"):
                if "at" not in w or "look" not in w:
                    raise ValueError(f"{ww}: needs 'at' [x, y] and 'look' (piece or [x, y, z]), or 'prev': true.")
                _xy(w["at"], f"{ww}.at")
                if isinstance(w["look"], str):
                    _choice(w["look"].split("^")[0], tuple(sorted(names)), f"{ww}.look")
                else:
                    _xy(w["look"], f"{ww}.look")
    else:
        if "at" not in cam or "look" not in cam:
            raise ValueError(f"{where}: 'camera' needs 'at' [x, y] and 'look' (name of a piece or [x, y, z]).")
        _xy(cam["at"], f"{where}.camera.at")
        if isinstance(cam["look"], str):
            _choice(cam["look"].split("^")[0], tuple(sorted(names)), f"{where}.camera.look")
        else:
            _xy(cam["look"], f"{where}.camera.look")
    ids = {i["id"] for i in _catalog()}
    kinds = {i["kind"] for i in _catalog()}
    seen = set()
    for n, p in enumerate(stage.get("props", []), 1):
        pw = f"{where}.props[{n}]"
        _keys(p, PROP_KEYS, pw)
        if ("id" in p) == ("kind" in p):
            raise ValueError(f"{pw}: use 'id' (catalog model) OR 'kind' (drawn type).")
        for one in (p["id"] if isinstance(p.get("id"), list) else [p["id"]] if "id" in p else []):
            _choice(one, tuple(sorted(ids)), f"{pw}.id")
        if "kind" in p:
            _choice(p["kind"], tuple(sorted(kinds)), f"{pw}.kind")
        if "layout" in p:
            _choice(p["layout"], LAYOUTS, f"{pw}.layout")
        for key in ("at", "to"):
            if key in p:
                _xy(p[key], f"{pw}.{key}")
        base = p.get("name") or p.get("id") or p.get("kind")
        if isinstance(base, list):
            raise ValueError(f"{pw}: with 'id' as a list, give a 'name'.")
        span = p.get("span")
        if span is not None and not (span == "group" or (isinstance(span, list) and len(span) == 2)):
            raise ValueError(f"{pw}: 'span' is \"group\" or [first_scene, last_scene].")
        if base in seen:
            raise ValueError(f"{pw}: the name '{base}' is already in use in this scene (use 'name').")
        seen.add(base)
    import re                                         # cue on a group of loose pieces ('crowd' = crowd0, crowd1...)
    names = names | {m.group(1) for m in (re.match(r"^(.*\D)\d+$", x) for x in names) if m} | set(SET_TARGETS)
    for n, c in enumerate(stage.get("cues", []), 1):
        cw = f"{where}.cues[{n}]"
        _keys(c, CUE_KEYS, cw)
        _choice(c.get("do"), CUES, f"{cw}.do")
        if c["do"] not in ("shake", "light", "meteor", "water", "sink"):
            _choice(c.get("target"), tuple(sorted(names)), f"{cw}.target")
        if c["do"] == "light":
            _choice(c.get("light"), LIGHTS, f"{cw}.light")
        if not ({"word", "t", "frac"} & c.keys()):
            raise ValueError(f"{cw}: say when it happens: 'word' (spoken word), 't' (seconds) or 'frac' (0 to 1).")
        if c["do"] == "meteor" and not ("from" in c and "to" in c):
            raise ValueError(f"{cw}: 'meteor' needs 'from' and 'to' ([x, y, z] in the sky, in meters).")
        if c["do"] == "action" and c.get("action") == "cast" and "to" in c and len(c["to"]) != 2:
            raise ValueError(f"{cw}: the 'cast' 'to' is [x, y] on the water.")
        if c["do"] == "dust" and not 0.1 <= float(c.get("reach", 0.55)) <= 0.6:
            raise ValueError(f"{cw}: the 'dust' 'reach' goes from 0.1 to 0.6 (fraction of the distance to the camera).")
        if c["do"] == "move" and "to" not in c:
            raise ValueError(f"{cw}: 'move' needs 'to' [x, y].")
        if c["do"] == "action" and "action" not in c:
            raise ValueError(f"{cw}: 'action' needs the animation name (e.g. \"Run\").")
        if c["do"] == "water" and not (isinstance(c.get("color"), str) and c["color"].startswith("#") and len(c["color"]) == 7):
            raise ValueError(f"{cw}: 'water' needs 'color' in hex (e.g. \"#123A4C\"); only on the 'ocean' stage.")
        if c["do"] == "react":
            if "look" not in c and "lean" not in c:
                raise ValueError(f"{cw}: 'react' needs 'look' (piece, [x, y, z], \"front\" or null) and/or 'lean' (degrees).")
            lk = c.get("look")
            if isinstance(lk, str) and lk not in ("front", "keep"):
                _choice(lk, tuple(sorted(names)), f"{cw}.look")
            if "lean" in c and not -25 <= float(c["lean"]) <= 20:
                raise ValueError(f"{cw}: the 'react' 'lean' goes from -25 (backward) to 20 degrees (forward).")
